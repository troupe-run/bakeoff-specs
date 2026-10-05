"""Mutation re-measure (Plan 3 Task 20): the whole arm test suite per mutant, so no pytest node ID is ever parsed.

mutmut 3 maps tests to mutants by node ID and crashes on some arms' parametrised IDs (pass 1 ccsdd and control:
`baseline_rc 0`, `mutmut_run_rc 1`, every sampled mutant `not_checked`). This path keeps mutmut's mutant generation
(`quality.list_mutants`: `mutmut run '__bk_list_only__'` writes `mutants/`, `mutmut results` names them) and its
trampoline (the mutated modules dispatch on the `MUTANT_UNDER_TEST` environment variable), and replaces mutmut's
own test selection: for each chosen mutant the WHOLE suite runs once, from `mutants/`, with that variable set —

    cd mutants && MUTANT_UNDER_TEST=<name> PYTHONPATH=<mutants/source:mutants/src:mutants> \\
        timeout <s> ../.venv/bin/python -m pytest -q -x -p no:cacheprovider

The PYTHONPATH mirrors mutmut's own `setup_source_paths` (mutated `source/`, `src/`, `.` first), so the mutated
modules shadow the arm's editable install. Exit codes map to verdicts by `verdict`; the score is the same
`quality.mutation_summary` over the SAME seeded sample the original run drew (`quality.sample`, `pins.limits.
mutation_sample`), so a re-measured score compares with the arms whose original run was measured.

Two checks run first, in their own container, before any mutant: the suite from `mutants/` with a name that
matches no mutant (`__baseline__`: the trampoline calls the original) must pass, and with the trampoline's own
sentinel `fail` (it raises inside every mutated function) must fail. A baseline that does not pass there, or a
sentinel that does not fail (the tests never reached a trampoline: the original code was imported, or nothing is
covered), is a harness failure — `crashed`, the score withheld, never 0 and never every mutant "survived".

The same discipline as `quality._mutation`: one tester container per batch of `BATCH` mutants, the arm's pytest
output redirected to a log file inside the copy, and each exit code echoed as `__rc <name> <code>` only after every
mutant in the batch has run (after a tail of that log), so the real marker is provably the last anchored line for
its name (`parse_batch`, `quality._last_marker`'s rule); a name with no marker (the container died or timed out) is
`not_checked`. The residual limit `quality._mutation` documents applies unchanged: the arm's own code runs as the
same uid with the copy writable, so this hardening stops accidental and printed forgeries, not an arm rewriting its
own interpreter.

The step's containers, the control one included, share a time budget of `pins.limits.mutation_seconds`, the same
budget the original mutmut run had (R31, R32). It is a real cap: each batch script gets the seconds left and starts a mutant
only while its full per-mutant timeout still fits in them (R32(3): never a truncated timeout, which would make a fake
`timeout` verdict), and each container's timeout is clamped to the seconds left plus `CONTAINER_SLACK_S`. Mutants never started are `not_checked`, so the summary is
`partial`; the scoring layer (`evidence.mutation`) scores over checked mutants only.

A run where no mutant is killed and every real verdict is `survived` is `crashed` ("no mutant killed: dispatch
unverified", R32): the sentinel shows a trampoline is reached, not that each mutant is dispatched.

Not like-for-like with mutmut's own results: mutmut gives a mutant that no test covers `no tests` (outside the
denominator), while the whole suite per mutant runs everything, so an uncovered mutant comes out `survived`. The
method is recorded (`method`) and shown in the report beside every score.

Runs only after pass 1 (it prepares fresh copies under the arm's `state/` scratch and uses Docker), holding the
runner lock (`runner score <pass> --stage remeasure`). Writes `quality/remeasure.json` and `quality/remeasure.log`
beside the original `summary.json`, which it never changes; `evidence.quality` prefers a measured re-measure.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

from runner import config, quality
from runner import paths
from runner.paths import Paths
from runner.scoring import evidence, inputs, values

METHOD = "whole-suite-per-mutant"
BATCH = 20                       # mutants per tester container
MIN_MUTANT_TIMEOUT_S = 60        # per-mutant `timeout` floor
TIMEOUT_FACTOR = 10              # per-mutant timeout = this x the baseline suite's seconds (container start included)
CONTAINER_SLACK_S = 60           # a batch container's timeout beyond the step's remaining budget (kill grace, tail)
NO_BUDGET_S = 10 ** 9            # `remaining` when no budget applies (the docker spike)
BASELINE_NAME = "__baseline__"   # matches no mutant: the trampoline calls the original function
SENTINEL_NAME = "fail"           # mutmut's trampoline raises MutmutProgrammaticFailException for this value
_LOG_TAIL = 4000

# the verdict for each exit code of `pytest -x` under one mutant (brief, verbatim); anything else is "suspicious"
_VERDICTS = {0: "survived", 1: "killed", None: "timeout", 5: "no_tests"}


# --- pure ---------------------------------------------------------------------------------------------------------

def verdict(rc: int | None) -> str:
    return _VERDICTS.get(rc, "suspicious")


def mutant_timeout(baseline_s: float) -> int:
    return max(MIN_MUTANT_TIMEOUT_S, math.ceil(TIMEOUT_FACTOR * baseline_s))


# Every key a remeasure.json carries besides `quality.mutation_summary`'s own, with its default: every path —
# measured, crashed, baseline failed — writes the same key set.
_EXTRA_DEFAULTS: dict[str, object] = {
    "sampled": False, "sample_size": 0, "baseline_rc": None, "mutants_baseline_rc": None, "sentinel_rc": None,
    "mutant_timeout_s": None, "batches": 0, "harness_error": None, "sha": None, "targets": None,
    "budget_s": None, "budget_exhausted": False,
}


def summarise(verdicts: dict[str, str], *, crashed: bool = False, baseline_failed: bool = False,
              sampling: str = "seeded-sha256", **extra: object) -> dict:
    """`quality.mutation_summary` over one verdict per mutant (`not_checked` for a mutant that got none), with the
    `quality._mutation` crash rule: no real verdict while any mutant is unresolved is `crashed` (never a precise
    0.0); some unresolved alongside real verdicts is `partial`; every mutant `no_tests` is `unmeasured`."""
    counts = dict(quality.ZERO_MUTATION)
    for v in verdicts.values():
        counts[v] += 1
    counts["total"] = len(verdicts)
    real = sum(counts[k] for k in quality._REAL_OUTCOME_KEYS)
    unresolved = counts["not_checked"]
    if not crashed and real == 0 and unresolved > 0:
        crashed = True
    partial = not crashed and unresolved > 0
    return quality.mutation_summary(counts, partial=partial, baseline_failed=baseline_failed, crashed=crashed,
                                    **{**_EXTRA_DEFAULTS, **extra, "sampling": sampling, "method": METHOD})


_TIMEOUT_RCS = (124, 137)
_MARKER = re.compile(r"(?m)^__rc (\S+) (-?\d+|skipped)$")


def parse_batch(text: str, names: list[str]) -> dict[str, int | None]:
    """Each requested name's exit code from the LAST anchored `__rc <name> <code>` line (`text` is stdout only).
    `timeout`'s 124, and 137 (its `-k` SIGKILL after the grace period; R32), are None (a timeout). A name whose
    last marker is `skipped` (the budget ran out before it started), or that has none (the container died), is
    absent: the caller records it `not_checked`."""
    wanted, out = set(names), {}
    for name, code in _MARKER.findall(text):
        if name in wanted:
            out[name] = code if code == "skipped" else None if int(code) in _TIMEOUT_RCS else int(code)
    return {n: c for n, c in out.items() if c != "skipped"}


# Runs in the copy's root as the arm uid. Positional args: the per-mutant timeout, the step's remaining budget in
# seconds, then the names (argv, never interpolated). A mutant starts only while at least its full timeout is left of
# the budget (R32(3): a timeout clamped to a truncated budget would turn into a fake `timeout` verdict, a real unkilled
# one). The arm's pytest output goes to a log file; the
# markers are printed only after the loop and the log tail, from shell variables, so nothing the arm prints can come
# after them. Every requested name gets a real marker, `skipped` for one never started, so a forged marker in the
# tailed log can never stand in for a mutant that did not run.
_BATCH_SCRIPT = r"""
t="$1"; r="$2"; shift 2
cd mutants || exit 97
pp=""
for d in source src .; do [ -d "$d" ] && pp="${pp:+$pp:}$(cd "$d" && pwd)"; done
all=("$@"); rcs=()
for n in "${all[@]}"; do
  [ $((r - SECONDS)) -lt "$t" ] && break
  MUTANT_UNDER_TEST="$n" PYTHONPATH="$pp" timeout -k 10 "$t" ../.venv/bin/python -m pytest -q -x -p no:cacheprovider \
    >>../remeasure-batch.log 2>&1
  rcs+=("$?")
done
tail -c %d ../remeasure-batch.log
echo
for i in "${!all[@]}"; do printf '__rc %%s %%s\n' "${all[$i]}" "${rcs[$i]:-skipped}"; done
""" % _LOG_TAIL


def batch_command(names: list[str], per_mutant_timeout: int, remaining_s: int) -> list[str]:
    return ["bash", "-c", _BATCH_SCRIPT, "_", str(per_mutant_timeout), str(remaining_s), *names]


# --- the container seam (faked in unit tests) ----------------------------------------------------------------------

def _prepare(p: Paths, sha: str, label: str, out_dir: Path):
    from runner import hidden          # lazy, as quality.py does
    return hidden.prepare(p, sha, label, out_dir, with_quality=True, require_main=False)


def _baseline(p: Paths, copy: Path) -> tuple[int | None, float, str]:
    """The arm's suite at the copy root, exactly as `quality._mutation`'s baseline: (rc or None on timeout, seconds,
    output)."""
    t0 = time.monotonic()
    r = quality._run(p, copy, ["bash", "-c", quality._BASELINE_SCRIPT], 1800)
    return (None if r.timed_out else r.rc), time.monotonic() - t0, r.combined


def _list_mutants(p: Paths, copy: Path, tg: list[str]) -> list[str]:
    return quality.list_mutants(p, copy, tg)


def run_batch(p: Paths, copy: Path, names: list[str], timeout: int, log: list[str] | None = None,
              remaining: int | None = None) -> dict[str, int | None]:
    """One tester container runs the whole suite once per name, starting none once the step's `remaining` budget
    is spent (None: no budget). The container timeout is clamped to `remaining` + `CONTAINER_SLACK_S` (R32). A
    container that times out returns {} (every name then `not_checked`)."""
    rem = NO_BUDGET_S if remaining is None else max(0, int(remaining))
    outer = min(len(names) * (timeout + 15) + 120, rem + CONTAINER_SLACK_S)
    r = quality._run(p, copy, batch_command(names, timeout, rem), outer, env=quality.mutation_env(copy))
    if log is not None:
        shown = names if len(names) <= 3 else [*names[:2], f"... <{len(names) - 2} more>"]
        log.append(f"$ batch {' '.join(shown)}  (per mutant timeout {timeout}s; container {outer}s)"
                   + ("  TIMED OUT" if r.timed_out else "") + "\n" + r.combined[-(_LOG_TAIL + 4000):])
    return {} if r.timed_out else parse_batch(r.stdout, names)


_clock = time.monotonic           # the step budget's clock (faked in unit tests)


def _sample_size(pins: config.Pins) -> int:
    return pins.limits.mutation_sample


# --- one step, a pass ----------------------------------------------------------------------------------------------

def one(pass_: str, arm: str, step: int, pins: config.Pins | None = None) -> Path:
    """Re-measure one arm-step and write `quality/remeasure.json` + `quality/remeasure.log`. Always writes and
    returns the path: an exception anywhere is recorded as `crashed` with `harness_error`, never raised."""
    p = Paths(pass_, arm)
    qd = p.step(step) / "quality"
    qd.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    try:
        s = _measure(p, step, pins or config.load_pins(), qd, log)
    except Exception as e:                  # noqa: BLE001 -- a harness failure is crashed, never lost
        log.append(f"# exception: {type(e).__name__}: {e}")
        s = summarise({}, crashed=True, harness_error=f"{type(e).__name__}: {e}"[:200])
    out = qd / "remeasure.json"
    out.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n")
    (qd / "remeasure.log").write_text("\n".join(log) + "\n")
    return out


def _measure(p: Paths, step: int, pins: config.Pins, qd: Path, log: list[str]) -> dict:
    def crash(why: str, verdicts: dict[str, str] | None = None, **extra: object) -> dict:
        log.append(f"# crashed: {why}")
        return summarise(verdicts or {}, crashed=True, harness_error=why, **extra)

    git = evidence.read_json(p.step(step) / "git.json")
    sha = None if values.is_missing(git) else git["value"].get("sha_after")
    if not sha:
        return crash(f"no recorded sha_after in {p.step(step) / 'git.json'}")
    prep = _prepare(p, sha, f"{step:02d}-remeasure", qd / "remeasure-prep")
    if prep.quality_copy is None or not prep.prep.get("quality", {}).get("ok"):
        return crash("quality copy install failed", sha=sha)
    tg = quality.targets(prep.hidden_copy)          # copy A, never mutated, as quality.run_all does
    copy = prep.quality_copy
    common: dict[str, object] = {"sha": sha, "targets": tg}

    rc, secs, text = _baseline(p, copy)
    log.append(f"$ {quality._BASELINE_SCRIPT}  (baseline at the copy root, {secs:.1f}s)\n" + text[-_LOG_TAIL:])
    if rc == 1:                                     # the arm's own tests fail: its result, not ours, never scored
        return summarise({}, baseline_failed=True, sampling="n/a", baseline_rc=rc, **common)
    if rc == 5:                                     # no tests collected: not crashed, nothing to score
        return summarise({}, sampling="no tests", baseline_rc=rc, **common)
    if rc != 0:
        return crash(f"baseline at the copy root: {'timed out' if rc is None else f'rc {rc}'}", baseline_rc=rc,
                     **common)
    common["baseline_rc"] = rc

    names = _list_mutants(p, copy, tg)
    if not names:
        return crash("mutmut listed no mutants", **common)
    n = _sample_size(pins)
    chosen = quality.sample(names, n) if n > 0 else sorted(set(names))
    sampling = "seeded-sha256" if n > 0 else "all"
    t = mutant_timeout(secs)
    budget = pins.limits.mutation_seconds          # R31: the original run's budget, from the control container on
    start = _clock()
    common |= {"sampled": n > 0, "sample_size": len(chosen), "mutant_timeout_s": t, "budget_s": budget}
    log.append(f"# {len(names)} mutants listed; {len(chosen)} chosen ({sampling}); per-mutant timeout {t}s")

    def left() -> int:
        return max(0, int(budget - (_clock() - start)))

    ctl = run_batch(p, copy, [BASELINE_NAME, SENTINEL_NAME], t, log, remaining=left())     # counts against it
    common |= {"mutants_baseline_rc": ctl.get(BASELINE_NAME), "sentinel_rc": ctl.get(SENTINEL_NAME)}
    if ctl.get(BASELINE_NAME) != 0:
        return crash(f"the suite does not pass from mutants/ (rc {ctl.get(BASELINE_NAME)})", sampling=sampling,
                     **common)
    if ctl.get(SENTINEL_NAME) in (0, None):
        return crash(f"the trampoline sentinel did not fail the suite (rc {ctl.get(SENTINEL_NAME)}): the tests "
                     "never reached a mutated function", sampling=sampling, **common)

    got: dict[str, int | None] = {}
    batches = [chosen[i:i + BATCH] for i in range(0, len(chosen), BATCH)]
    ran, exhausted = 0, False
    for b in batches:
        if left() < t:                              # R31/R32: not reached within the budget (a full mutant timeout
                                                    # no longer fits): not_checked
            exhausted = True
            log.append(f"# step budget {budget}s spent: {len(batches) - ran} batch(es) not started")
            break
        got |= run_batch(p, copy, b, t, log, remaining=left())
        ran += 1
    exhausted = exhausted or (left() < t and any(name not in got for name in chosen))
    common |= {"budget_exhausted": exhausted}
    verdicts = {name: (verdict(got[name]) if name in got else "not_checked") for name in chosen}
    real = [v for v in verdicts.values() if v in quality._REAL_OUTCOME_KEYS]
    if real and all(v == "survived" for v in real):
        # R32: the control proves the sentinel reaches a trampoline, not that each mutant is dispatched; every real
        # verdict "survived" is far likelier a dispatch failure than an arm whose tests catch nothing
        return crash("no mutant killed: dispatch unverified", verdicts, sampling=sampling, batches=ran, **common)
    return summarise(verdicts, sampling=sampling, batches=ran, **common)


def _wanted(q: dict, every: bool) -> bool:
    """A step to re-measure: with `every`, any step with a quality record (R35: one method for every arm, so the
    owner can choose comparability); by default a `crashed` mutation run or one `unmeasured` because under half its
    sampled mutants were checked (R32)."""
    if values.is_missing(q):
        return False
    v = q.get("value") or {}
    if every:
        return True
    return v.get("mutation_state") == "crashed" or (
        v.get("mutation_state") == "unmeasured" and v.get("mutation_why") == evidence.PARTIAL_UNDER_HALF)


def targets(pass_: str, every: bool = False) -> list[tuple[str, int]]:
    """Every collected arm-step to re-measure (`_wanted`), sorted. A malformed record refuses (InputError)."""
    d = paths.scoring_out(pass_) / "collected"
    if not d.is_dir():
        raise inputs.InputError(f"{d} is missing: run `runner score {pass_} --stage collect` first")
    out = []
    for f in sorted(d.glob("*/[0-9][0-9].json")):
        try:
            rec = json.loads(f.read_text())
            q = rec.get("quality", {}) if isinstance(rec, dict) else None
            if not isinstance(q, dict) or not isinstance(q.get("value", {}), (dict, type(None))):
                raise ValueError("no quality record")
        except (OSError, ValueError) as e:
            raise inputs.InputError(f"{f} is malformed ({e}): re-run `runner score {pass_} --stage collect`") from None
        if _wanted(q, every):
            out.append((f.parent.name, int(f.stem)))
    return sorted(out)


def run(pass_: str, every: bool = False) -> list[Path]:
    return [one(pass_, arm, step) for arm, step in targets(pass_, every)]
