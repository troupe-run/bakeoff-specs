"""Task 22 (ruling 6, fix rounds 1-2, I-1): the N.a discovery stop's code check with real git in a real container.
The baseline is every (path, blob) the repo holds at the attempt's start (working tree, untracked files, every branch
tip's tree); a path is the arm's code only when its content is a blob that was not at that path then. Whatever an
earlier step left behind never counts, and no git state the arm creates can make the check raise. Run with
`--run-docker` (through the docker lock)."""
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


def test_changed_since_reports_only_paths_whose_content_is_a_new_blob(P):
    _leftovers(P)
    base = gitops.content_state(P)
    (P.repo / "new dir" / "u.py").write_text("y = 1\n")           # leftover untracked file, now edited
    (P.repo / "tracked.py").write_text("x = 2\n")                  # rewritten with the same content: no change
    (P.repo / "docs").mkdir(); (P.repo / "docs" / "d.md").write_text("d\n")
    (P.repo / "ignored" / "j.py").write_text("")                   # ignored: never reported
    gitops.git(P, "checkout", "-q", "-b", "other", "main", write=True)   # the uncommitted tracked.py change travels along
    (P.repo / "b.py").write_text("b = 1\n")
    gitops.git(P, "add", "b.py", write=True)
    gitops.git(P, "commit", "-q", "-m", "b", write=True, env=WHO)
    gitops.git(P, "checkout", "-q", "feature", write=True)
    assert gitops.changed_since(P, base) == ["b.py", "docs/d.md", "new dir/u.py"]


def test_committing_leftover_code_is_not_a_change(P):                                           # fix round 2
    _leftovers(P)
    base = gitops.content_state(P)
    gitops.git(P, "add", "-A", write=True)
    gitops.git(P, "commit", "-q", "-m", "the previous step's work", write=True, env=WHO)
    assert gitops.changed_since(P, base) == []


def test_checking_out_main_from_the_leftover_feature_branch_is_not_a_change(P):
    _leftovers(P)
    (P.repo / "tracked.py").write_text("x = 1\n")                  # a clean tree, so checkout is plain
    gitops.git(P, "checkout", "-q", "abandoned", write=True)       # HEAD left on a branch with its own file
    base = gitops.content_state(P)
    gitops.git(P, "checkout", "-q", "main", write=True)
    assert gitops.changed_since(P, base) == []


def test_a_path_touched_then_reverted_is_not_a_change(P):
    _leftovers(P)
    base = gitops.content_state(P)
    (P.repo / "tracked.py").write_text("x = 99\n")
    (P.repo / "tracked.py").write_text("x = 2\n")
    assert gitops.changed_since(P, base) == []


def test_a_genuinely_new_code_edit_is_a_change(P):
    _leftovers(P)
    base = gitops.content_state(P)
    (P.repo / "tracked.py").write_text("x = 3\n")
    assert gitops.changed_since(P, base) == ["tracked.py"]


def test_a_commit_on_a_detached_head_is_seen(P):
    _leftovers(P)
    (P.repo / "tracked.py").write_text("x = 1\n")
    base = gitops.content_state(P)
    gitops.git(P, "checkout", "-q", "--detach", "main", write=True)
    (P.repo / "d.py").write_text("d = 1\n")
    gitops.git(P, "add", "d.py", write=True)
    gitops.git(P, "commit", "-q", "-m", "detached", write=True, env=WHO)
    (P.repo / "d.py").unlink()                                      # not in the working tree, only in the commit
    gitops.git(P, "rm", "-q", "--cached", "d.py", write=True)
    assert gitops.changed_since(P, base) == ["d.py"]


def test_virtualenvs_and_tool_caches_are_never_hashed_or_reported(P):
    _leftovers(P)
    base = gitops.content_state(P)
    for d in gitops.NEVER_CODE:
        (P.repo / "pkg" / d / "x").mkdir(parents=True, exist_ok=True)
        (P.repo / "pkg" / d / "x" / "f.py").write_text("f = 1\n")
        (P.repo / d).mkdir(exist_ok=True); (P.repo / d / "g.py").write_text("g = 1\n")
    assert gitops.changed_since(P, base) == []
    assert not any(any(d in k for d in gitops.NEVER_CODE) for k in base["pairs"])


def test_a_nested_repo_without_a_commit_never_makes_the_check_raise_and_is_reported(P):        # fix round 2
    _leftovers(P)
    (P.repo / "empty-at-start").mkdir(); gitops.git(P, "-C", "empty-at-start", "init", "-q", write=True)
    base = gitops.content_state(P)                                  # a nested repo with no commit: no raise
    (P.repo / "nested").mkdir(); gitops.git(P, "-C", "nested", "init", "-q", write=True)
    (P.repo / "nested" / "code.py").write_text("c = 1\n")
    assert gitops.changed_since(P, base) == ["nested/"]


def test_a_baseline_tip_deleted_and_pruned_never_makes_the_check_raise(P):                     # fix round 2
    _leftovers(P)
    (P.repo / "tracked.py").write_text("x = 1\n")
    base = gitops.content_state(P)
    gitops.git(P, "branch", "-q", "-D", "abandoned", write=True)
    gitops.git(P, "reflog", "expire", "--expire=now", "--all", write=True)
    gitops.git(P, "gc", "-q", "--prune=now", write=True)
    assert gitops.git(P, "cat-file", "-e", base["tips"]["refs/heads/abandoned"], check=False).returncode != 0
    (P.repo / "n.py").write_text("n = 1\n")
    assert gitops.changed_since(P, base) == ["n.py"]


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


# ---- fix round 3 ---------------------------------------------------------------------------------------------------

def test_detached_commits_left_by_an_earlier_step_are_not_a_change(P):
    _leftovers(P)
    (P.repo / "tracked.py").write_text("x = 1\n")
    gitops.git(P, "checkout", "-q", "--detach", "main", write=True)
    (P.repo / "left.py").write_text("left = 1\n")
    gitops.git(P, "add", "left.py", write=True)
    gitops.git(P, "commit", "-q", "-m", "left detached", write=True, env=WHO)
    base = gitops.content_state(P)                                  # the arm then does nothing
    assert "HEAD" in base["tips"] and gitops.changed_since(P, base) == []


def test_a_file_named_with_quotes_is_hashed_as_itself(P):
    _leftovers(P)
    (P.repo / '"a.py"').write_text("a = 1\n")
    base = gitops.content_state(P)
    assert gitops.changed_since(P, base) == []
    (P.repo / '"a.py"').write_text("a = 2\n")
    assert gitops.changed_since(P, base) == ['"a.py"']


def test_a_control_character_in_a_name_is_reported_not_a_broken_check(P):
    _leftovers(P)
    base = gitops.content_state(P)
    (P.repo / "odd\x01name.py").write_text("o = 1\n")
    assert gitops.changed_since(P, base) == ["odd\x01name.py"]


def test_an_orphan_checkout_does_not_blind_the_check(P):
    _leftovers(P)
    base = gitops.content_state(P)
    gitops.git(P, "checkout", "-q", "--orphan", "fresh", write=True)
    (P.repo / "orphan.py").write_text("o = 1\n")
    assert gitops.changed_since(P, base) == ["orphan.py"]
