"""Stage 1: every measured value per arm-step, each with its source path. Deterministic; no LLM."""
from __future__ import annotations
import re
from pathlib import Path
from runner import config, paths
from runner.scoring import STEPS, churn, evidence, inputs, phases, regressions, values

_STEP_DIR = re.compile(r"^\d\d$")


def arms(pass_dir: Path) -> list[str]:
    return sorted(d.name for d in pass_dir.iterdir()
                  if d.is_dir() and any(_STEP_DIR.match(c.name) for c in d.iterdir() if c.is_dir()))


def _spec_paths(arm: str) -> list:
    try:
        return config.load_arm(arm).spec_paths
    except FileNotFoundError:               # dry and fixture arms have no arms/<name>.toml: no spec folders exempt
        return []                           # (a ConfigError on a real arm's file is a bug and propagates)


def _hidden(step_dir: Path, excl) -> tuple[dict, dict | None]:
    s = evidence.hidden_summary(step_dir)
    if values.is_missing(s):
        return s, None
    if not s["value"].get("scoreable", True):
        return values.missing(s["source"], "not scoreable"), None
    tests = dict(s["value"].get("tests", {}))
    kept = {t: o for t, o in tests.items() if t not in excl.defects}
    passed = sum(1 for o in kept.values() if o == "passed")
    return values.val({"passed": passed, "total": len(kept), "excluded": sorted(set(tests) - set(kept)),
                       "per_test": kept}, s["source"]), tests


def step(pass_: str, arm: str, n: int, *, prev_tests, excl, rules, docker: bool) -> tuple[dict, dict | None]:
    """The collected record and this step's raw hidden tests (None when unscoreable), which feed the next step."""
    d = paths.RESULTS / pass_ / arm / f"{n:02d}"
    hidden, tests = _hidden(d, excl)
    run = evidence.run_record(d)
    git = evidence.read_json(d / "git.json")
    git_src = git.get("source", git.get("missing", ""))
    rec = {
        "arm": arm, "step": n,
        "outcome": run if values.is_missing(run) else values.val(run["value"].get("outcome"), run["source"]),
        "hidden": hidden,
        "regressions": (values.missing(hidden.get("missing", ""), "no hidden results") if tests is None else
                        values.val(regressions.compute(prev_tests, tests, excl.defects), hidden["source"])),
        "quality": evidence.quality(d), "time": evidence.arm_time(d), "cost": evidence.costs(d),
        "questions": evidence.questions(d), "violations": evidence.violations(d),
        "churn": (churn.for_step(pass_, arm, git, inputs.load_stale(n)) if docker
                  else values.missing(git_src, "deferred: run with Docker after pass 1")),
        "phases": {"method": phases.method_phases(d),
                   "common": phases.common_phases(d, _spec_paths(arm), rules)},
    }
    return rec, tests


def run(pass_: str, *, docker: bool = True) -> list[Path]:
    excl, rules = inputs.load_excluded(), inputs.load_phase_rules()
    out_dir, written = paths.scoring_out(pass_) / "collected", []
    for arm in arms(paths.RESULTS / pass_):
        prev = None
        for n in STEPS:
            if not (paths.RESULTS / pass_ / arm / f"{n:02d}").is_dir():
                continue
            rec, tests = step(pass_, arm, n, prev_tests=prev, excl=excl, rules=rules, docker=docker)
            prev = tests if tests is not None else prev
            f = out_dir / arm / f"{n:02d}.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(values.dump(rec))
            written.append(f)
    return written
