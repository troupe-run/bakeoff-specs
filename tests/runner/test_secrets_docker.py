"""Task 21 in real containers: publish scans the FULL history it pushes; a snapshot is scanned with its git
history. Run with `--run-docker`. Fake tokens only."""
import subprocess
import pytest
from runner import docker, gitops, repo, secrets
from runner.paths import Paths

pytestmark = pytest.mark.docker

PAT = "github_pat_" + "A" * 22 + "_" + "b" * 59
ANT = "sk-ant-oat01-" + "x" * 40
OAUTH = "fake-oauth-" + "q" * 30
HOME_PAT = "fakepat" + "9" * 30


@pytest.fixture(autouse=True)
def _no_leftover_containers():
    yield
    left = subprocess.run(["docker", "ps", "-aq", "--filter", "label=bakeoff.run=dry9/dryrun"],
                          capture_output=True, text=True).stdout.split()
    docker.sweep("bakeoff.run=dry9/dryrun")
    assert left == [], "a container outlived its operation"


@pytest.fixture
def P(tmp_state):
    p = Paths("dry9", "dryrun")
    repo.init(p, "dryrun", "dry9")
    return p


def _publish_to_local_target(P, tmp_path_factory, monkeypatch):
    target = tmp_path_factory.mktemp("publish-target") / "t.git"
    subprocess.run(["git", "init", "-q", "--bare", str(target)], check=True, env=gitops._host_env())
    monkeypatch.setattr(repo, "github_slug", lambda pass_, arm: "troupe-run/test")
    real_push = gitops.push_from_bare
    monkeypatch.setattr(gitops, "push_from_bare", lambda bare, url, ref="main": real_push(bare, str(target), ref))
    return target


def test_publish_refuses_a_secret_that_only_history_still_holds(P, tmp_path_factory, monkeypatch):
    (P.repo / "cfg.txt").write_text(f"a\n{PAT}\n")
    leaked = gitops.commit_all(P, gitops.IDENTITY, "add config")
    (P.repo / "cfg.txt").write_text("a\n")
    gitops.commit_all(P, gitops.IDENTITY, "scrub config")                 # the tip tree is clean again
    target = _publish_to_local_target(P, tmp_path_factory, monkeypatch)
    with pytest.raises(secrets.SecretFound) as e:
        repo.publish(P, "dry9", ask=lambda q: True, scan=lambda t, h: secrets.scan_publish(t, h, []))
    [f] = e.value.findings
    assert f.kind == "github-pat" and "(cfg.txt)" in f.path and f.line == 2
    assert PAT not in str(e.value) + e.value.detail
    blob = gitops.git(P, "rev-parse", f"{leaked}:cfg.txt").stdout.decode().strip()
    assert blob in f.path
    refs = subprocess.run(["git", "-C", str(target), "for-each-ref"], capture_output=True, text=True,
                          env=gitops._host_env()).stdout
    assert refs == ""                                                     # nothing was pushed


def test_publish_of_a_clean_history_pushes(P, tmp_path_factory, monkeypatch):
    (P.repo / "a.py").write_text("print('hi')\n")
    gitops.commit_all(P, gitops.IDENTITY, "clean")
    target = _publish_to_local_target(P, tmp_path_factory, monkeypatch)
    assert repo.publish(P, "dry9", ask=lambda q: True, scan=lambda t, h: secrets.scan_publish(t, h, [OAUTH]))
    pushed = subprocess.run(["git", "-C", str(target), "rev-parse", "main"], capture_output=True, text=True,
                            env=gitops._host_env()).stdout.strip()
    assert pushed == gitops.main_sha(P)


def test_a_snapshot_is_scanned_with_its_git_history_and_the_pat_file_is_exempt(P):
    gh = P.home / ".config" / "gh"; gh.mkdir(parents=True)
    (gh / "hosts.yml").write_text(f"github.com:\n    oauth_token: {HOME_PAT}\n    x: {PAT}\n")  # by design
    (P.home / ".bash_history").write_text(f"echo {HOME_PAT}\n")          # the arm printed its PAT
    proj = P.config_dir / "projects" / "p"; proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(f'{{"text": "{OAUTH}"}}\n')            # the keychain token in a transcript
    (P.repo / "k.txt").write_text(ANT + "\n")
    gitops.commit_all(P, gitops.IDENTITY, "leak")
    gitops.git(P, "rm", "-q", "k.txt", write=True)                   # in the container: a host unlink can
    gitops.commit_all(P, gitops.IDENTITY, "unleak")                      # look stale through the bind mount
    gitops.git(P, "push", "-q", "origin", "main", write=True)
    snap = repo.snapshot(P, 3)
    lits = [OAUTH, *secrets.home_pat_values(P.home)]
    found = secrets.scan_snapshot(P, snap, lits, pat=HOME_PAT)            # HOME_PAT plays the keychain PAT
    got = sorted((f.kind, f.path.split(":", 1)[1].split(" ")[0] if " history: " not in f.path else "history")
                 for f in found)
    assert ("literal", "home/.bash_history") in got
    assert ("literal", "home/.claude/projects/p/s.jsonl") in got
    assert got.count(("anthropic-token", "history")) >= 2                # the work repo AND the origin
    hosts = [(f.kind, f.line) for f in found if f.path.endswith("home/.config/gh/hosts.yml")]
    assert hosts == [("github-pat", 3)]            # the keychain PAT is exempt there; another token is not (6)
    assert all(OAUTH not in f.path and HOME_PAT not in f.path for f in found)
    assert not list((P.scratch / "secret-scan").glob("*"))               # extraction removed


def test_an_oauth_token_in_the_pat_file_is_still_found(P):
    gh = P.home / ".config" / "gh"; gh.mkdir(parents=True)
    (gh / "hosts.yml").write_text(f"github.com:\n    oauth_token: {HOME_PAT}\n# {OAUTH}\n")
    snap = repo.snapshot(P, 4)
    found = secrets.scan_snapshot(P, snap, [OAUTH, *secrets.home_pat_values(P.home)], pat=HOME_PAT)
    assert [(f.kind, f.line) for f in found if "hosts.yml" in f.path] == [("literal", 3)]
