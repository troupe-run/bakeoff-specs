"""`runner score <pass> [--stage S]`: each stage reads the previous stage's files (spec §9)."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from runner import faults, paths
from runner.scoring import (aggregate, anonymise, collect, confidence, context, decisions, evidence, inputs, judge, leakcheck, page,
                            remeasure, report, review, values)


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


def _refuse_tracked_anon_key(pass_: str) -> None:
    """The key de-anonymises the published evidence: refuse while it sits under results/ AND git tracks it (staged or
    committed). Asks the HARNESS repo only (paths.REPO_ROOT), never an arm repo."""
    key = paths.scoring_out(pass_) / "anon-key.json"
    if not key.exists():
        return
    try:
        rel = key.resolve().relative_to(paths.REPO_ROOT.resolve())
    except ValueError:
        return
    try:
        r = subprocess.run(["git", "-C", str(paths.REPO_ROOT), "ls-files", "--error-unmatch", "--", str(rel)],
                           capture_output=True, text=True)
    except OSError as e:                  # fail closed: no git means we cannot show the key is untracked
        raise inputs.InputError(f"cannot check whether {rel} is tracked by git ({e}); refusing to report") from None
    if r.returncode == 1:                 # only 1 means "not tracked"; anything else is an error, not an all-clear
        return
    if r.returncode != 0:
        raise inputs.InputError(f"cannot check whether {rel} is tracked by git (git exit {r.returncode}: "
                                f"{r.stderr.strip()}); refusing to report")
    raise inputs.InputError(
        f"{rel} is tracked by git: it maps Arm labels to arms and would de-anonymise the published evidence. "
        f"`git rm --cached {rel}`, move it to state/{pass_}-scoring/, then re-run report.")


def _report(ns) -> None:
    scores = _scores(ns.pass_)             # refuse before writing anything
    _refuse_tracked_anon_key(ns.pass_)
    _write_confidence(ns.pass_, scores)    # so confidence.json can never lag the report
    print(report.run(ns.pass_))
    print(page.run(ns.pass_))


def _estimates(ns) -> tuple[dict, dict]:
    """The judge stage's and the decision stages' (extract, align, context) estimates: one approval covers their
    total."""
    d = decisions.estimate(ns.pass_, retry_failed=ns.retry_failed)
    c = context.estimate(ns.pass_, retry_failed=ns.retry_failed)
    return (judge.estimate(ns.pass_, retry_failed=ns.retry_failed),
            d | {"calls": d["calls"] + c["calls"], "context_calls": c["calls"]})


def _approve(ns) -> None:
    """Every stage that spends model quota refuses unless `judge-approved` covers the current total estimate."""
    j, d = _estimates(ns)
    judge.check_approval(ns.pass_, j["calls"] + d["calls"])


def _judge_estimate(ns) -> None:
    """Calls (judge + decision extract/align), input size and the implied cost (at the PO's mean cost per call), plus
    the upper bound if every call needed its one parse retry. Needs no approval."""
    j, d = _estimates(ns)
    calls = j["calls"] + d["calls"]
    e = {"calls": calls, "judge_calls": j["calls"], "decision_calls": d["calls"],
         "input_mb": round(j["input_mb"] + d["input_mb"], 3)}
    # Every call is retried once when its reply does not parse, so 2x is the upper bound. Shown only: approval is
    # checked against `calls` (judge.check_approval), as before.
    upper = judge.implied_cost(ns.pass_, 2 * calls)
    e |= {"calls_with_parse_retries": 2 * calls, "implied_usd_with_parse_retries": upper["implied_usd"]}
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


def _decisions_context(ns) -> None:
    """Spends model quota (two calls per topic) and uses Docker (each label's final code in the tester sandbox)."""
    _approve(ns)
    print(json.dumps(context.run(ns.pass_, judge.ContainerJudge(ns.pass_), context.ArmRunner(ns.pass_),
                                 retry_failed=ns.retry_failed, only=getattr(ns, "only", None)), indent=2,
                     sort_keys=True))


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
            for f in (remeasure.run(ns.pass_, every=True) if getattr(ns, "all", False) else remeasure.run(ns.pass_)):
                print(f)
    except NotReady as e:
        raise inputs.InputError(str(e)) from None


def _leak_check(ns) -> None:
    """Final review I2: every file under anon/ (contents and paths, repo/ and diff.patch included) searched for every
    arm's names by the independent checker. Writes leak-check.json (the report discloses it); hits exit 1."""
    anon = paths.scoring_out(ns.pass_) / "anon"
    if not anon.is_dir():
        raise inputs.InputError(f"{anon} is missing: run the anonymise stage first")
    hits = leakcheck.check(anon, collect.arms(paths.RESULTS / ns.pass_))
    files = sum(1 for f in anon.rglob("*") if f.is_file())
    out = paths.scoring_out(ns.pass_) / "leak-check.json"
    out.write_text(values.dump({"files": files, "hits": [{"path": p, "word": w} for p, w in hits]}))
    if hits:
        raise inputs.InputError(f"leak check: {len(hits)} hit(s) in {files} file(s) under {anon} ({out}):\n"
                                + "\n".join(f"- {p}: {w}" for p, w in hits))
    print(f"leak check: no leaks in {files} file(s) under {anon} ({out})")


STAGES = {
    "all-fail": lambda ns: print(json.dumps(evidence.all_fail(paths.RESULTS / ns.pass_,
                                                               collect.arms(paths.RESULTS / ns.pass_)), indent=2)),
    "collect": lambda ns: print(len(collect.run(ns.pass_, docker=not ns.no_docker)), "records"),
    "anonymise": lambda ns: print(anonymise.run(ns.pass_)),     # Docker (container git); rewrites anon/ and anon-key.json
    "leak-check": _leak_check,
    "judge-estimate": _judge_estimate,
    "judge": _judge,
    "decisions-extract": _decisions_extract,
    "decisions-align": _decisions_align,
    "decisions-context": _decisions_context,
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
