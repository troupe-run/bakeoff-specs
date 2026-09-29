"""Product-owner agent (Task 13): the protocol parser, brief growth, escalation (incl. owner parks), the
step-5 PO view, the PO session's mounts (OD21), and `decide`'s session/retry logic — all without Docker
(`session.run_turn` and `egress.Stage` are replaced by in-process fakes; no model calls)."""
import contextlib, dataclasses, gzip, json
from pathlib import Path

import pytest

from runner import config, handoff, owner, paths, po, session
from runner.paths import Paths
from runner.session import TurnResult

REPO = Path(__file__).resolve().parents[2]


def J(**o):
    base = {"kind": "question", "answers": [{"question": "q?", "reply": "x", "escalate": False, "cited": "contract §General"}],
            "reply": None, "approved": None, "command": None, "arguments": "", "significant": False}
    base.update(o); return json.dumps(base)


# --- parse ----------------------------------------------------------------------------------------------------

def test_plain_json_parses():
    d = po.parse(J())
    assert d.kind == "question" and d.answers[0].reply == "x"


def test_json_inside_a_code_fence_parses():
    assert po.parse("```json\n" + J(kind="continue", answers=[], reply="Please continue.") + "\n```").kind == "continue"


def test_mixed_questions_answer_some_and_escalate_others():                    # review F-12
    d = po.parse(J(answers=[{"question": "a?", "reply": "yes", "escalate": False, "cited": "brief"},
                            {"question": "b?", "reply": None, "escalate": True, "cited": None}]))
    assert [a.escalate for a in d.answers] == [False, True] and d.escalated == ["b?"]


def test_next_command_may_name_a_skill_without_a_slash():                       # review F-2
    d = po.parse(J(kind="next_command", answers=[], command="bmad-create-architecture", arguments=""))
    assert d.command == "bmad-create-architecture"


def test_approval_parses_with_a_verdict():
    d = po.parse(J(kind="approval", answers=[], reply="Consistent with Overrides.", approved=True))
    assert d.approved is True and d.reply == "Consistent with Overrides."


def test_step_done_parses():
    assert po.parse(J(kind="step_done", answers=[])).kind == "step_done"


@pytest.mark.parametrize("bad", [
    "not json", J(kind="chat"), J(answers=[]),
    J(answers=[{"question": "q", "reply": "an answer", "escalate": True, "cited": None}]),
    J(answers=[{"question": "q", "reply": None, "escalate": False, "cited": None}]),
    J(kind="approval", answers=[], reply="ok", approved=None),
    J(kind="next_command", answers=[], command=None),
    J(kind="continue", answers=[], reply="ok go"),
    J(kind="step_done", answers=[], reply="x"),
    "[1, 2]",                                                  # JSON, but not an object
    J(answers=[{"reply": "x", "escalate": False}]),            # an answer without its question
    J(answers=["just a string"]),                              # an answer that is not an object
    J(approved="yes", kind="approval", answers=[], reply="ok"),  # approved must be a bool
])
def test_protocol_violations_are_rejected(bad):
    with pytest.raises(po.ProtocolError):
        po.parse(bad)


def test_decision_shape_is_what_the_owner_module_uses():
    """Task 14's owner.gate reads decision.approved/.reply; the stub's names and field order are kept."""
    assert [f.name for f in dataclasses.fields(po.Decision)] == \
        ["kind", "reply", "answers", "approved", "command", "arguments", "significant"]
    assert [f.name for f in dataclasses.fields(po.Answer)] == ["question", "reply", "escalate", "cited"]


def test_protocol_says_it_replaces_the_briefs_escalate_format():               # review Q-3
    text = po.PROTOCOL.read_text()
    assert "replaces the brief's reply format" in text and "ESCALATE" in text


def test_protocol_forbids_mentioning_later_steps_and_writing():
    text = po.PROTOCOL.read_text()
    assert "Never mention later steps" in text and "You never write or edit anything" in text


# --- brief growth ---------------------------------------------------------------------------------------------

BRIEF = "# Product-owner brief\n\n## Escalated answers\n(Appended during the bake-off: question, answer, date, arm that first raised it.)\n"


def test_escalated_answer_is_appended_under_the_escalated_answers_heading(tmp_path):
    b = tmp_path / "po-brief.md"
    b.write_text(BRIEF)
    po.append_escalation(b, "Should floats keep trailing zeros?", "Print as written in the file.", "pass1", "openspec", 1,
                         source="real")
    tail = b.read_text().splitlines()[-1]
    assert tail.startswith("- **Q:** Should floats keep trailing zeros? **A:** Print as written in the file.")
    assert "pass1" in tail and "first raised by openspec at step 1" in tail


def test_escalated_answer_records_date_pass_arm_step_and_real_or_scripted_owner(tmp_path):   # controller ruling
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    po.append_escalation(b, "q1?", "a1", "pass1", "openspec", 2, source="real", today="2026-09-29")
    po.append_escalation(b, "q2?", "a2", "dry9", "dryrun", 3, source="scripted", today="2026-09-30")
    lines = b.read_text().splitlines()
    assert lines[-2] == "- **Q:** q1? **A:** a1 _(2026-09-29; pass1; first raised by openspec at step 2; " \
                        "answered by the real owner)_"
    assert lines[-1] == "- **Q:** q2? **A:** a2 _(2026-09-30; dry9; first raised by dryrun at step 3; " \
                        "answered by the scripted owner)_"


def test_the_owner_source_is_required_and_checked(tmp_path):
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    with pytest.raises(TypeError):
        po.append_escalation(b, "q?", "a", "pass1", "openspec", 1)            # no source: never guessed
    with pytest.raises(ValueError):
        po.append_escalation(b, "q?", "a", "pass1", "openspec", 1, source="po")
    assert b.read_text() == BRIEF


def test_a_multi_line_owner_answer_stays_inside_its_bullet(tmp_path):
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    po.append_escalation(b, "Floats?", "Print floats\nexactly as written.", "pass1", "speckit", 4, source="real",
                         today="2026-09-29")
    entry = b.read_text().splitlines()[-2:]
    assert entry[0] == "- **Q:** Floats? **A:** Print floats"
    assert entry[1].startswith("  exactly as written. _(2026-09-29; pass1; first raised by speckit at step 4;")


def test_a_multi_line_question_is_folded_to_one_line(tmp_path):
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    po.append_escalation(b, "Should\n  floats  keep zeros?", "Yes.", "pass1", "ccsdd", 1, source="real")
    assert b.read_text().splitlines()[-1].startswith("- **Q:** Should floats keep zeros? **A:** Yes.")


def test_the_answer_goes_into_its_section_even_when_a_section_follows(tmp_path):
    b = tmp_path / "po-brief.md"
    b.write_text(BRIEF + "\n## Later section\nkeep me last\n")
    po.append_escalation(b, "q?", "a", "pass1", "control", 1, source="real")
    text = b.read_text()
    assert text.index("- **Q:** q?") < text.index("## Later section") and text.endswith("keep me last\n")


def test_a_brief_without_the_section_is_refused(tmp_path):
    b = tmp_path / "po-brief.md"; b.write_text("# brief\n")
    with pytest.raises(ValueError):
        po.append_escalation(b, "q?", "a", "pass1", "control", 1, source="real")


@pytest.mark.parametrize("answer", ["", "   \n ", owner.Park("escalation", "q?", "eof", 0.0, 1.0), None])
def test_a_park_or_an_empty_answer_is_never_appended(tmp_path, answer):
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    with pytest.raises((TypeError, ValueError)):
        po.append_escalation(b, "q?", answer, "pass1", "control", 1, source="real")
    assert b.read_text() == BRIEF


def test_the_real_scenario_brief_has_the_escalated_answers_section():
    assert "## Escalated answers" in (REPO / "scenario" / "po-brief.md").read_text()


def test_commit_brief_is_a_no_op_outside_the_real_passes(tmp_path, monkeypatch):
    got = []
    monkeypatch.setattr(po.gitops, "commit_harness_file", lambda path, msg: got.append((path, msg)))
    for p in ("dry9", "probe", "canary"):
        po.commit_brief(tmp_path / "b.md", p, "dryrun", 1)
    assert got == []


def test_commit_brief_commits_exactly_the_brief_path_on_real_passes(tmp_path, monkeypatch):   # review S-8
    got = []
    monkeypatch.setattr(po.gitops, "commit_harness_file", lambda path, msg: got.append((path, msg)))
    po.commit_brief(tmp_path / "b.md", "pass1", "openspec", 3)
    assert got == [(tmp_path / "b.md", "PO brief: escalated answer (pass1, openspec step 3)")]


# --- escalate: the owner may park -----------------------------------------------------------------------------

def _script(tmp_path):
    s = tmp_path / "owner.toml"; s.write_text('[escalations]\ndefault = "Keep it simple."\n'); return s


def test_escalate_with_the_scripted_owner_appends_a_scripted_answer(tmp_path, monkeypatch):
    commits = []
    monkeypatch.setattr(po, "commit_brief", lambda *a: commits.append(a))
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    o = owner.ScriptedOwner(_script(tmp_path)).bind(config.load_arm("dryrun"))
    got = po.escalate(o, "b?", "the arm said b?", brief_path=b, pass_="dry9", arm="dryrun", step=2, out_dir=tmp_path / "out")
    assert isinstance(got, po.Escalation) and got.answer == "Keep it simple." and got.source == "scripted"
    assert "answered by the scripted owner" in b.read_text().splitlines()[-1]
    assert commits == [(b, "dry9", "dryrun", 2)]


def test_escalate_with_the_real_owner_appends_a_real_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(po, "commit_brief", lambda *a: None)
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    lines = iter(["Print as written.", "."])
    o = owner.Owner(input_fn=lambda prompt="": next(lines), out=lambda s: None)
    got = po.escalate(o, "Floats?", "ctx", brief_path=b, pass_="pass1", arm="openspec", step=1, out_dir=tmp_path / "out")
    assert got.source == "real" and got.answer == "Print as written."
    assert "answered by the real owner" in b.read_text().splitlines()[-1]


def test_a_parked_escalation_is_recorded_and_returned_never_answered(tmp_path, monkeypatch):
    commits = []
    monkeypatch.setattr(po, "commit_brief", lambda *a: commits.append(a))
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    o = owner.Owner(input_fn=lambda prompt="": pytest.fail("an unattended owner reads nothing"), out=lambda s: None,
                    unattended=True)
    got = po.escalate(o, "Floats?", "ctx", brief_path=b, pass_="pass1", arm="openspec", step=1, out_dir=tmp_path / "out")
    assert isinstance(got, owner.Park) and got.reason == "unattended"
    assert b.read_text() == BRIEF and commits == []                         # nothing appended, nothing committed
    rec = [json.loads(l) for l in (tmp_path / "out" / "po" / "parked-escalations.jsonl").read_text().splitlines()]
    assert rec == [{"question": "Floats?", "pass": "pass1", "arm": "openspec", "step": 1, "prompt": "escalation",
                    "context": "Floats?", "reason": "unattended", "at": got.at, "seconds": got.seconds}]


def test_an_empty_owner_answer_is_parked_not_appended(tmp_path, monkeypatch):
    monkeypatch.setattr(po, "commit_brief", lambda *a: pytest.fail("nothing to commit"))
    b = tmp_path / "po-brief.md"; b.write_text(BRIEF)
    lines = iter(["."])
    o = owner.Owner(input_fn=lambda prompt="": next(lines), out=lambda s: None)
    got = po.escalate(o, "Floats?", "ctx", brief_path=b, pass_="pass1", arm="openspec", step=1, out_dir=tmp_path / "out")
    assert isinstance(got, owner.Park) and got.reason == "empty-answer" and b.read_text() == BRIEF
    assert (tmp_path / "out" / "po" / "parked-escalations.jsonl").exists()


# --- the step-5 PO view (Tasks 13/15/23 binding requirement) --------------------------------------------------

STEP5 = (REPO / "scenario" / "steps" / "05-overrides.md").read_text()
CONTRACT = (REPO / "scenario" / "contract.md").read_text()


def test_before_crb_is_sent_the_po_sees_cr_a_only():
    brief, contract = po.step_view(5, STEP5, CONTRACT, crb_sent=False, delivery="two-requests")
    assert "CR-A" in brief and "CR-B" not in brief and "In-include" not in brief
    assert "two change requests" not in brief                               # the heading would pre-announce CR-B
    assert contract == handoff.in_force(5, CONTRACT, after_crb=False) and "In-include" not in contract


def test_once_crb_is_sent_the_po_sees_both_requests_and_the_in_include_section():
    brief, contract = po.step_view(5, STEP5, CONTRACT, crb_sent=True, delivery="two-requests")
    assert "CR-A" in brief and "CR-B" in brief
    assert contract == handoff.in_force(5, CONTRACT, after_crb=True) and "In-include" in contract


def test_one_message_mode_shows_everything_from_the_start():
    brief, contract = po.step_view(5, STEP5, CONTRACT, crb_sent=False, delivery="one-message")
    assert brief == STEP5 and contract == handoff.in_force(5, CONTRACT, after_crb=True)


def test_the_default_delivery_is_the_scenario_setting_and_the_default_view_is_conservative():
    brief, contract = po.step_view(5, STEP5, CONTRACT)
    if handoff.STEP5["delivery"] == "two-requests":
        assert "CR-B" not in brief and "In-include" not in contract


@pytest.mark.parametrize("step", [1, 2, 3, 4, 6, 7])
def test_other_steps_see_their_whole_brief_and_the_sections_in_force(step):
    text = next((REPO / "scenario" / "steps").glob(f"{step:02d}-*.md")).read_text()
    assert po.step_view(step, text, CONTRACT) == (text, handoff.in_force(step, CONTRACT))


# --- the PO session: mounts (OD21) and decide() without Docker ------------------------------------------------

@pytest.fixture
def ctx(tmp_state):
    p = Paths("dry9", "dryrun")
    p.work.mkdir(parents=True)
    return po.PoContext("dry9", "dryrun", 1, 1, p, config.load_pins().images["dryrun"], True, "## General\n",
                        "# Step 1", [], tmp_state / "out")


@pytest.fixture
def brief(tmp_path):
    b = tmp_path / "brief.md"; b.write_text(BRIEF); return b


class FakeStage:
    def __init__(self, *a, **k):
        self.net = "bk-net-fake"
        FakeStage.made.append(a)

    def __enter__(self): return self

    def __exit__(self, *exc): return None


def GOOD(kind="continue"):
    return json.dumps({"kind": kind, "answers": [], "reply": "Please continue." if kind == "continue" else None,
                       "approved": None, "command": None, "arguments": "", "significant": False})


def fake_turns(monkeypatch, replies, model=None):
    """`session.run_turn` stand-in: each call pops (outcome, text), writes a stream + a transcript like the real
    fake claude, and records the Turn it was given."""
    model = model or config.load_pins().model
    FakeStage.made = []
    monkeypatch.setattr(po.egress, "Stage", FakeStage)
    seen, queue = [], list(replies)

    def run_turn(t, cred, out_dir, timeout_s):
        seen.append(t)
        outcome, text = queue.pop(0)
        (out_dir / "turns").mkdir(parents=True, exist_ok=True)
        stream = out_dir / "turns" / f"{session.stem(t)}.stream.jsonl.gz"
        sid = f"s{t.n}"
        evs = [{"type": "system", "subtype": "init", "model": model, "claude_code_version": "2.1.281"},
               {"type": "assistant", "message": {"model": model, "content": [{"type": "text", "text": text}]}}]
        result = None
        if outcome in ("ok", "is_error"):
            result = {"type": "result", "is_error": outcome == "is_error", "result": text,
                      "modelUsage": {model: {}}, "total_cost_usd": 0.01}
            evs.append(result)
        with gzip.open(stream, "wt") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in evs))
        proj = t.config_dir / "projects" / "-work-bakeoff-specs-dryrun"; proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{sid}.jsonl").write_text(json.dumps(evs[1]) + "\n")
        return TurnResult(sid, outcome, text if result else "", evs[0], result, 0.01, {}, {}, 0.1, [], stream, None)

    monkeypatch.setattr(po.session, "run_turn", run_turn)
    return seen


def test_the_po_session_mounts_work_read_only_and_no_hidden_tests(ctx, brief, monkeypatch):
    seen = fake_turns(monkeypatch, [("ok", GOOD())])
    po.decide(ctx, "working", po.credentials.dummy(), 1, brief)
    t = seen[0]
    m = {x.ctr: x for x in t.mounts}
    assert m["/work"].host == ctx.paths.work and m["/work"].ro is True
    assert m["/home/actor"].host == ctx.paths.po_home and m["/home/actor"].ro is False
    po_files = sorted(k for k in m if k.startswith("/po/"))
    assert po_files == ["/po/contract.md", "/po/message.md", "/po/po-brief.md", "/po/protocol.md", "/po/qa.md",
                        "/po/step.md"] and all(m[k].ro for k in po_files)
    assert set(m) == {"/work", "/home/actor", *po_files}                    # nothing else: no /hidden, no /opt
    for x in t.mounts:                                                      # OD21: never hidden tests or reference
        assert not x.host.resolve().is_relative_to((REPO / "tests").resolve())
        assert not x.host.resolve().is_relative_to((REPO / "reference").resolve())
        assert not x.host.resolve().is_relative_to(ctx.paths.scratch.resolve())
        assert "hidden" not in x.ctr
    assert t.role == "po" and t.inbox_dir == ctx.paths.inbox("po") and t.workdir == ctx.paths.container_repo
    assert t.message == "Read /po/protocol.md and follow it."
    assert t.env["BK_ISOLATED"] == "1" and t.env["BK_TOOLS"] == "Read,Glob,Grep" and t.dry is True
    assert FakeStage.made[0][:4] == ("dry9", "dryrun", "po", config.load_pins().egress_po)


@pytest.mark.parametrize("bad", ["tests/hidden", "reference", "scratch"])
def test_a_mount_of_hidden_tests_reference_or_scratch_is_refused(ctx, bad):
    from runner.docker import Mount
    src = ctx.paths.scratch / "x" if bad == "scratch" else REPO / bad
    with pytest.raises(PermissionError):
        po.check_mounts([Mount(src, "/x", True)], ctx.paths)


def test_a_writable_work_mount_is_refused(ctx):
    from runner.docker import Mount
    with pytest.raises(PermissionError):
        po.check_mounts([Mount(ctx.paths.work, "/work", False)], ctx.paths)


def test_another_arms_state_is_refused(ctx):
    from runner.docker import Mount
    with pytest.raises(PermissionError):
        po.check_mounts([Mount(Paths("dry9", "other").work, "/work", True)], ctx.paths)


def test_decide_keeps_every_input_and_verifies_the_pin(ctx, brief, monkeypatch):
    fake_turns(monkeypatch, [("ok", GOOD())])
    ctx = dataclasses.replace(ctx, qa_so_far=[{"arm_message": "a?", "answered_by": "po", "reply": "b"}])
    r = po.decide(ctx, "working", po.credentials.dummy(), 7, brief)
    d = ctx.out_dir / "po" / "a1-007"
    assert r.decision.kind == "continue" and r.pin.ok and r.retries == 0 and len(r.turns) == 1
    assert (d / "message.md").read_text() == "working" and (d / "po-brief.md").read_text() == BRIEF
    assert (d / "step.md").read_text() == "# Step 1" and (d / "contract.md").read_text() == "## General\n"
    assert "Q1: a?" in (d / "qa.md").read_text() and "A1 (po): b" in (d / "qa.md").read_text()
    assert (d / "protocol.md").read_text() == po.PROTOCOL.read_text()
    assert json.loads((d / "decision.json").read_text())["kind"] == "continue"
    assert json.loads((d / "model-pin.json").read_text())["ok"] is True
    assert list((d / "transcripts").rglob("*.jsonl.gz"))                    # collected (review C-6)


def test_an_off_pin_po_transcript_is_reported(ctx, brief, monkeypatch):
    fake_turns(monkeypatch, [("ok", GOOD())], model="claude-haiku-4-5")
    r = po.decide(ctx, "working", po.credentials.dummy(), 1, brief)
    assert r.pin.ok is False and r.pin.violations


def test_a_parse_failure_gets_a_second_session_with_the_error(ctx, brief, monkeypatch):
    seen = fake_turns(monkeypatch, [("ok", "nonsense"), ("ok", GOOD("step_done"))])
    r = po.decide(ctx, "done", po.credentials.dummy(), 1, brief)
    assert r.decision.kind == "step_done" and len(seen) == 2
    assert "could not be used" in seen[1].message and seen[0].n != seen[1].n


def test_two_parse_failures_are_a_protocol_error_with_evidence(ctx, brief, monkeypatch):
    fake_turns(monkeypatch, [("ok", "nonsense"), ("ok", "still nonsense")])
    with pytest.raises(po.ProtocolError) as e:
        po.decide(ctx, "x", po.credentials.dummy(), 2, brief)
    assert len(e.value.po_result.turns) == 2
    assert (ctx.out_dir / "po" / "a1-002" / "model-pin.json").exists()      # evidence kept on failure too


def test_a_transient_failure_is_retried_in_place_with_backoff(ctx, brief, monkeypatch):
    seen = fake_turns(monkeypatch, [("is_error", "API Error: 529"), ("no_result", ""), ("ok", GOOD())])
    slept = []
    monkeypatch.setattr(po.time, "sleep", slept.append)
    ctx = dataclasses.replace(ctx, pins=dataclasses.replace(
        config.load_pins(), limits=dataclasses.replace(config.load_pins().limits, transient_backoff=[3, 7])))
    r = po.decide(ctx, "x", po.credentials.dummy(), 1, brief)
    assert r.decision.kind == "continue" and r.retries == 2 and slept == [3, 7] and len(seen) == 3
    assert "could not be used" not in seen[1].message                      # a retry is not a parse complaint


def test_transient_failures_beyond_the_backoff_are_a_session_error_never_a_protocol_error(ctx, brief, monkeypatch):  # C-5
    fake_turns(monkeypatch, [("is_error", "API Error: 529 overloaded"), ("is_error", "API Error: 529 overloaded")])
    monkeypatch.setattr(po.time, "sleep", lambda s: None)
    ctx = dataclasses.replace(ctx, pins=dataclasses.replace(
        config.load_pins(), limits=dataclasses.replace(config.load_pins().limits, transient_backoff=[0])))
    with pytest.raises(po.SessionError) as e:
        po.decide(ctx, "x", po.credentials.dummy(), 3, brief)
    assert not isinstance(e.value, po.ProtocolError) and e.value.outcome == "is_error" and "529" in e.value.detail
    assert (ctx.out_dir / "po" / "a1-003" / "model-pin.json").exists()


@pytest.mark.parametrize("outcome", ["auth_failed", "timeout"])
def test_auth_failure_and_timeout_raise_at_once(ctx, brief, monkeypatch, outcome):
    seen = fake_turns(monkeypatch, [(outcome, ""), ("ok", GOOD())])
    monkeypatch.setattr(po.time, "sleep", lambda s: pytest.fail("no backoff for " + outcome))
    with pytest.raises(po.SessionError) as e:
        po.decide(ctx, "x", po.credentials.dummy(), 1, brief)
    assert e.value.outcome == outcome and len(seen) == 1


def test_decide_reads_limits_from_ctx_pins_when_given(ctx, brief, monkeypatch):   # preflight M11 (signature)
    fake_turns(monkeypatch, [("ok", GOOD())])
    got = {}
    real = po.session.run_turn
    def spy(t, cred, out_dir, timeout_s):
        got["timeout"] = timeout_s
        return real(t, cred, out_dir, timeout_s)
    monkeypatch.setattr(po.session, "run_turn", spy)
    pins = config.load_pins()
    ctx = dataclasses.replace(ctx, pins=dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, turn_seconds=42)))
    po.decide(ctx, "x", po.credentials.dummy(), 1, brief)
    assert got["timeout"] == 42


def test_attempts_never_collide(ctx, brief, monkeypatch):
    fake_turns(monkeypatch, [("ok", GOOD()), ("ok", GOOD())])
    po.decide(ctx, "x", po.credentials.dummy(), 1, brief)
    po.decide(dataclasses.replace(ctx, attempt=2), "y", po.credentials.dummy(), 1, brief)
    assert (ctx.out_dir / "po" / "a1-001" / "message.md").read_text() == "x"
    assert (ctx.out_dir / "po" / "a2-001" / "message.md").read_text() == "y"
