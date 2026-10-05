"""`runner score <pass> [--stage S]`: each stage reads the previous stage's files (spec §9)."""
from __future__ import annotations
import json
from pathlib import Path
from runner import paths
from runner.scoring import aggregate, collect, confidence, evidence, inputs, page, report, values


def _scores(pass_: str) -> dict:
    f = paths.scoring_out(pass_) / "scores.json"
    if not f.exists():
        raise inputs.InputError(f"{f} is missing: run `runner score {pass_} --stage aggregate` first")
    return json.loads(f.read_text())


def _confidence(ns) -> None:
    out = paths.scoring_out(ns.pass_) / "confidence.json"
    out.write_text(values.dump(confidence.check(_scores(ns.pass_))))
    print(out)


def _report(ns) -> None:
    _scores(ns.pass_)                      # refuse before writing anything
    print(report.run(ns.pass_))
    print(page.run(ns.pass_))


STAGES = {
    "all-fail": lambda ns: print(json.dumps(evidence.all_fail(paths.RESULTS / ns.pass_,
                                                               collect.arms(paths.RESULTS / ns.pass_)), indent=2)),
    "collect": lambda ns: print(len(collect.run(ns.pass_, docker=not ns.no_docker)), "records"),
    "aggregate": lambda ns: print(aggregate.run(ns.pass_, ns.baseline)),
    "confidence": _confidence,
    "report": _report,
}
DEFAULT = ("collect", "aggregate", "confidence", "report")


def score(ns) -> int:
    try:
        for s in ([ns.stage] if ns.stage else DEFAULT):
            STAGES[s](ns)
    except inputs.InputError as e:
        print(f"score: {e}")
        return 1
    return 0
