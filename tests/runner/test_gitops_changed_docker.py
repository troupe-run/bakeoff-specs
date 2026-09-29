"""Task 22 (ruling 6, fix round 1 I-1): the N.a discovery stop's code check with real git in a real container. The
baseline is the repo's CONTENT at the attempt's start (working tree, untracked files, branch tips), so whatever an
earlier step left behind never counts as this attempt's edit. Run with `--run-docker` (through the docker lock)."""
import contextlib, subprocess
import pytest
from runner import drive, gitops, repo
from runner.paths import Paths
from runner.po import Decision, PoResult
from runner.session import TurnResult
from runner.transcripts import PinReport
from tests.runner.conftest import make_test_ctx

pytestmark = pytest.mark.docker

WHO = {"GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@b", "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@b"}


@pytest.fixture
def P(tmp_state):
    p = Paths("dry9", "dryrun")
    repo.init(p, "dryrun", "dry9")
    yield p
    left = subprocess.run(["docker", "ps", "-aq", "--filter", "label=bakeoff.run=dry9/dryrun"],
                          capture_output=True, text=True).stdout.split()
    assert left == [], "a git container outlived its operation"


def _leftovers(P) -> str:
    """What a previous step can leave: an abandoned branch with commits, HEAD on a feature branch, an uncommitted
    tracked change, untracked code and an ignored file. Returns the step's `sha_before` (main)."""
    (P.repo / "tracked.py").write_text("x = 1\n")
    (P.repo / ".gitignore").write_text("ignored/\n")
    gitops.commit_all(P, gitops.IDENTITY, "step 1")
    sha_before = gitops.main_sha(P)
    gitops.git(P, "checkout", "-q", "-b", "abandoned", write=True)
    (P.repo / "old.py").write_text("")
    gitops.git(P, "add", "old.py", write=True)
    gitops.git(P, "commit", "-q", "-m", "abandoned", write=True, env=WHO)
    gitops.git(P, "checkout", "-q", "-b", "feature", "main", write=True)     # HEAD left on a feature branch
    (P.repo / "tracked.py").write_text("x = 2\n")                              # uncommitted tracked change
    (P.repo / "new dir").mkdir(); (P.repo / "new dir" / "u.py").write_text("")  # untracked code, with a space
    (P.repo / "ignored").mkdir(); (P.repo / "ignored" / "i.py").write_text("")
    return sha_before


def test_leftover_state_from_a_previous_step_is_not_a_change(P):
    _leftovers(P)
    base = gitops.content_state(P)
    assert gitops.changed_since(P, base) == []


def test_changed_since_reports_only_paths_whose_content_changed_after_the_baseline(P):
    _leftovers(P)
    base = gitops.content_state(P)
    (P.repo / "new dir" / "u.py").write_text("y = 1\n")           # leftover untracked file, now edited
    (P.repo / "tracked.py").write_text("x = 2\n")                  # rewritten with the same content: no change
    (P.repo / "docs").mkdir(); (P.repo / "docs" / "d.md").write_text("d\n")
    (P.repo / "ignored" / "j.py").write_text("")                   # ignored: never reported
    gitops.git(P, "checkout", "-q", "-b", "other", "main", write=True)   # the uncommitted tracked.py change travels along
    (P.repo / "b.py").write_text("")
    gitops.git(P, "add", "b.py", write=True)
    gitops.git(P, "commit", "-q", "-m", "b", write=True, env=WHO)
    gitops.git(P, "checkout", "-q", "feature", write=True)
    (P.repo / "tracked.py").write_text("x = 2\n")                  # the working tree as at the baseline again
    assert gitops.changed_since(P, base) == ["b.py", "docs/d.md", "new dir/u.py"]


def test_a_discovery_attempt_on_leftover_state_does_not_stop_on_turn_1_and_stops_at_the_arms_code_edit(P, tmp_path,
                                                                                                     monkeypatch):
    sha_before = _leftovers(P)
    ctx = make_test_ctx(tmp_path, arm="dryrun")
    ctx.sha_before = sha_before
    edits = [lambda: None, lambda: (P.repo / "src.py").write_text("print(1)\n")]
    sent = []

    def fake_turn(t, cred, out, timeout):
        sent.append(t.message)
        edits[len(sent) - 1]()
        return TurnResult("s1", "ok", f"turn {len(sent)}", {}, {}, 0.0, {}, {}, 1.0, [], None, None, [], [])
    monkeypatch.setattr(drive.session, "run_turn", fake_turn)
    monkeypatch.setattr(drive.egress, "Stage", lambda *a, **k: contextlib.nullcontext(type("S", (), {"net": "n"})()))
    monkeypatch.setattr(drive.checklist, "require_clean_green", lambda p: None)
    monkeypatch.setattr(drive.po, "decide", lambda *a, **k: PoResult(
        Decision("continue", None, [], None, None, "", False), [], PinReport(True, 1, 1, 0, 0, ["2.1.281"], False, [])))
    r = drive.run_attempt(ctx, 1, "go", stop_at_first_gate_or_code=True)
    assert r.outcome == "discovery-stop" and r.discovery == {"why": "code", "turn": 2, "paths": ["src.py"]}
