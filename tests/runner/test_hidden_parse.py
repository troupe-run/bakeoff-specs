import os
from pathlib import Path
import pytest
from harness import validate_suites
from runner import docker, gitops, hidden, repo
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT
from tests.hidden.theatre import share_with_arm
from runner import bundle_unpack

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
    caps = {"SETUID", "SETGID", "KILL", "DAC_OVERRIDE", "SETPCAP", "SYS_RESOURCE"}
    assert s.user == "0:0" and set(s.cap_add) == caps
    assert s.cmd[:4] == ["setpriv", "--reuid=1000", "--regid=1000", "--clear-groups"]
    assert "--ambient-caps=+setuid,+setgid,+kill,+dac_override,+setpcap,+sys_resource" in s.cmd
    i = s.cmd.index("--")
    assert s.cmd[i + 1:i + 6] == ["bash", "-c", hidden.ENTRY.read_text(), "entry", hidden.UNPACKER.read_text()]


def test_the_arm_cli_runs_under_its_own_uid_with_no_caps_and_setpriv_execs_it():
    pre = hidden.arm_prefix("/work/bakeoff-specs-dryrun")
    assert pre == ["choom", "-n", "1000", "--",            # set by the harness (SYS_RESOURCE): the arm cannot lower it
                   "setpriv", "--reuid=1001", "--regid=1001", "--clear-groups", "--inh-caps=-all",
                   "--ambient-caps=-all", "--bounding-set=-all", "--",
                   "uv", "run", "--quiet", "--project", "/work/bakeoff-specs-dryrun", "troupe"]
    argv = hidden._pytest_argv(["tests/hidden", "--step", "1"], "/work/bakeoff-specs-dryrun")
    assert "--cmd-prefix=" + " ".join(pre) in argv
    assert "--junitxml=/results/junit.xml" in argv and "--forward-ref-step" not in argv


# 2026-10-02 (pass 1): pytest's early conftest discovery runs before plugin options are registered, so a SEPARATE
# option value that is an existing path (`--impl /work/<arm>`) became a test-path anchor and the ARM's
# `conftest.py`/`tests/conftest.py` were imported into the harness-uid pytest. Every option value is joined with `=`.
_ARGV_CASES = [(["tests/hidden", "--step", "3"], "/work/bakeoff-specs-dryrun", False),
               (["tests/hidden", "--step", "3", "--collect-only", "--first-step-only", "3"], "/nonexistent", False),
               (["tests/hidden/test_step1_history.py::test_x[a]", "--step", "1"], "/work/bakeoff-specs-dryrun", False),
               (["tests/hidden/test_step1_history.py::test_x", "--step", "1"], "/opt/reference", True),
               ([hidden.SUBSTITUTE_TEST, "--step", "6"], "/work/bakeoff-specs-dryrun", False)]


def _after_pytest(argv: list[str]) -> list[str]:
    i = argv.index("pytest")
    assert argv[i - 2:i + 1] == hidden.PYTEST
    return argv[i + 1:]


@pytest.mark.parametrize("args,impl,reference", _ARGV_CASES)
def test_hidden_pytest_argv_passes_impl_and_cmd_prefix_joined_with_equals(args, impl, reference):
    argv = hidden._pytest_argv(args, impl, reference)
    assert f"--impl={impl}" in argv
    assert [a for a in argv if a.startswith("--cmd-prefix=")]
    assert not {"--impl", "--cmd-prefix", "--rootdir", "--junitxml", "--step", "--first-step-only"} & set(argv)
    assert impl not in argv


@pytest.mark.parametrize("args,impl,reference", _ARGV_CASES)
def test_hidden_pytest_argv_has_no_bare_value_but_hidden_test_paths_and_ini_pins(args, impl, reference):
    rest = _after_pytest(hidden._pytest_argv(args, impl, reference))
    bare = [a for i, a in enumerate(rest) if not a.startswith("-") and rest[i - 1] != "-o"]
    assert bare and all(a == "tests/hidden" or a.startswith("tests/hidden/") for a in bare), bare
    assert [a for i, a in enumerate(rest) if i and rest[i - 1] == "-o"] == hidden.PYTEST_PINS[2::2]


def test_hidden_pytest_argv_joins_the_callers_step_options():
    rest = _after_pytest(hidden._pytest_argv(["tests/hidden", "--step", "3", "--first-step-only", "3"], "/x"))
    assert rest[:3] == ["tests/hidden", "--step=3", "--first-step-only=3"]


@pytest.mark.parametrize("args", [["tests/hidden", "/work/bakeoff-specs-dryrun"],      # a bare absolute path
                                  ["/harness/tests/hidden"], ["tests/hidden/../../work/x"], ["tests/hiddenx"],
                                  ["tests/hidden", "--step"],                            # a value-taking option, no value
                                  ["tests/hidden", "--impl", "/work/x"], ["tests/hidden", "--impl=/work/x"],
                                  ["tests/hidden", "--cmd-prefix=x"], ["tests/hidden", "--rootdir=/work"],
                                  ["tests/hidden", "--junitxml=/work/j.xml"], ["tests/hidden", "--confcutdir=/work"],
                                  ["tests/hidden", "--step", "1", "x"], ["tests/hidden", "-k", "x"]])
def test_hidden_pytest_argv_refuses_a_bare_value_or_a_harness_owned_option(args):
    with pytest.raises(ValueError):
        hidden._pytest_argv(args, "/work/bakeoff-specs-dryrun")


def test_reference_runs_are_the_harness_uid_and_forward_the_ref_step():      # fix round 2, item 1 (b)
    argv = hidden._pytest_argv(["tests/hidden"], "/opt/reference", reference=True)
    assert "--cmd-prefix=uv run --quiet --project /opt/reference troupe" in argv
    assert "--forward-ref-step" in argv


def test_both_uids_see_the_same_login_name_in_env_and_passwd(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "harness")
    assert s.env["LOGNAME"] == s.env["USER"] == "actor" and s.env["BAKEOFF_SHARE_THEATRE_WITH_ARM"] == "1"
    m = {x.ctr: x for x in s.mounts}
    assert m["/etc/passwd"].ro and m["/etc/group"].ro and "BAKEOFF_ARM_UNDER_TEST" not in s.env
    assert "actor:x:1001:1001:" in Path(m["/etc/passwd"].host).read_text()


def test_no_container_mounts_an_out_dir_the_arm_could_write(tmp_state, accounts):
    for mode in ("harness", "script", "prep"):
        _, _, s = _spec(tmp_state, mode)
        assert "/out" not in {x.ctr for x in s.mounts}, mode


def test_the_prep_container_has_no_harness_mounts_and_no_privileges(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "prep")
    assert not [x for x in s.mounts if x.ctr.startswith(("/harness", "/etc"))]
    # fix round 3: arm build code (uv sync runs the arm's build backend) is untrusted, like the arm itself
    assert s.user == "1001:1001" and s.cap_add == () and s.tmpfs == ()


def test_collection_runs_with_no_arm_code_mounted(tmp_state, accounts):
    _, _, s = _spec(tmp_state, "harness", copy=False)
    assert "/work" not in {x.ctr for x in s.mounts}


def test_the_hidden_tests_are_never_bind_mounted_but_streamed_into_a_harness_only_tmpfs(tmp_state, accounts):
    # fix round 2, item 2: Docker Desktop bind mounts cannot be protected by permissions
    _, copy, s = _spec(tmp_state, "harness")
    m = {x.ctr: x for x in s.mounts}
    assert not [c for c in m if c.startswith("/harness")]
    assert "/harness:rw,uid=1000,gid=1000,mode=0700,size=64m" in s.tmpfs
    assert "/results:rw,uid=1000,gid=1000,mode=0700,size=160m" in s.tmpfs         # item 3: not the shared /tmp
    assert s.stdin
    assert m["/work"].host == copy.parent and s.network == "none" and not s.proxy
    assert {k: s.env[k] for k in ("UV_OFFLINE", "UV_NO_SYNC", "PYTHONDONTWRITEBYTECODE", "UV_CACHE_DIR")} == \
        {"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1", "UV_CACHE_DIR": "/tmp/uv-cache"}


def test_the_harness_bundle_is_exactly_the_hidden_suite_and_its_config():
    files = dict(bundle_unpack.parse(hidden.harness_bundle()))
    every = {f.relative_to(REPO_ROOT).as_posix() for f in (REPO_ROOT / "tests" / "hidden").rglob("*")
             if f.is_file() and "__pycache__" not in f.parts}                         # fix round 3: every file
    assert set(files) == every | {"pyproject.toml", "tests/__init__.py", "tests/conftest.py"}
    assert files["tests/hidden/driver.py"] == (REPO_ROOT / "tests/hidden/driver.py").read_bytes()


def test_the_bundle_refuses_a_link_loudly(tmp_path, monkeypatch):
    (tmp_path / "tests" / "hidden").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("")
    for f in ("tests/__init__.py", "tests/conftest.py", "tests/hidden/a.py"):
        (tmp_path / f).write_text("x")
    (tmp_path / "tests" / "hidden" / "data.yml").write_text("k: v")
    (tmp_path / "tests" / "hidden" / "link.py").symlink_to(tmp_path / "pyproject.toml")
    monkeypatch.setattr(hidden, "REPO_ROOT", tmp_path)
    with pytest.raises(ValueError, match="link"):
        hidden.harness_bundle()
    (tmp_path / "tests" / "hidden" / "link.py").unlink()
    assert "tests/hidden/data.yml" in dict(bundle_unpack.parse(hidden.harness_bundle()))


def _rec(name: str, data: bytes, size: int | None = None) -> bytes:
    return f"{name} {len(data) if size is None else size}\n".encode() + data


@pytest.mark.parametrize("blob,why", [
    (_rec("a.py", b"x", size=-1), "size"),
    (_rec("a.py", b"x" * 10, size=11), "truncated"),
    (_rec("a.py", b"x") + _rec("b.py", b"yy")[:-1], "truncated"),
    (_rec("a.py", b"x", size=bundle_unpack.MAX_FILE + 1), "size"),
    (_rec("/etc/x", b"x"), "path"),
    (_rec("a/../b", b"x"), "path"),
    (_rec("a//b", b"x"), "path"),
    (_rec("a.py", b"x") + _rec("a.py", b"x"), "duplicate"),
    (b"no header at all", "header"),
])
def test_the_in_container_unpacker_rejects_bad_records(blob, why):             # fix round 3, minor
    with pytest.raises(ValueError, match=why):
        bundle_unpack.parse(blob)


def test_the_in_container_unpacker_writes_files_with_0700_dirs(tmp_path):     # renamed, fix round 4
    bundle_unpack.write(_rec("tests/hidden/a.py", b"A") + _rec("pyproject.toml", b"P")
                        + _rec("tests/hidden/data/deep/x.txt", b"X"), tmp_path)
    assert (tmp_path / "tests/hidden/a.py").read_bytes() == b"A" and (tmp_path / "pyproject.toml").read_bytes() == b"P"
    made = [d for d in tmp_path.rglob("*") if d.is_dir()]                    # Task 18 m3: EVERY created directory
    assert sorted(d.relative_to(tmp_path).as_posix() for d in made) == [
        "tests", "tests/hidden", "tests/hidden/data", "tests/hidden/data/deep"]
    assert all(d.stat().st_mode & 0o777 == 0o700 for d in made), [(d, oct(d.stat().st_mode)) for d in made]
    assert all(f.stat().st_mode & 0o777 == 0o600 for f in tmp_path.rglob("*") if f.is_file())


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
    assert a.count("--tmpfs") == 1
    b = docker.run_argv(dataclasses.replace(base, user="0:0", cap_add=("KILL", "SETUID"), tmpfs=("/r:mode=0700",)))
    assert b[b.index("/r:mode=0700") - 1] == "--tmpfs"
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


# --- fix round 2 ---------------------------------------------------------------------------------------------

def test_install_failed_wins_over_a_harness_fault():                          # item 4
    s = hidden.summarise(1, {}, [], flaky=[], flaky_arm=[], exit_code=2, install_failed=True,
                         collected=["m::a", "m::b"], attribution="harness-fault: pytest exit 2")
    assert s.scoreable and s.install_failed and (s.total, s.passed, s.failed) == (2, 0, 2)


RES_OOM = b"low 0\nhigh 0\nmax 0\noom 1\noom_kill 1\noom_group_kill 0\n--pids\nmax 0\n--tmp\ntmpfs 4194304 12 4194292 1% /tmp\n"
RES_PIDS = b"oom_kill 0\n--pids\nmax 3\n--tmp\ntmpfs 4194304 12 4194292 1% /tmp\n"
RES_FULL = b"oom_kill 0\n--pids\nmax 0\n--tmp\ntmpfs 4194304 4194304 0 100% /tmp\n"
RES_CALM = b"oom_kill 0\n--pids\nmax 0\n--tmp\ntmpfs 4194304 12 4194292 1% /tmp\n"


def test_resource_evidence_is_read_from_the_cgroup_and_tmp_records():
    assert hidden.resource_evidence({"resources": RES_OOM}) == ["oom-kill:1"]
    assert hidden.resource_evidence({"resources": RES_PIDS}) == ["pids-max:3"]
    assert hidden.resource_evidence({"resources": RES_FULL}) == ["tmp-full"]
    assert hidden.resource_evidence({"resources": RES_CALM, "pytest.log": b"OSError: [Errno 28] No space left on device"}) == ["enospc-in-log"]
    assert hidden.resource_evidence({"resources": RES_CALM}) == []


def test_a_pytest_death_with_resource_evidence_is_arm_resource_not_harness_fault():   # item 3 ruling
    tests, code, attribution = hidden.assess(["m::a", "m::b"], {"exit": b"137\n", "resources": RES_OOM})
    assert (tests, code, attribution) == ({}, 137, "arm-resource")
    _, _, attribution = hidden.assess(["m::a", "m::b"], {"exit": b"137\n", "resources": RES_CALM})
    assert attribution.startswith("harness-fault")


def test_a_completed_run_with_a_valid_junit_is_scored_even_under_resource_pressure():
    tests, code, attribution = hidden.assess(["m::a", "m::b"], {"exit": b"1\n", "junit.xml": J_FAIL, "resources": RES_FULL})
    assert (tests, attribution) == ({"m::a": "passed", "m::b": "failed"}, None)


def test_timed_out_needs_the_timeout_exit_code_as_well_as_the_elapsed_time():       # item 5 (entry script)
    text = hidden.ENTRY.read_text()
    assert '"$rc" = 124' in text and '"$rc" = 137' in text


def _fake_run(monkeypatch, results):
    calls = []
    monkeypatch.setattr(hidden, "_collect", lambda p, step, first_only: ["m::a", "m::b"] if not first_only else ["m::b"])
    def fake(p, copy, args, **kw):
        calls.append(args)
        return results.pop(0), None
    monkeypatch.setattr(hidden, "_pytest", fake)
    return calls


def test_arm_resource_is_rerun_once_and_a_clean_rerun_is_scored(tmp_state, monkeypatch):
    calls = _fake_run(monkeypatch, [{"exit": b"137\n", "resources": RES_OOM},
                                     {"exit": b"0\n", "junit.xml": J_PASS, "resources": RES_CALM}])
    s = hidden.run(Paths("dryhp", "dryrun"), tmp_state / "c", 1, tmp_state / "out")
    assert len(calls) == 2 and (s.scoreable, s.passed, s.attribution) == (True, 2, None)
    assert s.resource_evidence == [["oom-kill:1"], []]


def test_arm_resource_twice_scores_the_step_all_failed_with_the_evidence(tmp_state, monkeypatch):
    calls = _fake_run(monkeypatch, [{"exit": b"137\n", "resources": RES_OOM},
                                     {"exit": b"137\n", "resources": RES_PIDS}])
    s = hidden.run(Paths("dryhp", "dryrun"), tmp_state / "c", 1, tmp_state / "out")
    assert len(calls) == 2
    assert (s.scoreable, s.attribution, s.total, s.passed, s.failed) == (True, "arm-resource", 2, 0, 2)
    assert s.resource_evidence == [["oom-kill:1"], ["pids-max:3"]]
    import json
    assert json.loads((tmp_state / "out" / "hidden" / "summary.json").read_text())["resource_evidence"] == s.resource_evidence


# --- the arm's environment is an allowlist (item 1) ---------------------------------------------------------

from tests.hidden import driver


def test_the_arm_gets_an_allowlisted_environment_only(monkeypatch):
    for k in list(os.environ):
        monkeypatch.delenv(k)
    keep = {"PATH": "/usr/bin", "HOME": "/home/actor", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TMPDIR": "/tmp",
            "UV_OFFLINE": "1", "UV_CACHE_DIR": "/tmp/uv-cache", "LOGNAME": "actor", "USER": "actor", "TZ": "UTC",
            "PYTHONDONTWRITEBYTECODE": "1"}
    drop = {"TROUPE_REF_STEP": "3", "TROUPE_REF_ANYTHING": "x", "PYTEST_CURRENT_TEST": "t", "PYTEST_ADDOPTS": "-x",
            "BAKEOFF_SHARE_THEATRE_WITH_ARM": "1", "PYTHONPATH": "/harness", "SECRET_TOKEN": "s", "TROUPE_ACTOR": "a"}
    for k, v in {**keep, **drop}.items():
        monkeypatch.setenv(k, v)
    env = driver.Cli(["x"])._env({"TROUPE_ACTOR": "alice"})
    assert env == {**keep, "TROUPE_ACTOR": "alice"}


def test_the_reference_step_is_forwarded_only_when_asked(monkeypatch):
    monkeypatch.setenv("TROUPE_REF_STEP", "3")
    assert "TROUPE_REF_STEP" not in driver.Cli(["x"])._env(None)
    assert driver.Cli(["x"], forward=("TROUPE_REF_STEP",))._env(None)["TROUPE_REF_STEP"] == "3"


def test_the_ref_step_is_forwarded_for_the_reference_only(tmp_path):
    ref = REPO_ROOT / "reference"
    assert driver.forwarded(str(ref), None, False, ref) == ("TROUPE_REF_STEP",)      # Plan 1 host runs
    assert driver.forwarded("/work/bakeoff-specs-x", "setpriv ... troupe", False, ref) == ()
    assert driver.forwarded("/work/bakeoff-specs-x", None, False, ref) == ()
    assert driver.forwarded("/opt/reference", "uv run ...", True, ref) == ("TROUPE_REF_STEP",)


# --- fix round 3 -----------------------------------------------------------------------------------------------

def test_the_reference_image_is_used_only_by_reference_runs(tmp_state, accounts):
    pins = hidden.config.load_pins()
    assert pins.images["tester_ref"] != pins.images["tester"]
    p = Paths("dryhp", "dryrun")
    copy = _copy(p)
    seen = {}
    for mode in ("prep", "harness", "script"):
        seen[mode] = hidden._spec(p, copy, ["true"], mode=mode).image
    seen["reference"] = hidden._spec(p, None, ["true"], mode="harness", reference=True).image
    assert seen == {"prep": pins.images["tester"], "harness": pins.images["tester"], "script": pins.images["tester"],
                    "reference": pins.images["tester_ref"]}
    with pytest.raises(ValueError):                    # the reference image never gets an arm copy
        hidden._spec(p, copy, ["true"], mode="harness", reference=True)


def test_reference_runs_go_through_the_reference_image(tmp_state, accounts, monkeypatch):
    got = []
    monkeypatch.setattr(hidden, "_run", lambda s, timeout: got.append(s) or type("R", (), {"stdout": b"", "stderr": b"", "returncode": 1})())
    hidden.classify_flaky(Paths("dryhp", "dryrun"), 1, "tests/hidden/test_step1_history.py::test_x")
    assert got and {s.image for s in got} == {hidden.config.load_pins().images["tester_ref"]}
    assert not [m for s in got for m in s.mounts if m.ctr == "/work"]


def test_the_cli_caps_what_it_exposes_to_assertions():
    small = "hello\n"
    assert driver.cap(small) == small
    big = "a" * 100_000 + "TAIL"
    c = driver.cap(big)
    assert c.endswith("TAIL") and len(c.encode()) <= driver.CAP + 200
    assert c.startswith("[... ") and "truncated" in c.splitlines()[0]


def test_the_cli_result_is_capped_on_both_streams(tmp_path):
    cli = driver.Cli([__import__("sys").executable, "-c",
                      "import sys; sys.stdout.write('o' * 300000 + 'END'); sys.stderr.write('e' * 300000 + 'ERR'); sys.exit(3)"])
    r = cli("show", theatre=tmp_path)
    assert r.code == 3 and r.out.endswith("END") and r.err.endswith("ERR")
    assert len(r.out.encode()) <= driver.CAP + 200 and len(r.err.encode()) <= driver.CAP + 200


def test_the_watcher_readiness_failure_message_is_bounded(tmp_path):         # fix round 4: behaviour, not grep
    from tests.hidden.watcher import Watching
    cli = driver.Cli([__import__("sys").executable, "-c",
                      "import sys; sys.stderr.write('e' * 300000 + 'LAST'); sys.exit(2)"])
    with pytest.raises(AssertionError) as ei:
        with Watching(cli, tmp_path, ready_timeout=15):
            pass
    msg = str(ei.value)
    assert "never printed its readiness line" in msg and msg.endswith("LAST")
    assert "bytes truncated" in msg and len(msg.encode()) <= driver.CAP + 300


# --- fix round 4: result classification — a harness problem is never scored against an arm -------------------

def _raised(blob: bytes) -> "hidden.ResultsError":
    with pytest.raises(hidden.ResultsError) as ei:
        hidden.unpack_results(blob)
    return ei.value


MARK = driver.cap("z" * (driver.CAP + 5000)).splitlines()[0].encode()       # exactly what Cli writes


def test_the_marker_the_classifier_looks_for_is_the_one_cli_writes():
    assert hidden.TRUNCATION_MARKER.search(MARK) and MARK.startswith(b"[... ")
    assert not hidden.TRUNCATION_MARKER.search(b"[... many bytes truncated ...]")


@pytest.mark.parametrize("blob", [
    b"exit -1\n",                                                          # negative size
    _frames({"exit": b"0"}) + b"junit.xml -5\n",                           # negative size, scoreable member
    b"resources 70000\n" + b"r" * 70000,                                   # harness-only member over its cap
    b"exit 999\n" + MARK * 40,                                             # harness-only member over its cap, marked
], ids=["exit-negative", "junit-negative", "resources-70000", "exit-999-marked"])
def test_a_bad_size_on_a_harness_only_member_or_a_negative_size_is_a_harness_fault(blob):
    e = _raised(blob)
    assert hidden._frames_error(e).startswith("harness-fault")


@pytest.mark.parametrize("blob", [b"exit -1\n", _frames({"exit": b"0"}) + b"junit.xml -5\n"], ids=["exit", "junit"])
def test_a_negative_size_is_a_malformed_results_frame(blob):                   # Task 18 m1
    e = _raised(blob)
    assert "malformed results frame" in str(e) and e.overflow is None


def test_an_oversized_junit_with_the_cli_marker_in_its_tail_is_arm_output():
    cap = hidden.RESULT_CAPS["junit.xml"]
    body = b"<testsuites>" + b"x" * cap + b"<failure message='" + MARK + b"\ntail'/>"
    msg = hidden._frames_error(_raised(_frames({"exit": b"1\n"}) + f"junit.xml {len(body)}\n".encode() + body))
    assert msg.startswith("arm-output"), msg
    assert "junit.xml" in msg and str(len(body)) in msg and "marker found" in msg


def test_an_oversized_junit_without_the_marker_is_a_harness_fault():
    cap = hidden.RESULT_CAPS["junit.xml"]
    body = b"<testsuites>" + b"x" * (cap + 10)
    msg = hidden._frames_error(_raised(f"junit.xml {len(body)}\n".encode() + body))
    assert msg.startswith("harness-fault"), msg
    assert "junit.xml" in msg and str(len(body)) in msg and "marker not found" in msg


def test_an_oversized_pytest_log_whose_readable_tail_has_the_marker_is_arm_output():
    size = hidden.RESULT_CAPS["pytest.log"] + 1
    msg = hidden._frames_error(_raised(f"pytest.log {size}\n".encode() + b"E  AssertionError: " + MARK))
    assert msg.startswith("arm-output") and "pytest.log" in msg and str(size) in msg and "marker found" in msg


def test_arm_output_keeps_its_detail_in_the_attribution_and_the_summary(tmp_state, monkeypatch):
    monkeypatch.setattr(hidden, "_collect", lambda p, step, first_only: ["m::a", "m::b"] if not first_only else [])
    size = hidden.RESULT_CAPS["junit.xml"] + 7
    err = hidden._frames_error(_raised(f"junit.xml {size}\n".encode() + MARK))
    monkeypatch.setattr(hidden, "_pytest", lambda *a, **k: (None, err))
    s = hidden.run(Paths("dryhp", "dryrun"), tmp_state / "c", 1, tmp_state / "out")
    assert (s.scoreable, s.passed, s.failed) == (True, 0, 2)
    assert s.attribution.startswith("arm-output") and s.attribution != "arm-output"
    assert "junit.xml" in s.attribution and str(size) in s.attribution and "marker found" in s.attribution
    import json
    assert json.loads((tmp_state / "out" / "hidden" / "summary.json").read_text())["attribution"] == s.attribution


def test_an_oversized_result_without_the_marker_is_not_scored(tmp_state, monkeypatch):
    monkeypatch.setattr(hidden, "_collect", lambda p, step, first_only: ["m::a", "m::b"] if not first_only else [])
    err = hidden._frames_error(_raised(f"junit.xml {hidden.RESULT_CAPS['junit.xml'] + 1}\n".encode() + b"no mark"))
    monkeypatch.setattr(hidden, "_pytest", lambda *a, **k: (None, err))
    s = hidden.run(Paths("dryhp", "dryrun"), tmp_state / "c", 1, tmp_state / "out")
    assert not s.scoreable and s.attribution.startswith("harness-fault") and s.tests == {}


def test_a_malformed_result_is_still_a_harness_fault():
    assert hidden._frames_error(_raised(b"not framed at all")).startswith("harness-fault")


RES_RESULTS_FULL = b"oom_kill 0\n--pids\nmax 0\n--tmp\ntmpfs 1 0 1 0% /tmp\n--results\ntmpfs 131072 131072 0 100% /results\n"


def test_a_full_results_tmpfs_with_the_marker_is_arm_output():
    res = {"exit": b"3\n", "resources": RES_RESULTS_FULL, "pytest.log": b"F" * 100 + b"\nE  " + MARK + b"\n"}
    tests, _, attribution = hidden.assess(["m::a"], res)
    assert tests == {"m::a": "failed"} and attribution.startswith("arm-output")
    assert "/results full" in attribution and "pytest.log" in attribution and "marker found" in attribution


def test_a_full_results_tmpfs_without_the_marker_is_a_harness_fault():
    tests, _, attribution = hidden.assess(["m::a"], {"exit": b"3\n", "resources": RES_RESULTS_FULL, "pytest.log": b"boom"})
    assert tests == {} and attribution.startswith("harness-fault") and "marker not found" in attribution


def test_pytest_is_pinned_quiet_with_assertion_truncation_on(tmp_state, accounts):
    argv = hidden._pytest_argv(["tests/hidden", "--step", "1"], "/work/bakeoff-specs-dryrun")
    assert argv[:7] == ["env", "-u", "CI", "-u", "BUILD_NUMBER", "-u", "PYTEST_ADDOPTS"]   # pytest's CI switch
    assert argv[7:10] == hidden.PYTEST
    assert "-q" in argv and not [a for a in argv if a.startswith("-v") or a.startswith("--verbos")]
    for o in ("truncation_limit_lines=8", "truncation_limit_chars=640", "verbosity_assertions=auto"):
        assert argv[argv.index(o) - 1] == "-o"
    for bad in (["-v"], ["-vv"], ["--verbose"], ["--verbosity=2"], ["-o", "verbosity_assertions=2"],
                ["--override-ini=truncation_limit_lines=0"], ["-c", "x.toml"], ["-p", "x"],
                ["-xvv"], ["-rv"], ["-xqq"], ["-sp", "x"], ["-xo", "a=b"], ["-xc", "x.toml"]):   # Task 18 m2: clusters
        with pytest.raises(ValueError):
            hidden._pytest_argv(["tests/hidden", *bad], "/work/bakeoff-specs-dryrun")
    _, _, s = _spec(tmp_state, "harness", cmd=argv)
    assert not {"CI", "BUILD_NUMBER", "PYTEST_ADDOPTS"} & set(s.env)
    assert s.cmd[s.cmd.index("entry") + 3:] == argv            # entry <unpacker> <timeout> <this argv>, verbatim


def test_the_bundled_pytest_config_does_not_undo_the_pins():
    import tomllib
    ini = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    assert "-v" not in ini.get("addopts", "") and not {"truncation_limit_lines", "truncation_limit_chars",
                                                       "verbosity_assertions"} & set(ini)


# ---- follow-up 4: an acceptance run that did not complete is assessed like the main suite ------------------------------

def _acc(monkeypatch, results):
    calls = []

    def fake(p, copy, args, **k):
        calls.append(args)
        r = results[min(len(calls), len(results)) - 1]
        return (r, None) if isinstance(r, dict) else (None, r)
    monkeypatch.setattr(hidden, "_pytest", fake)
    return calls


def test_an_acceptance_run_killed_for_resources_twice_is_the_arms_failure(monkeypatch):
    calls = _acc(monkeypatch, [{"exit": b"137", "resources": RES_OOM}])
    r = hidden.run_acceptance(None, None, 6, "body")
    assert (r["outcome"], r["attribution"]) == ("failed", "arm-resource") and len(calls) == 2
    assert r["resource_evidence"] == [["oom-kill:1"], ["oom-kill:1"]]


def test_an_acceptance_run_killed_once_then_completed_is_scored_and_keeps_its_evidence(monkeypatch):
    junit = b'<testsuite><testcase classname="tests.hidden.test_zz_substitute" name="test_x"/></testsuite>'
    _acc(monkeypatch, [{"exit": b"137", "resources": RES_OOM}, {"exit": b"0", "resources": RES_CALM,
                                                                  "junit.xml": junit}])
    r = hidden.run_acceptance(None, None, 6, "body")
    assert r["outcome"] == "passed" and r["resource_evidence"] == [["oom-kill:1"], []]


def test_an_acceptance_run_over_budget_is_the_arms_failure(monkeypatch):
    _acc(monkeypatch, [{"exit": b"124", "timed_out": b"", "resources": RES_CALM}])
    r = hidden.run_acceptance(None, None, 6, "body")
    assert (r["outcome"], r["attribution"]) == ("failed", "arm-timeout")


def test_an_acceptance_run_that_died_without_resource_evidence_is_still_an_error(monkeypatch):
    _acc(monkeypatch, [{"exit": b"2", "resources": RES_CALM}])
    r = hidden.run_acceptance(None, None, 6, "body")
    assert r["outcome"] == "error" and r["attribution"].startswith("harness-fault")
