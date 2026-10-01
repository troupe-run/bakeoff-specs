# Task 15: the turn loop for one attempt at a step (no docker: session.run_turn, po.decide, egress.Stage,
# gitops.*, commands.installed, repo.recover and checklist.require_clean_green are scripted fakes).
import contextlib, json
import pytest
from runner import checklist, drive, faults, handoff, owner, po
from runner.po import Decision, Answer, PoResult
from runner.session import TurnResult
from runner.transcripts import PinReport
from tests.runner.conftest import StubOwner, make_test_ctx

OKPIN = PinReport(True, 1, 1, 0, 0, ["2.1.281"], False, [])


def TR(text="", outcome="ok", sid="s1", cred_files=(), retries=()):
    return TurnResult(sid, outcome, text, {}, {} if outcome == "ok" else None, 0.0, {}, {}, 1.0, list(retries),
                      None, None, [], list(cred_files))


def D(kind, reply=None, answers=(), approved=None, command=None, arguments=""):
    return Decision(kind, reply, list(answers), approved, command, arguments, False)


@pytest.fixture
def rig(monkeypatch, tmp_path, tmp_state):
    sent, script, state = [], {"arm": [], "po": []}, {"dirty": False, "head_in_main": True, "main": "sha1"}
    calls = []
    monkeypatch.setattr(drive.egress, "Stage", lambda *a, **k: contextlib.nullcontext(type("S", (), {"net": "n"})()))

    def fake_turn(t, cred, out, timeout):
        calls.append("turn")
        sent.append((t.message, t.env.get("BK_RESUME", ""))); return script["arm"].pop(0)
    monkeypatch.setattr(drive.session, "run_turn", fake_turn)
    monkeypatch.setattr(drive.po, "decide", lambda ctx, msg, cred, n, brief: PoResult(script["po"].pop(0), [TR()], OKPIN))
    monkeypatch.setattr(drive.commands, "installed", lambda p, arm: {"opsx:apply", "opsx:archive", "bmad-create-architecture"})
    monkeypatch.setattr(drive.gitops, "state", lambda p: type("R", (), {**state, "branch": "main", "head": "sha1"})())
    monkeypatch.setattr(drive.gitops, "diffstat", lambda p, a, b: "")
    monkeypatch.setattr(drive.gitops, "worktree_diffstat", lambda p: "")
    monkeypatch.setattr(drive, "_invoked", lambda cmd, turns: False)
    monkeypatch.setattr(drive.repo, "recover", lambda p: calls.append("recover"))
    monkeypatch.setattr(drive.checklist, "require_clean_green", lambda p: calls.append("clean-green"))
    ctx = make_test_ctx(tmp_path, arm="openspec")
    ctx.calls = calls
    return sent, script, state, ctx


def msgs(sent): return [m for m, _ in sent]


def qlines(ctx): return [json.loads(l) for l in (ctx.out / "questions.jsonl").read_text().splitlines()]


# ---- the plan's tests (brief Step 2, verbatim) ---------------------------------------------------------------

def test_follows_the_methods_next_command_then_runs_must_run_then_ends(rig):
    sent, script, _, ctx = rig
    script["arm"] = [TR("proposal ready, run /opsx:apply"), TR("done"), TR("archived")]
    script["po"] = [D("next_command", command="/opsx:apply"), D("step_done"), D("step_done")]
    r = drive.run_attempt(ctx, 1, "/opsx:propose brief")
    assert msgs(sent) == ["/opsx:propose brief", "/opsx:apply", "/opsx:archive"] and r.outcome == "done"


def test_a_named_skill_is_sent_in_its_invocation_form(rig):                      # review F-2
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("bmad")
    script["arm"] = [TR("Next, run the bmad-create-architecture skill."), TR("done")]
    script["po"] = [D("next_command", command="bmad-create-architecture"), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert msgs(sent)[1] == "/bmad-create-architecture"


def test_uninstalled_next_command_becomes_please_continue(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("run /opsx:frobnicate"), TR("ok")]
    script["po"] = [D("next_command", command="/opsx:frobnicate"), D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert msgs(sent)[1] == "Please continue." and r.interventions == ["next_command-not-installed:/opsx:frobnicate"]


def test_mixed_questions_only_escalate_the_uncovered_one(rig):                   # review F-12
    sent, script, _, ctx = rig
    ctx.run = "a"                                   # N.a: an escalation reaches the owner (N.b: the fallback)
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("Two questions: a? b?"), TR("done")]
    script["po"] = [D("question", answers=[Answer("a?", "Yes, per General.", False, "General"),
                                            Answer("b?", None, True, None)]), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert ctx.owner.escalations == ["b?"]
    assert "Yes, per General." in msgs(sent)[1] and ctx.owner.escalation_answer in msgs(sent)[1]
    assert "b?" in ctx.brief_path.read_text()
    q = json.loads((ctx.out / "questions.jsonl").read_text().splitlines()[0])
    assert q["escalated"] == ["b?"] and q["answered_by"] == "po+owner"          # fix round 1 ruling
    assert q["cited"] == "General"                                              # no stray "; " separators


def test_transient_api_error_is_retried_in_place_then_succeeds(rig):            # review C-4
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("API Error: 529 overloaded", outcome="is_error"), TR("done")]
    script["po"] = [D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "done" and r.retries == 1
    assert sent[1] == ("Please continue.", "s1")                               # same session, resumed


def test_transient_errors_become_a_harness_fault_only_when_retries_run_out(rig):
    sent, script, _, ctx = rig
    script["arm"] = [TR("API Error: 529 overloaded", outcome="is_error")] * 4
    slept = []
    ctx.sleep = slept.append
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert e.value.kind == "infra-is_error" and "overloaded" in e.value.signature and len(sent) == 4
    assert slept == [60, 300, 900]                                              # limits.transient_backoff


def test_a_non_transient_api_error_faults_at_once(rig):
    sent, script, _, ctx = rig
    script["arm"] = [TR("API Error: 400 invalid_request_error", outcome="is_error")]
    with pytest.raises(faults.HarnessFault):
        drive.run_attempt(ctx, 1, "go")
    assert len(sent) == 1


def test_a_persisted_credential_is_a_harness_fault(rig):                         # review S-3
    sent, script, _, ctx = rig
    script["arm"] = [TR("ok", cred_files=[".credentials.json"])]
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert e.value.kind == "credential-persisted"


def test_po_session_failure_is_infra_not_protocol(rig, monkeypatch):            # review C-5
    sent, script, _, ctx = rig
    script["arm"] = [TR("hi")]
    def boom(*a, **k): raise po.SessionError("is_error", "API Error: 529")
    monkeypatch.setattr(drive.po, "decide", boom)
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert e.value.kind == "infra-po-is_error"


def test_exchange_cap_ends_the_attempt_as_stalled(rig):
    sent, script, _, ctx = rig
    ctx.pins = drive.dataclasses.replace(ctx.pins, limits=drive.dataclasses.replace(ctx.pins.limits, exchanges_per_attempt=2))
    script["arm"] = [TR("?")] * 3
    script["po"] = [D("continue", "Please continue.")] * 3
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "stalled" and r.breach == "exchanges"


def test_commit_nudge_is_sent_once_when_work_is_not_on_main(rig):               # OD4 A
    sent, script, state, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    state["head_in_main"] = False
    script["arm"] = [TR("done"), TR("still done")]
    script["po"] = [D("step_done"), D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert msgs(sent)[1] == handoff.MESSAGES["commit_on_main"] and r.outcome == "done"


def test_no_nudge_when_od4_b_is_chosen(rig, monkeypatch):                        # OD4 B
    sent, script, state, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    monkeypatch.setitem(handoff.MESSAGES, "commit_on_main", "")
    state["dirty"] = True
    script["arm"] = [TR("done")]; script["po"] = [D("step_done")]
    assert drive.run_attempt(ctx, 1, "go").outcome == "done" and len(sent) == 1


def test_cr_b_preempts_the_end_of_the_second_turn(rig):                         # OD6 B
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.later_messages = ["CR-B text"]
    script["arm"] = [TR("Plan ready. Approve?"), TR("Question: x?"), TR("both done")]
    script["po"] = [D("approval", "Approved.", approved=True), D("step_done")]
    drive.run_attempt(ctx, 1, "CR-A text")
    assert msgs(sent) == ["CR-A text", "Approved.", "CR-B text"]
    kinds = [json.loads(l)["kind"] for l in (ctx.out / "questions.jsonl").read_text().splitlines()]
    assert kinds == ["approval", "preempted", "step_done"]


def test_cr_b_still_arrives_if_the_arm_reports_done_in_its_first_turn(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.later_messages = ["CR-B text"]
    script["arm"] = [TR("all done"), TR("CR-B done")]
    script["po"] = [D("step_done"), D("step_done")]
    drive.run_attempt(ctx, 1, "CR-A text")
    assert msgs(sent) == ["CR-A text", "CR-B text"]


def test_fresh_session_before_a_cited_command(rig):                              # OD19 B
    sent, script, _, ctx = rig
    ctx.arm = drive.dataclasses.replace(drive.config.load_arm("openspec"),
                                        fresh_session_before=[{"command": "/opsx:apply", "source": "cited"}])
    script["arm"] = [TR("run /opsx:apply"), TR("done"), TR("archived")]
    script["po"] = [D("next_command", command="/opsx:apply"), D("step_done"), D("step_done")]
    r = drive.run_attempt(ctx, 1, "/opsx:propose x")
    assert sent[1] == ("/opsx:apply", "") and "fresh-session:/opsx:apply" in r.interventions


def test_configured_export_is_sent_once_after_its_trigger_ran(rig, monkeypatch):  # OD24 B path, on a fixture arm
    sent, script, _, ctx = rig
    ctx.arm = drive.dataclasses.replace(drive.config.load_arm("speckit"), export_after="/speckit-tasks")
    script["arm"] = [TR("run /speckit-tasks"), TR("tasks done"), TR("exported"), TR("converged")]
    script["po"] = [D("next_command", command="/speckit-tasks"), D("step_done"), D("step_done"), D("step_done")]
    monkeypatch.setattr(drive.commands, "installed", lambda p, arm: {"speckit-tasks", "speckit-taskstoissues", "speckit-converge"})
    drive.run_attempt(ctx, 1, "/speckit-specify x")
    assert msgs(sent) == ["/speckit-specify x", "/speckit-tasks", "/speckit-taskstoissues", "/speckit-converge"]


# ---- binding rulings (controller, Task 15) --------------------------------------------------------------------

class ParkingOwner(StubOwner):
    def __init__(self, where, reason="unattended"):
        super().__init__(); self.where, self.reason = where, reason

    def escalation(self, q, ctx):
        self.escalations.append(q)
        if self.where == "escalation":
            return owner.Park("escalation", q, self.reason, 1.0, 0.5)
        if self.where == "empty":
            return "   ", 0.5
        return super().escalation(q, ctx)

    def gate(self, msg, dec, diff):
        self.gates.append(msg)
        if self.where == "gate":
            return owner.Park("gate", msg, self.reason, 1.0, 3.0)
        return super().gate(msg, dec, diff)


def test_a_parked_gate_parks_the_attempt_cleanly_and_is_recorded(rig):          # ruling 1
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.owner = ParkingOwner("gate")
    script["arm"] = [TR("Plan ready. Approve?")]
    script["po"] = [D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "parked" and isinstance(r.park, owner.Park) and r.park.reason == "unattended"
    assert len(sent) == 1                                                       # nothing sent after the park
    q = qlines(ctx)[-1]
    assert q["kind"] == "approval" and q["owner_action"] == "park" and q["park"]["reason"] == "unattended"
    assert q["park"]["context"] == "Plan ready. Approve?" and q["reply"] is None
    g = json.loads((ctx.out / "owner-gates.jsonl").read_text().splitlines()[-1])
    assert g["owner_action"] == "park" and g["final_reply"] is None


@pytest.mark.parametrize("where,reason", [("escalation", "timeout"), ("empty", "empty-answer")])
def test_a_parked_escalation_is_recorded_never_appended_and_parks_the_attempt(rig, where, reason):  # ruling 1
    sent, script, _, ctx = rig
    ctx.run = "a"                                   # N.a: an escalation reaches the owner (N.b: the fallback)
    ctx.arm = drive.config.load_arm("control"); ctx.owner = ParkingOwner(where, reason)
    before = ctx.brief_path.read_text()
    script["arm"] = [TR("Two questions: a? b?")]
    script["po"] = [D("question", answers=[Answer("a?", "Yes.", False, "General"), Answer("b?", None, True, None)])]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "parked" and r.park.reason == reason and len(sent) == 1
    assert ctx.brief_path.read_text() == before                                 # never appended
    q = qlines(ctx)[-1]
    assert q["kind"] == "question" and q["owner_action"] == "park" and q["park"]["reason"] == reason
    assert q["escalated"] == ["b?"] and q["reply"] is None
    assert (ctx.out / "po" / "parked-escalations.jsonl").exists()


def test_a_scripted_owner_answer_is_appended_as_scripted(rig, tmp_path):        # ruling 2
    sent, script, _, ctx = rig
    ctx.run = "a"                                   # N.a: an escalation reaches the owner (N.b: the fallback)
    ctx.arm = drive.config.load_arm("dryrun")
    (tmp_path / "s.toml").write_text('[escalations]\ndefault = "Scripted answer."\n')
    ctx.owner = owner.ScriptedOwner(tmp_path / "s.toml").bind(ctx.arm)
    script["arm"] = [TR("b?"), TR("done"), TR("closed")]                         # dryrun's must_run: /dry-close
    script["po"] = [D("question", answers=[Answer("b?", None, True, None)]), D("step_done"), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    text = ctx.brief_path.read_text()
    assert "Scripted answer." in text and "answered by the scripted owner" in text


def test_a_stub_owner_answer_is_appended_as_real(rig):                           # ruling 2
    sent, script, _, ctx = rig
    ctx.run = "a"                                   # N.a: an escalation reaches the owner (N.b: the fallback)
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("b?"), TR("done")]
    script["po"] = [D("question", answers=[Answer("b?", None, True, None)]), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert "answered by the real owner" in ctx.brief_path.read_text()


def _step5_ctx(ctx):
    from runner.paths import REPO_ROOT
    brief = (REPO_ROOT / "scenario" / "steps" / "05-overrides.md").read_text()
    contract = (REPO_ROOT / "scenario" / "contract.md").read_text()
    ctx.step, ctx.step_brief, ctx.contract = 5, brief, contract
    ctx.contract_in_force = handoff.in_force(5, contract)          # what orchestrate passes today: CR-B's section too
    ctx.arm = drive.config.load_arm("control")
    first, second = handoff.step5(brief, contract)
    ctx.later_messages = [second]
    return first, second


def test_step5_po_sees_cr_a_only_until_cr_b_is_sent_then_both(rig, monkeypatch):  # ruling 3
    sent, script, _, ctx = rig
    first, second = _step5_ctx(ctx)
    seen = []
    def decide(pctx, msg, cred, n, brief):
        seen.append((pctx.step_brief, pctx.contract_in_force)); return PoResult(script["po"].pop(0), [TR()], OKPIN)
    monkeypatch.setattr(drive.po, "decide", decide)
    script["arm"] = [TR("Approve?"), TR("working"), TR("both done")]
    script["po"] = [D("approval", "Approved.", approved=True), D("step_done")]
    drive.run_attempt(ctx, 1, first)
    assert msgs(sent)[2] == second
    (b1, c1), (b2, c2) = seen
    assert "## CR-A" in b1 and "## CR-B" not in b1 and "## In-include" not in c1 and "## Overrides" in c1
    assert "## CR-A" in b2 and "## CR-B" in b2 and "## In-include" in c2
    assert (b1, c1) == po.step_view(5, ctx.step_brief, ctx.contract, crb_sent=False)
    assert (b2, c2) == po.step_view(5, ctx.step_brief, ctx.contract, crb_sent=True)


def test_step5_cr_b_is_not_resent_in_a_later_attempt(rig, monkeypatch):         # ruling 3 (drive state)
    sent, script, _, ctx = rig
    first, second = _step5_ctx(ctx)
    seen = []
    def decide(pctx, msg, cred, n, brief):
        seen.append(pctx.contract_in_force); return PoResult(script["po"].pop(0), [TR()], OKPIN)
    monkeypatch.setattr(drive.po, "decide", decide)
    script["arm"] = [TR("done"), TR("both done")]
    script["po"] = [D("step_done"), D("step_done")]
    drive.run_attempt(ctx, 1, first)
    assert msgs(sent) == [first, second] and ctx.later_sent == 1
    script["arm"] = [TR("fixed")]; script["po"] = [D("step_done")]
    drive.run_attempt(ctx, 2, handoff.MESSAGES["no_progress"], resume="s1")
    assert msgs(sent)[2:] == [handoff.MESSAGES["no_progress"]]
    assert "## In-include" in seen[-1]


def test_step5_without_the_full_contract_refuses_rather_than_leaking_cr_b(rig):  # ruling 3
    sent, script, _, ctx = rig
    _step5_ctx(ctx); ctx.contract = None
    with pytest.raises(ValueError, match="contract"):
        drive.run_attempt(ctx, 1, "go")
    assert sent == []


def _pin(**kw):
    base = dict(ok=True, assistant_messages=1, stream_assistant_messages=1, synthetic=0, truncated_lines=0,
                claude_code_versions=["2.1.281"], no_evidence=False, violations=[], unverified_streams=[])
    return PinReport(**{**base, **kw})


@pytest.mark.parametrize("pin,kind,sig", [
    (None, "model-pin", "no-report"),
    (_pin(stream_assistant_messages=0), "model-pin", "no-stream-evidence"),
    (_pin(ok=False, no_evidence=True), "model-pin", "no-evidence"),
    (_pin(ok=False, violations=[{"file": "s", "line": 1, "where": "assistant.message.model", "model": "claude-x"}]),
     "model-pin", "claude-x"),
    (_pin(ok=False, violations=[{"file": "s", "line": None, "where": "claude_code_version", "model": "unverifiable"}]),
     "pin-claude-version", "unverifiable"),
    (_pin(ok=False, unverified_streams=["s"]), "model-pin", "unverified"),
])
def test_a_po_pin_problem_is_a_harness_fault_never_a_vacuous_pass(rig, monkeypatch, pin, kind, sig):  # ruling 4
    sent, script, _, ctx = rig
    script["arm"] = [TR("hi")]
    monkeypatch.setattr(drive.po, "decide", lambda *a: PoResult(D("continue", "Please continue."), [TR()], pin))
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert (e.value.kind, e.value.signature) == (kind, sig) and "po" in e.value.detail


def test_classify_pin_maps_an_unverifiable_claude_version():                     # ruling 4
    f = faults.classify_pin(_pin(ok=False, violations=[{"file": None, "line": None, "where": "claude_code_version",
                                                         "model": "unverifiable"}]), "arm")
    assert (f.kind, f.signature) == ("pin-claude-version", "unverifiable") and f.detail.startswith("arm:")


def test_arm_auth_failure_is_infra_auth_even_if_the_turn_also_left_a_credential(rig):   # ruling 4 precedence
    sent, script, _, ctx = rig
    script["arm"] = [TR("Not logged in", outcome="auth_failed", cred_files=[".credentials.json"])]
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert e.value.kind == "infra-auth"


def test_po_auth_failure_is_infra_auth_not_a_pin_fault(rig, monkeypatch):        # ruling 4 precedence
    sent, script, _, ctx = rig
    script["arm"] = [TR("hi")]
    def boom(*a, **k):
        e = po.SessionError("auth_failed", "Not logged in"); e.po_result = PoResult(None, [TR()], _pin(ok=False, no_evidence=True))
        raise e
    monkeypatch.setattr(drive.po, "decide", boom)
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert e.value.kind == "infra-auth" and "po" in e.value.detail


def test_setup_must_be_clean_and_green_before_any_turn(rig, monkeypatch):        # ruling 8
    sent, script, _, ctx = rig
    def dirty(p): raise checklist.NotReady("setup is dirty")
    monkeypatch.setattr(drive.checklist, "require_clean_green", dirty)
    with pytest.raises(checklist.NotReady):
        drive.run_attempt(ctx, 1, "go")
    assert sent == []


def test_recover_runs_before_the_first_turn(rig):                                # ruling 6
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("done")]; script["po"] = [D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert ctx.calls.index("recover") < ctx.calls.index("turn")
    assert ctx.calls.index("clean-green") < ctx.calls.index("turn")


def test_a_retry_storm_error_is_retried_even_without_a_telltale_text(rig):      # TurnResult.retries
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    storm = [{"type": "system", "subtype": "api_retry", "error": "rate_limit"}] * 3
    script["arm"] = [TR("Request failed", outcome="is_error", retries=storm), TR("done")]
    script["po"] = [D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "done" and r.retries == 1 and any("api-retry" in i for i in r.interventions)


def test_a_timeout_ends_the_attempt_with_a_turn_seconds_breach(rig):
    sent, script, _, ctx = rig
    script["arm"] = [TR("", outcome="timeout")]
    r = drive.run_attempt(ctx, 1, "go")
    assert (r.outcome, r.breach) == ("timeout", "turn_seconds")


def test_a_harness_fault_carries_the_attempts_turns_for_evidence(rig):
    sent, script, _, ctx = rig
    script["arm"] = [TR("ok", cred_files=[".credentials.json"])]
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert len(e.value.attempt_result.turns) == 1


def test_arm_sessions_get_the_pass_for_their_environment(rig, monkeypatch):     # session_env(pass_=) is required
    sent, script, _, ctx = rig
    seen = []
    real = drive.credentials.session_env
    def spy(*a, **k):
        seen.append(k); return real(*a, **k)
    monkeypatch.setattr(drive.credentials, "session_env", spy)
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("done")]; script["po"] = [D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert seen and all(k["pass_"] == "dry9" and k["role"] == "arm" for k in seen)


def test_invoked_uses_the_shared_skill_reader(monkeypatch, tmp_path):            # preflight m10
    monkeypatch.setattr(drive.transcripts, "invoked_skills", lambda s: {"speckit:speckit-tasks"} if s else set())
    t = TR(); t.stream_path = tmp_path / "x.gz"
    assert drive._invoked("/speckit-tasks", [t]) and not drive._invoked("/speckit-converge", [t])
    assert not drive._invoked("/speckit-tasks", [TR()])


# ---- fix round 1 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "API Error: 400 invalid_request_error: max_tokens 512 is too large",       # a number in 500-599, not a status
    "API Error: 400 {\"type\":\"invalid_request_error\",\"message\":\"prompt is 503 tokens too long\"}",
])
def test_a_client_error_mentioning_a_5xx_number_is_not_transient(rig, text):   # item 3
    sent, script, _, ctx = rig
    script["arm"] = [TR(text, outcome="is_error")]
    with pytest.raises(faults.HarnessFault) as e:
        drive.run_attempt(ctx, 1, "go")
    assert len(sent) == 1 and e.value.kind == "infra-is_error"


@pytest.mark.parametrize("text", ["API Error: 500 Internal server error", "API Error: 529 overloaded",
                                  "Request failed with status 503", "HTTP 502 Bad Gateway",
                                  '{"type":"error","error":{"type":"api_error","message":"Internal"}}',
                                  "API Error: 429 rate_limit_error"])
def test_real_server_errors_are_transient(rig, text):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR(text, outcome="is_error"), TR("done")]
    script["po"] = [D("step_done")]
    assert drive.run_attempt(ctx, 1, "go").retries == 1


def test_a_clear_4xx_is_never_transient_even_after_api_retries(rig):          # item 2
    sent, script, _, ctx = rig
    storm = [{"type": "system", "subtype": "api_retry", "error": "overloaded"}]
    script["arm"] = [TR("API Error: 400 invalid_request_error", outcome="is_error", retries=storm)]
    with pytest.raises(faults.HarnessFault):
        drive.run_attempt(ctx, 1, "go")
    assert len(sent) == 1


def test_owner_gates_is_absent_when_there_were_no_approvals(rig):             # item 7
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control")
    script["arm"] = [TR("q?"), TR("done")]
    script["po"] = [D("question", answers=[Answer("q?", "Yes.", False, None)]), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert not (ctx.out / "owner-gates.jsonl").exists()
    q = qlines(ctx)[0]
    assert q["answered_by"] == "po" and q["cited"] is None                     # item 5: nothing cited


class AnswerThenPark(StubOwner):
    def escalation(self, q, ctx):
        self.escalations.append(q)
        if len(self.escalations) == 1:
            return "First answer.", 1.0
        return owner.Park("escalation", q, "unattended", 1.0, 0.5)


def test_a_partial_park_keeps_the_answers_already_obtained_in_the_brief(rig):  # item 6
    sent, script, _, ctx = rig
    ctx.run = "a"                                   # N.a: an escalation reaches the owner (N.b: the fallback)
    ctx.arm = drive.config.load_arm("control"); ctx.owner = AnswerThenPark()
    script["arm"] = [TR("a? b? c?")]
    script["po"] = [D("question", answers=[Answer("a?", "Yes.", False, "General"), Answer("b?", None, True, None),
                                            Answer("c?", None, True, None)])]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "parked" and ctx.owner.escalations == ["b?", "c?"]
    brief = ctx.brief_path.read_text()
    assert "First answer." in brief and "c?" not in brief.split("## Escalated answers")[1]
    q = qlines(ctx)[-1]
    assert q["answered_by"] == "po+owner" and q["cited"] == "General" and q["escalated"] == ["b?", "c?"]
    assert q["park"]["context"] == "c?" and q["reply"] is None


def test_a_park_with_no_answers_obtained_is_answered_by_the_runner(rig):       # item 5
    sent, script, _, ctx = rig
    ctx.run = "a"                                   # N.a: an escalation reaches the owner (N.b: the fallback)
    ctx.arm = drive.config.load_arm("control"); ctx.owner = ParkingOwner("escalation")
    script["arm"] = [TR("b?")]
    script["po"] = [D("question", answers=[Answer("b?", None, True, None)])]
    drive.run_attempt(ctx, 1, "go")
    q = qlines(ctx)[-1]
    assert q["answered_by"] == "runner" and q["cited"] is None


def test_a_parked_gate_is_answered_by_the_runner(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.owner = ParkingOwner("gate")
    script["arm"] = [TR("Approve?")]
    script["po"] = [D("approval", "Approved.", approved=True)]
    drive.run_attempt(ctx, 1, "go")
    assert qlines(ctx)[-1]["answered_by"] == "runner"


# ---- Task 22 ruling 6: the N.a discovery stop ---------------------------------------------------------------------

@pytest.fixture
def disc(rig, monkeypatch):
    sent, script, state, ctx = rig
    ctx.arm = drive.config.load_arm("openspec")
    changed = {"paths": [], "baselines": []}

    def content_state(p):
        ctx.calls.append("baseline")
        b = {"files": {}, "tips": {}, "n": len(changed["baselines"])}
        changed["baselines"].append(b)
        return b

    def changed_since(p, baseline):
        changed.setdefault("seen", []).append(baseline)
        got = changed["paths"]
        return list(next(got) if hasattr(got, "__next__") else got)
    monkeypatch.setattr(drive.gitops, "content_state", content_state)
    monkeypatch.setattr(drive.gitops, "changed_since", changed_since)
    return sent, script, ctx, changed


def test_discovery_stops_at_the_first_approval_request_without_asking_the_owner(disc):
    sent, script, ctx, _ = disc
    script["arm"] = [TR("Spec drafted. Do you approve the proposal?")]
    script["po"] = [D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert r.outcome == "discovery-stop" and r.discovery["why"] == "approval" and ctx.owner.gates == []
    [q] = qlines(ctx)
    assert q["kind"] == "approval" and q["owner_action"] == "discovery-stop" and q["reply"] is None


def test_discovery_stops_at_the_first_turn_that_edits_code_outside_the_spec_and_docs_paths(disc):
    sent, script, ctx, changed = disc
    script["arm"] = [TR("Wrote the proposal."), TR("Started implementing.")]
    script["po"] = [D("continue")]
    changed["paths"] = iter([["openspec/changes/x/proposal.md", "docs/notes.md"],
                             ["openspec/changes/x/tasks.md", "src/troupe/cli.py"]])
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert r.outcome == "discovery-stop" and r.discovery == {"why": "code", "turn": 2, "paths": ["src/troupe/cli.py"]}
    assert len(sent) == 2 and len(qlines(ctx)) == 1                    # the PO never saw the code turn


def test_discovery_answers_questions_and_keeps_going_while_only_specs_change(disc):
    sent, script, ctx, changed = disc
    changed["paths"] = ["openspec/changes/x/proposal.md"]
    script["arm"] = [TR("Which theatre wins?"), TR("Ready: approve?")]
    script["po"] = [D("question", answers=[drive.po.Answer("Which theatre wins?", "The flag.", False, "General")]),
                    D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert msgs(sent) == ["go", "The flag."] and r.discovery["why"] == "approval"


def test_the_code_check_diffs_against_a_baseline_taken_once_at_the_attempts_start_after_recover(disc):  # I-1
    sent, script, ctx, changed = disc
    script["arm"] = [TR("a"), TR("b")]
    script["po"] = [D("continue"), D("approval", "Approved.", approved=True)]
    drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert ctx.calls[:3] == ["clean-green", "recover", "baseline"] and ctx.calls.count("baseline") == 1
    [b] = changed["baselines"]
    assert changed["seen"] == [b, b]


def test_without_the_stop_option_an_approval_goes_to_the_owner_and_code_is_never_checked(disc, monkeypatch):
    sent, script, ctx, changed = disc
    monkeypatch.setattr(drive.gitops, "content_state", lambda p: pytest.fail("a baseline outside discovery"))
    monkeypatch.setattr(drive.gitops, "changed_since", lambda p, b: pytest.fail("the code check ran outside discovery"))
    script["arm"] = [TR("approve?"), TR("done"), TR("archived")]
    script["po"] = [D("approval", "Approved.", approved=True), D("step_done"), D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert ctx.owner.gates == ["approve?"] and r.outcome == "done" and r.discovery is None


def test_discovery_at_step_5_lets_the_po_classify_the_turn_cr_b_would_preempt(disc):           # L-3
    sent, script, ctx, changed = disc
    ctx.arm = drive.config.load_arm("control"); ctx.later_messages = ["CR-B text"]
    script["arm"] = [TR("Working."), TR("Plan for CR-A ready. Approve?")]
    script["po"] = [D("continue"), D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "CR-A text", stop_at_first_gate_or_code=True)
    assert r.discovery["why"] == "approval" and "CR-B text" not in msgs(sent) and ctx.later_sent == 0


def test_discovery_at_step_5_still_preempts_with_cr_b_when_the_po_sees_no_gate(disc):
    sent, script, ctx, changed = disc
    ctx.arm = drive.config.load_arm("control"); ctx.later_messages = ["CR-B text"]
    script["arm"] = [TR("Working."), TR("Still working."), TR("Both planned. Approve?")]
    script["po"] = [D("continue"), D("continue"), D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "CR-A text", stop_at_first_gate_or_code=True)
    assert msgs(sent) == ["CR-A text", "Please continue.", "CR-B text"] and r.discovery["why"] == "approval"
    kinds = [(q["kind"], q.get("po_kind")) for q in qlines(ctx)]
    assert kinds == [("continue", None), ("preempted", "continue"), ("approval", None)]


@pytest.mark.parametrize("path, spec", [
    ("openspec/changes/x/proposal.md", True), ("docs/design.md", True), ("README.md", True),
    ("src/troupe/cli.py", False), ("tests/test_cli.py", False), ("pyproject.toml", False),
    (".venv/bin/python", True), ("src/troupe/__pycache__/cli.cpython-312.pyc", True),
])
def test_outside_spec_sorts_paths_by_the_arms_spec_paths_and_the_common_docs_paths(path, spec):
    arm, pins = drive.config.load_arm("openspec"), drive.config.load_pins()
    assert (drive.outside_spec([path], arm, pins) == []) is spec


# ---- Task 22 fix round 2 (I-1): an arm's git state can never make the code check raise ---------------------------

def test_a_baseline_that_cannot_be_taken_leaves_the_code_check_unavailable_and_the_attempt_running(disc, monkeypatch):
    sent, script, ctx, changed = disc
    def broken(p):
        raise drive.docker.ContainerError("git content state failed in container (128): fatal: bad object")
    monkeypatch.setattr(drive.gitops, "content_state", broken)
    monkeypatch.setattr(drive.gitops, "changed_since", lambda p, b: pytest.fail("checked without a baseline"))
    script["arm"] = [TR("working"), TR("approve?")]
    script["po"] = [D("continue"), D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert r.discovery["why"] == "approval"
    assert r.code_check["status"] == "unavailable" and "bad object" in r.code_check["reasons"][0]["reason"]
    assert r.code_check["reasons"][0]["turn"] == 0


def test_a_code_check_that_fails_on_one_turn_is_recorded_and_the_next_turn_is_checked_again(disc, monkeypatch):
    sent, script, ctx, changed = disc
    results = iter([drive.docker.ContainerError("git content state failed (1)"), ["src/troupe/cli.py"]])

    def flaky(p, b):
        x = next(results)
        if isinstance(x, Exception):
            raise x
        return x
    monkeypatch.setattr(drive.gitops, "changed_since", flaky)
    script["arm"] = [TR("a"), TR("b")]
    script["po"] = [D("continue")]
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert r.discovery == {"why": "code", "turn": 2, "paths": ["src/troupe/cli.py"]}
    assert r.code_check["status"] == "unavailable" and [x["turn"] for x in r.code_check["reasons"]] == [1]


def test_a_code_check_that_always_works_is_recorded_as_ok(disc):
    sent, script, ctx, changed = disc
    script["arm"] = [TR("approve?")]
    script["po"] = [D("approval", "Approved.", approved=True)]
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert r.code_check == {"status": "ok", "reasons": []}


def test_the_never_code_directories_are_one_named_constant_turned_into_exclude_pathspecs():
    from runner import gitops
    assert set(gitops.NEVER_CODE) == {".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
                                      "node_modules"}
    assert ":(exclude,glob)**/node_modules/**" in gitops.never_code_pathspecs()


# ---- final fix batch A3: N.a uses the arm's discovery tracker ---------------------------------------------------------

def test_an_na_attempt_installs_the_discovery_pat_and_points_gh_at_the_discovery_repo(rig, monkeypatch):
    import dataclasses
    from runner.paths import Paths
    sent, script, _, ctx = rig
    ctx = dataclasses.replace(ctx, pass_="pass1", arm=drive.config.load_arm("control"),
                              paths=Paths("pass1", "control"), run="a")
    envs, installed = [], []
    monkeypatch.setattr(drive.checklist, "install_disc_pat", lambda p, arm, pass_: installed.append((arm.name, pass_)))
    real = drive.session.run_turn
    monkeypatch.setattr(drive.session, "run_turn", lambda t, *a: envs.append(t.env) or real(t, *a))
    monkeypatch.setattr(drive.gitops, "content_state", lambda p: {})
    script["arm"] = [TR("done")]
    script["po"] = [D("step_done")]
    drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert installed == [("control", "pass1")]
    assert envs[0]["GH_REPO"] == "troupe-run/bakeoff-specs-control-pass1-disc"


def test_an_nb_attempt_keeps_the_normal_repo_and_pat(rig, monkeypatch):
    import dataclasses
    from runner.paths import Paths
    sent, script, _, ctx = rig
    ctx = dataclasses.replace(ctx, pass_="pass1", arm=drive.config.load_arm("control"), paths=Paths("pass1", "control"))
    envs = []
    monkeypatch.setattr(drive.checklist, "install_disc_pat", lambda *a: pytest.fail("N.b got the discovery PAT"))
    real = drive.session.run_turn
    monkeypatch.setattr(drive.session, "run_turn", lambda t, *a: envs.append(t.env) or real(t, *a))
    script["arm"] = [TR("done")]
    script["po"] = [D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert envs[0]["GH_REPO"] == "troupe-run/bakeoff-specs-control-pass1"


# ---- final fix batch A5: an arm session killed for memory is the owner's resource rule, not infra-no_result ----------

def OOM(sid="s1"):
    r = TR("", outcome="no_result", sid=sid)
    r.oom_killed, r.exit_code = True, 137
    return r


def test_an_oom_killed_turn_is_rerun_once_in_the_same_session(rig):
    sent, script, _, ctx = rig
    script["arm"] = [OOM(), TR("done"), TR("archived")]
    script["po"] = [D("step_done"), D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "done" and len(r.resource_events) == 1
    assert msgs(sent)[:2] == ["go", handoff.MESSAGES["resume_after_error"]] and sent[1][1] == "s1"
    assert not [i for i in r.interventions if i.startswith("transient-retry")]


def test_an_oom_killed_turn_twice_ends_the_attempt_as_arm_resource_never_a_harness_fault(rig):
    sent, script, _, ctx = rig
    script["arm"] = [OOM(), OOM()]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "arm-resource" and len(r.resource_events) == 2 and len(sent) == 2


def test_an_oom_on_a_transient_retry_resend_is_arm_resource_too(rig):          # follow-up 1
    sent, script, _, ctx = rig
    script["arm"] = [TR("", outcome="no_result"), OOM(), OOM()]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "arm-resource" and len(r.resource_events) == 2 and len(sent) == 3


# ---- owner, 2026-10-01: in N.b an escalation gets the fixed fallback reply, never the owner ---------------------

FALLBACK = handoff.MESSAGES["escalation_fallback"]


def test_the_fallback_reply_is_the_owners_wording_from_scenario_toml():
    assert FALLBACK == ("The brief doesn't cover this. Make the safest assumption (the one least likely to lose or "
                        "corrupt a user's data or to contradict the contract), record it as a decision with your "
                        "reason, and carry on.")


def test_an_nb_escalation_gets_the_fallback_reply_not_the_owner_and_leaves_the_brief_alone(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.run = "b"
    before = ctx.brief_path.read_text()
    script["arm"] = [TR("b?"), TR("done")]
    script["po"] = [D("question", answers=[Answer("b?", None, True, None)]), D("step_done")]
    r = drive.run_attempt(ctx, 1, "go")
    assert r.outcome == "done" and msgs(sent)[1] == FALLBACK
    assert ctx.owner.escalations == []                                          # the owner was never asked
    assert ctx.brief_path.read_text() == before                                 # not appended
    assert not (ctx.out / "po" / "parked-escalations.jsonl").exists()
    q = qlines(ctx)[0]
    assert q["escalated"] == ["b?"] and q["fallback"] == ["b?"] and q["answered_by"] == "fallback"
    assert q["reply"] == FALLBACK and q["owner_seconds"] == 0.0


def test_a_mixed_nb_decision_combines_the_po_answer_with_the_fallback_for_the_escalated_one(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.run = "b"
    before = ctx.brief_path.read_text()
    script["arm"] = [TR("a? b?"), TR("done")]
    script["po"] = [D("question", answers=[Answer("a?", "Yes, per General.", False, "General"),
                                            Answer("b?", None, True, None)]), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert msgs(sent)[1] == f"On “a?”: Yes, per General.\n\nOn “b?”: {FALLBACK}"
    assert ctx.owner.escalations == [] and ctx.brief_path.read_text() == before
    q = qlines(ctx)[0]
    assert q["escalated"] == ["b?"] and q["fallback"] == ["b?"] and q["answered_by"] == "po+fallback"
    assert q["cited"] == "General"


def test_an_na_escalation_still_asks_the_owner_and_records_no_fallback(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.run = "a"
    script["arm"] = [TR("b?"), TR("done")]
    script["po"] = [D("question", answers=[Answer("b?", None, True, None)]), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert ctx.owner.escalations == ["b?"] and msgs(sent)[1] == ctx.owner.escalation_answer
    assert ctx.owner.escalation_answer in ctx.brief_path.read_text().split("## Escalated answers")[1]
    q = qlines(ctx)[0]
    assert q["fallback"] == [] and q["answered_by"] == "owner"


def test_an_nb_approval_gate_still_goes_to_the_owner(rig):
    sent, script, _, ctx = rig
    ctx.arm = drive.config.load_arm("control"); ctx.run = "b"
    script["arm"] = [TR("Plan ready. Approve?"), TR("done")]
    script["po"] = [D("approval", "Approved.", approved=True), D("step_done")]
    drive.run_attempt(ctx, 1, "go")
    assert ctx.owner.gates == ["Plan ready. Approve?"] and msgs(sent)[1] == "Approved."
    assert json.loads((ctx.out / "owner-gates.jsonl").read_text().splitlines()[0])["owner_action"] == "accept"
