"""Hidden tests against an arm, inside a tester container (OD23).

The arm's committed `refs/heads/main` is exported (in a container — never untarred on the host) into a copy
that sits at the same path the arm used (`/work/bakeoff-specs-<arm>`). A prep container (PyPI-only egress, no
harness anything) installs it; then every test run happens in a separate, network-less tester container, outside
every arm session.

Separation inside the tester (fix rounds 1-3):

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
- the reference (`/opt/reference`, the answer key) exists only in its own image, `bakeoff-tester-ref` (fix round
  3): the tester image every arm-code container uses (prep, harness, script) holds no reference at all. Only
  the harness's reference runs (flake classification, `_spec(..., reference=True)`, never with an arm copy) use
  it, running the reference as the harness uid (uid-1000-only, 0700, in the image layer);
- a run is scored only if it is consistent: pytest exit 0 or 1, exit 0 iff no failure in the junit, and the
  junit's tests exactly the collected set (collected with no arm code mounted). An abnormal death with resource
  evidence is `arm-resource` (re-run once, then all-failed); a run over budget is `arm-timeout` (all failed);
  results overflow (a junit/log member over its cap, or `/results` full) is `arm-output` (all failed) only when
  `driver.Cli`'s truncation marker corroborates it (fix round 4); anything else abnormal is a `harness-fault`
  (not scoreable).

The remaining PLAN-2 NOTEs are resolved as before: one network namespace (`127.0.0.1` for `served`), no
`docker exec` (env reaches the CLI), `--init` reaps, the container is removed.
"""
from __future__ import annotations
import functools, json, os, re, shutil, stat, subprocess, time, uuid, xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from runner import config, docker, egress, gitops, repo
from runner.faults import HarnessFault
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT
from harness.validate_suites import allowlisted   # single source for allowlist matching (review m10)

ENV = {"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1", "UV_CACHE_DIR": "/tmp/uv-cache",
       "HOME": "/home/actor", "UV_PYTHON_DOWNLOADS": "never"}
PYTEST = ["/opt/harness/bin/python", "-m", "pytest"]
# pytest's assertion truncation is what bounds the reprs in failure messages (e.g. a theatre file compared in an
# assert). It is off at verbosity >= 2 or when CI/BUILD_NUMBER is set (`_pytest.compat.running_on_ci`), and
# PYTEST_ADDOPTS could add -vv: strip those from pytest's own environment and pin the rest (fix round 4, item 3).
PYTEST_ENV_STRIP = ("CI", "BUILD_NUMBER", "PYTEST_ADDOPTS")
PYTEST_PINS = ["-q", "-o", "verbosity_assertions=auto", "-o", "truncation_limit_lines=8",
               "-o", "truncation_limit_chars=640"]
PYTEST_FORBIDDEN = ("-v", "--verbos", "-o", "--override-ini", "-c", "--config-file", "-p", "-q", "--quiet")
PYTEST_FORBIDDEN_SHORT = set("vocpq")     # Task 18 m2: in a combined short-flag cluster too (`-xvv`, `-rv`)


def _forbidden(a: str) -> bool:
    if a.startswith(PYTEST_FORBIDDEN):
        return True
    return a.startswith("-") and not a.startswith("--") and bool(PYTEST_FORBIDDEN_SHORT & set(a[1:]))
MAIN = "refs/heads/main"
NO_MAIN = "arm-no-main"      # the arm left no committed main: its step attempt is all-failed (final fix batch A1)
HARNESS_UID, ARM_UID = 1000, 1001
HARNESS_CAPS = ("SETUID", "SETGID", "KILL", "DAC_OVERRIDE", "SETPCAP", "SYS_RESOURCE")
# SETPCAP: drop the arm's bounding set; SYS_RESOURCE: pin the arm's oom_score_adj at 1000 so it cannot lower it.
ENTRY = REPO_ROOT / "runner" / "tester_entry.sh"      # passed as `bash -c` text, not mounted
UNPACKER = REPO_ROOT / "runner" / "bundle_unpack.py"  # passed to the entry as source text (run as `python -c`)
RESULTS = "/results"
RESULT_CAPS = {"exit": 64, "timed_out": 64, "resources": 64_000, "junit.xml": 48_000_000, "pytest.log": 8_100_000}
OWN_TMPFS = "rw,uid=1000,gid=1000,mode=0700"               # harness-only: the arm can neither enter nor fill them
HARNESS_TMPFS = (f"/harness:{OWN_TMPFS},size=64m", f"/results:{OWN_TMPFS},size=160m")
BUNDLE = ("pyproject.toml", "tests/__init__.py", "tests/conftest.py", "tests/hidden")
ARM_OOM_SCORE_ADJ = 1000
PER_COMMAND = 60       # driver.Cli's per-command timeout: the whole-run budget scales with it
MARGIN = 300
OUTER_GRACE = 120      # docker's own timeout: after the in-container one, so it only fires if the container hangs


class HiddenError(RuntimeError):
    """A tester container could not do the harness's own part (collection, reading the image's accounts): a
    harness fault (`infra-hidden`, final fix batch A1), never the arm's result and never a runner bug."""


class NoMain(RuntimeError):
    """The arm repo has no `refs/heads/main`: the arm's own outcome (all-failed), never a harness fault."""


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


# Every option VALUE in the hidden pytest's argv is joined to its option with `=` (2026-10-02, pass 1): pytest's
# early conftest discovery runs before plugin/conftest options are registered, so a separate value that is an
# existing path — `--impl /work/<arm>` — became a test-path anchor and the ARM's `conftest.py`/`tests/conftest.py`
# were imported into this harness-uid process (`--confcutdir` does not stop it). The only bare elements left are the
# positional hidden-test paths and the `-o` pins' values; `_check_bare` refuses anything else, loudly.
CALLER_VALUE_OPTS = ("--step", "--first-step-only")     # the callers' options that take a value: joined here
CALLER_FLAGS = ("--collect-only",)


def _is_hidden_path(a: str) -> bool:
    path = a.split("::", 1)[0]
    return (path == "tests/hidden" or path.startswith("tests/hidden/")) and ".." not in path.split("/")


def _join_caller_args(args: list[str]) -> list[str]:
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a in CALLER_VALUE_OPTS:
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                raise ValueError(f"{a} needs a value: {args}")
            out.append(f"{a}={args[i + 1]}")
            i += 2
            continue
        if not (a in CALLER_FLAGS or a.startswith(tuple(f"{o}=" for o in CALLER_VALUE_OPTS)) or _is_hidden_path(a)):
            raise ValueError(f"hidden pytest args are hidden-test paths, {CALLER_VALUE_OPTS} and {CALLER_FLAGS}; "
                             f"the rest is the harness's: {a!r}")
        out.append(a)
        i += 1
    return out


def _check_bare(argv: list[str]) -> None:
    """After the pytest module, a bare (non-option) element must be a hidden-test path or an `-o` pin's value: any
    other would be a conftest-discovery anchor for pytest (a future regression fails here, not in the tester)."""
    rest = argv[argv.index(PYTEST[-1]) + 1:]
    bad = [a for i, a in enumerate(rest)
           if not a.startswith("-") and not (rest[i - 1] == "-o" and a in PYTEST_PINS) and not _is_hidden_path(a)]
    if bad:
        raise ValueError(f"a bare value in the hidden pytest argv would anchor conftest discovery: {bad}")


def _pytest_argv(args: list[str], impl: str, reference: bool = False) -> list[str]:
    """Arm runs: the CLI as uid 1001, no TROUPE_REF_STEP. Reference runs (flake classification): the reference is
    reachable only by the harness uid, so it runs as uid 1000 and gets its step (fix round 2, item 1 (b)).
    The single builder of every hidden pytest command line: every option value is `=`-joined (see above)."""
    bad = [a for a in args if _forbidden(a)]
    if bad:     # verbosity, ini overrides, config files and plugins are the harness's pins, never a caller's
        raise ValueError(f"pytest args may not override the harness pins: {bad}")
    prefix = ["uv", "run", "--quiet", "--project", impl, "troupe"] if reference else arm_prefix(impl)
    argv = ["env", *[x for k in PYTEST_ENV_STRIP for x in ("-u", k)], *PYTEST, *_join_caller_args(args),
            f"--impl={impl}", f"--cmd-prefix={' '.join(prefix)}", *(["--forward-ref-step"] if reference else []),
            *PYTEST_PINS, "-pno:cacheprovider", "--rootdir=/harness", f"--junitxml={RESULTS}/junit.xml"]
    _check_bare(argv)
    return argv


def _bundle_files() -> list[Path]:
    """Every file under tests/hidden (fix round 3: not just *.py — a data file the suite reads must arrive too),
    minus bytecode caches; links are refused by harness_bundle."""
    out = []
    for rel in BUNDLE:
        f = REPO_ROOT / rel
        if f.is_dir():
            out += sorted(x for x in f.rglob("*") if "__pycache__" not in x.parts and x.suffix != ".pyc"
                          and (x.is_symlink() or x.is_file()))
        else:
            out.append(f)
    return out


SUBSTITUTE_TEST = "tests/hidden/test_zz_substitute.py"      # a step-6 substitute bug's acceptance test (Task 23)
_EXTRA_NAME = re.compile(r"tests/hidden/test_[A-Za-z0-9_]+\.py")


def harness_bundle(extra: dict[str, bytes] | None = None) -> bytes:
    """The hidden suite + its config as `<path> <size>\n<bytes>` records, streamed on the tester's stdin into the
    uid-1000 0700 /harness tmpfs (never bind-mounted: Docker Desktop mounts are readable by every uid). `extra`
    adds test files (a substitute bug's acceptance test) — only `tests/hidden/test_<name>.py` paths."""
    parts = []
    for f in _bundle_files():
        if f.is_symlink():
            raise ValueError(f"harness bundle refuses a link: {f}")
        data = f.read_bytes()
        parts.append(f"{f.relative_to(REPO_ROOT).as_posix()} {len(data)}\n".encode() + data)
    for rel, data in (extra or {}).items():
        if not _EXTRA_NAME.fullmatch(rel):
            raise ValueError(f"an extra bundle file must be tests/hidden/test_<name>.py, not {rel!r}")
        parts.append(f"{rel} {len(data)}\n".encode() + data)
    return b"".join(parts)


def unpack_bundle(blob: bytes) -> dict[str, bytes]:
    """The in-container unpacker's own parse (runner/bundle_unpack.py), for tests."""
    from runner import bundle_unpack
    return dict(bundle_unpack.parse(blob))


# Exactly what `tests/hidden/driver.cap` writes at the head of a capped stream (a pure test ties the two together).
TRUNCATION_MARKER = re.compile(rb"\[\.\.\. [0-9]+ bytes truncated \.\.\.\]")
MARKER_SCAN = 8_000_000     # how much of a member's readable tail is searched for the marker
ARM_OUTPUT_MEMBERS = ("junit.xml", "pytest.log")    # the only members arm output can grow; the rest are harness-only


def marker_in_tail(data: bytes) -> bool:
    return TRUNCATION_MARKER.search(data[-MARKER_SCAN:]) is not None


class ResultsError(ValueError):
    """`overflow`: set only for junit.xml/pytest.log at a non-negative size over its cap —
    {"member", "size", "cap", "marker"} (marker: the Cli truncation marker is in the readable tail)."""
    def __init__(self, msg: str, overflow: dict | None = None):
        super().__init__(msg)
        self.overflow = overflow


def _overflow_detail(member: str, size: int | str, marker: bool) -> str:
    return f"{member} {size} bytes; Cli truncation marker {'found' if marker else 'not found'}"


def _frames_error(e: ResultsError) -> str:
    """An over-cap junit.xml/pytest.log is `arm-output` (all-failed, scoreable) only when the Cli cap's truncation
    marker corroborates that arm output grew it; without the marker, and for anything else wrong with the frames
    (a negative size, a harness-only member over its cap, a bad header), it is a `harness-fault` (fix round 4).
    The member, its size and whether the marker was found are kept in the attribution."""
    o = e.overflow
    if o is None:
        return f"harness-fault: {e}"
    return f"{'arm-output' if o['marker'] else 'harness-fault'}: results member over its cap (cap {o['cap']}): " \
           + _overflow_detail(o["member"], o["size"], o["marker"])


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
        if size < 0 or (size > RESULT_CAPS[name] and name not in ARM_OUTPUT_MEMBERS):
            raise ResultsError(f"malformed results frame: {name} has size {size} (cap {RESULT_CAPS[name]})")
        if size > RESULT_CAPS[name]:
            readable = blob[nl + 1:min(nl + 1 + size, len(blob))]
            raise ResultsError(f"results member {name} is {size} bytes (cap {RESULT_CAPS[name]})",
                               {"member": name, "size": size, "cap": RESULT_CAPS[name],
                                "marker": marker_in_tail(readable)})
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
    pids, _, rest = rest.partition("--tmp")
    tmp, _, results = rest.partition("--results")
    kv = lambda block: dict(l.split()[:2] for l in block.splitlines() if len(l.split()) >= 2)
    if int(kv(mem).get("oom_kill", "0") or 0) > 0:
        ev.append(f"oom-kill:{kv(mem)['oom_kill']}")
    if int(kv(pids).get("max", "0") or 0) > 0:
        ev.append(f"pids-max:{kv(pids)['max']}")
    cols = tmp.split()
    if len(cols) >= 4 and cols[3].isdigit() and int(cols[3]) < 1024:
        ev.append("tmp-full")
    rcols = results.split()
    if len(rcols) >= 4 and rcols[3].isdigit() and int(rcols[3]) < 1024:
        ev.append("results-full")
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
    ev = resource_evidence(res)
    if "results-full" in ev:           # arm output filling /results is the arm's result — if the marker says so
        found = [m for m in ARM_OUTPUT_MEMBERS if marker_in_tail(res.get(m, b""))]
        detail = "; ".join(_overflow_detail(m, len(res[m]), m in found) for m in ARM_OUTPUT_MEMBERS if m in res) \
            or "no junit.xml or pytest.log"
        if found:
            return {t: "failed" for t in collected}, code, f"arm-output: /results full: {detail}"
        return {}, code, f"harness-fault: /results full: {detail}"
    if code not in (0, 1) or "junit.xml" not in res:
        if ev:
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
    # None (scored normally) | "arm-timeout" | "arm-resource" (both all-failed, scoreable) | "arm-output: <member,
    # size, marker found>" (results overflow corroborated by the Cli marker; all-failed, scoreable) | "arm-no-main"
    # (no committed main, `all_failed`) |
    # "harness-fault: <why>" (not scoreable, no outcomes)
    attribution: str | None = None
    skipped: int = 0
    resource_evidence: list = field(default_factory=list)   # one list per full-suite attempt
    install: dict | None = None      # A2: the sync's outcome and cause per try (`install_record`), logs in prep-*.json
    harness_retests: list = field(default_factory=list)      # A1/A2: harness faults re-tested on this commit
    acceptance: dict | None = None   # A4: a substitute step-6 bug's acceptance test on this commit, its hidden-suite
                                     # regressions against the precheck baseline, and `progress` (what decides)

    def write(self, out_dir: Path) -> None:
        (out_dir / "hidden").mkdir(parents=True, exist_ok=True)
        (out_dir / "hidden" / "summary.json").write_text(json.dumps(asdict(self), indent=2, sort_keys=True))


def summarise(step, tests, new_at_step, flaky, flaky_arm, exit_code, install_failed=False,
              collected: list[str] | None = None, attribution: str | None = None,
              resource_evidence: list | None = None, install: dict | None = None) -> Summary:
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
                       scoreable=False, attribution=attribution, resource_evidence=ev, install=install)
    else:
        final = {t: ("flaky" if t in flaky else "failed" if t in flaky_arm else o) for t, o in tests.items()}
    new = [t for t in new_at_step if t in final]
    return Summary(step, len(final), sum(o == "passed" for o in final.values()),
                   sum(o == "failed" for o in final.values()), sum(o == "flaky" for o in final.values()),
                   len([t for t in flaky_arm if t in final]), final, new, sum(final[t] == "passed" for t in new),
                   sum(final[t] == "passed" and not allowlisted(t) for t in new),
                   exit_code, install_failed, True, attribution, sum(o == "skipped" for o in final.values()), ev,
                   install)


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
            raise HiddenError(f"cannot read {f} from {image}: {r.stderr[:300]}")
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
          env: dict | None = None, workdir: str | None = None, timeout: int = 600, name: str = "tester",
          reference: bool = False) -> RunSpec:
    """`mode`: "prep" (the arm's build: uid 1001, no caps, no harness mounts), "harness" (the entry script runs
    `cmd` — pytest — as uid 1000; the arm is uid 1001 via --cmd-prefix) or "script" (`cmd` as uid 1001, no
    caps). All run in the tester image, which holds no reference; `reference=True` (harness mode, no arm copy)
    selects the reference image for the harness's own reference runs. Creates a fresh, empty home for this one
    container (removed by `_run`)."""
    if mode not in ("prep", "harness", "script"):
        raise ValueError(mode)
    if reference and (mode != "harness" or copy is not None):
        raise ValueError("the reference image runs only the harness's reference runs, never an arm copy")
    pins = config.load_pins()
    image = pins.images["tester_ref" if reference else "tester"]
    home = _tester_root(p) / f"home-{uuid.uuid4().hex[:12]}"
    home.mkdir(parents=True)
    mounts = [Mount(home, "/home/actor", False)]
    if copy is not None:
        mounts.insert(0, Mount(copy.parent, "/work", False))
    e = {**ENV, **(env or {})}
    user, caps, tmpfs, stdin = f"{ARM_UID}:{ARM_UID}", (), (), False    # prep: arm build code is untrusted too
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
                   "bash", "-c", ENTRY.read_text(), "entry", UNPACKER.read_text(), str(timeout), *cmd]
            tmpfs, stdin = HARNESS_TMPFS, True        # the suite arrives on stdin (harness_bundle)
        else:                                          # the arm uid alone: no harness dirs, no reference, no caps
            caps = ("SETUID", "SETGID", "SETPCAP", "SYS_RESOURCE")
            cmd = [*_drop_to_arm(), *cmd]
    return RunSpec(name=f"bk-{name}-{p.pass_}-{p.arm}-{int(time.time() * 1000) % 10**8}-{uuid.uuid4().hex[:4]}",
                   image=image, label=f"bakeoff.run={p.pass_}/{p.arm}", network=network, mounts=mounts, env=e,
                   workdir=workdir or (f"/work/{copy.name}" if copy is not None else "/"), cmd=cmd, stdin=stdin,
                   limits=pins.limits, proxy=proxy, user=user, cap_add=caps, tmpfs=tmpfs)


def _run(s: RunSpec, timeout: float, extra: dict[str, bytes] | None = None):
    try:
        return docker.run(s, input=harness_bundle(extra) if s.stdin else None, timeout=timeout)
    finally:
        for m in s.mounts:
            if m.ctr == "/home/actor":
                _rmtree(m.host)


# ---- installing the arm's project (final fix batch A2) ---------------------------------------------------------
# A failed `uv sync` is retried with backoff. The LAST failure is classified from uv's output and the proxy log:
# a network or proxy error (DNS, connection refused/reset, a 5xx from the index, the proxy refusing an allowlisted
# host) is the harness's — `prepare_copy` raises `infra-sync`, stepflow re-tests the same commit, and it is never an
# arm attempt; a resolution, build or packaging error (or anything unrecognised) is the arm's `install_failed`.
SYNC_BACKOFF = (10, 30, 90)
_sleep = time.sleep
NETWORK_ERRORS = re.compile(
    r"dns error|failed to lookup address|Name or service not known|Temporary failure in name resolution|"
    r"nodename nor servname|Connection refused|Connection reset|connection closed before message completed|"
    r"error sending request|tcp connect error|operation timed out|timed out|Request failed after \d+ retries|"
    r"server error \(5\d\d|status(?: code)?:? 5\d\d|\b5\d\d (?:Internal Server Error|Bad Gateway|"
    r"Service Unavailable|Gateway Time-?out)|Network is unreachable|No route to host|CONNECT tunnel failed|"
    r"unsuccessful tunnel|proxy error", re.I)


_UV_LINE = ("error:", "Caused by:", "×", "├─▶", "╰─▶", "│")


def uv_lines(log: str) -> list[str]:
    """uv's OWN error lines (follow-up 3): `error:`, `Caused by:` and its `×`/`├─▶`/`╰─▶` chain — never the
    arm's build-backend output, which uv prints indented under `[stdout]`/`[stderr]` headers (anything the arm's
    setup.py prints, "Connection refused" included, is the arm's)."""
    out, block = [], None
    for raw in log.splitlines():
        text = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if block is not None:
            if not text or indent >= block:
                continue                                  # inside the backend's output
            block = None
        if text in ("[stdout]", "[stderr]"):
            block = indent
            continue
        if text.startswith(_UV_LINE):
            out.append(text)
    return out


def classify_sync(log: str, proxy_log: str, hosts: list[str]) -> tuple[str, str]:
    """("network" | "arm", why) for a failed sync. A host the proxy refused that the prep allowlist allows is the
    proxy's fault; one it does not allow is the arm's project reaching off the allowlist."""
    refused = sorted({h for h, v in egress.decisions(proxy_log) if v == "refused"})
    ours = [h for h in refused if any(re.fullmatch(pat.strip("^$"), h) or re.match(pat, h) for pat in hosts)]
    if ours:
        return "network", f"the proxy refused allowlisted host(s) {ours}"
    if refused:
        return "arm", f"the project needs host(s) off the prep allowlist: {refused}"
    own = uv_lines(log)
    if (line := next((l for l in own if NETWORK_ERRORS.search(l)), None)):
        return "network", line[:200]
    lines = own or [l.strip() for l in log.splitlines() if l.strip()]
    return "arm", (next((l for l in lines if l.startswith(("×", "error", "error:"))), lines[-1] if lines else
                        "sync failed with no output"))[:200]


def install_record(rec: dict | None) -> dict | None:
    """The sync record without its logs, for `hidden/summary.json` (the logs stay in `prep-<label>.json`)."""
    if not rec:
        return None
    return {"ok": rec.get("ok"), "cause": rec.get("cause"), "why": rec.get("why"),
            "tries": [{k: t.get(k) for k in ("exit", "cause", "why")} for t in rec.get("tries", [])]}


def _proxy_log(st) -> str:
    try:
        return st.log_text()
    except Exception:                  # the classification then rests on uv's own output
        return ""


def _sync(p: Paths, copy: Path, st: egress.Stage, with_mutmut: bool) -> dict:
    lock = _lockfile(copy)
    cmd = "uv sync --frozen" if lock else "uv sync"
    if with_mutmut:       # mutmut only in copy B (review C-1)
        cmd += " && uv pip install --python .venv/bin/python --require-hashes -r /opt/mutmut-requirements.txt"
    rec: dict = {"lockfile": lock, "command": cmd, "tries": []}
    seen = 0
    for i in range(1 + len(SYNC_BACKOFF)):
        if i:
            _sleep(SYNC_BACKOFF[i - 1])
        r = _run(_spec(p, copy, ["bash", "-c", cmd], mode="prep", network=st.net, proxy=True,
                       env={"UV_OFFLINE": "0", "UV_NO_SYNC": "0"}, name="prep"), timeout=1800)
        log = (r.stdout + r.stderr).decode(errors="replace")
        t = {"exit": r.returncode, "log": log[-4000:]}
        if r.returncode == 0:
            rec["tries"].append(t)
            rec.update(ok=True, cause=None, why=None)
            return rec
        plog = _proxy_log(st)
        t["cause"], t["why"] = classify_sync(log, plog[seen:], st.hosts)
        seen = len(plog)
        rec["tries"].append(t)
    rec.update(ok=False, cause=rec["tries"][-1]["cause"], why=rec["tries"][-1]["why"])
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
    net = [(k, rec[k]) for k in ("hidden", "quality") if isinstance(rec.get(k), dict) and rec[k].get("cause") == "network"]
    if net:                            # A2: the harness's network, never the arm's install
        k, r = net[0]
        raise HarnessFault("infra-sync", re.sub(r"\d", "", str(r.get("why")))[:80] or "network",
                           f"{k} copy: {r.get('why')} (after {len(r['tries'])} tries; prep-{label}.json)")
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
        raise NoMain(f"{p.pass_}/{p.arm}: the arm repo has no {MAIN}")
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
            timeout: int = 600, reference: bool = False,
            extra: dict[str, bytes] | None = None) -> tuple[dict[str, bytes] | None, str | None]:
    """pytest in the tester as the harness uid; returns (results members, error). Never raises for what the
    run itself did: a hung container or unreadable results is reported as an error string."""
    impl = impl or (f"/work/{copy.name}" if copy is not None else "/nonexistent")
    s = _spec(p, copy, _pytest_argv(args, impl, reference), mode="harness", env=env, workdir="/harness", reference=reference,
              timeout=timeout)
    try:
        r = _run(s, timeout=timeout + 30 + OUTER_GRACE, **({"extra": extra} if extra else {}))
    except subprocess.TimeoutExpired:
        return None, f"container did not finish within {timeout + 30 + OUTER_GRACE}s"
    try:
        return unpack_results(r.stdout), None
    except ResultsError as e:
        return None, f"{_frames_error(e)} (docker exit {r.returncode}: {r.stderr.decode(errors='replace')[-300:]})"


def _collect(p: Paths, step: int, first_only: bool) -> list[str]:
    """Collection with NO arm code mounted (collect-only of tests/hidden imports no arm code)."""
    args = ["tests/hidden", "--step", str(step), "--collect-only"] + (["--first-step-only", str(step)] if first_only else [])
    res, err = _pytest(p, None, args)
    if err or res is None or res.get("exit", b"").strip() != b"0":
        raise HiddenError(f"hidden collection failed: {err or (res or {}).get('pytest.log', b'')[-800:]!r}")
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


def run_acceptance(p: Paths, copy: Path, step: int, body: str) -> dict:
    """A step-6 substitute bug's acceptance test (owner, preflight B5; Task 23 ruling): the owner's pytest file body,
    streamed in the harness bundle as `SUBSTITUTE_TEST` (it may use the hidden suite's `cli`/`tmp_theatre` fixtures
    and needs `@pytest.mark.steps(...)`), run against the arm's copy like any hidden test. `outcome` is "failed"
    (what delivery needs: the bug is real on this commit), "passed", or "error" with the detail.
    A run that did not complete is assessed like the main suite (follow-up 4): an abnormal death with resource
    evidence is `arm-resource` (re-run once; a repeat fails it), over budget `arm-timeout`, corroborated results
    overflow `arm-output` — each the arm's "failed", with `attribution`; anything else is "error" (the harness's).
    `resource_evidence` has one list per run."""
    evidence: list[list[str]] = []
    for _ in (1, 2):
        res, err = _pytest(p, copy, [SUBSTITUTE_TEST, "--step", str(step)], timeout=run_timeout(20),
                           extra={SUBSTITUTE_TEST: body.encode()})
        if err or res is None:
            if err and err.startswith("arm-output"):
                return {"outcome": "failed", "attribution": err, "resource_evidence": evidence}
            return {"outcome": "error", "detail": err or "no results",
                    "attribution": err if err and err.startswith("harness-fault") else f"harness-fault: {err}",
                    "resource_evidence": evidence}
        evidence.append(resource_evidence(res))
        code = res.get("exit", b"").strip().decode(errors="replace")
        try:
            tests = parse_junit(res["junit.xml"]) if "junit.xml" in res else {}
        except ET.ParseError as e:
            return {"outcome": "error", "detail": f"unparseable junit ({e})", "exit": code,
                    "attribution": "harness-fault: unparseable junit", "resource_evidence": evidence}
        if tests:
            return {"outcome": "failed" if any(o == "failed" for o in tests.values()) else "passed", "tests": tests,
                    "exit": code, "resource_evidence": evidence}
        _, _, attribution = assess([], res)
        if attribution is None or attribution.startswith("harness-fault"):
            log = res.get("pytest.log", b"")[-1500:].decode(errors="replace")
            return {"outcome": "error", "detail": f"pytest exit {code}, no test ran: {log}", "exit": code,
                    "attribution": attribution or "harness-fault: no test ran", "resource_evidence": evidence}
        if attribution != "arm-resource":            # arm-timeout, arm-output: the arm's, at once
            return {"outcome": "failed", "attribution": attribution, "exit": code, "resource_evidence": evidence}
    return {"outcome": "failed", "attribution": "arm-resource", "exit": code, "resource_evidence": evidence}


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


def all_failed(p: Paths, step: int, out_dir: Path, why: str) -> Summary:
    """The step's suite scored all-failed without running arm code (final fix batch A1: an arm with no committed
    `main`; A5: an attempt failed for an arm violation). Collection runs with no arm code, as in `run`; `why` is
    the attribution recorded in `hidden/summary.json`."""
    collected = _collect(p, step, first_only=False)
    new_at_step = _collect(p, step, first_only=True)
    s = summarise(step, {t: "failed" for t in collected}, new_at_step, [], [], -1, collected=collected,
                  attribution=why)
    s.write(out_dir)
    return s


def run(p: Paths, copy: Path, step: int, out_dir: Path, install_failed: bool = False,
        install: dict | None = None) -> Summary:
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
            if err and err.startswith("arm-output"):     # corroborated results overflow: all-failed, detail kept
                tests, code, attribution = {t: "failed" for t in collected}, -1, err
            else:
                tests, code, attribution = {}, -1, err if err and err.startswith("harness-fault") else f"harness-fault: {err}"
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
    s = summarise(step, tests, new_at_step, flaky, flaky_arm, code, install_failed, collected, attribution, evidence,
                  install)
    s.write(out_dir)
    return s
