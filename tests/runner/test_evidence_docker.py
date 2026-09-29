"""`evidence.finalise` with real containerised git on a dry repo (review S-1). Run with `--run-docker`."""
import json
import pytest
from runner import evidence, gitops, repo
from runner.transcripts import PinReport
from runner.drive import AttemptResult
from tests.runner.conftest import FakeHiddenSummary, make_test_ctx

pytestmark = pytest.mark.docker


def test_git_json_names_main_and_the_step_log(tmp_state, tmp_path):
    ctx = make_test_ctx(tmp_path, arm="dryrun", step=1)
    before = repo.init(ctx.paths, "dryrun", "dry9")
    (ctx.paths.repo / "a.py").write_text("1")
    gitops.commit_all(ctx.paths, gitops.IDENTITY, "step 1")
    s = FakeHiddenSummary(1, {}, [], [], [])
    s.write(ctx.out)
    evidence.finalise(ctx, attempts=[AttemptResult("done", "s")], extra_turns={}, hidden=s, quality={},
                      pin=PinReport(True, 1, 0, 0, 0, [], False, []), sha_before=before, started=1.7e9, ended=1.7e9 + 1,
                      fault_entries=[], shas={"po_brief_at_handoff": "", "contract": "", "step_brief": ""},
                      tests_seconds=0, outcome="done")
    g = json.loads((ctx.out / "git.json").read_text())
    assert g["sha_after"] == gitops.main_sha(ctx.paths) and [e["subject"] for e in g["log"]] == ["step 1"]
