"""Re-run mutmut's ORIGINAL method on a pass's arm-step whose original mutation run crashed (owner rulings O1-O3,
2026-10-08; investigation: .superpowers/sdd/2026-10-05-scoring/mutmut-crash-investigation.md).

The method is `quality._mutation` itself, unchanged except for what the rulings changed for every arm: the pinned
baseline timeout (O2, `pins.limits.mutation_baseline_seconds`) and the node-ID resume after a failed run (O1). The
step's committed tree (`git.json` `sha_after`) is prepared afresh (`hidden.prepare`, copy B), exactly as the live
quality stage prepares it.

The original pass-1 evidence is never touched: the result goes to `quality/rerun/mutation.json` (the mutation
summary plus a `rerun` provenance record: reason, ruling text, date, sha, method "mutmut") and
`quality/rerun/mutmut.log`; a step that already has a rerun is refused, never overwritten, unless that rerun
failed in the harness (`harness_error`): it is then kept in `quality/rerun/attempt-<n>/` and the step is retried. Only
a step whose original mutation run is crashed is re-run. `evidence.quality`
uses a current, measured rerun only in place of an original that is not measured, and says so.

Run one step: `python -m runner.scoring.rerun <pass> <arm> <step> <O1|O2|O3>` (holds the runner lock; uses Docker,
so wrap it in the docker lock). Always writes a result: an exception is recorded as crashed with `harness_error`."""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

from runner import config, quality
from runner.paths import Paths
from runner.scoring import evidence, values

METHOD = "mutmut"
REASONS = {
    "O1": "mutmut's in-process re-collection could not resolve node IDs its stats recorded; failed runs resume "
          "once with those IDs mapped to their function-level IDs",
    "O2": "the mutation baseline timeout (pins.limits.mutation_baseline_seconds) was raised for every arm",
    "O1+O2": "the raised baseline timeout (O2), then mutmut with the node-ID resume (O1)",
    "O3": "re-run unchanged: the original baseline was killed (rc 137) for a reason not attributable to the arm",
}


def rerun_dir(p: Paths, step: int) -> Path:
    return p.step(step) / "quality" / "rerun"


def _prepare(p: Paths, sha: str, label: str, out_dir: Path):
    from runner import hidden            # lazy, as quality.py does
    return hidden.prepare(p, sha, label, out_dir, with_quality=True, require_main=False)


def one(pass_: str, arm: str, step: int, reason: str, pins: config.Pins | None = None,
        today: str | None = None) -> Path:
    if reason not in REASONS:
        raise ValueError(f"reason must be one of {sorted(REASONS)}, not {reason!r}")
    p = Paths(pass_, arm)
    orig = evidence.read_json(p.step(step) / "quality" / "summary.json")
    state = None if values.is_missing(orig) else evidence.mutation((orig["value"] or {}).get("mutation") or {})["state"]
    if state != "crashed":                      # I-1: only a crashed original is ever re-run
        raise ValueError(f"{p.step(step)}: the original mutation run is {state or 'missing'}, not crashed: "
                         "nothing to re-run")
    rd = rerun_dir(p, step)
    out = rd / "mutation.json"
    if out.exists():
        try:
            prev = json.loads(out.read_text())
            failed = bool(prev["rerun"]["harness_error"])
        except (ValueError, KeyError, TypeError):
            failed = False
        if not failed:
            raise FileExistsError(f"{out} exists: a rerun is never overwritten")
        n = 1 + sum(1 for d in rd.glob("attempt-*") if d.is_dir())      # I-2: a harness failure may be retried;
        keep = rd / f"attempt-{n}"                                      # its record is kept beside the new one
        keep.mkdir()
        for name in ("mutation.json", "mutmut.log"):
            if (rd / name).exists():
                (rd / name).rename(keep / name)
    rd.mkdir(parents=True, exist_ok=True)
    git = evidence.read_json(p.step(step) / "git.json")
    sha = None if values.is_missing(git) else git["value"].get("sha_after")
    prov = {"reason": reason, "ruling": REASONS[reason], "method": METHOD, "sha": sha,
            "date": today or datetime.date.today().isoformat(), "harness_error": None}
    try:
        if not sha:
            raise RuntimeError(f"no recorded sha_after in {p.step(step) / 'git.json'}")
        prep = _prepare(p, sha, f"{step:02d}-rerun", rd / "prep")
        if prep.quality_copy is None or not prep.prep.get("quality", {}).get("ok"):
            raise RuntimeError("quality copy install failed")
        tg = quality.targets(prep.hidden_copy)
        m = quality._mutation(p, prep.quality_copy, tg, rd, pins or config.load_pins(), log_dir=rd)
    except Exception as e:                      # noqa: BLE001 -- a harness failure is recorded, never lost
        prov["harness_error"] = f"{type(e).__name__}: {e}"[:300]
        m = quality._mutation_placeholder("n/a")
    out.write_text(json.dumps({**m, "rerun": prov}, indent=2, sort_keys=True) + "\n")
    return out


def main(argv: list[str]) -> int:
    from runner import preflight
    pass_, arm, step, reason = argv
    with preflight.lock():
        out = one(pass_, arm, int(step), reason)
    s = json.loads(out.read_text())
    print(json.dumps({"out": str(out), "crashed": s.get("crashed"), "score": s.get("score"),
                      "killed": s.get("killed"), "total": s.get("total"), "not_checked": s.get("not_checked"),
                      "nodeid_rewrites": s.get("nodeid_rewrites"), "harness_error": s["rerun"]["harness_error"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
