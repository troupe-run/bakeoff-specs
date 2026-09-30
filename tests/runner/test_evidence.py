import json
import pytest
from runner import checklist, evidence, gitops, owner as owner_mod
from runner.drive import AttemptResult
from runner.session import TurnResult
from tests.runner.conftest import finalise_inputs


def TR(usd, model="claude-opus-5-5", denials=()):
    return TurnResult("s", "ok", "", {}, {}, usd, {"input_tokens": 10, "output_tokens": 2},
                      {model: {"inputTokens": 10}}, 1.0, [], None, None, list(denials), [])


def test_cost_states_unit_and_source_and_keeps_arm_po_and_harness_apart():
    c = evidence.cost({"arm": [TR(1.25), TR(0.75)], "po": [TR(0.1)], "harness": [TR(0.2)]})
    assert c["unit"] == "USD" and "client-side estimate" in c["source"]
    assert c["arm"]["usd"] == 2.0 and c["arm"]["turns"] == 2 and c["po"]["usd"] == 0.1 and c["harness"]["usd"] == 0.2
    assert c["arm"]["usage"]["input_tokens"] == 20


def test_research_attempts_count_denied_web_tools_and_refused_hosts():         # review F-8
    log = 'CONNECT docs.python.org:443 HTTP/1.1\nProxying refused on filtered domain "docs.python.org"\n'
    r = evidence.research_attempts([TR(0, denials=[{"tool_name": "WebSearch"}, {"tool_name": "Bash"}])], log)
    assert r == {"denied_web_tools": 1, "refused_hosts": ["docs.python.org"]}


def test_possible_missed_approvals_are_listed():                                # review C-8
    qa = [{"kind": "continue", "arm_message": "Shall I proceed with this plan?", "n": 3},
          {"kind": "continue", "arm_message": "Working on tests.", "n": 4},
          {"kind": "approval", "arm_message": "Please approve.", "n": 5}]
    assert [q["n"] for q in evidence.possible_missed_approvals(qa)] == [3]


# ---- fix round 1, MEDIUM: owner-shell interventions must be keyed by a harness-recorded SHA, never by ------
# ---- pattern-matching the arm's own (forgeable) git log ----------------------------------------------------
def test_owner_shell_commit_entries_matches_only_recorded_shas():
    """The arm commits under the same `gitops.IDENTITY` as `checklist.recheck` and can write any subject
    line — including a forged ` (owner shell adjustments)` suffix (`bbb222` here). Only a sha that the
    harness itself recorded (`aaa111`) may count."""
    log = [{"sha": "aaa111", "author": "Developer", "subject": "Set up Control 1.0 (owner shell adjustments)"},
           {"sha": "bbb222", "author": "Developer", "subject": "sneaky change (owner shell adjustments)"},
           {"sha": "ccc333", "author": "Developer", "subject": "step 3 commit"}]
    assert [c["sha"] for c in evidence.owner_shell_commit_entries(log, {"aaa111"})] == ["aaa111"]


def test_owner_shell_shas_reads_the_harness_side_record_under_setup_results(tmp_path, monkeypatch):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    ctx.paths.setup_results.mkdir(parents=True, exist_ok=True)
    (ctx.paths.setup_results / checklist.OWNER_SHELL_COMMITS_FILE).write_text(
        json.dumps([{"sha": "deadbeef", "at": "2026-09-29T00:00:00+00:00"}]))
    assert evidence.owner_shell_shas(ctx.paths) == {"deadbeef"}


def test_owner_shell_shas_is_empty_when_nothing_was_ever_recorded(tmp_path, monkeypatch):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    assert evidence.owner_shell_shas(ctx.paths) == set()


def test_finalise_records_a_harness_recorded_owner_shell_commit_as_an_intervention(tmp_path, monkeypatch):
    """Task 20 ledger ruling 2 (fix round 1): an owner's `runner checklist` commit must show up as an
    evidence intervention, keyed by the harness-recorded sha."""
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(gitops, "log", lambda p, a, b: [
        {"sha": "aaa111", "author": "Developer", "subject": "Set up Control 1.0 (owner shell adjustments)"},
        {"sha": "bbb222", "author": "Developer", "subject": "Set up Control 1.0"}])
    ctx.paths.setup_results.mkdir(parents=True, exist_ok=True)
    (ctx.paths.setup_results / checklist.OWNER_SHELL_COMMITS_FILE).write_text(
        json.dumps([{"sha": "aaa111", "at": "2026-09-29T00:00:00+00:00"}]))
    summary = evidence.finalise(ctx, **kw)
    run = json.loads((summary.parent / "run.json").read_text())
    assert "owner-shell-commit:aaa111" in run["interventions"]
    assert not any("bbb222" in i for i in run["interventions"])
    assert "owner-shell-commit:aaa111" in summary.read_text()


def test_finalise_ignores_an_arm_commit_that_forges_the_owner_shell_suffix(tmp_path, monkeypatch):
    """fix round 1 MEDIUM: a commit carrying the ` (owner shell adjustments)` suffix but NOT in the
    harness-side record (the arm could have written that subject itself) must never be counted."""
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(gitops, "log", lambda p, a, b: [
        {"sha": "forged0", "author": "Developer", "subject": "sneaky change (owner shell adjustments)"}])
    # no owner-shell-commits.json at all: nothing was ever recorded by the harness
    summary = evidence.finalise(ctx, **kw)
    run = json.loads((summary.parent / "run.json").read_text())
    assert not any("forged0" in i for i in run["interventions"])
    assert "forged0" not in summary.read_text()


# ---- fix round 1, HIGH: a parked outcome must be shown ------------------------------------------------------
@pytest.mark.parametrize("reason", ["unattended", "eof", "timeout", "owner-choice", "empty-answer"])
def test_finalise_shows_the_parked_attempts_reason_and_context(tmp_path, monkeypatch, reason):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    pk = owner_mod.Park("gate", "step 3 approval", reason, 1.7e9, 4.0)
    kw = {**kw, "attempts": [AttemptResult("parked", "s1", park=pk)], "outcome": "parked"}
    summary = evidence.finalise(ctx, **kw)
    run = json.loads((summary.parent / "run.json").read_text())
    assert run["park"] == {"attempt": 1, "prompt": "gate", "context": "step 3 approval", "reason": reason,
                           "at": 1.7e9, "seconds": 4.0}
    text = summary.read_text()
    assert "PARKED" in text and reason in text and "step 3 approval" in text


def test_finalise_records_the_park_from_the_last_attempt_only(tmp_path, monkeypatch):
    """Several attempts ran before the step parked; only the last one carries a `Park` (Task 15 ruling 1: a
    park ends the run at once, so no attempt after it exists) — the others must not be mistaken for it."""
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    pk = owner_mod.Park("escalation", "clarify expected output", "timeout", 1.7e9, 12.0)
    kw = {**kw, "attempts": [AttemptResult("stalled", "s1"), AttemptResult("timeout", "s2", breach="turn_seconds"),
                             AttemptResult("parked", "s3", park=pk)], "outcome": "parked"}
    summary = evidence.finalise(ctx, **kw)
    run = json.loads((summary.parent / "run.json").read_text())
    assert run["park"]["attempt"] == 3 and run["park"]["reason"] == "timeout"
    assert "clarify expected output" in summary.read_text()


def test_finalise_park_is_none_when_nothing_parked(tmp_path, monkeypatch):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    summary = evidence.finalise(ctx, **kw)
    run = json.loads((summary.parent / "run.json").read_text())
    assert run["park"] is None
    assert "PARKED" not in summary.read_text()


# ---- fix round 1, minor: ruff_arm_findings shown next to ruff_findings -------------------------------------
def test_finalise_shows_ruff_arm_findings_next_to_ruff_findings(tmp_path, monkeypatch):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    kw = {**kw, "quality": {"mutation": {}, "mypy_errors": 0, "ruff_findings": 3, "ruff_arm_findings": 1}}
    summary = evidence.finalise(ctx, **kw)
    text = summary.read_text()
    assert "ruff 3" in text and "1" in text.split("ruff 3", 1)[1].split("\n", 1)[0]


def test_finalise_writes_run_cost_git_pin_and_summary(tmp_path, monkeypatch):     # strengthened (review Q-11)
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    summary = evidence.finalise(ctx, **kw)
    d = summary.parent
    for rel in ["run.json", "cost.json", "git.json", "model-pin.json", "summary.md"]:   # written by finalise itself
        assert (d / rel).exists(), rel
    run = json.loads((d / "run.json").read_text())
    for k in ["started_at", "ended_at", "wall_seconds", "arm_session_seconds", "po_seconds", "owner_wait_seconds",
              "tests_seconds", "claude_version", "model", "plugin_route", "images", "po_brief_sha256_at_handoff",
              "po_brief_sha256_at_end", "contract_sha256", "step_brief_sha256", "research_attempts", "model_overrides",
              "outcome", "attempts", "interventions", "park"]:
        assert k in run, k
    git = json.loads((d / "git.json").read_text())
    assert git["sha_after"] == "main-sha" and git["head_in_main"] is True
    assert "Possible missed approvals" in summary.read_text()


# ---- fix round 2, item 8: the summary line names the reason when there is no score/count, never "None" ----

def test_mypy_summary_text_names_the_reason_instead_of_none():
    assert evidence.mypy_summary_text({"mypy_errors": 3}) == "3 errors"
    assert evidence.mypy_summary_text({"mypy_errors": 0}) == "0 errors"
    assert evidence.mypy_summary_text({"mypy_errors": None, "mypy_crashed": True}) == "crashed"
    assert evidence.mypy_summary_text({"mypy_errors": None, "mypy_timed_out": True}) == "timed out"


def test_mutation_summary_text_names_the_reason_instead_of_none():
    assert evidence.mutation_summary_text({"score": 0.5, "sampling": "seeded-sha256"}) == \
        "0.5 (seeded-sha256)"
    assert evidence.mutation_summary_text({"score": 0.5, "sampling": "all", "partial": True}) == \
        "0.5 (all, partial)"
    assert evidence.mutation_summary_text({"score": None, "crashed": True}) == "crashed"
    assert evidence.mutation_summary_text({"score": None, "baseline_failed": True}) == "baseline failed"
    assert evidence.mutation_summary_text({"score": None, "sampling": "no tests"}) == "no tests"
    assert evidence.mutation_summary_text({"score": None, "timed_out": True}) == "timed out"


def test_finalise_summary_names_the_reason_for_a_crashed_mutation_run(tmp_path, monkeypatch):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    kw = {**kw, "quality": {"mutation": {"score": None, "crashed": True, "sampling": "n/a"},
                            "mypy_errors": None, "mypy_crashed": True,
                            "ruff_findings": 3, "ruff_arm_findings": None}}
    summary = evidence.finalise(ctx, **kw)
    text = summary.read_text()
    assert "mypy crashed" in text and "None errors" not in text
    assert "mutation score crashed" in text and "mutation score None" not in text


# ---- fix round 3, item 7: ruff_summary_text/ruff_arm_summary_text; placeholder reasons render with their
# ---- own text instead of collapsing to a generic "crashed" -------------------------------------------------

def test_ruff_summary_text_names_the_reason_instead_of_none():
    assert evidence.ruff_summary_text({"ruff_findings": 3}) == "3"
    assert evidence.ruff_summary_text({"ruff_findings": 0}) == "0"
    assert evidence.ruff_summary_text({"ruff_findings": None, "ruff_crashed": True}) == "crashed"
    assert evidence.ruff_summary_text({"ruff_findings": None, "ruff_timed_out": True}) == "timed out"


def test_ruff_arm_summary_text_distinguishes_no_config_from_crashed():
    assert evidence.ruff_arm_summary_text({"ruff_arm_findings": 1}) == "1"
    # the arm simply has no ruff config: run_all leaves ruff_arm_crashed as None (never attempted)
    assert evidence.ruff_arm_summary_text({"ruff_arm_findings": None, "ruff_arm_crashed": None}) == "no config"
    # an actual failure trying to find out or run it: run_all sets ruff_arm_crashed True
    assert evidence.ruff_arm_summary_text({"ruff_arm_findings": None, "ruff_arm_crashed": True}) == "crashed"
    assert evidence.ruff_arm_summary_text({"ruff_arm_findings": None, "ruff_arm_crashed": None,
                                           "ruff_arm_timed_out": True}) == "timed out"


def test_mutation_summary_text_renders_placeholder_reasons_verbatim():
    assert evidence.mutation_summary_text({"score": None, "crashed": True, "sampling": "install failed"}) == \
        "install failed"
    assert evidence.mutation_summary_text(
        {"score": None, "crashed": True, "sampling": "error: RuntimeError: simulated mutation crash"}) == \
        "error: RuntimeError: simulated mutation crash"


def test_finalise_summary_shows_ruff_reasons_not_none(tmp_path, monkeypatch):
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    kw = {**kw, "quality": {"mutation": {}, "mypy_errors": 0,
                            "ruff_findings": None, "ruff_crashed": True,
                            "ruff_arm_findings": None, "ruff_arm_crashed": None}}
    summary = evidence.finalise(ctx, **kw)
    text = summary.read_text()
    assert "ruff crashed" in text and "ruff None" not in text
    assert "arm no config" in text and "arm None" not in text


def test_finalise_summary_says_quality_was_not_run_and_why(tmp_path, monkeypatch):      # final fix batch A1
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    kw["quality"] = {"skipped": "arm-no-main"}
    evidence.finalise(ctx, **kw)
    md = (ctx.out / "summary.md").read_text()
    assert "**Quality:** not run (arm-no-main)" in md and "crashed" not in md


def test_finalise_lists_the_arm_violations_of_the_step(tmp_path, monkeypatch):             # final fix batch A5
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    (ctx.out / "arm-violations.jsonl").write_text(json.dumps(
        {"run": "b", "attempt": 1, "kind": "setup-drift", "check": "common.origin", "detail": "x"}) + "\n")
    evidence.finalise(ctx, **kw)
    run = json.loads((ctx.out / "run.json").read_text())
    assert run["arm_violations"][0]["check"] == "common.origin"
    assert "## Arm violations" in (ctx.out / "summary.md").read_text() and "common.origin" in (ctx.out / "summary.md").read_text()
