"""Hidden tests against an arm, inside a tester container (OD23).

The arm's committed `refs/heads/main` is exported (in a container — never untarred on the host) into a copy
that sits at the same path the arm used (`/work/bakeoff-specs-<arm>`). A prep container (PyPI-only egress, no
harness anything) installs it; then every test run happens in a separate, network-less tester container, outside
every arm session.

Separation inside the tester (fix rounds 1 and 2):

- pytest runs as the HARNESS uid 1000 (`runner/tester_entry.sh`, passed as `bash -c` text) with only SETUID/
  SETGID (start the arm), KILL (signal its `watch` leader), DAC_OVERRIDE (read files the arm made private),
  SETPCAP (empty the arm's bounding set) and SYS_RESOURCE (pin the arm's oom_score_adj at 1000);
- the arm's CLI runs as uid 1001 via pytest's `--cmd-prefix` (`choom … -- setpriv … --`, both exec, so SIGTERM
  reaches the candidate exactly once) with every capability set empty and no_new_privs, and an ALLOWLISTED env
  (`tests/hidden/driver.py`: no TROUPE_REF_*, PYTEST_*, harness paths);
- both uids carry the same login name (uid 1001 gets a passwd/group entry with uid 1000's name, and
  `LOGNAME`/`USER` are that name), so `getpass`/`pwd` defaults match (Plan 1's login-name note);
- nothing the arm could read or write is bind-mounted for the harness (Docker Desktop bind mounts ignore
  ownership, measured): the hidden suite is streamed on stdin into `/harness`, and results are written to
  `/results`, both tmpfs owned by uid 1000, mode 0700, created before any arm code runs; results leave as
  length-framed records on the entry script's stdout and are parsed in memory;
- the reference (`/opt/reference`, the answer key) is uid-1000-only, 0700, in the image layer; reference runs
  (flake classification) run it as the harness uid;
- a run is scored only if it is consistent: pytest exit 0 or 1, exit 0 iff no failure in the junit, and the
  junit's tests exactly the collected set (collected with no arm code mounted). An abnormal death with resource
  evidence is `arm-resource` (re-run once, then all-failed); a run over budget is `arm-timeout` (all failed);
  anything else abnormal is a `harness-fault` (not scoreable).

The remaining PLAN-2 NOTEs are resolved as before: one network namespace (`127.0.0.1` for `served`), no
`docker exec` (env reaches the CLI), `--init` reaps, the container is removed.
"""
from __future__ import annotations
import functools, json, os, shutil, stat, subprocess, time, uuid, xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from runner import config, docker, egress, gitops, repo
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT
from harness.validate_suites import allowlisted   # single source for allowlist matching (review m10)

ENV = {"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1", "UV_CACHE_DIR": "/tmp/uv-cache",
       "HOME": "/home/actor", "UV_PYTHON_DOWNLOADS": "never"}
PYTEST = ["/opt/harness/bin/python", "-m", "pytest"]
MAIN = "refs/heads/main"
HARNESS_UID, ARM_UID = 1000, 1001
HARNESS_CAPS = ("SETUID", "SETGID", "KILL", "DAC_OVERRIDE", "SETPCAP", "SYS_RESOURCE")
# SETPCAP: drop the arm's bounding set; SYS_RESOURCE: pin the arm's oom_score_adj at 1000 so it cannot lower it.
ENTRY = REPO_ROOT / "runner" / "tester_entry.sh"      # passed as `bash -c` text, not mounted
RESULTS = "/results"
RESULT_CAPS = {"exit": 64, "timed_out": 64, "resources": 64_000, "junit.xml": 16_000_000, "pytest.log": 8_100_000}
OWN_TMPFS = "rw,uid=1000,gid=1000,mode=0700,size=64m"     # harness-only: the arm can neither enter nor fill it
HARNESS_TMPFS = (f"/harness:{OWN_TMPFS}", f"/results:{OWN_TMPFS}")
BUNDLE = ("pyproject.toml", "tests/__init__.py", "tests/conftest.py", "tests/hidden")
ARM_OOM_SCORE_ADJ = 1000
PER_COMMAND = 60       # driver.Cli's per-command timeout: the whole-run budget scales with it
MARGIN = 300
OUTER_GRACE = 120      # docker's own timeout: after the in-container one, so it only fires if the container hangs


# --- pure ----------------------------------------------------------------------------------------------------

def parse_junit(xml: str | bytes) -> dict[str, str]:
    """Same outcome rule as `harness/validate_suites.run` (Plan 1's validated instrument; review m10)."""
    out = {}
    for tc in ET.fromstring(xml).iter("testcase"):
        o = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
            "skipped" if tc.find("skipped") is not None else "passed"
        out[f"{tc.get('classname')}::{tc.get('name')}"] = o
    return out


def parse_collected(text: str) -> list[str]:
    ids = []
    for line in text.splitlines():
        if "::" in line and line.startswith("tests/"):
            path, _, name = line.strip().partition("::")
            ids.append(path.removesuffix(".py").replace("/", ".") + "::" + name)
    return ids


def to_nodeid(junit_id: str) -> str:
    mod, _, name = junit_id.partition("::")
    return mod.replace(".", "/") + ".py::" + name


def flake_verdict(outcomes: list[str]) -> str:
    return "failed" if all(o == "failed" for o in outcomes) else "flaky"


def run_timeout(n_tests: int) -> int:
    return n_tests * PER_COMMAND + MARGIN


def with_arm_user(passwd: str, group: str) -> tuple[str, str, str]:
    """The image's passwd/group plus uid/gid 1001 under uid 1000's name (duplicate name, different uid)."""
    row = next(l.split(":") for l in passwd.splitlines() if l.split(":")[2:3] == [str(HARNESS_UID)])
    name = row[0]
    pw = passwd if passwd.endswith("\n") else passwd + "\n"
    gr = group if group.endswith("\n") else group + "\n"
    return (pw + f"{name}:x:{ARM_UID}:{ARM_UID}:{row[4]}:{row[5]}:{row[6]}\n", gr + f"{name}:x:{ARM_UID}:\n", name)


def _drop_to_arm() -> list[str]:
    """OOM-first (set by the harness, which holds SYS_RESOURCE, so the arm cannot lower it), then uid 1001 with
    empty inheritable, ambient AND bounding sets. `choom` and `setpriv` both exec."""
    return ["choom", "-n", str(ARM_OOM_SCORE_ADJ), "--",
            "setpriv", f"--reuid={ARM_UID}", f"--regid={ARM_UID}", "--clear-groups", "--inh-caps=-all",
            "--ambient-caps=-all", "--bounding-set=-all", "--"]


def arm_prefix(impl: str) -> list[str]:
    """The arm's CLI as uid 1001 with no capabilities; every wrapper execs, so the `uv run` leader is the process
    `Watching` signals (one SIGTERM, as in Plan 1's selftest)."""
    return [*_drop_to_arm(), "uv", "run", "--quiet", "--project", impl, "troupe"]


def _pytest_argv(args: list[str], impl: str, reference: bool = False) -> list[str]:
    """Arm runs: the CLI as uid 1001, no TROUPE_REF_STEP. Reference runs (flake classification): the reference is
    reachable only by the harness uid, so it runs as uid 1000 and gets its step (fix round 2, item 1 (b))."""
    prefix = ["uv", "run", "--quiet", "--project", impl, "troupe"] if reference else arm_prefix(impl)
    return [*PYTEST, *args, "--impl", impl, "--cmd-prefix", " ".join(prefix), *(["--forward-ref-step"] if reference else []),
            "-q", "-p", "no:cacheprovider", "--rootdir", "/harness", f"--junitxml={RESULTS}/junit.xml"]


def _bundle_files() -> list[Path]:
    out = []
    for rel in BUNDLE:
        f = REPO_ROOT / rel
        out += sorted(x for x in f.rglob("*.py") if "__pycache__" not in x.parts) if f.is_dir() else [f]
    return out


def harness_bundle() -> bytes:
    """The hidden suite + its config as `<path> <size>\n<bytes>` records, streamed on the tester's stdin into the
    uid-1000 0700 /harness tmpfs (never bind-mounted: Docker Desktop mounts are readable by every uid)."""
    parts = []
    for f in _bundle_files():
        if f.is_symlink():
            raise ValueError(f"harness bundle refuses a link: {f}")
        data = f.read_bytes()
        parts.append(f"{f.relative_to(REPO_ROOT).as_posix()} {len(data)}\n".encode() + data)
    return b"".join(parts)


def unpack_bundle(blob: bytes) -> dict[str, bytes]:
    """Host-side mirror of the entry script's unpacker (used by tests)."""
    out, i = {}, 0
    while i < len(blob):
        nl = blob.index(b"\n", i)
        name, size = blob[i:nl].decode().rsplit(" ", 1)
        out[name] = blob[nl + 1:nl + 1 + int(size)]
        i = nl + 1 + int(size)
    return out


class ResultsError(ValueError):
    pass


def unpack_results(blob: bytes) -> dict[str, bytes]:
    """The entry script's stdout: records `<name> <size>\n<size bytes>`, read in memory. Only known names, once
    each, within size caps, exact lengths, nothing trailing. (No tar parsing anywhere in runner/.)"""
    out: dict[str, bytes] = {}
    i = 0
    if not blob:
        raise ResultsError("no results on stdout")
    while i < len(blob):
        nl = blob.find(b"\n", i, i + 64)
        if nl < 0:
            raise ResultsError(f"malformed results header at byte {i}")
        try:
            name_b, size_b = blob[i:nl].split(b" ")
            name, size = name_b.decode("ascii"), int(size_b)
        except ValueError as e:
            raise ResultsError(f"malformed results header at byte {i}") from e
        if name not in RESULT_CAPS:
            raise ResultsError(f"unexpected results member {name!r}")
        if name in out:
            raise ResultsError(f"duplicate results member {name}")
        if not 0 <= size <= RESULT_CAPS[name]:
            raise ResultsError(f"results member {name} is {size} bytes (cap {RESULT_CAPS[name]})")
        if nl + 1 + size > len(blob):
            raise ResultsError(f"results member {name} is truncated")
        out[name] = blob[nl + 1:nl + 1 + size]
        i = nl + 1 + size
    return out


def resource_evidence(res: dict[str, bytes]) -> list[str]:
    """What the entry script saw after pytest: cgroup OOM kills, the pids limit hit, /tmp full, ENOSPC in the log."""
    ev = []
    text = res.get("resources", b"").decode(errors="replace")
    mem, _, rest = text.partition("--pids")
    pids, _, tmp = rest.partition("--tmp")
    kv = lambda block: dict(l.split()[:2] for l in block.splitlines() if len(l.split()) >= 2)
    if int(kv(mem).get("oom_kill", "0") or 0) > 0:
        ev.append(f"oom-kill:{kv(mem)['oom_kill']}")
    if int(kv(pids).get("max", "0") or 0) > 0:
        ev.append(f"pids-max:{kv(pids)['max']}")
    cols = tmp.split()
    if len(cols) >= 4 and cols[3].isdigit() and int(cols[3]) < 1024:
        ev.append("tmp-full")
    if not ev and b"No space left on device" in res.get("pytest.log", b""):
        ev.append("enospc-in-log")
    return ev


def assess(collected: list[str], res: dict[str, bytes]) -> tuple[dict[str, str], int, str | None]:
    """(tests, pytest exit code, attribution). Scored only when consistent; `arm-timeout` fails every collected
    test. A completed run with a valid junit is scored even under resource pressure (the arm's own ENOSPC
    failures are failures). An abnormal pytest death WITH resource evidence is `arm-resource` (run() re-runs it
    once); anything else abnormal is a `harness-fault` with no tests."""
    try:
        code = int(res.get("exit", b"").strip())
    except ValueError:
        return {}, -1, "harness-fault: no exit code"
    if "timed_out" in res:
        return {t: "failed" for t in collected}, code, "arm-timeout"
    if code not in (0, 1) or "junit.xml" not in res:
        if resource_evidence(res):
            return {}, code, "arm-resource"
        return {}, code, f"harness-fault: pytest exit {code}" if code not in (0, 1) else "harness-fault: no junit"
    try:
        tests = parse_junit(res["junit.xml"])
    except ET.ParseError as e:
        return {}, code, f"harness-fault: unparseable junit ({e})"
    if set(tests) != set(collected):
        extra, missing = sorted(set(tests) - set(collected)), sorted(set(collected) - set(tests))
        return {}, code, f"harness-fault: junit/collection mismatch (+{extra[:5]} -{missing[:5]})"
    failures = any(o == "failed" for o in tests.values())
    if code == 0 and failures:
        return {}, code, "harness-fault: exit 0 with failures in junit"
    if code == 1 and not failures:
        return {}, code, "harness-fault: exit 1 without failures in junit"
    return tests, code, None


@dataclass
class Summary:
    step: int
    total: int
    passed: int
    failed: int
    flaky: int
    flaky_arm: int
    tests: dict[str, str]
    new_at_step: list[str]
    new_passed: int
    new_discriminating_passed: int
    exit_code: int
    install_failed: bool = False
    scoreable: bool = True
    attribution: str | None = None      # None | "arm-timeout" | "arm-resource" | "harness-fault: <why>"
    skipped: int = 0
    resource_evidence: list = field(default_factory=list)   # one list per full-suite attempt

    def write(self, out_dir: Path) -> None:
        (out_dir / "hidden").mkdir(parents=True, exist_ok=True)
        (out_dir / "hidden" / "summary.json").write_text(json.dumps(asdict(self), indent=2, sort_keys=True))


def summarise(step, tests, new_at_step, flaky, flaky_arm, exit_code, install_failed=False,
              collected: list[str] | None = None, attribution: str | None = None,
              resource_evidence: list | None = None) -> Summary:
    """Harness flakes (`flaky`: flaky on the reference too) are neither passed nor failed; arm flakes
    (`flaky_arm`: stable on the reference) count as failed for the arm and are recorded (review C-2).
    `install_failed` (prep failed twice): every test counts as failed. Skipped tests (none in the hidden suite
    today) count in `total` and `skipped`, neither passed nor failed. A `harness-fault` is not scoreable: no
    outcomes, `total` = the collected count. `install_failed` wins over a harness-fault (fix round 2, item 4)."""
    ev = resource_evidence or []
    if install_failed:    # the arm's result: every test fails (a test may pass vacuously on uv's own exit 2)
        final = {t: "failed" for t in (tests or collected or [])}
    elif attribution is not None and attribution.startswith("harness-fault"):
        return Summary(step, len(collected or []), 0, 0, 0, 0, {}, [], 0, 0, exit_code, install_failed,
                       scoreable=False, attribution=attribution, resource_evidence=ev)
    else:
        final = {t: ("flaky" if t in flaky else "failed" if t in flaky_arm else o) for t, o in tests.items()}
    new = [t for t in new_at_step if t in final]
    return Summary(step, len(final), sum(o == "passed" for o in final.values()),
                   sum(o == "failed" for o in final.values()), sum(o == "flaky" for o in final.values()),
                   len([t for t in flaky_arm if t in final]), final, new, sum(final[t] == "passed" for t in new),
                   sum(final[t] == "passed" and not allowlisted(t) for t in new),
                   exit_code, install_failed, True, attribution, sum(o == "skipped" for o in final.values()), ev)


@dataclass
class Prepared:
    hidden_copy: Path
    quality_copy: Path | None
    prep: dict = field(default_factory=dict)


# --- containers ----------------------------------------------------------------------------------------------

def _rmtree(path: Path) -> None:
    """Delete a copy or tester home without following links; arm code may have left read-only dirs."""
    def fix(func, p_, exc):
        os.chmod(os.path.dirname(p_), stat.S_IRWXU)
        if func is not os.unlink and os.path.isdir(p_) and not os.path.islink(p_):
            os.chmod(p_, stat.S_IRWXU); shutil.rmtree(p_, onexc=fix)
        else:
            func(p_)
    if os.path.lexists(path):
        shutil.rmtree(path, onexc=fix)


def _lockfile(copy: Path) -> bool:
    """A lockfile only if `uv.lock` is a regular file (lstat: a link is not followed on the host)."""
    try:
        return stat.S_ISREG(os.lstat(copy / "uv.lock").st_mode)
    except FileNotFoundError:
        return False


def _tester_root(p: Paths) -> Path:
    """Harness-owned tester dirs (fresh homes, accounts, the reference-flake dummy): beside, never inside,
    scratch/home."""
    return p.base / "tester"


@functools.lru_cache(maxsize=None)
def _image_accounts(image: str) -> tuple[str, str]:
    def cat(f: str) -> str:
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--label", "bakeoff.accounts=1", image,
                            "cat", f], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"cannot read {f} from {image}: {r.stderr[:300]}")
        return r.stdout
    return cat("/etc/passwd"), cat("/etc/group")


def _accounts(p: Paths, image: str) -> tuple[Path, Path, str]:
    pw, gr, name = with_arm_user(*_image_accounts(image))
    d = _tester_root(p) / "etc"
    d.mkdir(parents=True, exist_ok=True)
    (d / "passwd").write_text(pw)
    (d / "group").write_text(gr)
    return d / "passwd", d / "group", name


def _spec(p: Paths, copy: Path | None, cmd: list[str], *, mode: str, network: str = "none", proxy: bool = False,
          env: dict | None = None, workdir: str | None = None, timeout: int = 600, name: str = "tester") -> RunSpec:
    """`mode`: "prep" (uid 1000, no caps, no harness mounts), "harness" (the entry script runs `cmd` — pytest —
    as uid 1000; the arm is uid 1001 via --cmd-prefix) or "script" (`cmd` as uid 1001, no caps). Creates a
    fresh, empty home for this one container (removed by `_run`)."""
    if mode not in ("prep", "harness", "script"):
        raise ValueError(mode)
    pins = config.load_pins()
    image = pins.images["tester"]
    home = _tester_root(p) / f"home-{uuid.uuid4().hex[:12]}"
    home.mkdir(parents=True)
    mounts = [Mount(home, "/home/actor", False)]
    if copy is not None:
        mounts.insert(0, Mount(copy.parent, "/work", False))
    e = {**ENV, **(env or {})}
    user, caps, tmpfs, stdin = "1000:1000", (), (), False
    if mode != "prep":
        passwd, group, login = _accounts(p, image)
        mounts += [Mount(passwd, "/etc/passwd", True), Mount(group, "/etc/group", True)]
        e |= {"LOGNAME": login, "USER": login, "BAKEOFF_SHARE_THEATRE_WITH_ARM": "1"}
        user = "0:0"
        if mode == "harness":
            caps = HARNESS_CAPS
            low = ",".join(f"+{c.lower()}" for c in HARNESS_CAPS)
            cmd = ["setpriv", f"--reuid={HARNESS_UID}", f"--regid={HARNESS_UID}", "--clear-groups",
                   f"--inh-caps={low}", f"--ambient-caps={low}", "--",
                   "bash", "-c", ENTRY.read_text(), "entry", str(timeout), *cmd]
            tmpfs, stdin = HARNESS_TMPFS, True        # the suite arrives on stdin (harness_bundle)
        else:                                          # the arm uid alone: no harness dirs, no reference, no caps
            caps = ("SETUID", "SETGID", "SETPCAP", "SYS_RESOURCE")
            cmd = [*_drop_to_arm(), *cmd]
    return RunSpec(name=f"bk-{name}-{p.pass_}-{p.arm}-{int(time.time() * 1000) % 10**8}-{uuid.uuid4().hex[:4]}",
                   image=image, label=f"bakeoff.run={p.pass_}/{p.arm}", network=network, mounts=mounts, env=e,
                   workdir=workdir or (f"/work/{copy.name}" if copy is not None else "/"), cmd=cmd, stdin=stdin,
                   limits=pins.limits, proxy=proxy, user=user, cap_add=caps, tmpfs=tmpfs)


def _run(s: RunSpec, timeout: float):
    try:
        return docker.run(s, input=harness_bundle() if s.stdin else None, timeout=timeout)
    finally:
        for m in s.mounts:
            if m.ctr == "/home/actor":
                _rmtree(m.host)


def _sync(p: Paths, copy: Path, st: egress.Stage, with_mutmut: bool) -> dict:
    lock = _lockfile(copy)
    cmd = "uv sync --frozen" if lock else "uv sync"
    if with_mutmut:       # mutmut only in copy B (review C-1)
        cmd += " && uv pip install --python .venv/bin/python --require-hashes -r /opt/mutmut-requirements.txt"
    rec: dict = {"lockfile": lock, "command": cmd, "tries": []}
    for _ in (1, 2):      # a failed sync is retried once; a second failure is install_failed (the arm's result)
        r = _run(_spec(p, copy, ["bash", "-c", cmd], mode="prep", network=st.net, proxy=True,
                       env={"UV_OFFLINE": "0", "UV_NO_SYNC": "0"}, name="prep"), timeout=1800)
        rec["tries"].append({"exit": r.returncode, "log": (r.stdout + r.stderr).decode(errors="replace")[-4000:]})
        if r.returncode == 0:
            rec["ok"] = True
            return rec
    rec["ok"] = False
    return rec


def prepare_copy(p: Paths, copy: Path, out_dir: Path, label: str, quality_copy: Path | None = None,
                 source: dict | None = None) -> Prepared:
    """Install an already-exported copy (and optionally copy B) in a PyPI-only prep container."""
    pins = config.load_pins()
    rec: dict = {**(source or {})}
    with egress.Stage(p.pass_, p.arm, "tester", pins.egress_tester_prep, out_dir / "egress-tester.log") as st:
        rec["hidden"] = _sync(p, copy, st, False)
        if quality_copy is not None:
            rec["quality"] = _sync(p, quality_copy, st, True)
    (out_dir / "hidden").mkdir(parents=True, exist_ok=True)
    (out_dir / "hidden" / f"prep-{label}.json").write_text(json.dumps(rec, indent=2))
    return Prepared(copy, quality_copy, rec)


def prepare(p: Paths, sha: str, label: str, out_dir: Path, with_quality: bool = False,
            require_main: bool = True) -> Prepared:
    """Export the committed tree (in a container) into copy A (`scratch/<label>/a/`) and, with `with_quality`,
    copy B (`…/b/`), then install. Hidden tests run on exactly `refs/heads/main`: `sha` may be that ref, and
    otherwise must be the commit it points to (`require_main=False` only for a deliberate re-test of a
    recorded commit)."""
    main = gitops.main_sha(p)
    commit = main if sha == MAIN else sha
    if commit is None:
        raise RuntimeError(f"{p.pass_}/{p.arm}: the arm repo has no {MAIN}")
    if require_main and commit != main:
        raise ValueError(f"{p.pass_}/{p.arm}: hidden tests run on {MAIN} ({main}), not {sha}")
    base = p.scratch / label
    _rmtree(base)
    a = base / "a" / f"bakeoff-specs-{p.arm}"
    repo.export(p, commit, a)
    b = None
    if with_quality:
        b = base / "b" / f"bakeoff-specs-{p.arm}"
        repo.export(p, commit, b)
    return prepare_copy(p, a, out_dir, label, b, source={"ref": sha, "commit": commit, "main": main})


def _pytest(p: Paths, copy: Path | None, args: list[str], *, impl: str | None = None, env: dict | None = None,
            timeout: int = 600, reference: bool = False) -> tuple[dict[str, bytes] | None, str | None]:
    """pytest in the tester as the harness uid; returns (results members, error). Never raises for what the
    run itself did: a hung container or unreadable results is reported as an error string."""
    impl = impl or (f"/work/{copy.name}" if copy is not None else "/nonexistent")
    s = _spec(p, copy, _pytest_argv(args, impl, reference), mode="harness", env=env, workdir="/harness",
              timeout=timeout)
    try:
        r = _run(s, timeout=timeout + 30 + OUTER_GRACE)
    except subprocess.TimeoutExpired:
        return None, f"container did not finish within {timeout + 30 + OUTER_GRACE}s"
    try:
        return unpack_results(r.stdout), None
    except ResultsError as e:
        return None, f"{e} (docker exit {r.returncode}: {r.stderr.decode(errors='replace')[-300:]})"


def _collect(p: Paths, step: int, first_only: bool) -> list[str]:
    """Collection with NO arm code mounted (collect-only of tests/hidden imports no arm code)."""
    args = ["tests/hidden", "--step", str(step), "--collect-only"] + (["--first-step-only", str(step)] if first_only else [])
    res, err = _pytest(p, None, args)
    if err or res is None or res.get("exit", b"").strip() != b"0":
        raise RuntimeError(f"hidden collection failed: {err or (res or {}).get('pytest.log', b'')[-800:]!r}")
    return parse_collected(res["pytest.log"].decode(errors="replace"))


def run_script(p: Paths, copy: Path, script: str) -> str:
    """A shell script in the tester sandbox as the ARM uid (network none, no caps); used by the hand-edit probe."""
    return _run(_spec(p, copy, ["bash", "-c", script], mode="script"), timeout=600).stdout.decode(errors="replace")


def _single(p: Paths, copy: Path | None, step: int, nodeid: str, junit_id: str, *, impl: str | None = None,
            env: dict | None = None, reference: bool = False) -> str:
    res, err = _pytest(p, copy, [nodeid, "--step", str(step)], impl=impl, env=env, timeout=run_timeout(1),
                       reference=reference)
    if err or res is None:
        return "failed"
    tests, _, attribution = assess([junit_id], res)
    return "passed" if attribution is None and tests.get(junit_id) == "passed" else "failed"


def classify_flaky(p: Paths, step: int, nodeid: str) -> str:
    """Run the test 3x alone against the reference image copy (`/opt/reference`, `TROUPE_REF_STEP=step`):
    any failure there = a harness flake ("harness"); stable there = an arm flake ("arm") (review C-2)."""
    mod, _, name = nodeid.partition("::")
    junit_id = mod.removesuffix(".py").replace("/", ".") + "::" + name
    for _ in range(3):
        if _single(p, None, step, nodeid, junit_id, impl="/opt/reference", env={"TROUPE_REF_STEP": str(step)},
                   reference=True) != "passed":
            return "harness"
    return "arm"


def run(p: Paths, copy: Path, step: int, out_dir: Path, install_failed: bool = False) -> Summary:
    """Collect (no arm code), run the step's suite as the harness uid with the arm as its own uid, re-run each
    failure twice alone in fresh containers, classify flakes against the reference. Host records
    (`hidden/{summary,flake}.json`, `pytest.log`, `junit.xml`) are written only here, never in a mounted dir."""
    hd = out_dir / "hidden"
    hd.mkdir(parents=True, exist_ok=True)
    collected = _collect(p, step, first_only=False)
    new_at_step = _collect(p, step, first_only=True)
    evidence: list[list[str]] = []
    for attempt in (1, 2):         # an `arm-resource` death is re-run once (fix round 2, item 3)
        res, err = _pytest(p, copy, ["tests/hidden", "--step", str(step)], timeout=run_timeout(len(collected)))
        if res is not None:
            (hd / "pytest.log").write_bytes(res.get("pytest.log", b""))
            if "junit.xml" in res:
                (hd / "junit.xml").write_bytes(res["junit.xml"])
        if err is not None or res is None:
            tests, code, attribution = {}, -1, f"harness-fault: {err}"
            break
        tests, code, attribution = assess(collected, res)
        evidence.append(resource_evidence(res))
        if attribution != "arm-resource":
            break
    else:                          # arm-resource twice: the step scores all-failed, evidence recorded
        tests = {t: "failed" for t in collected}
    flaky: list[str] = []
    flaky_arm: list[str] = []
    reruns: dict[str, list[str]] = {}
    if attribution is None and not install_failed:
        for t, o in tests.items():
            if o != "failed":
                continue
            outcomes = ["failed"] + [_single(p, copy, step, to_nodeid(t), t) for _ in range(2)]
            reruns[t] = outcomes
            if flake_verdict(outcomes) == "flaky":
                (flaky if classify_flaky(p, step, to_nodeid(t)) == "harness" else flaky_arm).append(t)
    (hd / "flake.json").write_text(json.dumps({"reruns": reruns, "harness_flaky": flaky, "arm_flaky": flaky_arm,
                                               "report": [f"flaky-test:{to_nodeid(t)}" for t in flaky]}, indent=2))
    s = summarise(step, tests, new_at_step, flaky, flaky_arm, code, install_failed, collected, attribution, evidence)
    s.write(out_dir)
    return s
