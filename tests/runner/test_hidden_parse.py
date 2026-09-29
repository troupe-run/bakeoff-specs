from pathlib import Path
from runner import docker, hidden
from runner.paths import Paths, REPO_ROOT

JUNIT = '''<testsuites><testsuite>
<testcase classname="tests.hidden.test_step2_sync" name="test_a"/>
<testcase classname="tests.hidden.test_step2_sync" name="test_b"><failure message="x"/></testcase>
<testcase classname="tests.hidden.test_step1_history" name="test_history_does_not_reconcile"/>
</testsuite></testsuites>'''

def test_junit_outcomes_are_parsed():
    assert hidden.parse_junit(JUNIT) == {"tests.hidden.test_step2_sync::test_a": "passed",
                                         "tests.hidden.test_step2_sync::test_b": "failed",
                                         "tests.hidden.test_step1_history::test_history_does_not_reconcile": "passed"}

def test_collect_only_node_ids_become_junit_ids():
    out = "tests/hidden/test_step2_sync.py::test_a\ntests/hidden/test_step2_sync.py::test_b[x]\n\n2 tests collected\n"
    assert hidden.parse_collected(out) == ["tests.hidden.test_step2_sync::test_a", "tests.hidden.test_step2_sync::test_b[x]"]

def test_allowlisted_new_tests_do_not_count_as_progress():
    tests = {"m::test_a": "failed", "m::test_history_does_not_reconcile": "passed"}
    s = hidden.summarise(2, tests, ["m::test_a", "m::test_history_does_not_reconcile"], flaky=[], flaky_arm=[], exit_code=1)
    assert s.new_passed == 1 and s.new_discriminating_passed == 0

def test_arm_flakes_count_as_failed_and_harness_flakes_as_flaky():         # review C-2
    tests = {"m::a": "failed", "m::b": "failed", "m::c": "passed"}
    s = hidden.summarise(2, tests, ["m::a", "m::b", "m::c"], flaky=["m::a"], flaky_arm=["m::b"], exit_code=1)
    assert (s.passed, s.failed, s.flaky, s.flaky_arm) == (1, 1, 1, 1)
    assert s.tests["m::b"] == "failed" and s.tests["m::a"] == "flaky"

def test_install_failed_fails_every_test_even_one_that_passed_vacuously():
    # found by the docker run: `uv run` on an uninstalled project exits 2 with stderr, which is exactly what
    # test_show_without_path_is_a_usage_error_before_step_3 asserts — the brief says every test fails
    tests = {"m::test_a": "failed", "m::test_usage": "passed"}
    s = hidden.summarise(1, tests, ["m::test_a", "m::test_usage"], flaky=[], flaky_arm=[], exit_code=1,
                         install_failed=True)
    assert (s.passed, s.failed, s.new_passed, s.new_discriminating_passed) == (0, 2, 0, 0)
    assert s.install_failed and s.tests == {"m::test_a": "failed", "m::test_usage": "failed"}

def test_flake_verdict_needs_three_failures_to_be_a_plain_failure():
    assert hidden.flake_verdict(["failed", "failed", "failed"]) == "failed"
    assert hidden.flake_verdict(["failed", "passed", "failed"]) == "flaky"

def test_node_id_for_a_rerun_is_the_file_path_form():
    assert hidden.to_nodeid("tests.hidden.test_step2_sync::test_b[x]") == "tests/hidden/test_step2_sync.py::test_b[x]"


# --- the run container's shape (controller rulings; review §3 NOTE 1, OD23) ---------------------------------

def _run_spec(tmp_state, *, out: bool = True):
    p = Paths("dryhp", "dryrun")
    copy = p.scratch / "01-a1" / "a" / "bakeoff-specs-dryrun"
    copy.mkdir(parents=True)
    with docker.recording() as got:
        docker.run_argv(hidden._spec(p, copy, ["true"], out=(tmp_state / "out") if out else None))
    return p, copy, got[0]

def test_the_run_container_has_no_network_and_no_host_login_variables(tmp_state):
    _, _, s = _run_spec(tmp_state)
    assert s.network == "none" and not s.proxy
    assert not {"USER", "LOGNAME"} & set(s.env)
    assert {k: s.env[k] for k in ("UV_OFFLINE", "UV_NO_SYNC", "PYTHONDONTWRITEBYTECODE", "UV_CACHE_DIR")} == \
        {"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1", "UV_CACHE_DIR": "/tmp/uv-cache"}

def test_the_harness_tests_are_mounted_read_only_and_the_copy_at_the_arms_own_path(tmp_state):
    _, copy, s = _run_spec(tmp_state)
    m = {x.ctr: x for x in s.mounts}
    assert m["/harness/tests"].ro and m["/harness/tests"].host == REPO_ROOT / "tests"
    assert m["/harness/pyproject.toml"].ro
    assert m["/work"].host == copy.parent and s.workdir == "/work/bakeoff-specs-dryrun"

def test_the_tester_never_mounts_scratch_or_the_arm_home_writable(tmp_state):
    p, copy, s = _run_spec(tmp_state)
    for x in s.mounts:
        if x.ro:
            continue
        assert x.host not in (p.scratch, p.home, p.base, p.work), x
        assert not Path(x.host).is_relative_to(p.home), x
        # the only writable things under scratch are the copy's own parent (and nothing above it)
        if Path(x.host).is_relative_to(p.scratch):
            assert x.host == copy.parent, x

def test_the_tester_home_is_fresh_and_empty_for_every_container(tmp_state):
    p = Paths("dryhp", "dryrun")
    copy = p.scratch / "x" / "a" / "bakeoff-specs-dryrun"; copy.mkdir(parents=True)
    homes = []
    for _ in range(2):
        s = hidden._spec(p, copy, ["true"])
        h = next(x.host for x in s.mounts if x.ctr == "/home/actor")
        assert list(Path(h).iterdir()) == []
        (Path(h) / "left-behind").write_text("x")
        homes.append(h)
    assert homes[0] != homes[1]

def test_without_out_there_is_no_out_mount(tmp_state):
    _, _, s = _run_spec(tmp_state, out=False)
    assert "/out" not in {x.ctr for x in s.mounts}
