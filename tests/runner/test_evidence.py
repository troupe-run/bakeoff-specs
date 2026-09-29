import json
from runner import evidence, gitops
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


def test_owner_shell_commits_finds_only_the_recheck_marker():
    """checklist.recheck (`runner checklist`) commits owner `runner shell` edits under the same neutral
    gitops.IDENTITY as every other setup commit — the ` (owner shell adjustments)` message suffix it always
    appends is the only marker (Task 20 ledger ruling 2)."""
    log = [{"sha": "aaa111", "author": "Developer", "subject": "Set up Control 1.0 (owner shell adjustments)"},
           {"sha": "bbb222", "author": "Developer", "subject": "Set up Control 1.0"},
           {"sha": "ccc333", "author": "Developer", "subject": "step 3 commit"}]
    assert [c["sha"] for c in evidence.owner_shell_commits(log)] == ["aaa111"]


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
              "outcome", "attempts", "interventions"]:
        assert k in run, k
    git = json.loads((d / "git.json").read_text())
    assert git["sha_after"] == "main-sha" and git["head_in_main"] is True
    assert "Possible missed approvals" in summary.read_text()


def test_finalise_records_owner_shell_commits_as_interventions(tmp_path, monkeypatch):
    """Task 20 ledger ruling 2: an owner's `runner checklist` (shell) commit must show up as an evidence
    intervention, not disappear into the plain git log."""
    ctx, kw = finalise_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(gitops, "log", lambda p, a, b: [
        {"sha": "aaa111", "author": "Developer", "subject": "Set up Control 1.0 (owner shell adjustments)"},
        {"sha": "bbb222", "author": "Developer", "subject": "Set up Control 1.0"}])
    summary = evidence.finalise(ctx, **kw)
    run = json.loads((summary.parent / "run.json").read_text())
    assert "owner-shell-commit:aaa111" in run["interventions"]
    assert not any("bbb222" in i for i in run["interventions"])
    assert "owner-shell-commit:aaa111" in summary.read_text()
