"""Task 23: `preflight.check_images` (content, not only local ID; the reference tree baked into bakeoff-tester-ref),
`preflight.lock`, and the targeted image build (only named images; never every image)."""
import json, threading

import pytest

from runner import checklist, config, images, preflight
from runner.paths import Paths


# ---- the reference tree -----------------------------------------------------------------------------------

def _ref(tmp_path):
    r = tmp_path / "reference"
    (r / "src" / "pkg").mkdir(parents=True)
    (r / "pyproject.toml").write_text("[project]\nname='x'\n")
    (r / "src" / "pkg" / "a.py").write_text("A = 1\n")
    return r


def test_the_reference_tree_hash_is_deterministic_and_follows_content(tmp_path):
    r = _ref(tmp_path)
    h = images.reference_tree(r)
    assert h == images.reference_tree(r) and len(h) == 64
    (r / "src" / "pkg" / "a.py").write_text("A = 2\n")
    assert images.reference_tree(r) != h


def test_the_reference_tree_ignores_what_the_build_context_excludes(tmp_path):     # .dockerignore
    r = _ref(tmp_path)
    h = images.reference_tree(r)
    (r / ".venv" / "bin").mkdir(parents=True); (r / ".venv" / "bin" / "python").write_text("x")
    (r / "src" / "pkg" / "__pycache__").mkdir(); (r / "src" / "pkg" / "__pycache__" / "a.pyc").write_bytes(b"\0")
    (r / ".pytest_cache").mkdir(); (r / ".pytest_cache" / "v").write_text("x")
    assert images.reference_tree(r) == h


def test_a_renamed_file_changes_the_reference_tree(tmp_path):
    r = _ref(tmp_path)
    h = images.reference_tree(r)
    (r / "src" / "pkg" / "a.py").rename(r / "src" / "pkg" / "b.py")
    assert images.reference_tree(r) != h


# ---- check_images -----------------------------------------------------------------------------------------

TAGS = {"base": "bakeoff-base:cc2.1.281", "tester": "bakeoff-tester:3", "tester_ref": "bakeoff-tester-ref:1",
        "proxy": "bakeoff-egress:1", "dryrun": "bakeoff-arm-dryrun:1"}


@pytest.fixture
def lock_env(tmp_state, tmp_path, monkeypatch):
    ref = _ref(tmp_path)
    lock = {"images": {t: {"id": f"id-{t}", "content": f"c-{t}"} for t in TAGS.values()},
            "arms": {"openspec": {"image": "bakeoff-arm-openspec:1", "id": "id-o", "content": "c-o"},
                     "bmad": {"image": "bakeoff-arm-bmad:1", "error": "unpinned plugin(s)"}},
            "reference_tree": images.reference_tree(ref)}
    lf = tmp_path / "images.lock.json"
    lf.write_text(json.dumps(lock))
    monkeypatch.setattr(images, "LOCK", lf)
    monkeypatch.setattr(images, "REFERENCE", ref)
    current = {**{t: f"c-{t}" for t in TAGS.values()}, "bakeoff-arm-openspec:1": "c-o"}
    monkeypatch.setattr(images, "content_id", lambda tag: current[tag])
    p = Paths("pass1", "openspec")
    p.setup_results.mkdir(parents=True)
    (p.setup_results / "versions.json").write_text(json.dumps({"image": lock["arms"]["openspec"]}))
    return type("E", (), {"lock": lock, "lf": lf, "current": current, "p": p, "ref": ref})


def test_check_images_passes_when_content_reference_and_setup_record_all_match(lock_env):
    preflight.check_images("openspec", lock_env.p)


def test_a_changed_image_content_is_refused_even_with_the_same_local_id(lock_env, monkeypatch):
    lock_env.current["bakeoff-tester:3"] = "c-rebuilt"
    monkeypatch.setattr(images, "current_id", lambda tag: f"id-{tag}", raising=False)
    with pytest.raises(checklist.NotReady, match="bakeoff-tester:3"):
        preflight.check_images("openspec", lock_env.p)


@pytest.mark.parametrize("tag", ["bakeoff-arm-openspec:1", "bakeoff-base:cc2.1.281", "bakeoff-tester-ref:1",
                                 "bakeoff-egress:1"])
def test_every_image_the_arm_step_uses_is_compared(lock_env, tag):
    lock_env.current[tag] = "c-other"
    with pytest.raises(checklist.NotReady, match=tag):
        preflight.check_images("openspec", lock_env.p)


def test_a_missing_image_is_refused_not_crashed(lock_env, monkeypatch):
    def gone(tag):
        raise images.subprocess.CalledProcessError(1, ["docker"])
    monkeypatch.setattr(images, "content_id", gone)
    with pytest.raises(checklist.NotReady, match="not loaded"):
        preflight.check_images("openspec", lock_env.p)


def test_a_reference_edited_since_the_build_is_refused(lock_env):
    (lock_env.ref / "src" / "pkg" / "a.py").write_text("A = 99\n")
    with pytest.raises(checklist.NotReady, match="reference"):
        preflight.check_images("openspec", lock_env.p)


def test_a_lock_without_a_recorded_reference_tree_is_refused(lock_env):
    del lock_env.lock["reference_tree"]
    lock_env.lf.write_text(json.dumps(lock_env.lock))
    with pytest.raises(checklist.NotReady, match="reference_tree"):
        preflight.check_images("openspec", lock_env.p)


def test_an_image_other_than_the_one_recorded_at_setup_is_refused(lock_env):
    (lock_env.p.setup_results / "versions.json").write_text(json.dumps(
        {"image": {"image": "bakeoff-arm-openspec:1", "id": "id-old", "content": "c-old"}}))
    with pytest.raises(checklist.NotReady, match="setup"):
        preflight.check_images("openspec", lock_env.p)


def test_an_arm_without_a_built_image_is_refused(lock_env):
    with pytest.raises(checklist.NotReady, match="bmad"):
        preflight.check_images("bmad", Paths("pass1", "bmad"))


def test_a_dry_arm_is_checked_against_the_dryrun_image(lock_env):
    p = Paths("dry1", "dryrun")
    p.setup_results.mkdir(parents=True)
    (p.setup_results / "versions.json").write_text(json.dumps(
        {"image": {"image": TAGS["dryrun"], **lock_env.lock["images"][TAGS["dryrun"]]}}))
    preflight.check_images("dryrun", p)
    lock_env.current[TAGS["dryrun"]] = "c-other"
    with pytest.raises(checklist.NotReady, match="dryrun"):
        preflight.check_images("dryrun", p)


def test_no_setup_record_is_refused(lock_env):
    (lock_env.p.setup_results / "versions.json").unlink()
    with pytest.raises(checklist.NotReady, match="versions.json"):
        preflight.check_images("openspec", lock_env.p)


# ---- the runner lock ---------------------------------------------------------------------------------------

def test_the_runner_lock_admits_one_holder_at_a_time(tmp_state):
    with preflight.lock():
        with pytest.raises(checklist.NotReady, match="runner.lock"):
            with preflight.lock():
                pass
    with preflight.lock():                   # released on exit
        pass


def test_the_runner_lock_is_released_when_the_body_raises(tmp_state):
    with pytest.raises(ZeroDivisionError):
        with preflight.lock():
            1 / 0
    with preflight.lock():
        pass


def test_orchestrate_notready_is_the_one_refusal_type():
    from runner import orchestrate
    assert orchestrate.NotReady is checklist.NotReady is preflight.NotReady


# ---- targeted build: only the named images, never every image ------------------------------------------------

@pytest.fixture
def build_env(lock_env, monkeypatch):
    built, saved = [], []
    monkeypatch.setattr(images, "check_pinned", lambda: None)
    monkeypatch.setattr(images, "_build", lambda tag, *a, **k: built.append(tag))
    monkeypatch.setattr(images, "current_id", lambda tag: f"new-id-{tag}")
    monkeypatch.setattr(images, "content_id", lambda tag: f"new-c-{tag}")
    monkeypatch.setattr(images, "_save", lambda tag: saved.append(tag) or f"tar-{tag}")
    monkeypatch.setattr(images, "_versions", lambda tag, extra: {"v": tag})
    return type("B", (), {"built": built, "saved": saved, "env": lock_env})


def test_building_only_the_reference_image_rebuilds_nothing_else_and_records_the_reference_tree(build_env):
    lock = images.build_only(["tester_ref"])
    assert build_env.built == ["bakeoff-tester-ref:1"]
    assert lock["images"]["bakeoff-tester-ref:1"]["content"] == "new-c-bakeoff-tester-ref:1"
    assert lock["images"]["bakeoff-tester:3"] == build_env.env.lock["images"]["bakeoff-tester:3"]   # untouched
    assert lock["arms"] == build_env.env.lock["arms"]                                              # untouched
    assert lock["reference_tree"] == images.reference_tree(build_env.env.ref)
    assert json.loads(build_env.env.lf.read_text()) == lock


def test_building_one_arm_image_touches_only_that_arm(build_env):
    lock = images.build_only(["openspec"])
    assert build_env.built == ["bakeoff-arm-openspec:1"]
    assert lock["arms"]["openspec"]["content"] == "new-c-bakeoff-arm-openspec:1"
    assert lock["arms"]["bmad"] == build_env.env.lock["arms"]["bmad"]
    assert lock["images"] == build_env.env.lock["images"]


def test_a_targeted_build_refuses_unknown_names_and_a_missing_lock(build_env, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="nonsense"):
        images.build_only(["nonsense"])
    assert build_env.built == []
    monkeypatch.setattr(images, "LOCK", tmp_path / "absent.json")
    with pytest.raises(RuntimeError, match="build_all"):
        images.build_only(["tester_ref"])


def test_a_targeted_build_refuses_a_parked_arm(build_env):
    with pytest.raises(ValueError, match="parked"):
        images.build_only(["bmad"])


def test_the_full_build_records_the_reference_tree_too(build_env, tmp_path, monkeypatch):
    monkeypatch.setattr(images, "LOCK", tmp_path / "fresh.lock.json")
    lock = images.build_all(["control"])
    assert lock["reference_tree"] == images.reference_tree(build_env.env.ref)
