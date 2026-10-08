"""Unattended, strictly sequential driver for the O1-O3 mutmut re-runs (owner, 2026-10-08).

    nohup python3 runner/scoring/rerun_queue.py <pass> <progress-log> <dockerlock.py> <arm:step:reason>... &

Each item runs `python -m runner.scoring.rerun <pass> <arm> <step> <reason>` under the docker lock, one after the
other, never in parallel. Every item appends a `start` and an `end` JSON line to the progress log (result summary,
exit code, seconds); its full output goes to `<progress-log dir>/mutmut-rerun-<arm>-<NN>.out`. A failed item is
recorded and the queue continues. O1's check: a node-ID rewrite on any arm other than those named in
`REWRITES_EXPECTED` is recorded as an `assertion` line (the run's result is kept; the owner decides)."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REWRITES_EXPECTED = {"ccsdd"}           # O1: only pass 1 ccsdd has node IDs pytest cannot re-resolve in-process


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _log(path: Path, rec: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps({"at": _now(), **rec}) + "\n")


def main(argv: list[str]) -> int:
    pass_, log, lock, items = argv[0], Path(argv[1]).resolve(), argv[2], argv[3:]
    log.parent.mkdir(parents=True, exist_ok=True)
    _log(log, {"event": "queue-start", "pass": pass_, "items": items})
    for item in items:
        arm, step, reason = item.split(":")
        out = log.parent / f"mutmut-rerun-{arm}-{int(step):02d}.out"
        _log(log, {"event": "start", "arm": arm, "step": int(step), "reason": reason, "output": str(out)})
        t0 = time.monotonic()
        with open(out, "w") as fh:
            rc = subprocess.call(["python3", lock, "uv", "run", "python", "-m", "runner.scoring.rerun", pass_, arm,
                                  step, reason], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
        result = None
        for line in reversed(out.read_text(errors="replace").splitlines()):
            if line.startswith("{") and '"out"' in line:
                try:
                    result = json.loads(line)
                except json.JSONDecodeError:
                    pass
                break
        _log(log, {"event": "end", "arm": arm, "step": int(step), "reason": reason, "rc": rc,
                   "seconds": round(time.monotonic() - t0), "result": result})
        if result and result.get("nodeid_rewrites") and arm not in REWRITES_EXPECTED:
            _log(log, {"event": "assertion", "arm": arm, "step": int(step),
                       "what": f"{result['nodeid_rewrites']} node-ID rewrite(s) on an arm other than "
                               f"{sorted(REWRITES_EXPECTED)} (O1 expected none)"})
    _log(log, {"event": "queue-end"})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
