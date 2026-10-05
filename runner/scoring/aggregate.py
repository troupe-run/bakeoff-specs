# runner/scoring/aggregate.py
"""Stage: collected + judged + ratings + owner verdicts + weights -> scores.json (spec §3, §4, §6). Deterministic."""
from __future__ import annotations
import json, statistics
from pathlib import Path
from runner import faults, paths
from runner.scoring import evidence, inputs, scales, values

ARM_MEASURED = {"violations", "choice"}
MEASURED = {"correctness", "regressions", "churn", "time", "mutation", "mypy_lint", "violations", "choice"}


def _v(x):
    return None if x is None or values.is_missing(x) else x["value"]


def collected(pass_: str) -> dict[str, dict[int, dict]]:
    out: dict[str, dict[int, dict]] = {}
    for f in sorted((paths.scoring_out(pass_) / "collected").glob("*/*.json")):
        out.setdefault(f.parent.name, {})[int(f.stem)] = json.loads(f.read_text())
    return out


def _verdicts(pass_: str) -> dict[tuple, dict]:
    f = paths.scoring_out(pass_) / "review" / "verdicts.jsonl"
    out: dict[tuple, dict] = {}
    lines = f.read_text().splitlines() if f.exists() else []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        where = f"{f}: verdicts.jsonl line {n}"
        try:
            r = json.loads(line)
            key = (r["part"], r["arm"], str(r["step"]))
            r["reason"], r["decided"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise inputs.InputError(f"{where}: bad row {line!r} ({e!r})") from e
        if isinstance(r["score"], bool) or not isinstance(r["score"], (int, float)) or not 0 <= r["score"] <= 4:
            raise inputs.InputError(f"{where}: score must be 0-4, got {r['score']!r}")
        if key in out:
            raise inputs.InputError(f"{where}: duplicate verdict for {key}")
        out[key] = r
    return out


def _judged(pass_: str, part: str, arm: str, key: str, verdicts: dict) -> dict:
    d = paths.scoring_out(pass_) / "judged" / part / arm / key
    lenses = {f.stem: json.loads(f.read_text()) for f in sorted(d.glob("*.json"))} if d.is_dir() else {}
    ok = {n: j["score"] for n, j in lenses.items() if j.get("status") == "ok" and j.get("score") is not None}
    owner = verdicts.get((part, arm, key.lstrip("0") or key))
    if not lenses and owner is None:
        return {"score": None, "why": "not judged"}
    if owner is None and not ok and any(j.get("status") == "not_applicable" for j in lenses.values()):
        return {"score": None, "why": "not applicable", "lenses": {}, "disputed": False}
    used = owner["score"] if owner else (statistics.median(ok.values()) if ok else None)
    out = {"score": scales.judged(used), "lenses": ok, "disputed": len(ok) >= 2 and max(ok.values()) - min(ok.values()) >= 2}
    if owner:
        out["owner"] = owner
    if used is None:                        # R24(d): absent evidence is unmeasured, and says so (never a zero)
        missing = any(j.get("status") == "input_missing" for j in lenses.values())
        out["why"] = "input missing" if missing else "judge_failed"
    return out


def _measured(part: str, rec: dict, base: dict | None, sc: dict) -> dict:
    h, q = _v(rec["hidden"]), _v(rec["quality"])
    if part == "correctness":
        return {"score": h["passed"] / h["total"]} if h and h["total"] else {"score": None, "why": "no hidden results"}
    if part == "regressions":
        r = _v(rec["regressions"])
        return {"score": r["rate"]} if r and r["rate"] is not None else {"score": None, "why": "no earlier tests"}
    if part == "mutation":
        if q and q["mutation_state"] == "measured" and q["mutation_score"] is not None:
            return {"score": q["mutation_score"]}
        if q and q["mutation_state"] == "measured":
            return {"score": None, "why": "measured but no score"}
        return {"score": None, "why": q["mutation_state"] if q else "no quality results"}
    if part == "mypy_lint":
        if q and q["mypy_errors"] is not None and q["ruff_findings"] is not None:
            return {"score": scales.deduction(q["mypy_errors"] + q["ruff_findings"], sc["lint_per_error"])}
        return {"score": None, "why": "mypy or ruff crashed"}
    if base is None:
        return {"score": None, "why": "no baseline for this step"}
    if part == "churn":
        a, b = _v(rec["churn"]), _v(base["churn"])
        return ({"score": scales.churn_score(a["lines"], b["lines"], sc["ratio_cap"])} if a and b
                else {"score": None, "why": "churn not measured"})
    if part == "time":
        t, bt = _v(rec["time"]), _v(base["time"])
        hh, bh = _v(rec["hidden"]), _v(base["hidden"])
        if not (t and bt and hh and bh):
            return {"score": None, "why": "time or passed tests missing"}
        if not bh["passed"]:
            return {"score": None, "why": "baseline passed no tests"}
        if not hh["passed"]:
            return {"score": 0.0}
        s = scales.ratio_score(t["seconds"] / hh["passed"], bt["seconds"] / bh["passed"], sc["ratio_cap"])
        return {"score": s} if s is not None else {"score": None, "why": "time or passed tests missing"}
    raise ValueError(part)


def _choice(pass_: str, arm: str, sc: dict) -> dict:
    f = paths.scoring_out(pass_) / "decisions" / "ratings.json"
    if not f.exists():
        return {"score": None, "why": "not rated"}
    table = scales.rating_table(sc)
    rs = [scales.rating(r["rating"], table) for t in json.loads(f.read_text())["topics"] for r in t["routes"]
          if arm in r["arms"]]
    rs = [r for r in rs if r is not None]
    return {"score": sum(rs) / len(rs)} if rs else {"score": None, "why": "no rated routes"}


def _part_steps(pass_, part, arm, recs, base_recs, rubrics, verdicts, sc) -> dict[str, dict]:
    if part in ARM_MEASURED or (part in rubrics and rubrics[part].unit == "arm"):
        if part == "choice":
            return {"arm": _choice(pass_, arm, sc)}
        if part == "violations":
            vs = {n: _v(r["violations"]) for n, r in sorted(recs.items())}
            gone = [n for n, v in vs.items() if v is None]
            if gone:
                return {"arm": {"score": None, "why": f"violations evidence missing for steps {gone}"}}
            return {"arm": {"score": scales.deduction(sum(len(v) for v in vs.values()), sc["violation_per_item"])}
                    if vs else {"score": None, "why": "no run records"}}
        return {"arm": _judged(pass_, part, arm, "arm", verdicts)}
    if part in MEASURED:
        return {str(n): _measured(part, r, base_recs.get(n), sc) for n, r in sorted(recs.items())}
    if part not in rubrics:
        raise inputs.InputError(f"weights.toml part {part!r} has no rubric in scoring/rubrics and is not a measured part")
    steps = [n for n in rubrics[part].steps if n in recs]
    return {str(n): _judged(pass_, part, arm, f"{n:02d}", verdicts) for n in steps}


def _part_score(steps: dict) -> float | None:
    xs = [s["score"] for s in steps.values() if s["score"] is not None]
    return sum(xs) / len(xs) if xs else None


def _dimension(dim: str, parts: dict, w: inputs.Weights) -> dict:
    share = (lambda p: w.part_share(dim, p)) if dim in w.parts else (lambda p: 1.0)
    measured = {p: v["score"] for p, v in parts.items() if v["score"] is not None}
    score = (w.dimensions[dim] * sum(share(p) * s for p, s in measured.items()) / sum(share(p) for p in measured)
             if measured else None)
    return {"score": score, "max": w.dimensions[dim], "parts": parts,
            "unmeasured_parts": sorted(p for p in parts if parts[p]["score"] is None)}


def _guard(pass_: str, arms: list[str], excluded: inputs.Exclusions) -> None:
    reviewed = excluded.reviewed
    pending = sorted({t for ts in evidence.all_fail(paths.RESULTS / pass_, arms).values() for t in ts} - reviewed)
    if pending:
        raise inputs.InputError("tests every arm failed are not reviewed in scoring/excluded-tests.toml: "
                                + ", ".join(pending))


def run(pass_: str, baseline: str = "control") -> Path:
    w, rubrics, verdicts = inputs.load_weights(), inputs.load_rubrics(), _verdicts(pass_)
    sc, coll = w.scales, collected(pass_)
    excluded = inputs.load_excluded()
    _guard(pass_, sorted(coll), excluded)
    arms_out = {}
    flags = [f"excluded-tests: {e['id']} verdict is a draft (decided: {e['decided']})"
             for e in excluded.entries if not str(e["decided"]).startswith("owner")]
    if (why := faults.halt_reason(pass_)):
        flags.append(f"pass {pass_} is HALTED: {why}")
    if baseline not in coll:
        flags.append(f"baseline arm '{baseline}' has no collected records")
    field = sorted({n for r in coll.values() for n in r})
    for arm in sorted(coll):
        if sorted(coll[arm]) != field:
            flags.append(f"{arm}: steps collected {sorted(coll[arm])} differ from the field {field}")
        dims = {}
        for dim in w.dimensions:
            names = list(w.parts.get(dim, {dim: 0}))
            parts = {}
            for part in names:
                steps = _part_steps(pass_, part, arm, coll[arm], coll.get(baseline, {}), rubrics, verdicts, sc)
                parts[part] = {"score": _part_score(steps), "steps": steps}
            dims[dim] = _dimension(dim, parts, w)
            if dims[dim]["score"] is None:
                flags.append(f"{arm}: {dim} unmeasured")
            flags += [f"{arm}: {dim}.{p} unmeasured" for p in dims[dim]["unmeasured_parts"]]
        arms_out[arm] = {"total": sum(d["score"] for d in dims.values() if d["score"] is not None),
                         "dimensions": dims}
    out = paths.scoring_out(pass_) / "scores.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(values.dump({"baseline": baseline, "weights": {"dimensions": w.dimensions, "parts": w.parts},
                                "arms": arms_out, "flags": sorted(flags)}))
    return out
