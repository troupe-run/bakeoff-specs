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


def test_the_arm_has_no_network(ref):
    p, copy = ref
    out = hidden.run_script(p, copy, "python3 -c 'import socket; socket.create_connection((\"1.1.1.1\", 80), 3)' "
                                     "2>&1 >/dev/null && echo NET || echo NONET")
    assert "NONET" in out, out


# fix round 2, item 1: the reference is in the tester image, so the arm uid must not reach it by ANY path.
REF_PROBE = r"""
ls /opt/reference >/dev/null 2>&1 && echo LIST-OK
cat /opt/reference/pyproject.toml >/dev/null 2>&1 && echo READ-OK
/opt/reference/.venv/bin/troupe --help >/dev/null 2>&1 && echo EXEC-OK
/opt/reference/.venv/bin/python -c 'import troupe_ref' >/dev/null 2>&1 && echo IMPORT-OK
PYTHONPATH=/opt/reference/src python3 -c 'import troupe_ref' >/dev/null 2>&1 && echo PYPATH-OK
uv run --offline --no-sync --project /opt/reference troupe --help >/dev/null 2>&1 && echo UVRUN-OK
find / -xdev \( -path /proc -o -path /sys \) -prune -o \( -name 'troupe_ref*' -o -name 'troupe-ref*' \) -readable -print 2>/dev/null | sed 's/^/FOUND /'
echo PROBE-DONE
"""


def test_the_arm_uid_cannot_reach_the_reference_by_any_path(ref):
    p, copy = ref
    out = hidden.run_script(p, copy, REF_PROBE)
    assert "PROBE-DONE" in out and not [l for l in out.splitlines() if l.endswith("-OK") or l.startswith("FOUND")], out


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
_FORGER = r'''import glob, json, os, signal, subprocess
FORGED = '<testsuites><testsuite>' + ''.join(
    '<testcase classname="tests.hidden.test_step1_history" name="t%d"/>' % i for i in range(25)) + '</testsuite></testsuites>'
FRAMES = ("exit 2\n0\n" + "junit.xml %d\n" % len(FORGED) + FORGED).encode()
LOG = "/work/bakeoff-specs-dryrun/attempts.log"

def _log(what, r):
    with open(LOG, "a") as fh:
        fh.write(f"{what} {r}\n")

def _try(what, fn):
    try:
        fn(); r = "OK"
    except Exception as e:
        r = type(e).__name__
    _log(what, r)

def _write(path, data=FORGED):
    def f():
        with open(path, "w" if isinstance(data, str) else "wb") as fh:
            fh.write(data)
    return f

def _status(pid):
    return dict(l.split(":", 1) for l in open(f"/proc/{pid}/status").read().splitlines() if ":" in l)

def _ppid(pid):
    return int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1])

def main():
    if os.path.exists(LOG):
        return 0                                  # attack once per run; later calls just do nothing
    me = _status("self")
    _log("uid", me["Uid"].split()[0])
    for k in ("CapEff", "CapAmb", "CapPrm", "CapBnd", "NoNewPrivs"):
        _log("status-" + k, me[k].strip())
    _log("oom", open("/proc/self/oom_score_adj").read().strip())
    _try("lower-oom", _write("/proc/self/oom_score_adj", "0"))
    _log("env", json.dumps(sorted(os.environ)))
    pytest_pid = os.getppid()                      # uv run is our parent; pytest is ITS parent
    while _status(pytest_pid)["Uid"].split()[0] == str(os.getuid()):
        pytest_pid = _ppid(pytest_pid)
    entry_pid = _ppid(pytest_pid)
    _log("targets", f"pytest={pytest_pid} entry={entry_pid} cmd={open(f'/proc/{pytest_pid}/cmdline','rb').read()[:60]!r}")
    _try("write-out", _write("/out/junit.xml"))
    _try("write-results", _write("/results/junit.xml"))
    _try("write-tmp-results", _write("/tmp/results/junit.xml"))
    for name, pid in (("pid1", 1), ("entry", entry_pid), ("pytest", pytest_pid)):
        _try(f"frames-fd1-{name}", _write(f"/proc/{pid}/fd/1", FRAMES))
    for name, pid in (("pytest", pytest_pid), ("entry", entry_pid), ("pid1", 1)):
        _try(f"kill-{name}", lambda pid=pid: os.kill(pid, signal.SIGKILL))
    _try("list-harness", lambda: os.listdir("/harness"))
    _try("read-test", lambda: open("/harness/tests/hidden/test_step1_history.py").read())
    _try("read-test-via-cwd", lambda: open(f"/proc/{pytest_pid}/cwd/tests/hidden/test_step1_history.py").read())
    _try("list-results", lambda: os.listdir("/results"))
    for path in ("/opt/reference/.venv/bin/troupe", "/opt/reference/.venv/bin/python"):
        _try("exec-ref " + path, lambda path=path: subprocess.run([path, "--help"], check=True, capture_output=True))
    return 0
'''


def test_an_arm_that_forges_junit_and_kills_pytest_scores_zero(state, tmp_path):     # fix rounds 1 + 2
    p, dst = _skeleton("forger", _FORGER, tmp_path)
    s = hidden.run(p, dst, 1, tmp_path)
    assert (s.scoreable, s.attribution, s.total, s.passed) == (True, None, EXPECTED[1], 0), s.attribution
    rows = [l.split(" ", 1) for l in (dst / "attempts.log").read_text().splitlines()]
    got = dict(rows)
    assert len(got) == len(rows), "attempted twice"
    # the real pytest-launched path: its own uid, no capabilities at all, no new privileges, OOM-first
    assert got["uid"] == "1001"
    assert {got[f"status-{k}"] for k in ("CapEff", "CapAmb", "CapPrm", "CapBnd")} == {"0000000000000000"}
    assert got["status-NoNewPrivs"] == "1" and got["oom"] == "1000" and got["lower-oom"] != "OK"
    env = json.loads(got["env"])
    assert not [k for k in env if k.startswith(("TROUPE_REF", "PYTEST", "BAKEOFF", "PYTHONPATH"))], env
    assert "b'/opt/harness/bin/python" in got["targets"] and "pytest" in got["targets"], got["targets"]
    attacks = {k: v for k, v in got.items() if k.startswith(("write-", "frames-", "kill-", "list-", "read-", "exec-ref"))}
    assert len(attacks) == 3 + 3 + 3 + 2 + 2 + 2, sorted(attacks)
    assert not [k for k, v in attacks.items() if v == "OK"], attacks
    assert {got["kill-pytest"], got["kill-entry"], got["kill-pid1"]} == {"PermissionError"}


def test_an_arm_that_execs_the_reference_scores_zero(state, tmp_path):                  # fix round 2, item 1
    shim = r"""import os, subprocess, sys
PATHS = [["/opt/reference/.venv/bin/troupe"], ["/opt/reference/.venv/bin/python", "-m", "troupe_ref.cli"],
         ["uv", "run", "--offline", "--no-sync", "--quiet", "--project", "/opt/reference", "troupe"]]
def main():
    os.environ["PYTHONPATH"] = "/opt/reference/src"
    for argv in PATHS:
        try:
            r = subprocess.run(argv + sys.argv[1:], capture_output=True)
        except OSError:
            continue
        if r.returncode == 0 or r.stdout:
            sys.stdout.buffer.write(r.stdout); sys.stderr.buffer.write(r.stderr)
            return r.returncode
    for argv in PATHS[:2]:
        try:
            os.execv(argv[0], argv + sys.argv[1:])
        except OSError:
            pass
    return 2
"""
    p, dst = _skeleton("refshim", shim, tmp_path)
    s = hidden.run(p, dst, 1, tmp_path)
    assert (s.scoreable, s.total, s.passed) == (True, EXPECTED[1], 0), [t for t, o in s.tests.items() if o == "passed"]


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
