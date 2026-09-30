# Task 25: the live probe's own logic. Pure verdicts only — nothing here calls Claude, the keychain or the network;
# the probe itself (`runner probe`) is owner-run.
import dataclasses, gzip, json, os

import pytest

from runner import config, credentials, handedit, po, probe, session


# ---- the brief's three tests (verbatim) -------------------------------------------------------------------------
def test_transcript_path_verdict_names_the_expected_layout(tmp_path):
    cfg = tmp_path / ".claude"
    (cfg / "projects" / "-work-probe").mkdir(parents=True)
    (cfg / "projects" / "-work-probe" / "s1.jsonl").write_text("{}\n")
    assert probe.transcript_layout(cfg, "/work/probe", "s1") == {"expected": "projects/-work-probe/s1.jsonl", "found": True}


def test_token_search_reports_files_by_name_only(tmp_path):
    (tmp_path / "a.json").write_text("xx SECRET yy"); (tmp_path / "b.json").write_text("clean")
    assert probe.files_containing(tmp_path, b"SECRET") == ["a.json"]


def test_od24_route_is_read_from_the_skill_text():
    assert probe.export_route("Use mcp__github__create_issue for each task") == "mcp"
    assert probe.export_route("Run `gh issue create --title ...`") == "gh"
    assert probe.export_route("nothing relevant") == "unknown"


# ---- P1: layout, models, hard links, the saved stream --------------------------------------------------------------
def test_a_transcript_elsewhere_is_reported_where_it_really_is(tmp_path):
    cfg = tmp_path / ".claude"
    (cfg / "projects" / "-work-other").mkdir(parents=True)
    (cfg / "projects" / "-work-other" / "s1.jsonl").write_text("{}\n")
    assert probe.transcript_layout(cfg, "/work/probe", "s1")["found"] is False
    assert probe.find_transcripts(cfg, "s1") == ["projects/-work-other/s1.jsonl"]


def test_files_containing_never_follows_a_link_or_opens_a_fifo(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir(); (outside / "t").write_text("SECRET")
    root = tmp_path / "root"; root.mkdir()
    (root / "link").symlink_to(outside / "t")
    os.mkfifo(root / "pipe")
    assert probe.files_containing(root, b"SECRET") == []


def test_transcript_models_reads_assistant_models_from_plain_and_gzip_files(tmp_path):
    a = tmp_path / "a.jsonl"
    a.write_text(json.dumps({"type": "assistant", "message": {"model": "claude-opus-5-5"}}) + "\n"
                 + json.dumps({"type": "user", "message": {"model": "not-this"}}) + "\nnot json\n")
    b = tmp_path / "b.jsonl.gz"
    with gzip.open(b, "wt") as fh:
        fh.write(json.dumps({"type": "assistant", "message": {"model": "claude-haiku-4-5"}}) + "\n")
    assert probe.transcript_models([a, b]) == ["claude-haiku-4-5", "claude-opus-5-5"]


def test_models_pinned_needs_at_least_one_model_and_every_one_accepted():
    assert probe.models_pinned(["claude-opus-5-5"], ["claude-opus-5-5"]) is True
    assert probe.models_pinned(["claude-opus-5-5", "claude-haiku-4-5"], ["claude-opus-5-5"]) is False
    assert probe.models_pinned([], ["claude-opus-5-5"]) is False       # no subagent transcript proves nothing


def test_hard_linked_lists_every_file_with_more_than_one_link(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "a.jsonl").write_text("x")
    os.link(tmp_path / "p" / "a.jsonl", tmp_path / "b.jsonl")
    (tmp_path / "c.jsonl").write_text("y")
    (tmp_path / "d").symlink_to(tmp_path / "c.jsonl")                  # a symlink is not a hard link
    assert probe.hard_linked(tmp_path) == ["b.jsonl", "p/a.jsonl"]


def test_hard_linked_is_empty_for_a_missing_root(tmp_path):
    assert probe.hard_linked(tmp_path / "nope") == []


def _gz(path, text):
    with gzip.open(path, "wt") as fh:
        fh.write(text)


def test_the_stream_is_saved_only_when_no_known_value_is_in_it(tmp_path):
    value = "probe-literal-value-0123456789"                             # stands in for the token (never real)
    dirty = tmp_path / "dirty.jsonl.gz"; _gz(dirty, '{"type":"system","x":"' + value + '"}\n')
    rec = probe.save_stream_if_clean(dirty, tmp_path / "out" / "P1-stream.jsonl.gz", [value])
    assert rec["saved"] is False and "literal" in rec["findings"] and value not in json.dumps(rec)
    assert not (tmp_path / "out" / "P1-stream.jsonl.gz").exists()
    clean = tmp_path / "clean.jsonl.gz"; _gz(clean, '{"type":"system","subtype":"init"}\n')
    rec = probe.save_stream_if_clean(clean, tmp_path / "out" / "P1-stream.jsonl.gz", [value])
    assert rec == {"saved": True, "path": str(tmp_path / "out" / "P1-stream.jsonl.gz")}
    assert (tmp_path / "out" / "P1-stream.jsonl.gz").read_bytes() == clean.read_bytes()


def test_a_stream_with_a_token_shape_is_not_saved_either(tmp_path):
    s = tmp_path / "s.jsonl.gz"; _gz(s, "sk-ant-oat01-" + "Ab3" * 20 + "\n")
    assert probe.save_stream_if_clean(s, tmp_path / "o.gz", [])["saved"] is False


# ---- P1c: auth-failure texts ------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,shape", [
    ("Not logged in · Please run /login", "Not logged in"),
    ("  Failed to authenticate. API Error: 401 {...}", "Failed to authenticate"),
    ("Invalid API key · Fix external API key", "Invalid API key"),
    ("I could not log in: Not logged in", None),                        # anchored, like session.Parsed.outcome
    ("", None),
])
def test_auth_shape_is_the_anchored_prefix_session_uses(text, shape):
    assert probe.auth_shape(text) == shape
    assert (probe.auth_shape(text) is not None) == str(text).strip().startswith(session.AUTH_FAILURE_SHAPES)


def test_the_no_credential_sends_an_empty_first_line_and_never_shows_a_value():
    c = probe.no_credential()
    assert c.payload() == b"\n"                                          # bk-claude-turn: fd 3 is empty
    assert isinstance(c, credentials.Credential) and repr(c) == "<credential>" and f"{c}" == "<credential>"
    c.check_turn(False)                                                  # a real (non-dry) probe turn may use it


def test_the_bogus_token_is_token_shaped_says_fake_and_differs_each_time():
    v1, v2 = probe.bogus_token(), probe.bogus_token()
    assert v1 != v2 and v1.startswith("sk-ant-oat01-") and "FAKE" in v1 and len(v1) > 60
    c = credentials.Credential(v1)
    assert c.payload() == (v1 + "\n").encode()


def test_auth_case_record_names_the_shape_and_the_retry_errors():
    r = session.TurnResult("sid", "auth_failed", "Not logged in · Please run /login", {}, {}, 0.0, {}, {}, 1.0,
                           [{"type": "system", "subtype": "api_retry", "error": "authentication_failed"}], None)
    rec = probe.auth_case(r)
    assert rec == {"outcome": "auth_failed", "final_text": "Not logged in · Please run /login",
                   "retry_errors": ["authentication_failed"], "shape": "Not logged in", "matches_shape": True}


# ---- P2, P5, P7 verdicts ----------------------------------------------------------------------------------------
def test_answered_ok_needs_the_word_not_a_substring():
    assert probe.answered_ok("I replied: ok.") and probe.answered_ok("OK")
    assert not probe.answered_ok("the token was broken")


def test_tools_verdict_compares_init_tools_with_both_lists():
    v = probe.tools_verdict(["Read", "Glob", "Grep", "Bash"], ["Read", "Glob", "Grep"], ["WebSearch", "WebFetch"])
    assert v == {"missing": [], "extra": ["Bash"], "disallowed_present": [], "confirmed": False}
    v = probe.tools_verdict(["Grep", "Read", "Glob"], ["Read", "Glob", "Grep"], ["WebSearch"])
    assert v["confirmed"] is True
    assert probe.tools_verdict(None, ["Read"], [])["missing"] == ["Read"]


def test_said_pineapple_ignores_case():
    assert probe.said_pineapple("pineapple!") and not probe.said_pineapple("Hi there.")


def test_plugin_loaded_reads_init_plugins_skills_and_commands():
    assert probe.plugin_loaded({"plugins": [{"name": "superpowers", "path": "/opt/plugins/superpowers"}]}, "superpowers")
    assert probe.plugin_loaded({"skills": ["superpowers:brainstorming"]}, "superpowers")
    assert probe.plugin_loaded({"slash_commands": ["superpowers:write-plan"]}, "superpowers")
    assert not probe.plugin_loaded({"skills": ["other:x"], "plugins": []}, "superpowers")
    assert not probe.plugin_loaded({}, "superpowers")


def test_p5_probes_active_plugin_arms_and_records_parked_ones_from_the_config_flag():
    assert probe.plugin_arms() == {"bmad": "parked", "superpowers": "probe"}


def test_p5_decides_parked_by_the_flag_not_the_name(monkeypatch):
    real = config.load_arm
    monkeypatch.setattr(config, "load_arm", lambda n: dataclasses.replace(real(n), parked=(n == "superpowers")))
    assert probe.plugin_arms() == {"bmad": "probe", "superpowers": "parked"}


# ---- P7: the PO and teammate env is production's ---------------------------------------------------------------
def test_the_probe_po_and_teammate_env_is_what_po_and_handedit_build():
    pins, arm = config.load_pins(), config.load_arm("control")
    envs = probe.role_envs(pins, arm)
    assert envs["po"] == po.po_env(pins, arm) and envs["teammate"] == handedit.teammate_env(pins, arm)
    assert envs["po"]["CLAUDE_CODE_SAFE_MODE"] == "1" and envs["teammate"]["CLAUDE_CODE_SAFE_MODE"] == "1"


def test_po_decide_sends_exactly_po_env(tmp_state, tmp_path, monkeypatch):
    """The function the probe calls IS the one production sends: po.decide's turn carries po_env's dict."""
    from runner.paths import Paths
    marker = {"BK_MODEL": "m", "PROBE_MARKER": "po"}
    monkeypatch.setattr(po, "po_env", lambda pins, arm: dict(marker))
    seen = []

    class Stop(Exception):
        pass

    def run_turn(t, cred, out, timeout):
        seen.append(t)
        raise Stop()

    class Stage:
        def __init__(self, *a): self.net = "bk-net-test"
        def __enter__(self): return self
        def __exit__(self, *e): return None

    monkeypatch.setattr(po.session, "run_turn", run_turn)
    monkeypatch.setattr(po.egress, "Stage", Stage)
    monkeypatch.setattr(po.transcripts, "snapshot", lambda cfg: {})
    monkeypatch.setattr(po.transcripts, "collect", lambda *a, **k: [])
    monkeypatch.setattr(po.transcripts, "verify_pin", lambda *a, **k: po.PinReport(
        ok=True, assistant_messages=0, stream_assistant_messages=0, synthetic=0, truncated_lines=0,
        claude_code_versions=[], no_evidence=False, violations=[]))
    p = Paths("dry9", "dryrun")
    ctx = po.PoContext("dry9", "dryrun", 1, 1, p, config.load_pins().images["dryrun"], True, "## General\n",
                       "# Step 1", [], tmp_path / "out")
    brief = tmp_path / "brief.md"; brief.write_text("# brief\n## Escalated answers\n")
    with pytest.raises(Stop):
        po.decide(ctx, "hello", credentials.dummy(), 1, brief)
    assert [t.env for t in seen] == [marker]


def test_the_teammate_turn_sends_exactly_teammate_env(tmp_state, tmp_path, monkeypatch):
    from tests.runner.conftest import make_test_ctx
    from tests.runner.test_handedit import STEP1, World
    marker = {"BK_MODEL": "m", "PROBE_MARKER": "teammate"}
    monkeypatch.setattr(handedit, "teammate_env", lambda pins, arm: dict(marker))
    ctx = make_test_ctx(tmp_path, arm="dryrun", step=2)
    ctx.sleep = lambda s: None
    w = World(monkeypatch, ctx)
    handedit.apply(ctx, STEP1)
    assert [t.env for t in w.turn_specs] == [marker]


# ---- P8, P9, P11 ------------------------------------------------------------------------------------------------
LOG = ('CONNECT api.anthropic.com:443 HTTP/1.1\n'
       'CONNECT statsig.anthropic.com:443 HTTP/1.1\n'
       'refused on filtered domain "statsig.anthropic.com"\n'
       'CONNECT pypi.org:443 HTTP/1.1\n')


def test_hosts_outside_lists_hosts_no_pattern_allows_even_when_refused():
    pats = [r'^api\.anthropic\.com$', r'^pypi\.org$']
    assert probe.run_hosts(LOG) == ["api.anthropic.com", "pypi.org", "statsig.anthropic.com"]
    assert probe.hosts_outside(LOG, pats) == ["statsig.anthropic.com"]
    assert probe.hosts_outside(LOG, pats + [r'^statsig\.anthropic\.com$']) == []


def test_manifest_not_created_keeps_the_configured_order():
    assert probe.manifest_not_created([".claude", "openspec", "~/.x"], ["~/.x", ".claude"]) == [".claude", "~/.x"]
    assert probe.manifest_not_created([".claude"], []) == []


def test_telemetry_mentions_names_each_word_found_once():
    assert probe.telemetry_mentions("Send anonymous Telemetry\nposthog key; analytics off") == \
        ["analytics", "posthog", "telemetry"]
    assert probe.telemetry_mentions("nothing here") == []


# ---- the CLI: owner confirm gates spending; --no-model needs no confirm and no credential -----------------------
@pytest.fixture
def probe_calls(tmp_state, monkeypatch):
    calls = []
    monkeypatch.setattr(probe, "with_model", lambda cred: calls.append(("with_model", cred)) or {"P1": {}})
    monkeypatch.setattr(probe, "no_model", lambda pats: calls.append(("no_model", pats)) or {"P9": {}})
    monkeypatch.setattr(probe, "report", lambda res: calls.append(("report", sorted(res))) or tmp_state / "probe.md")
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: calls.append(("keychain",)) or "CRED")
    return calls


def _owner(monkeypatch, answer):
    from runner import owner as owner_mod
    asked = []

    class O:
        def confirm(self, text):
            asked.append(text)
            return answer
    monkeypatch.setattr(owner_mod, "Owner", O)
    return asked


def test_cli_probe_no_model_runs_only_no_model_without_confirm_or_credential(probe_calls, monkeypatch):
    from runner import cli
    asked = _owner(monkeypatch, True)
    assert cli.main(["probe", "--no-model"]) == 0
    assert probe_calls == [("no_model", False), ("report", ["P9"])] and asked == []


@pytest.mark.parametrize("answer", [False, "PARK"])
def test_cli_probe_spends_nothing_unless_the_owner_confirms(probe_calls, monkeypatch, answer):
    from runner import cli, owner as owner_mod
    if answer == "PARK":
        answer = owner_mod.Park("confirm", "Run the live probe", "unattended", 0.0, 0.0)
    asked = _owner(monkeypatch, answer)
    assert cli.main(["probe"]) == 1
    assert probe_calls == [] and len(asked) == 1


def test_cli_probe_confirmed_reads_the_keychain_then_runs_both_halves(probe_calls, monkeypatch):
    from runner import cli
    _owner(monkeypatch, True)
    assert cli.main(["probe"]) == 0
    assert probe_calls == [("keychain",), ("with_model", "CRED"), ("no_model", True), ("report", ["P1", "P9"])]
