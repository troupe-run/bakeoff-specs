"""Code quality: `mypy --strict`, ruff (isolated + the arm's own config), mutmut over the arm's own tests
(OD15), all inside the tester container, `--network none` (design §8, review C-1: mypy/ruff run on copy A,
mutmut only on copy B — an arm's mutation testing must never be able to see or touch the copy hidden tests
run against).

Tool failures (a crash, a timeout) are recorded as such and kept distinct from a real, clean result — a
crashed mypy is not "0 errors", a crashed mutation run is not "score 0" (every mutant "survived") or
"score 100" (denominator collapses to zero instead, via `mutation_summary`). Tool versions are read from the
same pinned requirements files the tester image itself installs from, so the numbers are reproducible without
re-deriving or guessing a version.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from runner import config
from runner.paths import Paths, REPO_ROOT

# `runner.hidden` (Task 18) is imported lazily, inside `_run` only, so this module has no hard import-time
# dependency on it — pure tests (test_quality.py) run with no hidden.py present at all. The only names used
# are `hidden.Prepared` (a type hint, never introspected at runtime), `hidden._spec(p, copy, cmd, *, network,
# proxy, out, env, workdir, name) -> RunSpec`, and `hidden._run(spec, timeout) -> CompletedProcess` — the same
# per-container-home-cleanup helper `hidden.py` itself uses. See the module docstring / task report for why.
if TYPE_CHECKING:
    from runner import hidden

TESTER_DIR = REPO_ROOT / "runner" / "images" / "tester"

STATUS = {"killed": "killed", "survived": "survived", "timeout": "timeout", "suspicious": "suspicious",
          "no tests": "no_tests", "skipped": "skipped", "not checked": "not_checked", "segfault": "killed"}

# One shared zero-summary literal (review m10: this dict was repeated 3x). `mutation_summary` only ever
# reads from a copy of it (`{**c, ...}`), so it is never mutated in place.
ZERO_MUTATION: dict[str, int] = {"killed": 0, "survived": 0, "timeout": 0, "suspicious": 0, "no_tests": 0,
                                 "skipped": 0, "total": 0}


# --- pure --------------------------------------------------------------------------------------------------

def mypy_errors(text: str) -> int:
    m = re.search(r"Found (\d+) errors?", text)
    return int(m.group(1)) if m else 0


def mypy_ok(rc: int) -> bool:
    """mypy exits 0 (clean) or 1 (errors found) for a real result; anything else is a tool crash
    (bad invocation, internal error) — never read as "0 errors"."""
    return rc in (0, 1)


def ruff_count(text: str) -> int:
    return len(json.loads(text or "[]"))


def ruff_parse(rc: int, text: str) -> tuple[int | None, bool]:
    """`--exit-zero` makes rc 0 for real findings; a genuine ruff crash still exits nonzero, or (rarely)
    exits 0 without producing the JSON array it always produces on a working run. Either way: crashed,
    findings unknown — never reported as 0 findings."""
    try:
        n = ruff_count(text)
    except json.JSONDecodeError:
        return None, True
    return n, rc != 0


def tool_versions() -> dict[str, str]:
    """Pinned tool versions the tester image actually installs from (reproducibility, controller ruling) —
    read from the same requirements files the image build uses, not re-derived or queried at run time."""
    text = (TESTER_DIR / "requirements.txt").read_text() + "\n" + (TESTER_DIR / "mutmut-requirements.txt").read_text()
    out = {}
    for name in ("mypy", "ruff", "mutmut", "pytest"):
        m = re.search(rf"(?m)^{name}==(\S+)", text)
        if m:
            out[name] = m.group(1)
    return out


def targets(copy: Path) -> list[str]:
    if (copy / "src").is_dir():
        return ["src"]
    try:
        scripts = tomllib.loads((copy / "pyproject.toml").read_text()).get("project", {}).get("scripts", {})
        mod = scripts.get("troupe", "").split(":")[0].split(".")[0]
        if mod and (copy / mod).is_dir():
            return [mod]
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return ["."]


def mutation_summary(c: dict[str, int], *, partial: bool, baseline_failed: bool,
                     **extra: object) -> dict[str, object]:
    denom = c["total"] - c["no_tests"] - c["skipped"]
    return {**c, "score": (c["killed"] / denom) if denom > 0 else None, "partial": partial,
            "baseline_failed": baseline_failed, **extra}


def parse_results(text: str) -> tuple[list[str], dict[str, int]]:
    names, counts = [], {v: 0 for v in ["killed", "survived", "timeout", "suspicious", "no_tests", "skipped",
                                        "not_checked"]}
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
    comparability across arms. Every other table is left untouched."""
    f = copy / "pyproject.toml"
    text = f.read_text() if f.exists() else ""
    text = re.sub(r"(?ms)^\[tool\.mutmut\]\n.*?(?=^\[|\Z)", "", text).rstrip("\n")
    f.write_text(text + f"\n\n[tool.mutmut]\npaths_to_mutate = {json.dumps(paths_)}\n")


# --- containers ----------------------------------------------------------------------------------------------

def _run(p: Paths, copy: Path, script: str, timeout: int) -> tuple[int, str]:
    """Every quality tool runs in its own tester container, `--network none` (hidden._run also cleans up
    the per-container home directory this creates, whether the run succeeds, fails or times out)."""
    from runner import hidden          # lazy: Task 18's module, not a module-load-time dependency
    r = hidden._run(hidden._spec(p, copy, ["bash", "-c", script], name="quality"), timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).decode(errors="replace")


def list_mutants(p: Paths, copy: Path, tg: list[str]) -> list[str]:
    """OD15 B precondition: list every mutant without running any. Falls back to OD15 A (run_all records
    `sampling: "unavailable"`) if the pinned mutmut cannot list without running."""
    set_mutmut_paths(copy, tg)
    _, out = _run(p, copy, ".venv/bin/mutmut run '__bk_list_only__' >/dev/null 2>&1; "
                  ".venv/bin/mutmut results --all true", 1800)
    return parse_results(out)[0]


def _mutation(p: Paths, copy: Path, tg: list[str], out_dir: Path, pins: config.Pins) -> dict[str, object]:
    """Mutation testing runs only on copy B (review C-1). The arm's own tests are the baseline: if they
    fail, that is the arm's result (`baseline_failed`), not a mutation score of 0."""
    lim = pins.limits
    log: list[str] = []

    def finish(summary: dict[str, object]) -> dict[str, object]:
        qd = out_dir / "quality"
        qd.mkdir(parents=True, exist_ok=True)
        (qd / "mutmut.log").write_text("\n".join(log))
        return summary

    rc, base = _run(p, copy, ".venv/bin/python -m pytest -q -p no:cacheprovider -x", 1800)
    log.append("$ baseline: pytest\n" + base[-4000:])
    if rc == 5:                                            # the arm has no tests of its own
        return finish(mutation_summary(dict(ZERO_MUTATION), partial=False, baseline_failed=False,
                                       sampled=False, sample_size=0, sampling="no tests"))
    if rc != 0:                                             # the arm's own tests fail: its result, not ours
        return finish(mutation_summary(dict(ZERO_MUTATION), partial=False, baseline_failed=True,
                                       sampled=False, sample_size=0, sampling="n/a"))

    set_mutmut_paths(copy, tg)
    sampling, chosen = "all", []
    if lim.mutation_sample > 0:
        names = list_mutants(p, copy, tg)
        if names:
            chosen, sampling = sample(names, lim.mutation_sample), "seeded-sha256"
        else:
            sampling = "unavailable"                       # listing unsupported by the pinned mutmut: fall back to A
    run = ".venv/bin/mutmut run --max-children 4" + "".join(f" '{n}'" for n in chosen)
    rc, out = _run(p, copy, f"timeout {lim.mutation_seconds} {run}; echo __rc=$?; .venv/bin/mutmut results --all true",
                   lim.mutation_seconds + 900)
    log.append(f"$ {run}\n" + out[-20000:])
    names, counts = parse_results(out)
    if chosen:
        wanted = set(chosen)
        _, counts = parse_results("\n".join(ln for ln in out.splitlines() if ln.strip().split(":")[0] in wanted))
    partial = "__rc=124" in out or counts.get("not_checked", 0) > 0
    return finish(mutation_summary({k: counts[k] for k in ZERO_MUTATION}, partial=partial, baseline_failed=False,
                                   sampled=bool(chosen), sample_size=len(chosen), sampling=sampling))


def run_all(p: Paths, prep: "hidden.Prepared", out_dir: Path, pins: config.Pins | None = None) -> dict[str, object]:
    """mypy and ruff run on copy A (never mutated); mutmut runs only on copy B (review C-1: copy A must come
    out of this untouched). `pins` may be overridden by the caller (e.g. the dry run's cheaper mutation
    budget) — default is the real pinned limits."""
    pins = pins or config.load_pins()
    qd = out_dir / "quality"
    qd.mkdir(parents=True, exist_ok=True)
    a, b = prep.hidden_copy, prep.quality_copy
    tg = targets(a)

    mypy_rc, mypy_out = _run(p, a, "/opt/harness/bin/mypy --strict --no-incremental --python-executable "
                             ".venv/bin/python " + " ".join(tg), 1800)
    (qd / "mypy.txt").write_text(mypy_out)
    mypy_crashed = not mypy_ok(mypy_rc)

    ruff_rc, ruff_out = _run(p, a, "/opt/harness/bin/ruff check --isolated --exit-zero --output-format json . "
                             "2>/dev/null", 600)
    (qd / "ruff.json").write_text(ruff_out)
    ruff_n, ruff_crashed = ruff_parse(ruff_rc, ruff_out)

    has_cfg = any((a / f).exists() for f in ("ruff.toml", ".ruff.toml")) or \
        "[tool.ruff" in ((a / "pyproject.toml").read_text() if (a / "pyproject.toml").exists() else "")
    ruff_arm = ruff_arm_crashed = None
    if has_cfg:
        ra_rc, ra = _run(p, a, "/opt/harness/bin/ruff check --exit-zero --output-format json . 2>/dev/null", 600)
        (qd / "ruff-arm.json").write_text(ra)
        ruff_arm, ruff_arm_crashed = ruff_parse(ra_rc, ra)

    if b is not None and prep.prep.get("quality", {}).get("ok"):
        mut = _mutation(p, b, tg, out_dir, pins)
    else:
        mut = mutation_summary(dict(ZERO_MUTATION), partial=False, baseline_failed=True, sampled=False,
                               sample_size=0, sampling="install failed")
    (qd / "mutation.json").write_text(json.dumps(mut, indent=2))

    s: dict[str, object] = {"mypy_errors": None if mypy_crashed else mypy_errors(mypy_out),
                            "mypy_crashed": mypy_crashed, "ruff_findings": ruff_n, "ruff_crashed": ruff_crashed,
                            "ruff_arm_findings": ruff_arm, "ruff_arm_crashed": ruff_arm_crashed,
                            "mutation": mut, "targets": tg, "tool_versions": tool_versions()}
    (qd / "summary.json").write_text(json.dumps(s, indent=2))
    return s
