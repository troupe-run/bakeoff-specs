"""Task 22 (ruling 6): `gitops.changed_paths`, the N.a discovery stop's code check, with real git in a real
container. Run with `--run-docker` (through the docker lock)."""
import subprocess
import pytest
from runner import gitops, repo
from runner.paths import Paths

pytestmark = pytest.mark.docker


@pytest.fixture
def P(tmp_state):
    p = Paths("dry9", "dryrun")
    repo.init(p, "dryrun", "dry9")
    yield p
    left = subprocess.run(["docker", "ps", "-aq", "--filter", "label=bakeoff.run=dry9/dryrun"],
                          capture_output=True, text=True).stdout.split()
    assert left == [], "a git container outlived its operation"


def test_changed_paths_sees_worktree_untracked_and_other_branch_changes_but_not_ignored_files(P):
    base = gitops.main_sha(P)
    (P.repo / "tracked.py").write_text("x = 1\n")
    (P.repo / ".gitignore").write_text("ignored/\n")
    gitops.commit_all(P, gitops.IDENTITY, "tracked")
    base2 = gitops.main_sha(P)
    (P.repo / "tracked.py").write_text("x = 2\n")                          # unstaged tracked change
    (P.repo / "new dir").mkdir(); (P.repo / "new dir" / "u.py").write_text("")   # untracked, with a space
    (P.repo / "ignored").mkdir(); (P.repo / "ignored" / "i.py").write_text("")
    gitops.git(P, "checkout", "-q", "-b", "feature", write=True)
    (P.repo / "feat.py").write_text("")
    gitops.git(P, "add", "feat.py", write=True)
    gitops.git(P, "commit", "-q", "-m", "feat", write=True, env={"GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@b",
                                                                 "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@b"})
    gitops.git(P, "checkout", "-q", "main", write=True)
    got = gitops.changed_paths(P, base2)
    assert got == ["feat.py", "new dir/u.py", "tracked.py"]
    assert set(gitops.changed_paths(P, base)) >= {".gitignore", "tracked.py", "feat.py"}


def test_changed_paths_is_empty_on_an_untouched_repo(P):
    assert gitops.changed_paths(P, gitops.main_sha(P)) == []
