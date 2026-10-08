"""Code quality: `mypy --strict`, ruff (isolated + the arm's own config), mutmut over the arm's own tests
(OD15), all inside the tester container, `--network none` (design §8, review C-1: mypy/ruff run on copy A,
mutmut only on copy B — an arm's mutation testing must never be able to see or touch the copy hidden tests
run against).

Tool failures (a crash, a timeout) are recorded as such and kept distinct from a real, clean result — a
crashed mypy is not "0 errors", a crashed or timed-out mutation run is not "score 0" (every mutant "survived")
or "score 100": `mutation_summary` withholds the score (`None`) whenever `crashed` is set, and separately
whenever the denominator collapses to zero. A crash inside the mutation run itself — `mutmut run` failing,
`mutmut results` failing to read back what it just did, or no mutant getting a real verdict while any is
left unresolved (`not_checked`, an all-`check_interrupted` run — fix round 2, item 1 — or a sampled name
missing, with or without "no tests" mutants alongside) — is recorded the same way, never folded into "no
mutants" or a misleadingly precise `0.0` (review ruling, fix round 1). A completed run in which every mutant
is "no tests" or "skipped" is the one exemption: not a crash, score `None`, `unmeasured` set (mutmut
attributed no test coverage to anything — see `mutation_env`). A `check_interrupted` mutant that isn't the whole run, or fewer statuses coming back than were
sampled, sets `partial` instead (fix round 2, items 1 and 5) and is never silently dropped. `run_all` guards
every phase — `targets()`, mypy, both ruff passes, `tool_versions()` and `_mutation` — in its own
`try/except`, so an exception anywhere is recorded as that phase's crash (with the exception type and message)
rather than losing every other phase's result or `summary.json` itself (fix round 2, item 2): this function
always returns, and always writes `summary.json`. Tool versions (and the tester image tag they were installed
into) are read from the same pinned requirements files the tester image itself installs from, so the numbers
are reproducible without re-deriving or guessing a version.

The host never opens an arm-written file through a link: by the time `pyproject.toml` is read or rewritten,
arm code has already run (build backend, `uv sync`) with `/work` writable, so a symlink, FIFO or oversized
file in its place is refused (`UnsafeFile`), never followed or read unbounded — the same convention
`hidden._lockfile` already uses (`os.lstat`, no follow) extended here to `O_NOFOLLOW`+`O_NONBLOCK` reads (a
FIFO substituted between the check and the open must not be able to hang the host) and atomic
temp-file-plus-`os.replace` writes (fix round 2, item 6), since this module also rewrites the file, not just
checks its type. The arm's `project.scripts.troupe` entry point (used to pick a mypy/mutmut target directory)
must be a plain dotted-identifier chain (`InvalidEntryPoint` otherwise, fix round 2, item 7) and is always
passed to a shell command quoted (`shlex.quote`), never interpolated raw.

mutmut itself is installed into, and always runs from, the arm's own `.venv` (`hidden._sync`'s
`with_mutmut` branch) — inherent to measuring the arm's actual code and dependencies, not a gap: mutation
testing that ran from a harness-controlled environment instead would not be testing what the arm shipped. But
that same fact is also this method's honest limit (fix round 3, item 2 — see `_mutation`'s docstring for the
full account): the arm's own test process runs each mutant as the same uid, with `/work` writable, so a
determined arm could tamper with its own `mutmut` binary or its own persisted mutation results directly,
without ever printing a forged line this module would see. Everything below closes the *accidental* and
*unprivileged-forgery* cases — a stray print, a naive attempt at a fake status or exit-code line — not a
hostile arm rewriting its own tooling. The mutation score is a 10%-weight code-quality input (design §8), only
as trustworthy as the arm's own environment; this is recorded here and in the task report as an owner-visible
note, not presented as solved.

Status lines (`<name>__mutmut_N: <status>`) are parsed only from a second, fresh container that runs nothing
but `mutmut results` — never from the container that actually ran the mutants, whose stdout could otherwise
carry a forged status line from the arm's own test output (fix round 3, item 1); duplicate names keep only
their last-seen status, never summed. The mutation run's own exit-code markers (`__run_rc`, `__results_rc`)
are each read from the LAST anchored occurrence on its own line in that container's stdout, never the first
(fix round 2, item 4): our own `echo` for a marker always runs after everything that step could have printed
(including a tailed log of arm output), so the real marker is provably always last.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
import time
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
# A mutant outcome that is real signal (as opposed to "we never actually got a status for it"). `check_interrupted`
# is deliberately excluded (fix round 2, item 1): "check was interrupted by user" means something (typically a
# signal) stopped mutmut checking that mutant before it could reach a real verdict — the same epistemic status
# as `not_checked`, not a verdict of its own. It still sets `partial`; it must never contribute to a score.
_REAL_OUTCOME_KEYS = ("killed", "survived", "timeout", "suspicious", "caught_by_type_check", "segfault")

# One shared zero-summary literal (review m10: this dict was repeated 3x). `mutation_summary` only ever
# reads from a copy of it (`{**c, ...}`), so it is never mutated in place.
ZERO_MUTATION: dict[str, int] = {**{k: 0 for k in MUTATION_COUNT_KEYS}, "total": 0}

MAX_CONFIG_BYTES = 1_000_000     # generous for a pyproject.toml; anything bigger is refused, not read


class UnsafeFile(ValueError):
    """Refused: the host never opens an arm-written path through a link, a FIFO, or an oversized file — arm
    code has already run, with `/work` writable, by the time quality reads or rewrites `pyproject.toml`."""


class InvalidEntryPoint(UnsafeFile):
    """The arm's `pyproject.toml` `project.scripts.troupe` entry point is not a safe dotted-identifier chain
    (fix round 2, item 7) — refused rather than interpolated into a shell command unchecked. A subclass of
    `UnsafeFile` (same "refuse on doubt" meaning), but deliberately *not* caught by `targets()`'s own
    fallback-on-parse-error handling: this one is recorded as `run_all`'s `targets_crashed`, not silently
    swallowed into the safe `["."]` default the way a merely-unreadable file is."""


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
    config file. `lstat` first (never follows a link to even check). The open itself adds `O_NONBLOCK` (fix
    round 2, item 6): without it, a FIFO substituted between the `lstat` and the `open` could make `os.open`
    itself block forever waiting for a writer — a host-side hang, not just a wrong read. `os.fstat` on the
    now-open descriptor re-checks `S_ISREG` and the size: this is the authoritative check (it can no longer be
    raced — a descriptor's type can't change after `open` returns), the `lstat` above is only a fast, cheap
    first refusal."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(st.st_mode):
        raise UnsafeFile(f"{path} is not a regular file (mode {oct(st.st_mode)})")
    if st.st_size > max_size:
        raise UnsafeFile(f"{path} is {st.st_size} bytes (cap {max_size})")
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        fst = os.fstat(fd)
        if not stat.S_ISREG(fst.st_mode):
            raise UnsafeFile(f"{path} is not a regular file once opened (mode {oct(fst.st_mode)})")
        if fst.st_size > max_size:
            raise UnsafeFile(f"{path} is {fst.st_size} bytes once opened (cap {max_size})")
        data = os.read(fd, max_size + 1)
    finally:
        os.close(fd)
    if len(data) > max_size:
        raise UnsafeFile(f"{path} grew past {max_size} bytes while it was being read")
    return data.decode("utf-8", errors="replace")


def _safe_write(path: Path, text: str, max_size: int = MAX_CONFIG_BYTES) -> None:
    """Refuses (`UnsafeFile`) to write through a symlink or onto any other non-regular-file path — never
    follows a link to write somewhere outside the copy. Writes to a fresh `tempfile.mkstemp` temp file in the
    same directory (fix round 3, item 3: `mkstemp` guarantees a fresh, securely-named, `O_EXCL`-created file —
    no hand-rolled name scheme, and a pre-existing path collision never escapes as a raw `FileExistsError`,
    `mkstemp` retries internally) and `os.replace`s it onto `path`: `rename(2)` replaces whatever directory
    entry is at `path` atomically and without following it, so even a symlink swapped in at the last moment is
    simply replaced, never written through — this makes the write immune to the read/write TOCTOU a plain
    "check-then-truncate-and-write" would still have. The write loop and the replace are one `try/except
    BaseException: unlink the temp file; re-raise` (fix round 3, item 3): a failure at either step — a short
    write, a disk-full `os.write`, or a failed `os.replace` — must never leave the temp file behind. A path
    that doesn't exist yet, or that already exists as a plain regular file, both succeed; one that exists as
    anything else is refused before the temp file is even created."""
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
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        try:
            written = 0
            while written < len(body):
                written += os.write(fd, body[written:])
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _valid_module_path(mod: str) -> bool:
    """A safe dotted-identifier chain (`troupe_cfg`, `troupe_cfg.cli`) — every dotted part must itself be a
    valid Python identifier. Anything else (shell metacharacters, an empty part, a leading digit, ...) is
    refused rather than guessed at or partially trusted."""
    return bool(mod) and all(part.isidentifier() for part in mod.split("."))


def targets(copy: Path) -> list[str]:
    if (copy / "src").is_dir():
        return ["src"]
    try:
        text = _safe_read(copy / "pyproject.toml")
    except UnsafeFile:
        return ["."]                        # an unsafe pyproject.toml: the safe default, not a hard refusal
    if text is None:
        return ["."]
    try:
        scripts = tomllib.loads(text).get("project", {}).get("scripts", {})
    except tomllib.TOMLDecodeError:
        return ["."]
    mod_full = scripts.get("troupe", "").split(":")[0]
    if not mod_full:
        return ["."]
    if not _valid_module_path(mod_full):
        # Unlike an unreadable/unparsable file, a *present but malformed* entry point is worth surfacing as
        # a crash (fix round 2, item 7) — it means the arm shipped something that doesn't look like a plain
        # module path, which is exactly the case that must never reach a shell command uninspected.
        raise InvalidEntryPoint(f"entry-point module {mod_full!r} is not a plain dotted identifier chain")
    mod = mod_full.split(".")[0]
    if (copy / mod).is_dir():
        return [mod]
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


# `unmeasured`: set only when a run completed and EVERY mutant came back "no tests" or "skipped" -- nothing to
# score, but not a crash either. Worded neutrally on purpose: an arm whose tests reach its code only through
# subprocesses produces this, and so would a harness fault in mutmut's coverage attribution (a pattern
# across arms points at the harness).
UNMEASURED_NO_COVERAGE = "no test coverage attributed"


def mutation_summary(c: dict[str, int], *, partial: bool, baseline_failed: bool, crashed: bool = False,
                     **extra: object) -> dict[str, object]:
    denom = c["total"] - c["no_tests"] - c["skipped"]
    score = None if crashed else ((c["killed"] / denom) if denom > 0 else None)
    unmeasured = (UNMEASURED_NO_COVERAGE if not crashed and c["total"] > 0 and denom == 0 else None)
    return {**c, "score": score, "partial": partial, "baseline_failed": baseline_failed, "crashed": crashed,
            "unmeasured": unmeasured, **extra}


def parse_results(text: str) -> tuple[list[str], dict[str, int]]:
    """One status per mutant name. If a name appears more than once (fix round 3, item 1 — a duplicate line,
    or a status-shaped line from elsewhere in the stream), the LAST occurrence wins and it is counted exactly
    once, never summed — duplicates must never inflate a count. `names` preserves first-seen order."""
    by_name: dict[str, str] = {}
    order: list[str] = []
    for m in re.finditer(r"(?m)^\s*(\S+__mutmut_\d+): ([a-z ]+?)\s*$", text):
        name, status = m.group(1), m.group(2)
        if name not in by_name:
            order.append(name)
        by_name[name] = status
    counts = {k: 0 for k in MUTATION_COUNT_KEYS}
    for status in by_name.values():
        counts[STATUS.get(status, "not_checked")] += 1
    counts["total"] = len(by_name)
    return order, counts


def _last_marker(text: str, name: str) -> int | None:
    """The LAST `name=<int>` occurrence in `text`, anchored to its own line (fix round 2, item 4): arm code
    running during `mutmut run` can print arbitrary stdout, including a line that looks exactly like one of
    our own `__run_rc=0` / `__results_rc=0` markers, to forge apparent success. Our own `echo` for a marker
    always runs strictly after everything that step could have produced, so the real marker is always the
    last anchored occurrence — never the first. `text` must be `stdout` only, never `stderr` (the real
    markers are only ever written there; searching `stderr` too would only widen the forgery surface for no
    benefit). A file-based marker (written somewhere the arm's uid cannot reach) would close this more
    completely, but `mode="script"` containers have no harness-owned mount to write it into without changing
    `hidden.py` itself — out of this task's file scope; anchored-last-line is the documented fallback."""
    matches = re.findall(rf"(?m)^{re.escape(name)}=(-?\d+)$", text)
    return int(matches[-1]) if matches else None


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

def mutation_env(copy: Path) -> dict[str, str]:
    """Extra env for the three mutation containers (listing, run, results) -- never baseline, mypy or ruff.

    mutmut 3 copies the project, `pyproject.toml` and `uv.lock` included, into `mutants/` and runs the arm's
    tests from there. An arm test that shells out to the CLI the contract prescribes (`uv run troupe ...` with
    cwd = the repo root computed from `__file__`) therefore runs `uv run` inside `mutants/`; uv discovers
    `mutants/` as a project of its own and, offline with `UV_NO_SYNC=1`, creates an EMPTY `mutants/.venv`,
    cannot install the project, and fails `Failed to spawn` -- that test fails mutmut's stats phase and the
    whole run crashes (canary control/01). `UV_PROJECT_ENVIRONMENT` points uv at the copy's prepared `.venv`
    (by its in-container path: `hidden._spec` mounts `copy.parent` at `/work`, workdir `/work/<copy.name>`).
    The subprocess then runs the prepared, UNMUTATED install, and mutmut 3 cannot attribute coverage across a
    subprocess anyway, so code reached only that way comes out `no tests` -- excluded from the score's
    denominator by `mutation_summary`, not counted as survived. (Putting `mutants/src` on PYTHONPATH as well was
    tried by the controller and breaks the mutmut run.)"""
    return {"UV_PROJECT_ENVIRONMENT": f"/work/{copy.name}/.venv"}


def _script_spec(p: Paths, copy: Path, cmd: list[str], *, name: str = "quality",
                 env: dict[str, str] | None = None) -> RunSpec:
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
    return hidden._spec(p, copy, cmd, mode="script", name=name, env=env)


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


def _run(p: Paths, copy: Path, cmd: list[str], timeout: int, env: dict[str, str] | None = None) -> ToolRun:
    """Every quality tool runs in its own tester container (see `_script_spec`); `hidden._run` also cleans up
    the per-container home directory this creates, whether the run succeeds, fails or times out. A container
    that does not finish within `timeout` is recorded as `timed_out` — never raised away (fix round 1, item 4:
    `run_all` always returns and records something, for every tool: baseline, mypy, ruff, mutation)."""
    from runner import hidden          # lazy: Task 18's module, not a module-load-time dependency
    try:
        r = hidden._run(_script_spec(p, copy, cmd, env=env), timeout=timeout)
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
    out = _run(p, copy, cmd, 1800, env=mutation_env(copy))
    return parse_results(out.combined)[0]


_BASELINE_SCRIPT = ".venv/bin/python -m pytest -q -p no:cacheprovider -x"
_RESULTS_SCRIPT = ".venv/bin/mutmut results --all true"
_LOG_NAMES_MAX = 5          # a sample longer than this is shown in mutmut.log as a count, not every name


# --- O1 (owner, 2026-10-08): node IDs pytest cannot resolve inside mutmut's own process -------------------------
# mutmut 3 runs pytest IN-PROCESS several times and passes the node IDs its stats run recorded back as arguments. An
# ID that a second in-process collection renders differently cannot be found (pass 1 ccsdd: `ids=repr` over strings
# holding "\n" gains a level of escaping on every collection after the first), pytest exits 4, and mutmut aborts the
# whole run (`BadTestExecutionCommandsException`, `mutmut run` rc 1) with every mutant `not checked`. Only after such
# a failure, the harness finds those IDs the same way (one full collection, then each ID resolved by a LATER
# collection in the same process, bisecting), maps each to its function-level ID (a superset: every parametrisation
# of that test) through a pytest plugin passed in `PYTEST_ADDOPTS`, and resumes `mutmut run` once on its saved stats
# within what is left of the same `mutation_seconds`. A run that succeeds never gets here, so an arm without such IDs
# runs exactly the original method; `nodeid_rewrites` records None (never checked), 0 or the count.

NODEID_PLUGIN = "bk_nodeid_rewrite"
_NODEID_MARKER = "__nodeid_unresolved"
_NODEID_SCRIPT = r"""
import contextlib, io, json, pytest
def run(args, plugins=()):
    b = io.StringIO()
    with contextlib.redirect_stdout(b), contextlib.redirect_stderr(b):
        return int(pytest.main(["--rootdir=.", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
                               plugins=list(plugins)))
class C:
    ids = []
    def pytest_itemcollected(self, item):
        C.ids.append(item.nodeid)
def bad(ids):
    if not ids or run(ids) == 0:
        return []
    if len(ids) == 1:
        return ids
    m = len(ids) // 2
    return bad(ids[:m]) + bad(ids[m:])
first = run([], [C()])
out = bad(list(dict.fromkeys(C.ids))) if first == 0 else None
print()
print("%s=" + json.dumps(out))
""" % _NODEID_MARKER


def function_level_nodeid(nodeid: str) -> str:
    """The node ID without its parametrisation, split exactly as pytest splits a command-line argument
    (`arg.partition("[")`): it selects every parametrisation of that test."""
    return nodeid.partition("[")[0]


def parse_unresolved_nodeids(stdout: str) -> list[str] | None:
    """The LAST anchored `__nodeid_unresolved=<json>` line (the arm's collection output could print a forged one
    earlier). None unless it is a JSON list of node IDs that each carry a parametrisation (`::` and `[`)."""
    found = re.findall(rf"(?m)^{_NODEID_MARKER}=(.*)$", stdout)
    try:
        got = json.loads(found[-1]) if found else None
    except json.JSONDecodeError:
        return None
    if not isinstance(got, list) or not all(isinstance(x, str) and "::" in x and "[" in x for x in got):
        return None
    return got


def nodeid_plugin_source(unresolved: list[str]) -> str:
    mapping = {n: function_level_nodeid(n) for n in unresolved}
    return ('"""Written by the bake-off harness (owner ruling O1): maps node IDs pytest cannot resolve in mutmut\'s\n'
            'process to their function-level IDs. Loaded only through PYTEST_ADDOPTS for a resumed mutmut run."""\n'
            f"_MAP = {json.dumps(mapping, sort_keys=True)}\n\n\n"
            "def pytest_configure(config):\n"
            "    config.args = list(dict.fromkeys(_MAP.get(a, a) for a in config.args))\n")


def _install_nodeid_plugin(copy: Path, unresolved: list[str]) -> None:
    sps = sorted((copy / ".venv" / "lib").glob("python*/site-packages"))
    if len(sps) != 1 or sps[0].is_symlink() or not sps[0].is_dir():
        raise UnsafeFile(f"expected exactly one real site-packages directory in the copy's .venv, found {sps}")
    _safe_write(sps[0] / f"{NODEID_PLUGIN}.py", nodeid_plugin_source(unresolved))


def mutmut_run_log_line(mutmut_argv: list[str], n_chosen: int, timeout_s: int) -> str:
    """The `$ ` line mutmut.log records for container 1: the argv mutmut really received (venv binary, flags,
    the chosen mutant names -- elided to a count past `_LOG_NAMES_MAX`), then the sample size and the inner
    `timeout` it ran under. Built from the same list `run_cmd` is, so the evidence cannot drift from what ran
    (the e2e copy-B check greps this line for `.venv/bin/mutmut run`). Names are shlex-quoted."""
    fixed, names = mutmut_argv[:len(mutmut_argv) - n_chosen], mutmut_argv[len(mutmut_argv) - n_chosen:]
    shown = [shlex.quote(a) for a in fixed]
    if len(names) > _LOG_NAMES_MAX:
        shown += [shlex.quote(n) for n in names[:2]] + [f"... <{len(names) - 2} more>"]
    else:
        shown += [shlex.quote(n) for n in names]
    what = f"sampled {n_chosen}" if n_chosen else "all"
    return f"$ {' '.join(shown)}  ({what}; under timeout {timeout_s}s)"


def _mutation(p: Paths, copy: Path, tg: list[str], out_dir: Path, pins: config.Pins,
              log_dir: Path | None = None, deselect: tuple[str, ...] = ()) -> dict[str, object]:
    """Mutation testing runs only on copy B (review C-1). The arm's own tests are the baseline: only the arm's
    pytest actually failing (rc 1) is `baseline_failed` — the arm's own result, not ours, and never scored.
    rc 5 means no tests were collected (`no_tests`), also not scored and not the arm's fault. Any other exit —
    a harness/container-level code (125, 126, 127, 137, ...), an unexpected crash, or a timeout — is `crashed`:
    the score is withheld (`None`), never read as `0.0`, and never confused with `baseline_failed`/`no_tests`
    (fix round 1, item 5).

    The mutation run itself happens in TWO containers (fix round 3, item 1): container 1 runs `mutmut run`
    (mutmut's own stdout/stderr redirected to a log file inside it — arm test code executes here and must
    never be able to print a line shaped like `<name>__mutmut_N: killed` and have it counted); container 2 is
    fresh and runs nothing but `mutmut results --all true` against the same host-mounted copy, so its stdout
    cannot carry anything the arm's own test output printed. It still executes the arm-writable
    `.venv/bin/mutmut`, so the residual-tampering limit below applies to it too. Status lines are parsed ONLY
    from container 2's stdout. `parse_results` also keeps one status per name — a duplicate line (forged or not) is never
    summed, the last occurrence wins.

    Each container gets its own exit-code marker (read from the LAST anchored occurrence on its own line in
    stdout only, never the first — even a forged marker embedded in container 1's tailed log cannot beat our
    own `echo`, which is always the provably-last line; fix round 2, item 4); either marker failing is also
    `crashed`, not "no mutants" (item 2) — as is the degenerate case where no mutant gets a real verdict and
    any is left unresolved (`not_checked`, `check_interrupted`, or a sampled name missing), even with some
    "no tests" alongside (mutmut assigns those in its stats phase, before checking anything — a run cut off by
    the inner timeout looks exactly like this) and even though nothing else looked wrong: zero real signal
    must never present as a score of `0.0`. The one exemption is a completed run in which EVERY mutant is
    "no tests" or "skipped": not crashed, score `None`, `unmeasured` set (`UNMEASURED_NO_COVERAGE`) — see
    `mutation_env` for how that arises. `check_interrupted` on its own (a mutant whose check
    was interrupted mid-way — typically a signal — without everything being interrupted) sets `partial`, the
    same as a partial `not_checked` set (fix round 2, item 1). Fewer statuses coming back than were sampled —
    mutmut silently dropping a requested mutant — also sets `partial` and is recorded as `missing_results`
    (item 5). Every return path — baseline failure, no tests, a harness fault, a refused pyproject.toml, either
    container timing out, or a real (possibly partial or crashed) run — carries the exact same key set, via the
    `common`/`post_sample_common` defaults below, so a consumer never has to guess which keys a given path
    bothered to set.

    **What this does not, and cannot, guard against** (fix round 3, item 2 — an owner-visible limitation, not
    a bug): the arm's own pytest process, running each mutant, is the same uid as the harness's `mutmut`
    invocation, with `/work` writable. A sufficiently determined arm could tamper with its own
    `.venv/bin/mutmut`, or write directly into `mutants/*.meta`/`mutants/mutmut-stats.json` — mutmut's own
    persisted result state — to fabricate a result container 2 would then read back as genuine, no forged
    stdout line required. The stdout hardening in this function closes the *accidental* and the
    *unprivileged-forgery* case (a stray print, or a naive attempt at gaming a printed line); it is not, and
    cannot be, a guarantee against a hostile arm actively rewriting its own tooling or its own on-disk mutation
    results. The mutation score is therefore only as trustworthy as the arm's own environment — a limitation
    of the whole "run untrusted code and trust the numbers it reports" method (OD15), not something quality.py
    can fix from the outside. Given the score is a 10%-weight input to the overall code-quality dimension
    (design §8), this residual risk is recorded here and in the task report rather than treated as solved."""
    lim = pins.limits
    log: list[str] = []

    def finish(counts: dict[str, int], *, partial: bool, baseline_failed: bool, crashed: bool = False,
              **extra: object) -> dict[str, object]:
        qd = log_dir or out_dir / "quality"         # log_dir: a scoring re-run's own folder (rerun.py, O1-O3)
        qd.mkdir(parents=True, exist_ok=True)
        summary = mutation_summary(counts, partial=partial, baseline_failed=baseline_failed, crashed=crashed,
                                   **extra)
        (qd / "mutmut.log").write_text("\n".join(log))
        return summary

    common = dict(sampled=False, sample_size=0, mutmut_run_rc=None, mutmut_results_rc=None, missing_results=0,
                  nodeid_rewrites=None)

    baseline = _run(p, copy, ["bash", "-c", _BASELINE_SCRIPT], lim.mutation_baseline_seconds)     # O2
    log.append(f"$ {_BASELINE_SCRIPT}  (baseline)\n" + baseline.combined[-4000:])
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
        log.append(f"# set_mutmut_paths refused: {e}")
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling="n/a", baseline_rc=baseline.rc, timed_out=False, **common)

    sampling, chosen = "all", []
    if lim.mutation_sample > 0:
        try:
            names = list_mutants(p, copy, tg)
        except UnsafeFile as e:
            log.append(f"# list_mutants refused: {e}")
            names = []
        if names:
            chosen, sampling = sample(names, lim.mutation_sample), "seeded-sha256"
        else:
            sampling = "unavailable"          # listing unsupported (or refused/timed out): fall back to A

    post_sample_common: dict[str, object] = dict(sampled=bool(chosen), sample_size=len(chosen), nodeid_rewrites=None)

    # Container 1: the actual mutation run. Arm test code executes here (it IS the arm's own pytest suite,
    # run under each mutant), so anything it prints to stdout must never reach a stream this function later
    # searches for a status line or a marker (fix round 3, item 1) -- mutmut's own stdout/stderr are redirected
    # to a log file *inside* the container instead. The exit code is captured into a shell variable immediately
    # (before the log tail, which could itself contain a forged marker-lookalike from the arm) and echoed last,
    # so the real marker is provably the final line regardless of what the tailed log contains. Mutant names
    # still reach mutmut through argv, never string interpolation (fix round 1): bash's own positional-parameter
    # handling quotes each one safely regardless of content, with no shell-injection surface.
    run_script = ('timeout "$1" "${@:2}" >mutmut-run.log 2>&1; rc=$?; tail -c 20000 mutmut-run.log; '
                  'echo __run_rc=$rc')
    mutmut_argv = [".venv/bin/mutmut", "run", "--max-children", "4", *chosen]
    run_cmd = ["bash", "-c", run_script, "_", str(lim.mutation_seconds), *mutmut_argv]
    menv = mutation_env(copy)
    if deselect:            # O5 (scoring re-run only): never the baseline above, which keeps every test
        menv["PYTEST_ADDOPTS"] = " ".join(f"--deselect {shlex.quote(t)}" for t in deselect)
        log.append("# O5 deselected from the mutmut runs: " + ", ".join(deselect))
    log.append("# listing, run and results containers: "
               + " ".join(f"{k}={v}" for k, v in menv.items())
               + "  (so `uv run` from inside mutants/ uses the prepared venv; the baseline above ran without it)")
    t0 = time.monotonic()
    run_outcome = _run(p, copy, run_cmd, lim.mutation_seconds + 300, env=menv)
    log.append(mutmut_run_log_line(mutmut_argv, len(chosen), lim.mutation_seconds) + "\n"
              + run_outcome.combined[-20000:])
    if run_outcome.timed_out:
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling=sampling, baseline_rc=baseline.rc, timed_out=True,
                      mutmut_run_rc=None, mutmut_results_rc=None, missing_results=0, **post_sample_common)
    run_rc = _last_marker(run_outcome.stdout, "__run_rc")
    if run_rc not in (0, 124):                  # O1: only a failed run is checked for unresolvable node IDs
        det = _run(p, copy, ["bash", "-c", 'cd mutants && exec ../.venv/bin/python -c "$1"', "_", _NODEID_SCRIPT],
                   600, env=menv)
        bad_ids = None if det.timed_out else parse_unresolved_nodeids(det.stdout)
        post_sample_common["nodeid_rewrites"] = None if bad_ids is None else len(bad_ids)
        log.append("# O1 check for node IDs pytest cannot resolve on a later in-process collection: "
                   + ("timed out" if det.timed_out else "no valid result" if bad_ids is None
                      else f"{len(bad_ids)}" + "".join(f"\n#   {n}" for n in bad_ids)))
        left = lim.mutation_seconds - int(time.monotonic() - t0)
        if bad_ids and left > 0:
            try:
                _install_nodeid_plugin(copy, bad_ids)
            except UnsafeFile as e:
                log.append(f"# O1 plugin refused: {e}")
            else:
                env2 = {**menv, "PYTEST_ADDOPTS": " ".join(filter(None, (menv.get("PYTEST_ADDOPTS"),
                                                                         f"-p {NODEID_PLUGIN}")))}
                run2_cmd = ["bash", "-c", run_script, "_", str(left), *mutmut_argv]
                run_outcome = _run(p, copy, run2_cmd, left + 300, env=env2)
                log.append(f"# O1 resumed with node IDs mapped to their function (PYTEST_ADDOPTS={env2['PYTEST_ADDOPTS']})\n"
                           + mutmut_run_log_line(mutmut_argv, len(chosen), left) + "\n" + run_outcome.combined[-20000:])
                if run_outcome.timed_out:
                    return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                                  sampling=sampling, baseline_rc=baseline.rc, timed_out=True,
                                  mutmut_run_rc=None, mutmut_results_rc=None, missing_results=0, **post_sample_common)
                run_rc = _last_marker(run_outcome.stdout, "__run_rc")

    # Container 2: fresh, and runs nothing but `mutmut results` (fix round 3, item 1), so no line the arm's test
    # output printed during the run can reach its stdout. It does run the arm-writable `.venv/bin/mutmut`, so a
    # deliberately tampered binary is NOT excluded -- see "what this does not guard against" above. mutmut's own
    # persisted state (the `mutants/` directory) survives on the host-mounted copy between the two containers,
    # so this one sees exactly what the run container just recorded. Status lines are parsed ONLY from here.
    results_outcome = _run(p, copy, ["bash", "-c", _RESULTS_SCRIPT + "; echo __results_rc=$?"], 300, env=menv)
    log.append(f"$ {_RESULTS_SCRIPT}  (fresh container)\n" + results_outcome.combined[-20000:])
    if results_outcome.timed_out:
        return finish(dict(ZERO_MUTATION), partial=False, baseline_failed=False, crashed=True,
                      sampling=sampling, baseline_rc=baseline.rc, timed_out=True,
                      mutmut_run_rc=run_rc, mutmut_results_rc=None, missing_results=0, **post_sample_common)
    results_rc = _last_marker(results_outcome.stdout, "__results_rc")

    out = results_outcome.stdout
    # A crash in `mutmut results` (or a missing marker entirely) is recorded as a crash, not "no mutants".
    crashed = results_rc != 0 or run_rc not in (0, 124)

    names, counts = parse_results(out)
    if chosen:
        wanted = set(chosen)
        _, counts = parse_results("\n".join(ln for ln in out.splitlines() if ln.strip().split(":")[0] in wanted))
    real_outcomes = sum(counts.get(k, 0) for k in _REAL_OUTCOME_KEYS)
    missing = max(0, len(chosen) - counts.get("total", 0)) if chosen else 0
    unresolved = counts.get("not_checked", 0) + counts.get("check_interrupted", 0) + missing
    expected_any_result = counts.get("total", 0) > 0 or bool(chosen)
    if (not crashed and expected_any_result and real_outcomes == 0
            and (unresolved > 0 or counts.get("total", 0) == 0)):
        # No real verdict at all and something left unresolved (not_checked/check_interrupted, a sampled name
        # mutmut never mentioned, or nothing at all) even though nothing else looked wrong: no real signal, so
        # this must never present as a precise-looking 0.0 (the exact regression this closes) -- including when
        # some mutants are "no tests" (assigned in mutmut's stats phase, before any check) and the rest were
        # never checked, e.g. a run cut off by the inner timeout. The ONE exemption: every mutant "no tests" or
        # "skipped" -- a completed run with nothing to score, recorded as `unmeasured`, not crashed.
        crashed = True
    partial = (not crashed) and (run_rc == 124 or counts.get("not_checked", 0) > 0 or
                                 counts.get("check_interrupted", 0) > 0 or missing > 0)
    return finish({k: counts[k] for k in ZERO_MUTATION}, partial=partial, baseline_failed=False, crashed=crashed,
                  sampling=sampling, baseline_rc=baseline.rc, timed_out=False, missing_results=missing,
                  mutmut_run_rc=run_rc, mutmut_results_rc=results_rc, **post_sample_common)


def _mutation_placeholder(sampling: str, *, crashed: bool = True, baseline_failed: bool = False,
                          baseline_rc: int | None = None, timed_out: bool = False) -> dict[str, object]:
    """A mutation summary carrying the full key set, for a path that never reached a real mutmut invocation
    at all — install failed, or an unexpected exception inside `_mutation` itself. Every path through this
    module returns the same keys, whatever went wrong (fix round 2, item 2)."""
    return mutation_summary(dict(ZERO_MUTATION), partial=False, baseline_failed=baseline_failed, crashed=crashed,
                            sampled=False, sample_size=0, sampling=sampling, baseline_rc=baseline_rc,
                            timed_out=timed_out, mutmut_run_rc=None, mutmut_results_rc=None, missing_results=0,
                            nodeid_rewrites=None)


def run_all(p: Paths, prep: "hidden.Prepared", out_dir: Path, pins: config.Pins | None = None) -> dict[str, object]:
    """mypy and ruff run on copy A (never mutated); mutmut runs only on copy B (review C-1: copy A must come
    out of this untouched). `pins` may be overridden by the caller (e.g. the dry run's cheaper mutation
    budget) — default is the real pinned limits.

    Every phase — `targets()`, mypy, the isolated ruff pass, `_has_arm_ruff_config()` and the arm-config ruff
    pass, `tool_versions()`, and `_mutation` — runs inside its own `try/except Exception`, never just the ones
    that happened to be exercised so far (fix round 2, item 2: the earlier version only guarded `targets()`
    and `_mutation`, so an exception in mypy or ruff would still crash the whole function and lose every
    result, including `summary.json` itself, not just that phase's). A caught exception is recorded as that
    phase's `<phase>_crashed = True` plus `<phase>_error` (`f"{type(e).__name__}: {e}"`, capped) — visible,
    not silently swallowed. This function therefore always returns, and always writes `summary.json`, however
    badly any individual tool misbehaves."""
    pins = pins or config.load_pins()
    qd = out_dir / "quality"
    qd.mkdir(parents=True, exist_ok=True)
    a, b = prep.hidden_copy, prep.quality_copy

    try:
        tg = targets(a)
        targets_crashed, targets_error = False, None
    except Exception as e:                       # noqa: BLE001 -- never lose the rest of the run's evidence
        tg, targets_crashed = ["."], True
        targets_error = f"{type(e).__name__}: {e}"[:200]

    try:
        mypy_targets = " ".join(shlex.quote(t) for t in tg)     # never interpolated raw (fix round 2, item 7)
        mypy_run = _run(p, a, ["bash", "-c", "/opt/harness/bin/mypy --strict --no-incremental "
                        "--cache-dir /tmp/mypy-cache --python-executable .venv/bin/python " + mypy_targets], 1800)
        (qd / "mypy.txt").write_text(mypy_run.combined)
        if mypy_run.timed_out:
            mypy_errors_val, mypy_crashed, mypy_timed_out, mypy_error = None, True, True, None
        else:
            assert mypy_run.rc is not None          # ToolRun invariant: rc is None only when timed_out
            mypy_errors_val, mypy_crashed = mypy_result(mypy_run.rc, mypy_run.combined)
            mypy_timed_out, mypy_error = False, None
    except Exception as e:                       # noqa: BLE001 -- never lose the rest of the run's evidence
        mypy_errors_val, mypy_crashed, mypy_timed_out = None, True, False
        mypy_error = f"{type(e).__name__}: {e}"[:200]

    try:
        ruff_run = _run(p, a, ["bash", "-c", "/opt/harness/bin/ruff check --isolated --exit-zero "
                        "--cache-dir /tmp/ruff-cache --output-format json ."], 600)
        (qd / "ruff.json").write_text(ruff_run.stdout)
        if ruff_run.timed_out:
            ruff_n, ruff_crashed, ruff_timed_out, ruff_error = None, True, True, None
        else:
            assert ruff_run.rc is not None          # ToolRun invariant: rc is None only when timed_out
            ruff_n, ruff_crashed = ruff_parse(ruff_run.rc, ruff_run.stdout)
            ruff_timed_out, ruff_error = False, None
    except Exception as e:                       # noqa: BLE001 -- never lose the rest of the run's evidence
        ruff_n, ruff_crashed, ruff_timed_out = None, True, False
        ruff_error = f"{type(e).__name__}: {e}"[:200]

    ruff_arm = ruff_arm_crashed = ruff_arm_error = None
    ruff_arm_timed_out = False
    try:
        has_cfg, ruff_arm_precheck_crashed = _has_arm_ruff_config(a)
        if ruff_arm_precheck_crashed:
            ruff_arm_crashed = True
        elif has_cfg:
            ra_run = _run(p, a, ["bash", "-c", "/opt/harness/bin/ruff check --exit-zero "
                           "--cache-dir /tmp/ruff-cache-arm --output-format json ."], 600)
            (qd / "ruff-arm.json").write_text(ra_run.stdout)
            if ra_run.timed_out:
                ruff_arm, ruff_arm_crashed, ruff_arm_timed_out = None, True, True
            else:
                assert ra_run.rc is not None        # ToolRun invariant: rc is None only when timed_out
                ruff_arm, ruff_arm_crashed = ruff_parse(ra_run.rc, ra_run.stdout)
    except Exception as e:                       # noqa: BLE001 -- never lose the rest of the run's evidence
        ruff_arm, ruff_arm_crashed, ruff_arm_timed_out = None, True, False
        ruff_arm_error = f"{type(e).__name__}: {e}"[:200]

    try:
        versions = tool_versions()
    except Exception as e:                       # noqa: BLE001 -- never lose the rest of the run's evidence
        versions = {"error": f"{type(e).__name__}: {e}"[:200]}

    if b is not None and prep.prep.get("quality", {}).get("ok"):
        try:
            mut = _mutation(p, b, tg, out_dir, pins)
        except Exception as e:           # noqa: BLE001 -- never lose the run's evidence to an exception
            mut = _mutation_placeholder(f"error: {type(e).__name__}: {e}"[:200])
    else:
        mut = _mutation_placeholder("install failed")
    (qd / "mutation.json").write_text(json.dumps(mut, indent=2))

    s: dict[str, object] = {
        "mypy_errors": mypy_errors_val, "mypy_crashed": mypy_crashed, "mypy_timed_out": mypy_timed_out,
        "mypy_error": mypy_error,
        "ruff_findings": ruff_n, "ruff_crashed": ruff_crashed, "ruff_timed_out": ruff_timed_out,
        "ruff_error": ruff_error,
        "ruff_arm_findings": ruff_arm, "ruff_arm_crashed": ruff_arm_crashed,
        "ruff_arm_timed_out": ruff_arm_timed_out, "ruff_arm_error": ruff_arm_error,
        "mutation": mut, "targets": tg, "targets_crashed": targets_crashed, "targets_error": targets_error,
        "tool_versions": versions,
    }
    (qd / "summary.json").write_text(json.dumps(s, indent=2))
    return s
