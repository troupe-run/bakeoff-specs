import pytest
from runner import config

@pytest.mark.parametrize("name", config.all_arms())
def test_every_real_arm_loads_and_names_its_own_repo(name):
    a = config.load_arm(name)
    assert a.name == name and a.repo_name == f"bakeoff-specs-{name}" and not a.dry and a.citation

def test_only_speckitty_tracks_outside_github():
    assert {n for n in config.all_arms() if config.load_arm(n).tracker != "github"} == {"speckitty"}

@pytest.mark.parametrize("name", config.all_arms())
def test_run_allowlist_adds_nothing_but_github_api(name):
    assert set(config.load_arm(name).egress_run) <= {r"^api\.github\.com$"}

def test_openspec_arm_env_sets_telemetry_off():                    # renamed (review Q-11); the image is Task 2's test
    assert config.load_arm("openspec").env["OPENSPEC_TELEMETRY"] == "0"

@pytest.mark.parametrize("name", config.all_arms())
def test_every_plugin_is_pinned_to_a_tag_and_a_repo(name):
    for pl in config.load_arm(name).plugins:
        assert pl.repo and pl.tag.startswith("v") and pl.version in pl.tag
