"""Task 23's docker-backed pieces, for real: the images a run uses checked by content against the lock, the arm's
leftovers set aside before the step-2 hand edit (real git in the arm's container), and a substitute bug's acceptance
test run in the tester against a real copy (it must FAIL on the step-5 commit to be delivered). Run with
`--run-docker`, under the docker lock. No model turn, no network beyond PyPI for the copy's install."""
import json
import shutil
import subprocess

import pytest

from runner import checklist, gitops, hidden, images, paths, preflight, repo
from runner.paths import Paths, REPO_ROOT

pytestmark = pytest.mark.docker
LABELS = ("bakeoff.run=dryorch/dryrun", "bakeoff.run=dryacc/dryrun")


@pytest.fixture(autouse=True)
def _no_leftover_containers():
    yield
    left = [c for lb in LABELS for c in subprocess.run(["docker", "ps", "-aq", "--filter", f"label={lb}"],
                                                        capture_output=True, text=True).stdout.split()]
    assert left == [], "a container outlived its operation"


# ---- check_images against the images that are really loaded ------------------------------------------------------

@pytest.fixture
def live_lock(tmp_state, tmp_path, monkeypatch):
    lock = images.lock()
    lock["reference_tree"] = images.reference_tree()           # as `images build --only tester_ref` records it
    lf = tmp_path / "images.lock.json"
    lf.write_text(json.dumps(lock))
    monkeypatch.setattr(images, "LOCK", lf)
    p = Paths("dryorch", "control")
    p.setup_results.mkdir(parents=True)
    (p.setup_results / "versions.json").write_text(json.dumps({"image": lock["arms"]["control"]}))
    return lock, lf, p


def test_the_loaded_images_match_the_lock_by_content(live_lock):
    preflight.check_images("control", live_lock[2])


def test_a_lock_that_names_other_content_refuses_to_start(live_lock):
    lock, lf, p = live_lock
    lock["images"]["bakeoff-tester:3"]["content"] = "sha256:" + "0" * 64
    lf.write_text(json.dumps(lock))
    with pytest.raises(checklist.NotReady, match="bakeoff-tester:3"):
        preflight.check_images("control", p)


# ---- leftovers set aside before the hand edit --------------------------------------------------------------

@pytest.fixture
def P(tmp_state):
    p = Paths("dryorch", "dryrun")
    repo.init(p, "dryrun", "dryorch")
    return p


def test_leftovers_on_a_branch_are_stashed_and_main_checked_out_clean(P):
    (P.repo / "a.py").write_text("A = 1\n")
    base = gitops.commit_all(P, gitops.IDENTITY, "step 1")
    gitops.git(P, "checkout", "-q", "-b", "feature", write=True)
    (P.repo / "a.py").write_text("A = 2\n")                           # tracked change
    (P.repo / "new.py").write_text("N = 1\n")                         # untracked file
    rec = gitops.set_aside_to_main(P, "bakeoff: leftovers at the end of step 1")
    assert rec == {"branch": "feature", "dirty": True, "stashed": True, "checked_out_main": True}
    st = gitops.state(P)
    assert (st.branch, st.dirty, st.head) == ("main", False, base)
    assert (P.repo / "a.py").read_text() == "A = 1\n" and not (P.repo / "new.py").exists()
    stash = gitops.git(P, "stash", "list").stdout.decode()
    assert "bakeoff: leftovers at the end of step 1" in stash              # kept, never deleted


def test_a_clean_main_is_left_exactly_as_it_is(P):
    before = gitops.state(P)
    assert gitops.set_aside_to_main(P, "x")["stashed"] is False
    assert gitops.state(P) == before and gitops.git(P, "stash", "list").stdout == b""


# ---- a substitute bug's acceptance test, in the tester ----------------------------------------------------------

@pytest.fixture(scope="module")
def step5_copy(tmp_path_factory):
    """The reference, prepared like an arm's copy and baked to BE its step-5 implementation."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(paths, "STATE", tmp_path_factory.mktemp("state"))
        p = Paths("dryacc", "dryrun")
        dst = p.scratch / "ref" / "a" / "bakeoff-specs-dryrun"
        shutil.copytree(REPO_ROOT / "reference", dst, ignore=shutil.ignore_patterns(".venv", "__pycache__"))
        prepared = hidden.prepare_copy(p, dst, tmp_path_factory.mktemp("prep"), "ref")
        assert prepared.prep["hidden"]["ok"], prepared.prep
        f = dst / "src" / "troupe_ref" / "step.py"
        f.write_text(f.read_text().replace('os.environ.get("TROUPE_REF_STEP", "7")', 'os.environ.get("TROUPE_REF_STEP", "5")'))
        yield p, prepared.hidden_copy


ALIAS_BUG = '''import pytest
from .theatre import build, read

SHARED = "defaults: &d\\n  model: opus\\ncoder:\\n  settings: *d\\nreviewer:\\n  settings: *d\\n"

@pytest.mark.steps(6)
def test_setting_through_an_alias_is_refused(cli, tmp_theatre):
    build(tmp_theatre, {".troupe/troupe.yml": SHARED})
    r = cli("set", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 3 and "--expand-alias" in r.err
'''

ALREADY_FINE = '''import pytest
from .theatre import build

@pytest.mark.steps(6)
def test_show_prints_a_value(cli, tmp_theatre):
    build(tmp_theatre, {".troupe/troupe.yml": "a: 1\\n"})
    assert cli("get", "a", theatre=tmp_theatre).out == "1\\n"
'''


def test_a_real_bug_on_the_step5_commit_fails_its_acceptance_test(step5_copy):
    p, copy = step5_copy
    r = hidden.run_acceptance(p, copy, 6, ALIAS_BUG)
    assert r["outcome"] == "failed", r


def test_behaviour_the_step5_commit_already_has_passes_so_it_is_no_substitute(step5_copy):
    p, copy = step5_copy
    r = hidden.run_acceptance(p, copy, 6, ALREADY_FINE)
    assert r["outcome"] == "passed", r


def test_an_acceptance_test_without_the_steps_marker_is_an_error_not_a_verdict(step5_copy):
    p, copy = step5_copy
    r = hidden.run_acceptance(p, copy, 6, ALREADY_FINE.replace("@pytest.mark.steps(6)\n", ""))
    assert r["outcome"] == "error", r
