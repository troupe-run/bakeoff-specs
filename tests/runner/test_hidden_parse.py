import os
from pathlib import Path
import pytest
from harness import validate_suites
from runner import docker, gitops, hidden, repo
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT
from tests.hidden.theatre import share_with_arm

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



# --- fix round 1: privilege separation inside the tester (reviewer forged a score via /out/junit.xml) --------

PASSWD = "root:x:0:0:root:/root:/bin/bash\nactor:x:1000:1000::/home/actor:/bin/bash\n"
GROUP = "root:x:0:\nactor:x:1000:\n"


@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setattr(hidden, "_image_accounts", lambda image: (PASSWD, GROUP))


def _copy(p: Paths) -> Path:
    copy = p.scratch / "01-a1" / "a" / "bakeoff-specs-dryrun"
    copy.mkdir(parents=True, exist_ok=True)
    return copy


def _spec(tmp_state, mode, *, copy=True, cmd=("true",)):
    p = Paths("dryhp", "dryrun")
    c = _copy(p) if copy else None
    with docker.recording() as got:
        docker.run_argv(hidden._spec(p, c, list(cmd), mode=mode))
    return p, c, got[0]


def test_the_arm_uid_gets_the_same_login_name_as_the_harness_uid():
    pw, gr, name = hidden.with_arm_user(PASSWD, GROUP)
    assert name == "actor"
    assert pw.splitlines()[-1] == "actor:x:1001:1001::/home/actor:/bin/bash" and pw.startswith(PASSWD)
    assert gr.splitlines()[-1] == "actor:x:1001:" and gr.startswith(GROUP)


def test_pytest_starts_as_the_harness_uid_with_only_the_caps_it_needs(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "harness")
    assert s.user == "0:0" and set(s.cap_add) == {"SETUID", "SETGID", "KILL", "DAC_OVERRIDE"}
    assert s.cmd[:4] == ["setpriv", "--reuid=1000", "--regid=1000", "--clear-groups"]
    assert "--ambient-caps=+setuid,+setgid,+kill,+dac_override" in s.cmd
    i = s.cmd.index("--")
    assert s.cmd[i + 1:i + 3] == ["bash", "/harness/entry.sh"]


def test_the_arm_cli_runs_under_its_own_uid_with_no_caps_and_setpriv_execs_it():
    pre = hidden.arm_prefix("/work/bakeoff-specs-dryrun")
    assert pre == ["setpriv", "--reuid=1001", "--regid=1001", "--clear-groups", "--inh-caps=-all",
                   "--ambient-caps=-all", "--", "uv", "run", "--quiet", "--project", "/work/bakeoff-specs-dryrun",
                   "troupe"]
    argv = hidden._pytest_argv(["tests/hidden", "--step", "1"], "/work/bakeoff-specs-dryrun")
    assert argv[argv.index("--cmd-prefix") + 1] == " ".join(pre)
    assert "--junitxml=/tmp/results/junit.xml" in argv


def test_both_uids_see_the_same_login_name_in_env_and_passwd(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "harness")
    assert s.env["LOGNAME"] == s.env["USER"] == "actor" and s.env["BAKEOFF_SHARE_THEATRE_WITH_ARM"] == "1"
    m = {x.ctr: x for x in s.mounts}
    assert m["/etc/passwd"].ro and m["/etc/group"].ro
    assert "actor:x:1001:1001:" in Path(m["/etc/passwd"].host).read_text()


def test_no_container_mounts_an_out_dir_the_arm_could_write(tmp_state, accounts):
    for mode in ("harness", "script", "prep"):
        _, _, s = _spec(tmp_state, mode)
        assert "/out" not in {x.ctr for x in s.mounts}, mode


def test_the_prep_container_has_no_harness_mounts_and_no_privileges(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "prep")
    assert not [x for x in s.mounts if x.ctr.startswith(("/harness", "/etc"))]
    assert s.user == "1000:1000" and s.cap_add == ()


def test_collection_runs_with_no_arm_code_mounted(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "harness", copy=False)
    assert "/work" not in {x.ctr for x in s.mounts}


def test_the_harness_tests_are_read_only_and_the_copy_at_the_arms_own_path(tmp_state, accounts):
    _, copy, s = _spec(tmp_state, "harness")
    m = {x.ctr: x for x in s.mounts}
    assert m["/harness/tests"].ro and m["/harness/tests"].host == REPO_ROOT / "tests"
    assert m["/harness/pyproject.toml"].ro and m["/harness/entry.sh"].ro
    assert m["/work"].host == copy.parent and s.network == "none" and not s.proxy
    assert {k: s.env[k] for k in ("UV_OFFLINE", "UV_NO_SYNC", "PYTHONDONTWRITEBYTECODE", "UV_CACHE_DIR")} == \
        {"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1", "UV_CACHE_DIR": "/tmp/uv-cache"}


def test_the_tester_never_mounts_scratch_or_the_arm_home_writable(tmp_state, accounts):
    for mode in ("harness", "script", "prep"):
        p, copy, s = _spec(tmp_state, mode)
        for x in s.mounts:
            if x.ro:
                continue
            assert x.host not in (p.scratch, p.home, p.base, p.work), x
            assert not Path(x.host).is_relative_to(p.home), x
            if Path(x.host).is_relative_to(p.scratch):
                assert x.host == copy.parent, x


def test_the_tester_home_is_fresh_and_empty_for_every_container(tmp_state, accounts):
    p = Paths("dryhp", "dryrun")
    copy = _copy(p)
    homes = []
    for _ in range(2):
        s = hidden._spec(p, copy, ["true"], mode="harness")
        h = next(x.host for x in s.mounts if x.ctr == "/home/actor")
        assert list(Path(h).iterdir()) == []
        (Path(h) / "left-behind").write_text("x")
        homes.append(h)
    assert homes[0] != homes[1]


def test_run_argv_takes_the_user_and_added_caps_from_the_spec_and_defaults_are_unchanged(tmp_state):
    base = RunSpec(name="n", image="i", label="l", network="none", mounts=[], env={}, workdir="/", cmd=["x"],
                   stdin=False, limits=hidden.config.load_pins().limits, proxy=False)
    a = docker.run_argv(base)
    assert a[a.index("--user") + 1] == "1000:1000" and "--cap-add" not in a
    import dataclasses
    b = docker.run_argv(dataclasses.replace(base, user="0:0", cap_add=("KILL", "SETUID")))
    assert b[b.index("--user") + 1] == "0:0"
    assert b[b.index("--cap-drop") + 1] == "ALL" and [b[i + 1] for i, v in enumerate(b) if v == "--cap-add"] == ["KILL", "SETUID"]


# --- results come back on stdout as length-framed records the harness wrote (no tarfile in runner/, see
# test_gitops.test_the_host_never_untars_or_tars_an_arm_tree); parsed in memory --------------------------------

def _frames(members: dict[str, bytes]) -> bytes:
    return b"".join(f"{n} {len(d)}\n".encode() + d for n, d in members.items())


def test_results_are_read_from_exact_length_frames():
    got = hidden.unpack_results(_frames({"exit": b"1\n", "junit.xml": b"<x/>", "pytest.log": b"log\nmore"}))
    assert got == {"exit": b"1\n", "junit.xml": b"<x/>", "pytest.log": b"log\nmore"}


@pytest.mark.parametrize("blob", [
    _frames({"exit": b"0", "../junit.xml": b"<x/>"}),
    _frames({"exit": b"0", "surprise": b"x"}),
    _frames({"exit": b"0", "junit.xml": b"x" * (hidden.RESULT_CAPS["junit.xml"] + 1)}),
    _frames({"exit": b"0"}) + _frames({"exit": b"1"}),                    # duplicate
    _frames({"exit": b"0"})[:-1],                                          # truncated
    b"exit 1\n0" + b"trailing",
    b"",
    b"not framed at all",
])
def test_unknown_names_oversize_duplicates_truncation_and_garbage_are_refused(blob):
    with pytest.raises(hidden.ResultsError):
        hidden.unpack_results(blob)


# --- scoring: exit code and junit must agree; the junit set must be the collected set ----------------------

J_PASS = b'<testsuites><testsuite><testcase classname="m" name="a"/><testcase classname="m" name="b"/></testsuite></testsuites>'
J_FAIL = b'<testsuites><testsuite><testcase classname="m" name="a"/><testcase classname="m" name="b"><failure/></testcase></testsuite></testsuites>'


def test_a_consistent_run_is_scored():
    tests, code, attribution = hidden.assess(["m::a", "m::b"], {"exit": b"1\n", "junit.xml": J_FAIL})
    assert (tests, code, attribution) == ({"m::a": "passed", "m::b": "failed"}, 1, None)


@pytest.mark.parametrize("res,why", [
    ({"exit": b"0\n", "junit.xml": J_FAIL}, "exit 0 with failures"),
    ({"exit": b"1\n", "junit.xml": J_PASS}, "exit 1 without failures"),
    ({"exit": b"137\n", "junit.xml": J_PASS}, "pytest exit 137"),
    ({"exit": b"2\n"}, "pytest exit 2"),
    ({"exit": b"0\n"}, "no junit"),
    ({"exit": b"0\n", "junit.xml": b"<oops"}, "unparseable junit"),
])
def test_an_inconsistent_or_abnormal_run_is_a_harness_fault_not_a_score(res, why):
    tests, code, attribution = hidden.assess(["m::a", "m::b"], res)
    assert tests == {} and attribution.startswith("harness-fault") and why in attribution


def test_a_junit_that_is_not_the_collected_set_is_refused():
    tests, _, attribution = hidden.assess(["m::a", "m::b", "m::c"], {"exit": b"0\n", "junit.xml": J_PASS})
    assert tests == {} and "junit/collection mismatch" in attribution and "m::c" in attribution


def test_a_timed_out_run_fails_every_collected_test_and_says_so():
    tests, code, attribution = hidden.assess(["m::a", "m::b"], {"exit": b"124\n", "timed_out": b"", "junit.xml": J_PASS})
    assert tests == {"m::a": "failed", "m::b": "failed"} and attribution == "arm-timeout"


def test_an_unscoreable_run_writes_a_summary_with_its_attribution():
    s = hidden.summarise(1, {}, [], flaky=[], flaky_arm=[], exit_code=2, collected=["m::a"],
                         attribution="harness-fault: pytest exit 2")
    assert (s.scoreable, s.total, s.passed, s.failed, s.attribution) == (False, 1, 0, 0, "harness-fault: pytest exit 2")
    t = hidden.summarise(1, {"m::a": "failed"}, [], flaky=[], flaky_arm=[], exit_code=124, collected=["m::a"],
                         attribution="arm-timeout")
    assert t.scoreable and t.failed == 1 and t.attribution == "arm-timeout"


def test_the_run_timeout_scales_with_the_number_of_tests():
    assert hidden.run_timeout(1) == hidden.PER_COMMAND + hidden.MARGIN
    assert hidden.run_timeout(161) == 161 * hidden.PER_COMMAND + hidden.MARGIN


# --- minors ------------------------------------------------------------------------------------------------

def test_allowlist_matching_is_the_harness_validators_own():
    assert hidden.allowlisted is validate_suites.allowlisted
    tests = {"m::test_history_does_not_reconcile": "passed", "m::test_history_does_not_reconcile[p]": "passed"}
    s = hidden.summarise(2, tests, list(tests), flaky=[], flaky_arm=[], exit_code=0)
    assert s.new_passed == 2 and s.new_discriminating_passed == 1      # a parametrised id is not the entry


def test_a_symlinked_uv_lock_is_not_a_lockfile(tmp_path):
    (tmp_path / "real.lock").write_text("x")
    (tmp_path / "uv.lock").symlink_to(tmp_path / "real.lock")
    assert hidden._lockfile(tmp_path) is False
    (tmp_path / "uv.lock").unlink(); (tmp_path / "uv.lock").write_text("x")
    assert hidden._lockfile(tmp_path) is True


def test_prepare_refuses_a_commit_that_is_not_main(tmp_state, monkeypatch):
    monkeypatch.setattr(gitops, "main_sha", lambda p: "a" * 40)
    monkeypatch.setattr(repo, "export", lambda *a: pytest.fail("exported a non-main commit"))
    with pytest.raises(ValueError, match="refs/heads/main"):
        hidden.prepare(Paths("dryhp", "dryrun"), "b" * 40, "x", tmp_state / "out")


def test_sharing_a_theatre_opens_it_and_only_traverse_on_its_own_ancestors(tmp_path):
    top = tmp_path / "top"; mid = top / "mid"; root = mid / "t"
    root.mkdir(parents=True)
    for d in (tmp_path, top, mid, root):
        d.chmod(0o700)
    share_with_arm(root, top)
    assert root.stat().st_mode & 0o777 == 0o777
    assert (mid.stat().st_mode & 0o777, top.stat().st_mode & 0o777) == (0o711, 0o711)
    assert tmp_path.stat().st_mode & 0o777 == 0o700            # nothing above `top` is touched
