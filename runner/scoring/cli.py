"""`runner score <pass> [--stage S]`: each stage reads the previous stage's files (spec §9)."""
from __future__ import annotations
import json
from pathlib import Path
from runner import faults, paths
from runner.scoring import (aggregate, collect, confidence, decisions, evidence, inputs, judge, page, remeasure,
                            report, review, values)


def _scores(pass_: str) -> dict:
    f = paths.scoring_out(pass_) / "scores.json"
    if not f.exists():
        raise inputs.InputError(f"{f} is missing: run `runner score {pass_} --stage aggregate` first")
    return json.loads(f.read_text())


def _write_confidence(pass_: str, scores: dict) -> Path:
    out = paths.scoring_out(pass_) / "confidence.json"
    out.write_text(values.dump(confidence.check(scores)))
    return out


def _confidence(ns) -> None:
    print(_write_confidence(ns.pass_, _scores(ns.pass_)))


def _report(ns) -> None:
    scores = _scores(ns.pass_)             # refuse before writing anything
    _write_confidence(ns.pass_, scores)    # so confidence.json can never lag the report
    print(report.run(ns.pass_))
    print(page.run(ns.pass_))


def _estimates(ns) -> tuple[dict, dict]:
    """The judge stage's and the decision stages' (extract, align) estimates: one approval covers their total."""
    return (judge.estimate(ns.pass_, retry_failed=ns.retry_failed),
            decisions.estimate(ns.pass_, retry_failed=ns.retry_failed))


def _approve(ns) -> None:
    """Every stage that spends model quota refuses unless `judge-approved` covers the current total estimate."""
    j, d = _estimates(ns)
    judge.check_approval(ns.pass_, j["calls"] + d["calls"])


def _judge_estimate(ns) -> None:
    """Calls (judge + decision extract/align), input size and the implied cost (at the PO's mean cost per call).
    Needs no approval."""
    j, d = _estimates(ns)
    calls = j["calls"] + d["calls"]
    e = {"calls": calls, "judge_calls": j["calls"], "decision_calls": d["calls"],
         "input_mb": round(j["input_mb"] + d["input_mb"], 3)}
    print(json.dumps(e | judge.implied_cost(ns.pass_, calls), indent=2, sort_keys=True))


def _judge(ns) -> None:
    """Spends model quota: refuses unless `judge-approved` covers the current estimate (`judge.check_approval`)."""
    _approve(ns)
    print(json.dumps(judge.run(ns.pass_, judge.ContainerJudge(ns.pass_), retry_failed=ns.retry_failed), indent=2,
                     sort_keys=True))


def _decisions_extract(ns) -> None:
    _approve(ns)
    print(decisions.extract(ns.pass_, judge.ContainerJudge(ns.pass_), retry_failed=ns.retry_failed))


def _decisions_align(ns) -> None:
    _approve(ns)
    print(decisions.align(ns.pass_, judge.ContainerJudge(ns.pass_), allow_failed=ns.allow_failed))


def _remeasure(ns) -> None:
    """Task 20 (after pass 1 only): Docker and the arms' state/ scratch, so it refuses on a halted pass (R31) and
    holds the runner lock, refusing while anything else (a run-pass) holds it. Then re-run `collect` so the scores pick the re-measures up."""
    from runner import preflight
    from runner.checklist import NotReady
    if faults.halted(ns.pass_):            # R31: unlike the other stages, this one is not exempt from a halt (R22)
        raise inputs.InputError(
            f"HALTED ({faults.ledger_paths(ns.pass_)[1]}): {faults.halt_reason(ns.pass_)} (design §9). remeasure "
            f"uses Docker and state/; review with the owner, then `runner faults resume {ns.pass_} --note \"...\"`.")
    try:
        with preflight.lock():
            for f in remeasure.run(ns.pass_):
                print(f)
    except NotReady as e:
        raise inputs.InputError(str(e)) from None


STAGES = {
    "all-fail": lambda ns: print(json.dumps(evidence.all_fail(paths.RESULTS / ns.pass_,
                                                               collect.arms(paths.RESULTS / ns.pass_)), indent=2)),
    "collect": lambda ns: print(len(collect.run(ns.pass_, docker=not ns.no_docker)), "records"),
    "judge-estimate": _judge_estimate,
    "judge": _judge,
    "decisions-extract": _decisions_extract,
    "decisions-align": _decisions_align,
    "decisions-sheet": lambda ns: print(decisions.sheet(ns.pass_)),
    "decisions-import": lambda ns: print(decisions.import_ratings(ns.pass_)),
    "review-sheet": lambda ns: print(review.sheet(ns.pass_)),
    "review-import": lambda ns: print(review.import_sheet(ns.pass_)),
    "aggregate": lambda ns: print(aggregate.run(ns.pass_, ns.baseline)),
    "confidence": _confidence,
    "report": _report,
    "remeasure": _remeasure,
}
DEFAULT = ("collect", "aggregate", "confidence", "report")


def score(ns) -> int:
    if not faults.valid_name(ns.pass_):
        print(f"score: bad pass name {ns.pass_!r}")
        return 1
    if not (paths.RESULTS / ns.pass_).is_dir():
        print(f"score: no such pass: {paths.RESULTS / ns.pass_} does not exist")
        return 1
    try:
        for s in ([ns.stage] if ns.stage else DEFAULT):
            STAGES[s](ns)
    except inputs.InputError as e:
        print(f"score: {e}")
        return 1
    return 0
