"""Hidden tests in the tester container (OD23), against real copies. Run with `--run-docker`, under the docker lock.

The acceptance test for Task 18 is fairness: the REFERENCE, exported like an arm repo and prepared like one,
reproduces Plan 1's validated counts exactly in the tester container (watcher, lineage/getpass and remote tests
included), and a skeleton that does nothing scores zero.
"""
import json
import shutil
import subprocess
import pytest
from runner import docker, hidden, paths, preflight
from runner.paths import Paths, REPO_ROOT

pytestmark = pytest.mark.docker
EXPECTED = {1: 101, 2: 109, 3: 121, 4: 135, 5: 146, 6: 151, 7: 161}   # results/instrument-validation.md
LABEL = "bakeoff.run=dryhidden/dryrun"


@pytest.fixture(scope="module")
def state(tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(paths, "STATE", tmp_path_factory.mktemp("state"))
        yield
    docker.sweep(LABEL)


@pytest.fixture(autouse=True)
def _no_leftover_containers():
    yield
    left = subprocess.run(["docker", "ps", "-aq", "--filter", f"label={LABEL}"],
                          capture_output=True, text=True).stdout.split()
    nets = subprocess.run(["docker", "network", "ls", "-q", "--filter", f"label={LABEL}"],
                          capture_output=True, text=True).stdout.split()
    docker.sweep(LABEL)
    assert (left, nets) == ([], []), "a tester container or network outlived its run"


@pytest.fixture(scope="module")
def ref(state, tmp_path_factory):
    p = Paths("dryhidden", "dryrun")
    dst = p.scratch / "ref" / "a" / "bakeoff-specs-dryrun"
    shutil.copytree(REPO_ROOT / "reference", dst, ignore=shutil.ignore_patterns(".venv", "__pycache__"))
    prep_out = tmp_path_factory.mktemp("prep")
    prepared = hidden.prepare_copy(p, dst, prep_out, "ref")
    assert prepared.prep["hidden"]["ok"], prepared.prep
    assert json.loads((prep_out / "hidden" / "prep-ref.json").read_text())["hidden"]["lockfile"] is True
    return p, prepared.hidden_copy


@pytest.mark.parametrize("step", range(1, 8))
def test_reference_passes_every_step_exactly_in_the_tester_container(ref, step, tmp_path):
    p, copy = ref
    s = hidden.run(p, copy, step, tmp_path)
    assert (s.total, s.passed, s.failed, s.flaky, s.flaky_arm) == (EXPECTED[step], EXPECTED[step], 0, 0, 0)
    assert s.exit_code == 0 and s.new_passed == len(s.new_at_step) > 0
    assert json.loads((tmp_path / "hidden" / "summary.json").read_text())["passed"] == EXPECTED[step]


def test_the_tester_env_has_no_login_name_variables(ref):                    # review §3 NOTE 1 lock-in
    p, copy = ref
    env = hidden.run_script(p, copy, "env")
    assert "HOME=/home/actor" in env.splitlines()                            # the script really ran
    assert not any(l.startswith(("USER=", "LOGNAME=")) for l in env.splitlines())


def test_the_tester_has_no_network_and_cannot_write_the_harness_tests(ref):
    p, copy = ref
    out = hidden.run_script(p, copy, "touch /harness/tests/x 2>&1 && echo WROTE; "
                                     "python3 -c 'import socket; socket.create_connection((\"1.1.1.1\", 80), 3)' "
                                     "2>&1 >/dev/null && echo NET || echo NONET; ls /harness")
    assert "WROTE" not in out and "NONET" in out and "tests" in out, out


def test_a_test_stable_on_the_reference_is_an_arm_flake(ref):                # review C-2
    p, _ = ref
    assert hidden.classify_flaky(p, 1, "tests/hidden/test_step1_load_show.py::test_show_nested_path_and_list_index") == "arm"


_SKELETON_PYPROJECT = '''[project]
name = "skeleton"
version = "0"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
troupe = "skeleton:main"

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
'''


# Found by this suite (Task 18): on a CLI that installs, exits 0 and does nothing, exactly one step-1 hidden
# test passes — it only checks that history is unchanged after a same-value `set`, which is vacuously true
# when nothing is ever recorded. It is not in harness/negative_allowlist.txt, so it also counts as
# discriminating progress. Changing the instrument (allowlist or test) is a controller/owner decision.
VACUOUS_ON_DO_NOTHING = {"tests.hidden.test_step1_history::test_set_to_the_same_value_records_nothing"}


@pytest.fixture(scope="module")
def skeleton(state, tmp_path_factory):
    """A CLI that exists, installs and does nothing. (No `uv.lock`: the prep takes the `uv sync` path,
    recorded as `lockfile: false`.)"""
    p = Paths("dryhidden", "dryrun")
    dst = p.scratch / "skel" / "a" / "bakeoff-specs-dryrun"
    (dst / "src" / "skeleton").mkdir(parents=True)
    (dst / "pyproject.toml").write_text(_SKELETON_PYPROJECT)
    (dst / "src" / "skeleton" / "__init__.py").write_text("def main():\n    return 0\n")
    out = tmp_path_factory.mktemp("skel")
    prep = hidden.prepare_copy(p, dst, out, "skel")
    assert prep.prep["hidden"]["ok"] and prep.prep["hidden"]["lockfile"] is False, prep.prep
    return hidden.run(p, dst, 1, out)


def test_a_do_nothing_skeleton_passes_only_the_known_vacuous_step1_test(skeleton):
    assert skeleton.total == EXPECTED[1]
    assert {t for t, o in skeleton.tests.items() if o != "failed"} == VACUOUS_ON_DO_NOTHING


@pytest.mark.xfail(strict=True, reason="instrument gap: test_set_to_the_same_value_records_nothing passes on a "
                                       "do-nothing arm and is not allowlisted (reported to the controller)")
def test_a_skeleton_that_does_nothing_scores_zero(skeleton):
    assert skeleton.passed == 0 and skeleton.new_discriminating_passed == 0


def test_an_uninstallable_arm_is_install_failed_and_scores_zero_without_reruns(state, tmp_path):
    p = Paths("dryhidden", "dryrun")
    dst = p.scratch / "broken" / "a" / "bakeoff-specs-dryrun"
    dst.mkdir(parents=True)
    (dst / "pyproject.toml").write_text('[project]\nname = "broken"\nversion = "0"\n'
                                        'dependencies = ["no-such-package-bakeoff-xyz==9.9.9"]\n')
    prep = hidden.prepare_copy(p, dst, tmp_path, "broken")
    assert prep.prep["hidden"]["ok"] is False and len(prep.prep["hidden"]["tries"]) == 2   # retried once
    s = hidden.run(p, dst, 1, tmp_path, install_failed=True)
    assert s.install_failed and s.passed == 0 and s.failed == s.total == EXPECTED[1]
    assert json.loads((tmp_path / "hidden" / "flake.json").read_text())["reruns"] == {}


def test_idle_reports_the_real_docker_vm_load():                            # review §3 NOTE 8
    ok, detail = preflight.idle()
    fields = dict(kv.split("=", 1) for kv in detail.split())
    assert float(fields["vm_load1"]) >= 0 and int(fields["vm_cpus"]) >= 1, detail
