# Task 25: the live probe's own logic. Pure verdicts only — nothing here calls Claude, the keychain or the network;
# the probe itself (`runner probe`) is owner-run.
import dataclasses, gzip, json, os, subprocess
from pathlib import Path

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


def test_files_containing_never_follows_a_link_and_never_opens_a_fifo(tmp_path, monkeypatch):
    outside = tmp_path / "outside"; outside.mkdir(); (outside / "t").write_text("SECRET")
    root = tmp_path / "root"; root.mkdir()
    (root / "link").symlink_to(outside / "t")
    os.mkfifo(root / "pipe")
    opened, real_open = [], os.open
    monkeypatch.setattr(os, "open", lambda path, *a, **k: opened.append(str(path)) or real_open(path, *a, **k))
    assert probe.files_containing(root, b"SECRET") == []
    assert str(root / "pipe") not in opened and str(root / "link") not in opened   # neither is ever opened


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


def test_auth_case_record_names_the_shape_and_the_retry_errors(tmp_path):
    retry = {"type": "system", "subtype": "api_retry", "error": "authentication_failed", "attempt": 1}
    r = session.TurnResult("sid", "auth_failed", "Not logged in · Please run /login", {}, {}, 0.0, {}, {}, 1.0,
                           [retry], None)
    rec = probe.auth_case(r)
    assert rec == {"outcome": "auth_failed", "final_text": "Not logged in · Please run /login",
                   "retry_errors": ["authentication_failed"], "api_retry_events": [retry], "last_event": None,
                   "stderr_tail": "", "shape": "Not logged in", "matches_shape": True}


def test_a_turn_stopped_before_its_result_still_records_what_claude_said(tmp_path):
    """Session stops the turn at api_retry/authentication_failed: no result event, final_text "". The retry events,
    the last system event and the stderr tail are kept, with the probe's own bogus token redacted."""
    bogus = probe.bogus_token()
    stream = tmp_path / "s.jsonl.gz"
    _gz(stream, json.dumps({"type": "system", "subtype": "init"}) + "\n"
        + json.dumps({"type": "system", "subtype": "api_retry", "error": "authentication_failed",
                      "error_text": "401 Invalid bearer token " + bogus}) + "\n{partial")
    stderr = tmp_path / "e.gz"; _gz(stderr, "x" * 5000 + "Failed to authenticate with " + bogus + "\n")
    retries = [{"type": "system", "subtype": "api_retry", "error": "authentication_failed"}]
    r = session.TurnResult(None, "auth_failed", "", {}, None, 0.0, {}, {}, 1.0, retries, stream, stderr)
    rec = probe.auth_case(r, redact=[bogus])
    assert rec["final_text"] == "" and rec["api_retry_events"] == retries
    assert rec["last_event"]["error_text"] == "401 Invalid bearer token <redacted>"
    assert rec["stderr_tail"].endswith("Failed to authenticate with <redacted>\n") and len(rec["stderr_tail"]) <= 4000
    assert bogus not in json.dumps(rec)


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
    monkeypatch.setattr(probe, "scan_results", lambda cred, keychain: calls.append(("scan", cred, keychain))
                        or {"count": 0, "findings": ""})
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
    assert probe_calls == [("no_model", False), ("scan", None, False), ("report", ["P9", "results_scan"])]
    assert asked == []


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
    assert probe_calls == [("keychain",), ("with_model", "CRED"), ("no_model", True), ("scan", "CRED", True),
                           ("report", ["P1", "P9", "results_scan"])]


def test_cli_probe_fails_loudly_when_results_hold_a_finding(probe_calls, monkeypatch, capsys):
    from runner import cli
    monkeypatch.setattr(probe, "scan_results", lambda cred, keychain: {"count": 1, "findings": "P1.json:3 literal"})
    assert cli.main(["probe", "--no-model"]) == 1
    assert "STOP: secret findings" in capsys.readouterr().out


def test_report_says_stop_and_names_the_pat_cleanup(tmp_state):
    f = probe.report({"results_scan": {"count": 2, "findings": "a:1 literal; b:2 literal"},
                      "PAT-cleanup": {"removed": ["x", "y"], "remaining": []}})
    text = f.read_text()
    assert text.startswith("# Live probe\n\n**STOP: 2 secret finding(s)")
    assert "every PAT file the probe installed was removed at the end (2 file(s))" in text
    assert "If any write test failed: that arm's token lacks issue write access — fix the PAT before any arm runs." in text
    f = probe.report({"PAT-cleanup": {"removed": [], "remaining": ["/s/h/.config/gh/hosts.yml"]}})
    assert "PAT copies NOT removed" in f.read_text()


# ---- the tracker snapshot never sees the write test's issue ------------------------------------------------------
def test_the_github_tracker_snapshot_drops_only_the_exact_probe_title(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from runner import tracker
    listed = [{"number": 1, "title": tracker.PROBE_ISSUE["title"]},
              {"number": 2, "title": "Alias bug"},
              {"number": 3, "title": tracker.PROBE_ISSUE["title"] + " (a real one)"}]
    seen = []
    monkeypatch.setattr(tracker, "_gh", lambda argv: seen.append(argv) or json.dumps(listed))
    ctx = SimpleNamespace(arm=config.load_arm("openspec"), pass_="pass1", out=tmp_path, run="b")
    snap = tracker.snapshot(ctx)
    assert [i["number"] for i in snap["issues"]] == [2, 3]
    assert seen == [tracker.gh_list_argv(config.github_slug("pass1", "openspec"))]
    assert [i["number"] for i in json.loads((tmp_path / "tracker.json").read_text())["issues"]] == [2, 3]


def test_the_write_test_title_and_body_are_the_one_tracker_constant():
    from runner import tracker
    assert tracker.PROBE_ISSUE["title"] == "test issue - please ignore"
    assert "bake-off harness" in tracker.PROBE_ISSUE["body"] and "ignore" in tracker.PROBE_ISSUE["body"]
    argv = probe.write_argv("troupe-run/x")
    assert argv == ["gh", "issue", "create", "--repo", "troupe-run/x", "--title", tracker.PROBE_ISSUE["title"],
                    "--body", tracker.PROBE_ISSUE["body"]]
    assert not {"--label", "--type", "--body-file"} & set(argv)


# ---- the real-world paths, against fakes (no Claude, keychain, Docker or network) --------------------------------
TOKEN = "probe-test-oauth-FAKE-0123456789abcdef"          # a test credential; the planted "leak"


class FakeStage:
    made: list = []

    def __init__(self, pass_, arm, phase, hosts, log_to):
        self.args, self.net, self.log_to = (pass_, arm, phase, list(hosts)), f"bk-net-{pass_}-{arm}-{phase}", log_to
        FakeStage.made.append(self)

    def __enter__(self): return self

    def __exit__(self, *e):
        self.log_to.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_to, "a") as fh:
            fh.write("CONNECT api.anthropic.com:443 HTTP/1.1\n")


def _fake_turn(turns):
    def run_turn(t, cred, out, timeout):
        turns.append((t, cred, out, timeout))
        sid = f"s{t.n}"
        leak = TOKEN if t.n == 1 else ""                     # turn 1 "leaks" the token into its stream and transcript
        init = {"type": "system", "subtype": "init", "session_id": sid, "model": "claude-opus-5-5",
                "tools": ["Read", "Glob", "Grep"], "note": leak}
        res = {"type": "result", "is_error": False, "result": "ok PINEAPPLE" if t.n == 8 else "ok"}
        s = out / "turns" / f"{session.stem(t)}.stream.jsonl.gz"; s.parent.mkdir(parents=True, exist_ok=True)
        _gz(s, json.dumps(init) + "\n" + json.dumps(res) + "\n")
        e = out / "turns" / f"{session.stem(t)}.stderr.gz"; _gz(e, "")
        proj = t.config_dir / "projects" / t.workdir.replace("/", "-")
        proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{sid}.jsonl").write_text(json.dumps({"type": "assistant", "message": {"model": "claude-opus-5-5"},
                                                       "leak": leak}) + "\n")
        if t.n in (3, 4):
            (proj / sid / "subagents").mkdir(parents=True, exist_ok=True)
            (proj / sid / "subagents" / "a.jsonl").write_text(
                json.dumps({"type": "assistant", "message": {"model": "claude-opus-5-5"}}) + "\n")
        return session.TurnResult(sid, "ok", res["result"], init, res, 0.01, {}, {}, 1.0, [], s, e)
    return run_turn


@pytest.fixture
def model_world(tmp_state, monkeypatch):
    from runner import checklist, egress, repo, transcripts
    from runner.transcripts import PinReport
    turns = []
    FakeStage.made = []

    def init(p, arm, pass_):
        for d in (p.config_dir, p.repo, p.snapshots, p.scratch):
            d.mkdir(parents=True)
        return "h0"
    monkeypatch.setattr(repo, "init", init)
    monkeypatch.setattr(egress, "Stage", FakeStage)
    monkeypatch.setattr(session, "run_turn", _fake_turn(turns))
    monkeypatch.setattr(transcripts, "verify_pin", lambda *a, **k: PinReport(True, 1, 1, 0, 0, ["2.1.281"], False))
    monkeypatch.setattr(checklist, "install_plugins", lambda p, arm, pass_, st, out: {"claude plugin install x": {"exit": 0}})
    return turns


def test_with_model_turn_order_envs_timeouts_and_stages(model_world):
    from runner import paths
    cred = credentials.Credential(TOKEN)
    res = probe.with_model(cred)
    pins, control, sp = config.load_pins(), config.load_arm("control"), config.load_arm("superpowers")
    ns = [t.n for t, *_ in model_world]
    assert ns == [90, 91, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 20]
    by_n = {t.n: (t, c, out, to) for t, c, out, to in model_world}
    # P1c: no credential, then a bogus token, in their own home, with the short timeout; never the real credential
    auth_home = probe.Paths(probe.NS, "control").base / "auth-home" / ".claude"
    assert [by_n[n][0].config_dir for n in (90, 91)] == [auth_home, auth_home]
    assert by_n[90][1].payload() == b"\n" and by_n[91][1].payload().startswith(b"sk-ant-oat01-PROBEFAKE")
    assert [by_n[n][3] for n in (90, 91)] == [probe.AUTH_TURN_SECONDS] * 2 and probe.AUTH_TURN_SECONDS <= 120
    assert all(by_n[n][1] is cred and by_n[n][3] == probe.TURN_SECONDS for n in ns if n not in (90, 91))
    # envs: resume on turn 2; isolation + tools on 9; the PO and teammate env is production's
    assert by_n[2][0].env["BK_RESUME"] == "s1"
    assert by_n[9][0].env["BK_ISOLATED"] == "1" and by_n[9][0].env["BK_TOOLS"] == "Read,Glob,Grep"
    assert by_n[10][0].env == po.po_env(pins, control) and by_n[11][0].env == handedit.teammate_env(pins, control)
    assert "BK_ISOLATED" not in by_n[8][0].env
    # ruling 5: P1–P7 run stage is exactly run_common; P5 route B keeps the arm's production run stage
    stages = {(s.args[1], s.args[2]): s for s in FakeStage.made}
    assert stages[("control", "run")].args[3] == pins.egress_run_common
    assert stages[("superpowers", "run")].args[3] == pins.egress_run_common + sp.egress_run
    assert stages[("superpowers", "setup")].args[3] == pins.egress_setup_common + sp.egress_setup
    assert {by_n[n][0].network for n in ns if n != 20} == {stages[("control", "run")].net}
    assert by_n[20][0].network == stages[("superpowers", "run")].net and by_n[20][0].image == sp.image
    if pins.plugin_route == "plugin-dir":
        assert by_n[20][0].env["BK_PLUGIN_DIRS"] == " ".join(f"/opt/plugins/{x.name}" for x in sp.plugins)
    # verdicts wired to the right turns
    assert res["P7"]["control_not_isolated"]["said_pineapple"] is True
    assert res["P7"]["isolated_ignored_claude_md"] is True and res["P2"]["ok"] is True
    assert res["P1"]["layout"]["found"] is True and res["P1"]["transcript_models"] == ["claude-opus-5-5"]
    assert res["P3"]["pinned"] is True and res["P5"]["bmad"] == "parked"
    # P10 found the planted token in the probe's config dir (the fake wrote it into a transcript)
    assert any(v["files_with_token"] for v in res["P10"]["config_dirs"].values())


def test_with_model_writes_raw_evidence_only_under_state_and_nothing_unscanned_into_results(model_world):
    from runner import paths
    cred = credentials.Credential(TOKEN)
    res = probe.with_model(cred)
    state = paths.STATE.resolve()
    assert all(Path(out).resolve().is_relative_to(state) for _t, _c, out, _to in model_world)
    results = paths.RESULTS
    assert not list(results.rglob("turns")) and not list(results.rglob("*.stderr.gz"))
    assert probe.files_containing(results, TOKEN.encode()) == []          # the leak never reached results/
    assert res["P1"]["stream_saved"]["saved"] is False and not (probe.out_dir() / "P1-stream.jsonl.gz").exists()
    assert res["P1"]["transcripts_published"]["withheld"] and res["P3"]["transcripts_published"]["copied"]
    scan = probe.scan_results(cred, keychain=False)
    assert scan["count"] == 0 and json.loads((probe.out_dir() / "P10.json").read_text())["results_scan"] == scan


def test_scan_results_finds_a_value_anywhere_under_results_probe(tmp_state):
    cred = credentials.Credential(TOKEN)
    (probe.out_dir() / "x").mkdir(parents=True)
    (probe.out_dir() / "x" / "leak.txt").write_text("…" + TOKEN + "…")
    (tmp_state / "results" / "probe-offline" / "a").mkdir(parents=True)
    (tmp_state / "results" / "probe-offline" / "a" / "log").write_text(TOKEN)
    rec = probe.scan_results(cred, keychain=False)
    assert rec["count"] == 2 and TOKEN not in json.dumps(rec)


PATS = {"pass1": "pat-pass1-FAKE-{arm}-000000000000", "disc": "pat-disc-FAKE-{arm}-111111111111"}


@pytest.fixture
def setup_world(tmp_state, monkeypatch):
    from runner import checklist, commands, docker, egress
    w = {"pat_reads": [], "specs": [], "hosts_at_call": []}
    FakeStage.made = []
    monkeypatch.setattr(egress, "Stage", FakeStage)
    monkeypatch.setattr(probe, "container_text", lambda image, cmd: "usage … telemetry")
    monkeypatch.setattr(credentials, "github_pat",
                        lambda pass_, arm: w["pat_reads"].append(("pass1", pass_, arm)) or PATS["pass1"].format(arm=arm))
    monkeypatch.setattr(credentials, "github_disc_pat",
                        lambda pass_, arm: w["pat_reads"].append(("disc", pass_, arm)) or PATS["disc"].format(arm=arm))

    def run_shell_only(ns, arm, offline=False):
        p = probe.Paths(ns, arm)
        for d in (p.config_dir, p.repo):
            d.mkdir(parents=True, exist_ok=True)
        if arm == "speckit" and not offline:
            sk = p.repo / ".claude" / "skills" / "speckit-taskstoissues"; sk.mkdir(parents=True)
            (sk / "SKILL.md").write_text("Run `gh issue create --title ...`")
        return [checklist.Check(f"{arm}.x", True, "")]
    monkeypatch.setattr(checklist, "run_shell_only", run_shell_only)
    monkeypatch.setattr(commands, "listing", lambda p, arm: commands.Listing({"/x"}, []))
    monkeypatch.setattr(checklist, "manifest_full", lambda p, arm: ({}, [".claude"]))

    def run(spec, input=None, timeout=None, stop_grace=30):
        docker.run_argv(spec)                              # the real argv checks (mount sources exist) + recording
        homes = [m.host for m in spec.mounts if m.ctr == "/home/actor"]
        hy = homes[0] / ".config" / "gh" / "hosts.yml" if homes else None
        w["specs"].append(spec)
        w["hosts_at_call"].append(hy.read_text() if hy and hy.exists() else None)
        if spec.cmd[:3] == ["gh", "issue", "create"]:
            slug = spec.cmd[spec.cmd.index("--repo") + 1]
            return subprocess.CompletedProcess(spec.cmd, 0, f"https://github.com/{slug}/issues/7\n".encode(), b"")
        return subprocess.CompletedProcess(spec.cmd, 0, b"", b"")
    monkeypatch.setattr(docker, "run", run)
    return w


def _pat_files(root):
    return sorted(str(f) for f in Path(root).rglob("*") if f.name in ("hosts.yml", ".bk-mcp.json"))


def test_no_model_without_pats_reads_and_installs_no_pat_and_writes_nothing(setup_world):
    from runner import paths
    res = probe.no_model(pats=False)
    assert setup_world["pat_reads"] == [] and _pat_files(paths.STATE) == []
    assert not [s for s in setup_world["specs"] if s.cmd[:2] == ["gh", "issue"] or "gh issue" in " ".join(s.cmd)]
    assert res["P9-write"] == {"skipped": probe.SKIPPED_PATS}
    assert all(e["issues_access"] == probe.SKIPPED_PATS for a, e in res["P9"]["setup"].items()
               if a in probe.write_arms())
    assert res["P9"]["setup"]["bmad"] == "parked" and res["P11"]["route"] == "gh"
    assert res["PAT-cleanup"] == {"removed": [], "remaining": []}


def test_the_write_test_touches_only_each_arms_two_repos_with_their_own_pats_and_closes_what_it_opens(setup_world):
    from runner import paths
    res = probe.no_model(pats=True)
    arms = probe.write_arms()
    assert arms == ["ccsdd", "control", "openspec", "speckit", "superpowers"]      # active GitHub arms; bmad parked
    gh = [(s, h) for s, h in zip(setup_world["specs"], setup_world["hosts_at_call"]) if s.cmd[:3] in
          (["gh", "issue", "create"], ["gh", "issue", "close"])]
    expected = []
    for a in arms:
        for target, slug in (("pass1", config.github_slug("pass1", a)), ("disc", config.github_disc_slug("pass1", a))):
            pat = PATS[target].format(arm=a)
            expected += [(probe.write_argv(slug), pat), (probe.close_argv(slug, "7"), pat)]
            assert res["P9-write"][a][target] == {"slug": slug, "created": 7, "closed": True}
    assert [(s.cmd, h and h.split("oauth_token: ")[1].split()[0]) for s, h in gh] == expected
    assert all(s.network.startswith("bk-net-probe-write-") and s.proxy and
               [m.ro for m in s.mounts] == [True] for s, _ in gh)
    ghstages = [s for s in FakeStage.made if s.args[2] == "ghwrite"]
    assert len(ghstages) == 2 * len(arms) and all(s.args[3] == config.load_pins().egress_setup_common for s in ghstages)
    # the read-only check is kept, with the pass-1 PAT
    assert all(res["P9"]["setup"][a]["issues_access"]["ok"] for a in arms)
    # every PAT copy is gone afterwards, and the cleanup says so
    assert _pat_files(paths.STATE) == []
    assert res["PAT-cleanup"]["remaining"] == [] and len(res["PAT-cleanup"]["removed"]) == 3 * len(arms)
    assert not any(v in probe.out_dir().joinpath("P9-write.json").read_text()
                   for a in arms for v in (PATS["pass1"].format(arm=a), PATS["disc"].format(arm=a)))


def test_a_failed_create_records_the_error_without_the_pat_and_closes_nothing(setup_world, monkeypatch):
    from runner import docker
    inner = docker.run

    def run(spec, input=None, timeout=None, stop_grace=30):
        if spec.cmd == probe.write_argv(config.github_slug("pass1", "control")):
            inner(spec)
            pat = PATS["pass1"].format(arm="control")
            return subprocess.CompletedProcess(spec.cmd, 1, b"", f"HTTP 403: token {pat} lacks issues:write".encode())
        return inner(spec)
    monkeypatch.setattr(docker, "run", run)
    res = probe.no_model(pats=True)
    rec = res["P9-write"]["control"]["pass1"]
    assert rec["created"] is None and rec["closed"] is False and "HTTP 403" in rec["error"]
    assert "<redacted>" in rec["error"] and "pat-pass1" not in rec["error"]
    slug = config.github_slug("pass1", "control")
    assert not [s for s in setup_world["specs"] if s.cmd == probe.close_argv(slug, "7")]    # nothing to close
    assert res["P9-write"]["control"]["disc"]["closed"] is True                              # the others still ran


def test_pat_copies_are_removed_even_when_a_step_raises(setup_world, monkeypatch):
    from runner import paths
    real_save = probe._save

    def save(name, data):
        if name == "P9-write":
            assert _pat_files(paths.STATE)                  # installed by now...
            raise RuntimeError("disk full")
        return real_save(name, data)
    monkeypatch.setattr(probe, "_save", save)
    with pytest.raises(RuntimeError, match="disk full"):
        probe.no_model(pats=True)
    assert _pat_files(paths.STATE) == []                    # ...and gone after the failure
    assert json.loads((probe.out_dir() / "PAT-cleanup.json").read_text())["remaining"] == []


def test_remove_pat_copies_unlinks_a_link_without_following_it(tmp_path):
    target = tmp_path / "keep.txt"; target.write_text("not a PAT")
    home = tmp_path / "home"; (home / ".config" / "gh").mkdir(parents=True)
    (home / ".config" / "gh" / "hosts.yml").symlink_to(target)
    (home / ".bk-mcp.json").write_text("{}")
    rec = probe.remove_pat_copies([home, home])
    assert rec["remaining"] == [] and len(rec["removed"]) == 2 and target.read_text() == "not a PAT"
