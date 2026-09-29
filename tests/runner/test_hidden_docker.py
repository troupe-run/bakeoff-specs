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


def test_the_arm_runs_as_its_own_uid_under_the_harness_login_name(ref):     # review §3 NOTE 1 + fix round 1
    p, copy = ref
    out = hidden.run_script(p, copy, "id -u; id -un; env; python3 -c 'import getpass; print(\"gp=\" + getpass.getuser())'")
    lines = out.splitlines()
    assert lines[:2] == ["1001", "actor"], out
    assert {"LOGNAME=actor", "USER=actor", "HOME=/home/actor", "gp=actor"} <= set(lines), out


def test_the_arm_has_no_network_and_cannot_write_the_harness_tests(ref):
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


def _skeleton(label: str, main: str, out):
    p = Paths("dryhidden", "dryrun")
    dst = p.scratch / label / "a" / "bakeoff-specs-dryrun"
    (dst / "src" / "skeleton").mkdir(parents=True)
    (dst / "pyproject.toml").write_text(_SKELETON_PYPROJECT)
    (dst / "src" / "skeleton" / "__init__.py").write_text(main)
    prep = hidden.prepare_copy(p, dst, out, label)
    assert prep.prep["hidden"]["ok"] and prep.prep["hidden"]["lockfile"] is False, prep.prep
    return p, dst


@pytest.fixture(scope="module")
def skeleton(state, tmp_path_factory):
    """A CLI that exists, installs and does nothing. (No `uv.lock`: the prep takes the `uv sync` path,
    recorded as `lockfile: false`.)"""
    out = tmp_path_factory.mktemp("skel")
    p, dst = _skeleton("skel", "def main():\n    return 0\n", out)
    return hidden.run(p, dst, 1, out)


# The reviewer's exploit, plus the obvious variants: forge an all-passing junit wherever the harness might read
# it, then try to kill pytest so the forged file is what gets scored. Every attempt is logged into the arm's own
# copy (the one place it may write), so the test proves the attempts ran and were refused.
_FORGER = r'''import glob, os, signal
FORGED = '<testsuites><testsuite>' + ''.join(
    '<testcase classname="tests.hidden.test_step1_history" name="t%d"/>' % i for i in range(25)) + '</testsuite></testsuites>'
LOG = "/work/bakeoff-specs-dryrun/attempts.log"

def _try(what, fn):
    try:
        fn(); r = "OK"
    except Exception as e:
        r = type(e).__name__
    with open(LOG, "a") as fh:
        fh.write(f"{what} {r}\n")

def _write(path):
    def f():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(FORGED)
    return f

def _kill_all_pytest():
    found = []
    for d in glob.glob("/proc/[0-9]*"):
        try:
            cmd = open(d + "/cmdline", "rb").read()
        except OSError:
            continue
        if b"pytest" in cmd:
            found.append(int(d.rsplit("/", 1)[1]))
    if not found:
        raise LookupError("no pytest process visible")
    for pid in found:
        os.kill(pid, signal.SIGKILL)

def _uid(pid):
    for line in open(f"/proc/{pid}/status"):
        if line.startswith("Uid:"):
            return int(line.split()[1])

def _kill_first_foreign_ancestor():
    pid = os.getppid()
    while _uid(pid) == os.getuid():
        pid = int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1])
    os.kill(pid, signal.SIGKILL)

def main():
    _try("write-out", _write("/out/junit.xml"))
    _try("write-results", _write("/tmp/results/junit.xml"))
    _try("kill-parent", _kill_first_foreign_ancestor)
    _try("kill-pytest", _kill_all_pytest)
    return 0
'''


def test_an_arm_that_forges_junit_and_kills_pytest_scores_zero(state, tmp_path):     # fix round 1
    p, dst = _skeleton("forger", _FORGER, tmp_path)
    s = hidden.run(p, dst, 1, tmp_path)
    assert (s.scoreable, s.attribution, s.total, s.passed) == (True, None, EXPECTED[1], 0), s.attribution
    attempts = (dst / "attempts.log").read_text().splitlines()
    assert attempts, "the forger never ran"
    results = {tuple(a.split()) for a in attempts}
    assert {r[0] for r in results} == {"write-out", "write-results", "kill-parent", "kill-pytest"}
    assert {r for r in results if r[0].startswith("kill-")} == {("kill-parent", "PermissionError"),
                                                               ("kill-pytest", "PermissionError")}, results
    assert not [r for r in results if r[1] == "OK"], results


def test_a_skeleton_that_does_nothing_scores_zero(skeleton):
    assert skeleton.total == EXPECTED[1]
    assert skeleton.passed == 0 and skeleton.new_discriminating_passed == 0, \
        [t for t, o in skeleton.tests.items() if o != "failed"]


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
