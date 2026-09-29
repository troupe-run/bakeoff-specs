from runner.paths import Paths, RESULTS, STATE, brief_path, REPO_ROOT


def test_state_and_results_are_per_pass_and_arm():
    p = Paths("pass1", "openspec")
    assert p.home == STATE / "pass1" / "openspec" / "home"
    assert p.repo == STATE / "pass1" / "openspec" / "work" / "bakeoff-specs-openspec"
    assert p.step(2) == RESULTS / "pass1" / "openspec" / "02"


def test_container_paths_are_constants():                                    # renamed (review Q-11)
    p = Paths("pass2", "speckit")
    assert p.container_repo == "/work/bakeoff-specs-speckit" and p.container_home == "/home/actor"


def test_every_role_has_its_own_inbox():                                     # review C-12
    p = Paths("pass1", "control")
    assert len({p.inbox("arm"), p.inbox("po"), p.inbox("teammate")}) == 3


def test_real_passes_use_the_real_brief_and_other_passes_a_copy():
    assert brief_path("pass1") == REPO_ROOT / "scenario" / "po-brief.md"
    assert brief_path("dry1") == STATE / "dry1" / "po-brief.md"
    assert brief_path("canary") == STATE / "canary" / "po-brief.md"
