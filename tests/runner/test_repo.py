"""repo.snapshot's bounded retry of tar's "file changed as we read it" (fix round 1, 2026-10-02), offline:
`docker.run` is faked, so no container runs."""
import subprocess
import pytest
from runner import docker, repo
from runner.paths import Paths


@pytest.fixture
def P(tmp_state, monkeypatch):
    p = Paths("dry9", "dryrun")
    for d in (p.home, p.work):
        d.mkdir(parents=True)
    monkeypatch.setattr(repo, "SNAPSHOT_RETRY_PAUSE", 0)
    return p


def _docker(monkeypatch, results):
    seen = []

    def run(spec, timeout=None, **k):
        seen.append(spec)
        rc, err = results.pop(0)
        return subprocess.CompletedProcess([], rc, b"", err.encode())
    monkeypatch.setattr(docker, "run", run)
    return seen


def test_a_snapshot_that_tar_saw_change_is_taken_again(P, monkeypatch):
    seen = _docker(monkeypatch, [(1, "tar: home: file changed as we read it"), (0, "")])
    assert repo.snapshot(P, 2) == P.snapshots / "step-02.tar" and len(seen) == 2


def test_a_tree_that_keeps_changing_still_fails_after_the_bounded_tries(P, monkeypatch):
    seen = _docker(monkeypatch, [(1, "tar: home: file changed as we read it")] * repo.SNAPSHOT_TRIES)
    with pytest.raises(docker.ContainerError, match="file changed as we read it"):
        repo.snapshot(P, 2)
    assert len(seen) == repo.SNAPSHOT_TRIES


def test_any_other_snapshot_failure_is_not_retried(P, monkeypatch):
    seen = _docker(monkeypatch, [(2, "tar: home/x: Cannot open: Permission denied")])
    with pytest.raises(docker.ContainerError, match="Permission denied"):
        repo.snapshot(P, 2)
    assert len(seen) == 1
