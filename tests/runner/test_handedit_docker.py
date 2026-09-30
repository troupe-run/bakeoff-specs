"""The hand edit against the real Docker daemon, with the fake claude and the dummy credential (no model calls).
Opt in with --run-docker; run under the docker lock.

The fake's `FAKE:sh=` directive (the scripted teammate's edit) is baked into `bakeoff-arm-dryrun:1` (rebuilt by
Task 24), so these tests run the image's own claude. The teammate's fixed prompt is extended with FAKE: lines by
monkeypatching `handedit.PROMPT` (a directive wins over the fake's scripted teammate role)."""
import dataclasses, gzip, json, shutil, subprocess
from pathlib import Path

import pytest

from runner import docker, gitops, handedit, hidden, repo
from runner.faults import HarnessFault
from runner.paths import Paths, REPO_ROOT
from tests.runner.conftest import make_test_ctx

pytestmark = pytest.mark.docker
LABEL = "bakeoff.run=dry9/dryrun"
# The teammate's scripted edit of the reference's CLI: TROUPE_THEATRE as --theatre's default, a test, and two side
# effects (`uv run` rewriting the lock, a cache dir) that must be cleaned rather than committed.
EDIT = ("FAKE:sh=sed -i 's/default=\"[.]\"/default=__import__(\"os\").environ.get(\"TROUPE_THEATRE\") or \".\"/' "
        "src/troupe_ref/cli.py && printf 'def test_theatre_env():\\n    assert True\\n' > tests/test_theatre_env.py "
        "&& echo '# rewritten' >> uv.lock && mkdir -p .pytest_cache && echo x > .pytest_cache/nodeids")



@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    assert not docker.running(LABEL), "a container outlived its run"
    nets = subprocess.run(["docker", "network", "ls", "-q", "--filter", f"label={LABEL}"],
                          capture_output=True, text=True).stdout.split()
    assert nets == [], "a network outlived its run"


def test_side_effects_are_removed_and_the_lockfile_restored(tmp_state):
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    (p.repo / "uv.lock").write_text("v1\n"); (p.repo / "cli.py").write_text("x = 1\n")
    gitops.commit_all(p, gitops.IDENTITY, "base")
    (p.repo / "cli.py").write_text("x = 2\n"); (p.repo / "uv.lock").write_text("v2\n")
    (p.repo / "__pycache__").mkdir(); (p.repo / "__pycache__" / "cli.cpython-312.pyc").write_bytes(b"\0")
    plan = handedit.clean_side_effects(p)
    assert plan.violations == [] and plan.restore == ["uv.lock"]
    assert (p.repo / "uv.lock").read_text() == "v1\n" and not (p.repo / "__pycache__" / "cli.cpython-312.pyc").exists()
    assert gitops.porcelain(p).strip() == "M cli.py"


def _ctx(tmp_path):
    c = make_test_ctx(tmp_path, arm="dryrun", step=2)
    c.sleep = lambda s: None
    return c


def _small_repo(p: Paths) -> str:
    repo.init(p, "dryrun", "dry9")
    (p.repo / "cli.py").write_text("x = 1\n")
    return gitops.commit_all(p, gitops.IDENTITY, "step 1")


def test_a_teammate_that_changes_nothing_fails_scope_twice_and_leaves_the_pre_edit_tree(tmp_state, tmp_path):
    p = Paths("dry9", "dryrun"); before = _small_repo(p)
    ctx = _ctx(tmp_path)
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, {})
    assert (e.value.kind, e.value.signature, e.value.detail) == ("hand-edit", "scope", "no Python file changed")
    assert len(e.value.hand_edit_turns) == 2 and all(t.outcome == "ok" for t in e.value.hand_edit_turns)
    assert gitops.main_sha(p) == before and gitops.porcelain(p) == ""
    out = ctx.out / "hand-edit"
    for k in (1, 2):                            # each try's transcripts were collected and pin-checked
        pin = json.loads((out / f"model-pin-t{k}.json").read_text())
        assert pin["ok"] and pin["assistant_messages"] >= 1 and pin["stream_assistant_messages"] >= 1
        assert list((out / "transcripts" / f"t{k}").rglob("*.jsonl.gz"))
        assert not p.teammate_home(k).exists()
    assert (p.snapshots / "step-02-pre-edit.tar").is_file() and not (p.snapshots / "step-02.tar").exists()


def test_the_teammate_container_sees_its_own_inbox_file_and_not_the_arms_home(tmp_state, tmp_path, monkeypatch):
    p = Paths("dry9", "dryrun"); _small_repo(p)
    (p.inbox("arm")).mkdir(parents=True, exist_ok=True); (p.inbox("arm") / "arm-a1-001.md").write_text("arm msg")
    monkeypatch.setattr(handedit, "PROMPT", handedit.PROMPT + "FAKE:ls_inbox\n")
    ctx = _ctx(tmp_path)
    with docker.recording() as specs, pytest.raises(HarnessFault):
        handedit.apply(ctx, {})
    turn = next(s for s in specs if s.cmd[:1] == ["bk-claude-turn"])
    vols = {m.ctr: m.host for m in turn.mounts}
    assert vols["/home/actor"] == p.teammate_home(1) and vols["/inbox/msg.md"].parent == p.inbox("teammate")
    assert p.home not in vols.values() and turn.env["BK_ISOLATED"] == "1"
    stream = next((ctx.out / "hand-edit" / "turns").glob("teammate-a1-*.stream.jsonl.gz"))
    with gzip.open(stream, "rt") as fh:
        events = [json.loads(l) for l in fh]
    assert [e["result"] for e in events if e.get("type") == "result"] == ["msg.md"]   # only its own message file


def test_auth_failed_is_infra_auth_after_one_try(tmp_state, tmp_path, monkeypatch):
    p = Paths("dry9", "dryrun"); before = _small_repo(p)
    monkeypatch.setattr(handedit, "PROMPT", handedit.PROMPT + "FAKE:auth_fail\n")
    ctx = _ctx(tmp_path)
    with pytest.raises(HarnessFault) as e:
        handedit.apply(ctx, {})
    assert (e.value.kind, e.value.signature) == ("infra-auth", "authentication_failed")
    assert len(e.value.hand_edit_turns) == 1 and gitops.main_sha(p) == before
    assert not (ctx.out / "hand-edit" / "try-2-failed.json").exists()


@pytest.fixture
def reference_arm(tmp_state):
    """A dry arm whose step-1 commit is the reference, baked to step 1 (as an arm's committed step-1 tree would
    be: the arm gets no TROUPE_REF_STEP)."""
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    shutil.copytree(REPO_ROOT / "reference", p.repo, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"))
    step = p.repo / "src" / "troupe_ref" / "step.py"
    step.write_text(step.read_text().replace('os.environ.get("TROUPE_REF_STEP", "7")', 'os.environ.get("TROUPE_REF_STEP", "1")'))
    (p.repo / ".gitignore").write_text(".venv/\n")
    gitops.commit_all(p, gitops.IDENTITY, "step 1")
    return p


def test_the_probe_fails_on_the_unedited_reference(reference_arm, tmp_path):     # the probe is not vacuous
    p = reference_arm
    prep = hidden.prepare(p, gitops.main_sha(p), "probe-pre", tmp_path)
    assert prep.prep["hidden"]["ok"]
    probe = handedit.parse_probe(hidden.run_script(p, prep.hidden_copy, handedit.PROBE_SH))
    assert probe == {"env_default": False, "flag_wins": True, "unchanged_without_env": True}


def test_a_scripted_teammate_edit_lands_on_main_as_sam_teammate_and_becomes_snapshot_2(reference_arm, tmp_path,
                                                                                      monkeypatch):
    p = reference_arm
    before = gitops.main_sha(p)
    lock_before = (p.repo / "uv.lock").read_text()
    step1 = {t: "passed" for t in hidden._collect(p, 1, first_only=False)}     # the reference passes all of step 1
    monkeypatch.setattr(handedit, "PROMPT", handedit.PROMPT + EDIT + "\n")
    ctx = _ctx(tmp_path)
    edit = handedit.apply(ctx, step1)

    assert edit.tries == 1 and edit.files == ["src/troupe_ref/cli.py", "tests/test_theatre_env.py"]
    assert edit.probe == {"env_default": True, "flag_wins": True, "unchanged_without_env": True}
    assert edit.side_effects["restored"] == ["uv.lock"] and edit.side_effects["removed"] == [".pytest_cache/nodeids"]
    assert gitops.main_sha(p) == edit.sha and gitops.log(p, before, edit.sha) == [
        {"sha": edit.sha, "author": "Sam Teammate", "subject": handedit.MESSAGE}]
    assert "Sam Teammate <sam.teammate@troupe.run>" in gitops.show(p, edit.sha)
    assert sorted(f for _, _, f in edit.numstat) == edit.files
    assert gitops.porcelain(p) == "" and (p.repo / "uv.lock").read_text() == lock_before
    out = ctx.out / "hand-edit"
    rec = json.loads((out / "recheck.json").read_text())
    assert rec["differences"] == {} and rec["after_edit"] == step1 and len(step1) == 101
    assert json.loads((out / "model-pin-t1.json").read_text())["ok"] is True
    assert (p.snapshots / "step-02.tar").is_file()

    # snapshot(2) is the post-edit state: a reset to it (after 2.a, or a harness re-run of step 2) keeps the edit
    (p.repo / "src" / "troupe_ref" / "cli.py").write_text("# 2.a scribbled here\n")
    repo.restore(p, 2)
    assert gitops.main_sha(p) == edit.sha and gitops.porcelain(p) == ""
    assert "TROUPE_THEATRE" in (p.repo / "src" / "troupe_ref" / "cli.py").read_text()


# ---- fix round 1 ------------------------------------------------------------------------------------------------

def test_the_teammate_cannot_write_the_repos_git_dir(tmp_state, tmp_path, monkeypatch):
    p = Paths("dry9", "dryrun"); _small_repo(p)
    monkeypatch.setattr(handedit, "PROMPT", handedit.PROMPT + "FAKE:sh=touch control-marker; touch .git/teammate-marker\n")
    monkeypatch.setattr(handedit.repo, "restore", lambda p_, s: None)     # keep what the turn left, to inspect it
    ctx = _ctx(tmp_path)
    with pytest.raises(HarnessFault):
        handedit.apply(ctx, {})
    assert (p.repo / "control-marker").exists()                         # the scripted command did run, in the repo
    assert not (p.repo / ".git" / "teammate-marker").exists()


def test_new_ignored_paths_and_an_untracked_nested_repo_are_removed_and_a_preexisting_venv_is_kept(tmp_state):
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    (p.repo / ".gitignore").write_text(".venv/\nbuild/\n"); (p.repo / "a.py").write_text("x = 1\n")
    gitops.commit_all(p, gitops.IDENTITY, "base")
    (p.repo / ".venv").mkdir(); (p.repo / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
    before = gitops.ignored(p)
    assert before == [".venv/"]
    # follow-up 11: a different SIZE (not just content), so git sees the change even when the write lands in the
    # same second as the index entry (racy-git: same size and mtime look unchanged from inside the container)
    (p.repo / "a.py").write_text("x = 20\n")
    (p.repo / "build").mkdir(); (p.repo / "build" / "out.bin").write_bytes(b"\0")
    gitops.git(p, "init", "-q", "vendor/lib", write=True)                 # a nested repo, made in a container
    (p.repo / "vendor" / "lib" / "x.txt").write_text("y\n")
    plan = handedit.clean_side_effects(p, ignored_before=before)
    assert plan.violations == [] and plan.remove == ["vendor/lib/"]
    assert plan.removed_ignored == ["build/"] and plan.ignored_preexisting == [".venv/"]
    assert not (p.repo / "build").exists() and not (p.repo / "vendor" / "lib").exists()
    assert (p.repo / ".venv" / "pyvenv.cfg").exists()
    assert gitops.porcelain(p).strip() == "M a.py"
