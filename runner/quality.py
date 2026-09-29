"""Code quality: `mypy --strict`, ruff (isolated + the arm's own config), mutmut over the arm's own tests
(OD15), all inside the tester container, `--network none` (design §8, review C-1: mypy/ruff run on copy A,
mutmut only on copy B — an arm's mutation testing must never be able to see or touch the copy hidden tests
run against).

Tool failures (a crash, a timeout) are recorded as such and kept distinct from a real, clean result — a
crashed mypy is not "0 errors", a crashed or timed-out mutation run is not "score 0" (every mutant "survived")
or "score 100": `mutation_summary` withholds the score (`None`) whenever `crashed` is set, and separately
whenever the denominator collapses to zero. A crash inside the mutation run itself — `mutmut run` failing, or
`mutmut results` failing to read back what it just did — is recorded the same way, never folded into "no
mutants" or a misleadingly precise `0.0` (review ruling, fix round 1). Tool versions (and the tester image tag
they were installed into) are read from the same pinned requirements files the tester image itself installs
from, so the numbers are reproducible without re-deriving or guessing a version.

The host never opens an arm-written file through a link: by the time `pyproject.toml` is read or rewritten,
arm code has already run (build backend, `uv sync`) with `/work` writable, so a symlink, FIFO or oversized
file in its place is refused (`UnsafeFile`), never followed or read unbounded — the same convention
`hidden._lockfile` already uses (`os.lstat`, no follow) extended here to `O_NOFOLLOW` reads and writes since
this module also rewrites the file, not just checks its type.

mutmut itself is installed into, and always runs from, the arm's own `.venv` (`hidden._sync`'s
`with_mutmut` branch) — inherent to measuring the arm's actual code and dependencies, not a gap: mutation
testing that ran from a harness-controlled environment instead would not be testing what the arm shipped.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from runner import config
from runner.docker import RunSpec
from runner.paths import Paths, REPO_ROOT

# `runner.hidden` (Task 18) is imported lazily, inside `_run` only, so this module has no hard import-time
# dependency on it — pure tests (test_quality.py) run with no hidden.py present at all. The only names used
# are `hidden.Prepared` (a type hint, never introspected at runtime), `hidden._spec(p, copy, cmd, *, mode,
# name)` and `hidden._run(spec, timeout) -> CompletedProcess` — the same per-container-home-cleanup helper
# `hidden.py` itself uses. See the module docstring / task report for why.
if TYPE_CHECKING:
    from runner import hidden

TESTER_DIR = REPO_ROOT / "runner" / "images" / "tester"

# mutmut 3.8.0's full status vocabulary (mutmut/stats.py `status_by_exit_code`); every status maps to its own
# field, none silently folded into another (fix round 1: "caught by type check" is tracked separately from
# "killed" — mutmut's own scoring/display keeps them separate too — and "check was interrupted by user" gets
# its own bucket rather than falling into the `not_checked` default).
STATUS = {"killed": "killed", "survived": "survived", "timeout": "timeout", "suspicious": "suspicious",
          "no tests": "no_tests", "skipped": "skipped", "not checked": "not_checked", "segfault": "segfault",
          "caught by type check": "caught_by_type_check",
          "check was interrupted by user": "check_interrupted"}

MUTATION_COUNT_KEYS = ("killed", "survived", "timeout", "suspicious", "no_tests", "skipped", "not_checked",
                       "caught_by_type_check", "check_interrupted", "segfault")
# A mutant outcome that is real signal (as opposed to "we never actually got a status for it").
_REAL_OUTCOME_KEYS = ("killed", "survived", "timeout", "suspicious", "caught_by_type_check", "segfault",
                     "check_interrupted")

# One shared zero-summary literal (review m10: this dict was repeated 3x). `mutation_summary` only ever
# reads from a copy of it (`{**c, ...}`), so it is never mutated in place.
ZERO_MUTATION: dict[str, int] = {**{k: 0 for k in MUTATION_COUNT_KEYS}, "total": 0}

MAX_CONFIG_BYTES = 1_000_000     # generous for a pyproject.toml; anything bigger is refused, not read


class UnsafeFile(ValueError):
    """Refused: the host never opens an arm-written path through a link, a FIFO, or an oversized file — arm
    code has already run, with `/work` writable, by the time quality reads or rewrites `pyproject.toml`."""


# --- pure --------------------------------------------------------------------------------------------------

def mypy_errors(text: str) -> int:
    m = re.search(r"Found (\d+) errors?", text)
    return int(m.group(1)) if m else 0


def mypy_ok(rc: int) -> bool:
    """mypy exits 0 (clean) or 1 (errors found) for a real result; anything else is a tool crash
    (bad invocation, internal error) — never read as "0 errors"."""
    return rc in (0, 1)


def mypy_result(rc: int, text: str) -> tuple[int | None, bool]:
    """(errors, crashed) for a real invocation. rc 0 is unconditionally clean (0 errors). rc 1 must carry a
    "Found N errors" summary line; its absence means mypy exited 1 for some other reason (an internal error
    can still exit 1), which is a crash, never silently read as "0 errors". Any other rc is always a crash."""
    if not mypy_ok(rc):
        return None, True
    if rc == 1:
        m = re.search(r"Found (\d+) errors?", text)
        return (int(m.group(1)), False) if m else (None, True)
    return 0, False


def ruff_count(text: str) -> int:
    return len(json.loads(text or "[]"))


def ruff_parse(rc: int, text: str) -> tuple[int | None, bool]:
    """`--exit-zero` makes rc 0 for real findings, so any nonzero rc is a crash — `findings` is always `None`
    then, never the parsed count even if `text` happens to still be valid JSON (fix round 1: a crash must
    never masquerade as a real, if unlucky, "0 findings" or coincidental count). rc 0 without the JSON array
    ruff always produces on a working run is also a crash. `text` must be stdout only — never stderr, which
    can carry unrelated diagnostic text (from the privilege-drop wrapper, say) that would corrupt the parse."""
    if rc != 0:
        return None, True
    try:
        return ruff_count(text), False
    except json.JSONDecodeError:
        return None, True


def tool_versions() -> dict[str, str]:
    """Pinned tool versions the tester image actually installs from (reproducibility, controller ruling) —
    read from the same requirements files the image build uses, not re-derived or guessed at run time. Also
    records the tester image tag itself: the tool versions are only reproducible together with it."""
    text = (TESTER_DIR / "requirements.txt").read_text() + "\n" + (TESTER_DIR / "mutmut-requirements.txt").read_text()
    out: dict[str, str] = {}
    for name in ("mypy", "ruff", "mutmut", "pytest"):
        m = re.search(rf"(?m)^{name}==(\S+)", text)
        if m:
            out[name] = m.group(1)
    out["tester_image"] = config.load_pins().images["tester"]
    return out


def _safe_read(path: Path, max_size: int = MAX_CONFIG_BYTES) -> str | None:
    """`None` if `path` doesn't exist. Raises `UnsafeFile` if it exists but is not a plain regular file within
    `max_size` — a symlink, FIFO, device, directory, or oversized file an arm could have substituted for a
    config file. `lstat` first (never follows a link to even check); the read itself also refuses to follow
    one (`O_NOFOLLOW`), belt-and-braces against a substitution between the check and the open."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(st.st_mode):
        raise UnsafeFile(f"{path} is not a regular file (mode {oct(st.st_mode)})")
    if st.st_size > max_size:
        raise UnsafeFile(f"{path} is {st.st_size} bytes (cap {max_size})")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        data = os.read(fd, max_size + 1)
    finally:
        os.close(fd)
    if len(data) > max_size:
        raise UnsafeFile(f"{path} grew past {max_size} bytes while it was being read")
    return data.decode("utf-8", errors="replace")


def _safe_write(path: Path, text: str, max_size: int = MAX_CONFIG_BYTES) -> None:
    """Refuses (`UnsafeFile`) to write through a symlink or onto any other non-regular-file path — never
    follows a link to write somewhere outside the copy. A path that doesn't exist yet is created as a plain
    regular file (`O_CREAT`); one that exists and is not a regular file is refused outright."""
    body = text.encode()
    if len(body) > max_size:
        raise UnsafeFile(f"refusing to write {len(body)} bytes to {path} (cap {max_size})")
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISREG(st.st_mode):
            raise UnsafeFile(f"{path} is not a regular file (mode {oct(st.st_mode)}); refusing to write")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        os.write(fd, body)
    finally:
        os.close(fd)


def targets(copy: Path) -> list[str]:
    if (copy / "src").is_dir():
        return ["src"]
    try:
        text = _safe_read(copy / "pyproject.toml")
        if text is None:
            return ["."]
        scripts = tomllib.loads(text).get("project", {}).get("scripts", {})
        mod = scripts.get("troupe", "").split(":")[0].split(".")[0]
        if mod and (copy / mod).is_dir():
            return [mod]
    except (OSError, tomllib.TOMLDecodeError, UnsafeFile):
        pass
    return ["."]


def _has_arm_ruff_config(copy: Path) -> tuple[bool, bool]:
    """(has_cfg, crashed). `ruff.toml`/`.ruff.toml` existence is checked with `lstat` (never opened — presence
    alone decides this, so a dangling or hostile symlink there is simply not treated as a real config, never
    followed). `pyproject.toml` is read through `_safe_read`; a refusal there means "we don't know", so the
    arm-config ruff pass is skipped and recorded as crashed rather than silently treated as "no config"."""
    for name in ("ruff.toml", ".ruff.toml"):
        try:
            st = os.lstat(copy / name)
        except FileNotFoundError:
            continue
        if stat.S_ISREG(st.st_mode):
            return True, False
    try:
        text = _safe_read(copy / "pyproject.toml")
    except UnsafeFile:
        return False, True
    return bool(text and "[tool.ruff" in text), False


def mutation_summary(c: dict[str, int], *, partial: bool, baseline_failed: bool, crashed: bool = False,
                     **extra: object) -> dict[str, object]:
    denom = c["total"] - c["no_tests"] - c["skipped"]
    score = None if crashed else ((c["killed"] / denom) if denom > 0 else None)
    return {**c, "score": score, "partial": partial, "baseline_failed": baseline_failed, "crashed": crashed,
            **extra}


def parse_results(text: str) -> tuple[list[str], dict[str, int]]:
    names, counts = [], {k: 0 for k in MUTATION_COUNT_KEYS}
    for m in re.finditer(r"(?m)^\s*(\S+__mutmut_\d+): ([a-z ]+?)\s*$", text):
        names.append(m.group(1))
        counts[STATUS.get(m.group(2), "not_checked")] += 1
    counts["total"] = len(names)
    return names, counts


def sample(names: list[str], n: int) -> list[str]:
    """Deterministic and arm-agnostic (OD15 B): the same N mutant names come out regardless of listing
    order, because the selection key is a hash of the name, not its position."""
    return sorted(sorted(set(names), key=lambda x: hashlib.sha256(x.encode()).hexdigest())[:n])


def set_mutmut_paths(copy: Path, paths_: list[str]) -> None:
    """Replace any `[tool.mutmut]` table the arm shipped with exactly `paths_to_mutate = <paths_>`, for
    comparability across arms. Every other table is left untouched.

    Reads/writes go through `_safe_read`/`_safe_write` (review ruling: the host never opens an arm-written path
    through a link). The existing content is validated as real TOML first, and refused (`UnsafeFile`) on any
    doubt rather than silently mishandled: an unparsable file, CRLF is normalised (not a doubt — TOML doesn't
    care about line-ending style), and a `tool.mutmut` expressed as an inline table or a dotted key
    (`tool.mutmut = {...}`, or `mutmut = {...}` under `[tool]`) rather than its own `[tool.mutmut]` (or
    `[tool.mutmut.sub]`) header — a shape a line-oriented strip cannot safely locate — is refused outright.
    A header line's own trailing comment is handled for free (the whole line is dropped regardless of what
    follows the closing `]`). The rewrite is self-checked (re-parsed, `paths_to_mutate` compared) before being
    written; a failed self-check is also a refusal, never a silently-broken file."""
    text = _safe_read(copy / "pyproject.toml")
    norm = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    try:
        doc = tomllib.loads(norm) if norm.strip() else {}
    except tomllib.TOMLDecodeError as e:
        raise UnsafeFile(f"pyproject.toml does not parse as TOML: {e}") from e

    header_re = re.compile(r"^\s*\[\s*tool\s*\.\s*mutmut\s*(\.[^\]\s]+)?\s*\]")
    has_header = any(header_re.match(line) for line in norm.split("\n"))
    if doc.get("tool", {}).get("mutmut") is not None and not has_header:
        raise UnsafeFile("[tool.mutmut] is set as an inline table or dotted key, not its own header — "
                         "refusing to guess where to strip it")

    any_header_re = re.compile(r"^\s*\[")
    out_lines: list[str] = []
    skipping = False
    for line in norm.split("\n"):
        if header_re.match(line):
            skipping = True
            continue
        if skipping and any_header_re.match(line):
            skipping = False
        if not skipping:
            out_lines.append(line)
    new_text = "\n".join(out_lines).rstrip("\n")
    new_text += f"\n\n[tool.mutmut]\npaths_to_mutate = {json.dumps(paths_)}\n"

    try:
        check = tomllib.loads(new_text)
        if check.get("tool", {}).get("mutmut", {}).get("paths_to_mutate") != paths_:
            raise ValueError("paths_to_mutate did not round-trip")
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise UnsafeFile(f"rewritten pyproject.toml failed its own self-check: {e}") from e
    _safe_write(copy / "pyproject.toml", new_text)


# --- containers ----------------------------------------------------------------------------------------------

def _script_spec(p: Paths, copy: Path, cmd: list[str], *, name: str = "quality") -> RunSpec:
    """Binding isolation rule: mutation, mypy and ruff execute the arm's own code, so they run the way prep and
    the hidden tests do — `hidden._spec(..., mode="script")` starts the container as root only long enough to
    `setpriv` down to uid 1001 (`ARM_UID`) with every capability cleared (`--bounding-set=-all`,
    `--ambient-caps=-all`, `--inh-caps=-all`) and `no_new_privs` set; `docker.run_argv` adds
    `--security-opt no-new-privileges` to every `RunSpec` unconditionally. `mode="script"` never accepts
    `reference=True` (that raises), so `_spec` can only pick the plain tester image — never `tester_ref`, which
    exists solely for the harness's own reference-flake runs and holds no arm-relevant tooling anyway. Network
    defaults to `"none"` and is never overridden here.

    `runner.run_script` (public) does the same `mode="script"` build, but hardcodes a 600s timeout and returns
    only decoded stdout — it drops the exit code and stderr. This task's whole point is distinguishing a tool
    crash from a clean result, which needs the exit code, and mypy/mutation need up to 1800s+, so `_spec`/`_run`
    are used directly here instead of the public wrapper."""
    from runner import hidden          # lazy: Task 18's module, not a module-load-time dependency
    return hidden._spec(p, copy, cmd, mode="script", name=name)


class ToolRun:
    """One tool invocation's result. `rc` is `None` only when `timed_out`. `stdout`/`stderr` are kept apart
    (fix round 1, item 3): a JSON parser must only ever see `stdout` — diagnostic text from the privilege-drop
    wrapper, if any, lands in `stderr` and is never allowed to corrupt the JSON stream."""

    __slots__ = ("rc", "stdout", "stderr", "timed_out")

    def __init__(self, rc: int | None, stdout: str, stderr: str, timed_out: bool = False) -> None:
        self.rc, self.stdout, self.stderr, self.timed_out = rc, stdout, stderr, timed_out

    @property
    def combined(self) -> str:
        return self.stdout + self.stderr


def _run(p: Paths, copy: Path, cmd: list[str], timeout: int) -> ToolRun:
    """Every quality tool runs in its own tester container (see `_script_spec`); `hidden._run` also cleans up
    the per-container home directory this creates, whether the run succeeds, fails or times out. A container
    that does not finish within `timeout` is recorded as `timed_out` — never raised away (fix round 1, item 4:
    `run_all` always returns and records something, for every tool: baseline, mypy, ruff, mutation)."""
    from runner import hidden          # lazy: Task 18's module, not a module-load-time dependency
    try:
        r = hidden._run(_script_spec(p, copy, cmd), timeout=timeout)
    except subprocess.TimeoutExpired:
        return ToolRun(rc=None, stdout="", stderr="", timed_out=True)
    return ToolRun(rc=r.returncode, stdout=r.stdout.decode(errors="replace"),
                   stderr=r.stderr.decode(errors="replace"))


def list_mutants(p: Paths, copy: Path, tg: list[str]) -> list[str]:
    """OD15 B precondition: list every mutant without running any. Falls back to OD15 A (run_all records
    `sampling: "unavailable"`) if the pinned mutmut cannot list without running — including when the listing
    attempt itself times out (an empty result either way, from `_run`'s uniform timeout handling)."""
    set_mutmut_paths(copy, tg)
    cmd = ["bash", "-c", ".venv/bin/mutmut run '__bk_list_only__' >/dev/null 2>&1; "
           ".venv/bin/mutmut results --all true"]
    out = _run(p, copy, cmd, 1800)
    return parse_results(out.combined)[0]


def _mutation(p: Paths, copy: Path, tg: list[str], out_dir: Path, pins: config.Pins) -> dict[str, object]:
    """Mutation testing runs only on copy B (review C-1). The arm's own tests are the baseline: only the arm's
    pytest actually failing (rc 1) is `baseline_failed` — the arm's own result, not ours, and never scored.
    rc 5 means no tests were collected (`no_tests`), also not scored and not the arm's fault. Any other exit —
    a harness/container-level code (125, 126, 127, 137, ...), an unexpected crash, or a timeout — is `crashed`:
    the score is withheld (`None`), never read as `0.0`, and never confused with `baseline_failed`/`no_tests`
    (fix round 1, item 5). The main mutation run and the results-reading step each get their own exit-code
    marker; either failing is also `crashed`, not "no mutants" (item 2) — as is the degenerate case where
    every selected mutant comes back "not checked" even though nothing else looked wrong: zero real signal
    must never present as a score of `0.0`."""
    lim = pins.limits
    log: list[str] = []

    def finish(counts: dict[str, int], *, partial: bool, baseline_failed: bool, crashed: bool = False,
              **extra: object) -> dict[str, object]:
        qd = out_dir / "quality"
        qd.mkdir(parents=True, exist_ok=True)
        summary = mutation_summary(counts, partial=partial, baseline_failed=baseline_failed, crashed=crashed,
                                   **extra)
        (qd / "mutmut.log").write_text("\n".join(log))
        return summary

    common = dict(sampled=False, sample_size=0, mutmut_run_rc=None, mutmut_results_rc=None)

    baseline = _run(p, copy, ["bash", "-c", ".venv/bin/python -m pytest -q -p no:cacheprovider -x"], 1800)
    log.append("$ baseline: pytest\n" + baseline.combined[-4000:])
    if baseline.timed_out:
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling="n/a", baseline_rc=None, timed_out=True, **common)
    if baseline.rc == 5:                                        # no tests collected -- not the arm's fault
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=False,
                      sampling="no tests", baseline_rc=baseline.rc, timed_out=False, **common)
    if baseline.rc == 1:                                        # the arm's own tests genuinely fail
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=True, crashed=False,
                      sampling="n/a", baseline_rc=baseline.rc, timed_out=False, **common)
    if baseline.rc != 0:                # 2/3/4/125/126/127/137/... -- a harness or container fault, not the arm
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling="n/a", baseline_rc=baseline.rc, timed_out=False, **common)

    try:
        set_mutmut_paths(copy, tg)
    except UnsafeFile as e:
        log.append(f"$ set_mutmut_paths refused: {e}")
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling="n/a", baseline_rc=baseline.rc, timed_out=False, **common)

    sampling, chosen = "all", []
    if lim.mutation_sample > 0:
        try:
            names = list_mutants(p, copy, tg)
        except UnsafeFile as e:
            log.append(f"$ list_mutants refused: {e}")
            names = []
        if names:
            chosen, sampling = sample(names, lim.mutation_sample), "seeded-sha256"
        else:
            sampling = "unavailable"          # listing unsupported (or refused/timed out): fall back to A

    # Mutant names reach mutmut through argv, never through string interpolation into the script (fix round
    # 1): `bash -c '<script using "$@">' _ <mutation_seconds> run --max-children 4 <name> <name> ...` — bash's
    # own argv handling quotes each name safely regardless of its content, with no shell-injection surface.
    script = 'timeout "$1" "${@:2}"; echo __run_rc=$?; .venv/bin/mutmut results --all true; echo __results_rc=$?'
    cmd = ["bash", "-c", script, "_", str(lim.mutation_seconds),
           ".venv/bin/mutmut", "run", "--max-children", "4", *chosen]
    outcome = _run(p, copy, cmd, lim.mutation_seconds + 900)
    log.append(f"$ mutmut run ({'sampled ' + str(len(chosen)) if chosen else 'all'})\n" + outcome.combined[-20000:])
    if outcome.timed_out:
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling=sampling, baseline_rc=baseline.rc, timed_out=True,
                      sampled=bool(chosen), sample_size=len(chosen),
                      mutmut_run_rc=None, mutmut_results_rc=None)

    out = outcome.combined
    run_rc_m = re.search(r"__run_rc=(-?\d+)", out)
    results_rc_m = re.search(r"__results_rc=(-?\d+)", out)
    run_rc = int(run_rc_m.group(1)) if run_rc_m else None
    results_rc = int(results_rc_m.group(1)) if results_rc_m else None
    # A crash in `mutmut results` (or a missing marker entirely) is recorded as a crash, not "no mutants".
    crashed = results_rc != 0 or run_rc not in (0, 124)

    names, counts = parse_results(out)
    if chosen:
        wanted = set(chosen)
        _, counts = parse_results("\n".join(ln for ln in out.splitlines() if ln.strip().split(":")[0] in wanted))
    real_outcomes = sum(counts.get(k, 0) for k in _REAL_OUTCOME_KEYS)
    if not crashed and counts.get("total", 0) > 0 and real_outcomes == 0:
        # Every selected mutant came back "not checked" even though nothing else looked wrong: no real signal
        # at all, so this must never present as a precise-looking 0.0 (the exact regression this closes).
        crashed = True
    partial = (not crashed) and (run_rc == 124 or counts.get("not_checked", 0) > 0)
    return finish({k: counts[k] for k in ZERO_MUTATION}, partial=partial, baseline_failed=False, crashed=crashed,
                  sampling=sampling, baseline_rc=baseline.rc, timed_out=False,
                  sampled=bool(chosen), sample_size=len(chosen),
                  mutmut_run_rc=run_rc, mutmut_results_rc=results_rc)


def run_all(p: Paths, prep: "hidden.Prepared", out_dir: Path, pins: config.Pins | None = None) -> dict[str, object]:
    """mypy and ruff run on copy A (never mutated); mutmut runs only on copy B (review C-1: copy A must come
    out of this untouched). `pins` may be overridden by the caller (e.g. the dry run's cheaper mutation
    budget) — default is the real pinned limits. Every phase is defensive: an unexpected exception in any one
    of them is recorded as that phase's crash rather than losing the results of every other phase (or the
    whole run) — this function always returns and always writes `summary.json`."""
    pins = pins or config.load_pins()
    qd = out_dir / "quality"
    qd.mkdir(parents=True, exist_ok=True)
    a, b = prep.hidden_copy, prep.quality_copy

    try:
        tg = targets(a)
    except Exception:                    # noqa: BLE001 -- targets() already handles its known cases; anything
        tg = ["."]                        # else here must not lose the rest of the run's evidence

    mypy_run = _run(p, a, ["bash", "-c", "/opt/harness/bin/mypy --strict --no-incremental "
                    "--cache-dir /tmp/mypy-cache --python-executable .venv/bin/python " + " ".join(tg)], 1800)
    (qd / "mypy.txt").write_text(mypy_run.combined)
    if mypy_run.timed_out:
        mypy_errors_val, mypy_crashed, mypy_timed_out = None, True, True
    else:
        assert mypy_run.rc is not None                 # ToolRun invariant: rc is None only when timed_out
        mypy_errors_val, mypy_crashed = mypy_result(mypy_run.rc, mypy_run.combined)
        mypy_timed_out = False

    ruff_run = _run(p, a, ["bash", "-c", "/opt/harness/bin/ruff check --isolated --exit-zero "
                    "--cache-dir /tmp/ruff-cache --output-format json ."], 600)
    (qd / "ruff.json").write_text(ruff_run.stdout)
    if ruff_run.timed_out:
        ruff_n, ruff_crashed, ruff_timed_out = None, True, True
    else:
        assert ruff_run.rc is not None                 # ToolRun invariant: rc is None only when timed_out
        ruff_n, ruff_crashed = ruff_parse(ruff_run.rc, ruff_run.stdout)
        ruff_timed_out = False

    has_cfg, ruff_arm_precheck_crashed = _has_arm_ruff_config(a)
    ruff_arm = ruff_arm_crashed = None
    ruff_arm_timed_out = False
    if ruff_arm_precheck_crashed:
        ruff_arm_crashed = True
    elif has_cfg:
        ra_run = _run(p, a, ["bash", "-c", "/opt/harness/bin/ruff check --exit-zero "
                       "--cache-dir /tmp/ruff-cache-arm --output-format json ."], 600)
        (qd / "ruff-arm.json").write_text(ra_run.stdout)
        if ra_run.timed_out:
            ruff_arm, ruff_arm_crashed, ruff_arm_timed_out = None, True, True
        else:
            assert ra_run.rc is not None                 # ToolRun invariant: rc is None only when timed_out
            ruff_arm, ruff_arm_crashed = ruff_parse(ra_run.rc, ra_run.stdout)

    if b is not None and prep.prep.get("quality", {}).get("ok"):
        try:
            mut = _mutation(p, b, tg, out_dir, pins)
        except Exception as e:           # noqa: BLE001 -- never lose the run's evidence to an exception
            mut = mutation_summary(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                                   sampled=False, sample_size=0,
                                   sampling=f"error: {type(e).__name__}: {e}"[:200])
    else:
        mut = mutation_summary(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                               sampled=False, sample_size=0, sampling="install failed")
    (qd / "mutation.json").write_text(json.dumps(mut, indent=2))

    s: dict[str, object] = {
        "mypy_errors": mypy_errors_val, "mypy_crashed": mypy_crashed, "mypy_timed_out": mypy_timed_out,
        "ruff_findings": ruff_n, "ruff_crashed": ruff_crashed, "ruff_timed_out": ruff_timed_out,
        "ruff_arm_findings": ruff_arm, "ruff_arm_crashed": ruff_arm_crashed,
        "ruff_arm_timed_out": ruff_arm_timed_out,
        "mutation": mut, "targets": tg, "tool_versions": tool_versions(),
    }
    (qd / "summary.json").write_text(json.dumps(s, indent=2))
    return s
