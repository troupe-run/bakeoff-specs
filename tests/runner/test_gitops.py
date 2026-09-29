"""Host-side git helpers (review B2): `ls_remote_tag` resolves a plugin's pinned tag to a commit SHA
before any arm image exists. Task 8 extends `runner/gitops.py` with the in-container helpers."""
import subprocess
import pytest
from runner import gitops


class FakeCompleted:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_ls_remote_tag_prefers_the_peeled_commit_of_an_annotated_tag(monkeypatch):
    def fake_run(argv, **kw):
        assert argv == ["git", "ls-remote", "--tags", "https://github.com/obra/superpowers"]
        return FakeCompleted("668b16d4d8d4d603fd257567684fbbffccbf2022\trefs/tags/v6.4.2\n"
                              "8ca22dba9a94f28898bbce59f2537ff4d87c747d\trefs/tags/v6.4.2^{}\n"
                              "deadbeef00000000000000000000000000000000\trefs/tags/v6.4.1\n")
    monkeypatch.setattr(gitops.subprocess, "run", fake_run)
    assert gitops.ls_remote_tag("obra/superpowers", "v6.4.2") == "8ca22dba9a94f28898bbce59f2537ff4d87c747d"


def test_ls_remote_tag_returns_the_lightweight_tag_commit_directly(monkeypatch):
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: FakeCompleted("abc123\trefs/tags/v1.0.0\n"))
    assert gitops.ls_remote_tag("x/y", "v1.0.0") == "abc123"


def test_ls_remote_tag_raises_when_the_remote_has_no_such_tag(monkeypatch):
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: FakeCompleted(""))
    with pytest.raises(gitops.TagNotFound, match="v6.12.0"):
        gitops.ls_remote_tag("bmad-code-org/bmad-plugins", "v6.12.0")


def test_ls_remote_tag_raises_git_remote_unavailable_not_tag_not_found_when_git_itself_fails(monkeypatch):
    """review fix-round-1 item 3: a nonzero exit from `git ls-remote` (network unreachable, repo not
    found, DNS failure, ...) means we couldn't even ask the question — that's a transient/environment
    failure, fatal, and must never be treated as 'this tag doesn't exist' (which parks the plugin)."""
    monkeypatch.setattr(gitops.subprocess, "run", lambda *a, **k: FakeCompleted("", returncode=128, stderr="boom"))
    with pytest.raises(gitops.GitRemoteUnavailable, match="boom"):
        gitops.ls_remote_tag("x/y", "v1.0.0")


def test_ls_remote_tag_raises_git_remote_unavailable_when_the_subprocess_call_itself_raises(monkeypatch):
    def raiser(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=30)
    monkeypatch.setattr(gitops.subprocess, "run", raiser)
    with pytest.raises(gitops.GitRemoteUnavailable):
        gitops.ls_remote_tag("x/y", "v1.0.0")


def test_git_remote_unavailable_is_not_a_tag_not_found():                  # they must not be confused
    assert not issubclass(gitops.GitRemoteUnavailable, gitops.TagNotFound)
    assert not issubclass(gitops.TagNotFound, gitops.GitRemoteUnavailable)


def test_host_env_disables_interactive_credential_prompts():
    env = gitops._host_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"


@pytest.mark.network
def test_ls_remote_tag_resolves_superpowers_v6_4_2_for_real():
    assert gitops.ls_remote_tag("obra/superpowers", "v6.4.2") == "8ca22dba9a94f28898bbce59f2537ff4d87c747d"


@pytest.mark.network
def test_bmad_plugins_repo_has_no_v6_12_0_tag_so_bmad_is_parked():
    """Evidence for B2: `bmad-code-org/bmad-plugins` (the repo CANDIDATES.md documents for the Claude Code
    plugin install) carries no tags at all — confirmed 2026-09-29 via `git ls-remote --tags` (empty) and a
    `git ls-remote` of all refs (only `main`, `core-tools-rename`, and PR refs). The plan's draft coordinates
    (tag `v6.12.0`, subdirs `plugins/bmad-method` / `plugins/bmad-core-tools`) do not exist on this repo;
    see task-3-report.md for the full finding."""
    with pytest.raises(gitops.TagNotFound):
        gitops.ls_remote_tag("bmad-code-org/bmad-plugins", "v6.12.0")
