# runner/scoring/aggregate.py
"""Stage: collected + judged + ratings + owner verdicts + weights -> scores.json (spec §3, §4, §6). Deterministic."""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
from runner import faults, paths
from runner.scoring import evidence, inputs, scales, values

ARM_MEASURED = {"violations", "choice"}
MEASURED = {"correctness", "regressions", "churn", "time", "cost", "mutation", "types", "lint", "size", "violations", "choice"}
FIELD_RELATIVE = {"time", "cost"}       # scored against the median arm at the step (owner, 2026-10-10)


def _v(x):
    return None if x is None or values.is_missing(x) else x["value"]


def collected(pass_: str) -> dict[str, dict[int, dict]]:
    out: dict[str, dict[int, dict]] = {}
    for f in sorted((paths.scoring_out(pass_) / "collected").glob("*/*.json")):
        out.setdefault(f.parent.name, {})[int(f.stem)] = json.loads(f.read_text())
    return out


def arm_violations(pass_: str, arm: str) -> dict:
    """R38: the arm's collected arm-level violations leaf; missing (never collected, or unreadable) is unmeasured."""
    f = paths.scoring_out(pass_) / "collected-arm" / f"{arm}.json"
    try:
        rec = json.loads(f.read_text())["arm_violations"]
    except FileNotFoundError:
        return values.missing(str(f), "not collected (run the collect stage)")
    except (OSError, ValueError, KeyError, TypeError) as e:
        return values.missing(str(f), f"unreadable: {e}")
    return rec


def read_verdicts(pass_: str) -> dict[tuple, dict]:
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
        if r["score"] is not None and (isinstance(r["score"], bool) or not isinstance(r["score"], (int, float))
                                       or not 0 <= r["score"] <= 4):
            raise inputs.InputError(f"{where}: score must be 0-4 or null (not applicable), got {r['score']!r}")
        if key in out:
            raise inputs.InputError(f"{where}: duplicate verdict for {key}")
        out[key] = r
    return out


def asked_question(rec: dict | None) -> bool | None:
    """Owner rule, 2026-10-10: did the arm send the PO at least one message of kind `question`, in the step's N.a
    (discovery) or N.b (scored) run? None when the question log is missing (unknown, never "asked none")."""
    q = _v(rec.get("questions")) if rec else None
    if q is None:
        return None
    return any(i.get("kind") == "question" for i in q.get("items", []))


def _judged(pass_: str, part: str, arm: str, key: str, verdicts: dict, names: frozenset[str],
            asked: bool | None = None, record_na: bool = False) -> dict:
    """One judged step from its lens files. Only files named after one of the rubric's lenses (`names`) count; any
    other is ignored and listed (`ignored_lenses`, flagged by run()). Fewer than three ok lenses is a `thin` panel.

    `record_na` (rubrics with `not_applicable = true`; owner rule, 2026-10-10): whether the step applies is decided
    by the question log, not by judge vote. No `question`-kind message (`asked` False) makes the step not applicable
    whatever the lenses scored; a question asked (`asked` True) ignores the not_applicable lenses and takes the median
    of the scoring ones. An unknown log (`asked` None) falls back to the lenses: n/a only if no lens scored. An owner
    verdict overrides either way."""
    d = paths.scoring_out(pass_) / "judged" / part / arm / key
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    stray = sorted(f.stem for f in files if f.stem not in names)
    lenses = {f.stem: json.loads(f.read_text()) for f in files if f.stem in names}
    ok = {n: j["score"] for n, j in lenses.items() if j.get("status") == "ok" and j.get("score") is not None}
    owner = verdicts.get((part, arm, key.lstrip("0") or key))
    extra = {"ignored_lenses": stray} if stray else {}
    if record_na:
        extra["asked"] = asked
    if not lenses and owner is None and not (record_na and asked is False):
        return {"score": None, "why": "not judged"} | extra
    if owner is None and record_na and asked is False:
        return {"score": None, "why": "not applicable (no question asked)", "lenses": {}, "disputed": False,
                "lenses_ignored": ok} | extra
    if owner is None and not ok and any(j.get("status") == "not_applicable" for j in lenses.values()):
        why = ("not applicable (a question was asked, but every lens answered not_applicable)"
               if record_na and asked else "not applicable")
        return {"score": None, "why": why, "lenses": {}, "disputed": False} | extra
    if owner is not None and owner["score"] is None:      # the owner ruled the step not applicable: unmeasured, never 0
        return {"score": None, "why": "not applicable", "lenses": ok, "disputed": False, "owner": owner} | extra
    used = owner["score"] if owner else (statistics.median(ok.values()) if ok else None)
    out = {"score": scales.judged(used), "lenses": ok, "disputed": len(ok) >= 2 and max(ok.values()) - min(ok.values()) >= 2,
           "thin": len(ok) < 3} | extra
    if owner:
        out["owner"] = owner
    if used is None:                        # R24(d): absent evidence is unmeasured, and says so (never a zero)
        missing = any(j.get("status") == "input_missing" for j in lenses.values())
        out["why"] = "input missing" if missing else "judge_failed"
    return out


def _per_kloc(part: str, q: dict | None, step_dir: Path, sc: dict) -> dict:
    """Owner rule, 2026-10-10, the same for every arm and step. `types`: mypy errors per 1,000 lines mypy checked;
    `lint`: ruff findings (harness ruleset, quality/ruff.json; a safe auto-fix counts `lint_safe_fix_weight`) per 1,000
    lines ruff checked. Each is normalised by its own tool's lines (quality/size.json): mypy runs over its targets
    (src when there is one), ruff over the whole repo (src and tests). Score max(0, 1 - per_kloc / <part>_zero_per_kloc).
    A crashed or timed-out tool, or no size measured, is unmeasured (None, with why), never 0."""
    if not q:
        return {"score": None, "why": "no quality results"}
    size = evidence.code_size(step_dir)
    if part == "types":
        if q.get("mypy_errors") is None:
            return {"score": None, "why": "mypy crashed or timed out"}
        if values.is_missing(size):
            return {"score": None, "why": size["why"]}
        lines, n = size["value"]["type_lines"], q["mypy_errors"]
        s = scales.per_kloc(n, lines, sc["types_zero_per_kloc"])
        return ({"score": s, "errors": n, "lines": lines, "per_kloc": n * 1000 / lines} if s is not None
                else {"score": None, "why": "no Python lines under mypy's targets"})
    if q.get("ruff_findings") is None:
        return {"score": None, "why": "ruff crashed or timed out"}
    if values.is_missing(size):
        return {"score": None, "why": size["why"]}
    found = evidence.ruff_list(step_dir)
    if values.is_missing(found):
        return {"score": None, "why": f"ruff findings unreadable: {found['why']}"}
    fs = found["value"]
    if len(fs) != q["ruff_findings"]:
        return {"score": None, "why": f"ruff.json holds {len(fs)} findings, the summary {q['ruff_findings']}"}
    lines, w = size["value"]["lint_lines"], scales.lint_weight(fs, sc["lint_safe_fix_weight"])
    s = scales.per_kloc(w, lines, sc["lint_zero_per_kloc"])
    safe = sum(1 for f in fs if isinstance(f, dict) and isinstance(f.get("fix"), dict)
               and f["fix"].get("applicability") == "safe")
    return ({"score": s, "findings": len(fs), "safe_fixes": safe, "weighted": w, "lines": lines,
             "per_kloc": w * 1000 / lines} if s is not None else {"score": None, "why": "no Python lines ruff checked"})


def _measured(part: str, rec: dict, base: dict | None, sc: dict, pass_: str) -> dict:
    h, q = _v(rec["hidden"]), _v(rec["quality"])
    if part in ("types", "lint"):
        return _per_kloc(part, q, paths.RESULTS / pass_ / rec["arm"] / f"{rec['step']:02d}", sc)
    if part == "correctness":
        return {"score": h["passed"] / h["total"]} if h and h["total"] else {"score": None, "why": "no hidden results"}
    if part == "regressions":
        r = _v(rec["regressions"])
        return {"score": r["rate"]} if r and r["rate"] is not None else {"score": None, "why": "no earlier tests"}
    if part == "mutation":
        if q and q["mutation_state"] == "measured" and q["mutation_score"] is not None:
            return {"score": q["mutation_score"], "method": q.get("mutation_method") or "unrecorded"}
        if q and q["mutation_state"] == "measured":
            return {"score": None, "why": "measured but no score"}
        return {"score": None, "why": (q.get("mutation_why") or q["mutation_state"]) if q else "no quality results"}
    if base is None:
        return {"score": None, "why": "no baseline for this step"}
    if part == "churn":
        a, b = _v(rec["churn"]), _v(base["churn"])
        return ({"score": scales.churn_score(a["lines"], b["lines"], sc["ratio_cap"])} if a and b
                else {"score": None, "why": "churn not measured"})
    raise ValueError(part)


def _raw(part: str, rec: dict) -> float | None:
    """The scored run's arm seconds (`time`) or USD (`cost`, cost.json "scored": PO and the N.a discovery run are
    excluded, as they are from time) for one step; None when unmeasured."""
    if part == "time":
        t = _v(rec.get("time"))
        x = t.get("seconds") if t else None
    else:
        c = _v(rec.get("cost"))
        x = c.get("scored_usd") if c else None
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 else None


def step_value(part: str, rec: dict) -> tuple[float | None, str | None]:
    """(raw time or cost for the step, None) or (None, why). An arm that passed no hidden test gets (inf, None): no
    outcome, the worst score, so failing fast never wins (owner, 2026-10-10: raw totals, easier to understand)."""
    hh = _v(rec.get("hidden"))
    x = _raw(part, rec)
    if x is None or not hh:
        return None, f"{part} or passed tests missing"
    return (x if hh["passed"] else math.inf), None


def _field_relative(part: str, n: int, rec: dict, field: dict[str, dict[int, dict]], sc: dict) -> dict:
    """Owner rule, 2026-10-10, the same for every arm and step: raw time and cost per step, on a log scale
    against the median of the arms measured at this step: 0.5 - log10(arm / median) / (2 log10 ratio_cap), clamped
    to [0, 1]. The median arm scores 0.5, ratio_cap times cheaper or faster 1, ratio_cap times dearer or slower 0. An
    arm that passed no hidden test scores 0 and is left out of the median; an unmeasured value is unmeasured."""
    mine, why = step_value(part, rec)
    if mine is None:
        return {"score": None, "why": why}
    xs = [x for x in (step_value(part, r[n])[0] for r in field.values() if n in r)
          if x is not None and math.isfinite(x)]
    if not xs:
        return {"score": None, "why": "no arm passed a hidden test at this step"}
    med = statistics.median(xs)
    if not math.isfinite(mine):
        return {"score": 0.0, "value": None, "median": med, "arms": len(xs)}
    return {"score": scales.ratio_score(mine, med, sc["ratio_cap"]), "value": mine, "median": med,
            "arms": len(xs)}


def _choice(pass_: str, arm: str, sc: dict) -> dict:
    f = paths.scoring_out(pass_) / "decisions" / "ratings.json"
    if not f.exists():
        return {"score": None, "why": "not rated"}
    table = scales.rating_table(sc)
    rs = [scales.rating(r["rating"], table) for t in json.loads(f.read_text())["topics"] for r in t["routes"]
          if arm in r["arms"]]
    rs = [r for r in rs if r is not None]
    return {"score": sum(rs) / len(rs)} if rs else {"score": None, "why": "no rated routes"}


def _source_lines(pass_: str, arm: str, n: int) -> tuple[int | None, str | None]:
    """(non-blank *.py lines under mypy's targets, i.e. src without tests, from quality/size.json, None) or (None, why)."""
    size = evidence.code_size(paths.RESULTS / pass_ / arm / f"{n:02d}")
    if values.is_missing(size):
        return None, size["why"]
    x = size["value"]["type_lines"]
    return (x, None) if x > 0 else (None, "no Python lines under mypy's targets")


def _size(pass_: str, arm: str, n: int, field: dict[str, dict[int, dict]], sc: dict) -> dict:
    """Owner rule, 2026-10-10, the same for every arm and step: source lines (`type_lines`, src only, so tests are not
    counted) against the median of the measured arms at the step, scales.size_score. Unmeasured is never 0."""
    mine, why = _source_lines(pass_, arm, n)
    if mine is None:
        return {"score": None, "why": why}
    xs = [x for x in (_source_lines(pass_, a, n)[0] for a in sorted(field) if n in field[a]) if x is not None]
    med = statistics.median(xs)
    return {"score": scales.size_score(mine, med, sc.get("size_plateau_fraction", 0.5), sc.get("size_zero_multiple", 4.0)),
            "lines": mine, "median": med, "arms": len(xs)}


def _part_steps(pass_, part, arm, recs, base_recs, rubrics, verdicts, sc, field=None) -> dict[str, dict]:
    if part in ARM_MEASURED or (part in rubrics and rubrics[part].unit == "arm"):
        if part == "choice":
            return {"arm": _choice(pass_, arm, sc)}
        if part == "violations":
            vs = {n: _v(r["violations"]) for n, r in sorted(recs.items())}
            gone = [n for n, v in vs.items() if v is None]
            if gone:
                return {"arm": {"score": None, "why": f"violations evidence missing for steps {gone}"}}
            if not vs:
                return {"arm": {"score": None, "why": "no run records"}}
            armlv = arm_violations(pass_, arm)
            if values.is_missing(armlv):                # R38: unmeasured, never a clean zero
                return {"arm": {"score": None, "why": f"arm-level violations unmeasured: {armlv['why']}"}}
            arm_list = armlv["value"]
            sev = inputs.load_violations()          # R36: each violation deducted by the severity of its kind
            kinds: dict[str, int] = {}
            for v in (x for step in [*vs.values(), arm_list] for x in step):
                k = v.get("kind") if isinstance(v, dict) and isinstance(v.get("kind"), str) else "unknown"
                kinds[k] = kinds.get(k, 0) + 1
            deducted = sum(sev.of(k) * n for k, n in kinds.items())
            return {"arm": {"score": max(0.0, 1.0 - deducted), "deducted": deducted, "kinds": kinds,
                             "arm_level": len(arm_list)}}
        return {"arm": _judged(pass_, part, arm, "arm", verdicts, _lens_names(rubrics[part]))}
    if part == "size":
        return {str(n): _size(pass_, arm, n, field or {arm: recs}, sc) for n in sorted(recs)}
    if part in FIELD_RELATIVE:
        return {str(n): _field_relative(part, n, r, field or {arm: recs}, sc) for n, r in sorted(recs.items())}
    if part in MEASURED:
        return {str(n): _measured(part, r, base_recs.get(n), sc, pass_) for n, r in sorted(recs.items())}
    if part not in rubrics:
        raise inputs.InputError(f"weights.toml part {part!r} has no rubric in scoring/rubrics and is not a measured part")
    steps = [n for n in rubrics[part].steps if n in recs]
    na = rubrics[part].not_applicable
    return {str(n): _judged(pass_, part, arm, f"{n:02d}", verdicts, _lens_names(rubrics[part]),
                            asked=asked_question(recs[n]) if na else None, record_na=na) for n in steps}


def _lens_names(r: inputs.Rubric) -> frozenset[str]:
    return frozenset(l["name"] for l in r.lenses)


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


def _total(dims: dict) -> float | None:
    """Ruling R34: 100 x the sum of the measured dimensions' scores over the sum of their maxima, never counting an
    unmeasured dimension as 0. Same rule as confidence.total (base weights, median), review._forced and the page."""
    measured = [d for d in dims.values() if d["score"] is not None]
    den = sum(d["max"] for d in measured)
    return 100 * sum(d["score"] for d in measured) / den if den > 0 else None


def _mutation_methods(arms_out: dict) -> dict[str, dict[str, int]]:
    """R35: {arm: {method: scored steps}} over the mutation steps that carry a score."""
    out: dict[str, dict[str, int]] = {}
    for arm, v in sorted(arms_out.items()):
        for d in v["dimensions"].values():
            for st in d["parts"].get("mutation", {}).get("steps", {}).values():
                if st["score"] is not None:
                    out.setdefault(arm, {}).setdefault(st["method"], 0)
                    out[arm][st["method"]] += 1
    return out


def _guard(pass_: str, arms: list[str], excluded: inputs.Exclusions) -> None:
    reviewed = excluded.reviewed
    pending = sorted({t for ts in evidence.all_fail(paths.RESULTS / pass_, arms).values() for t in ts} - reviewed)
    if pending:
        raise inputs.InputError("tests every arm failed are not reviewed in scoring/excluded-tests.toml: "
                                + ", ".join(pending))


def run(pass_: str, baseline: str = "control") -> Path:
    w, rubrics, verdicts = inputs.load_weights(), inputs.load_rubrics(), read_verdicts(pass_)
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
                steps = _part_steps(pass_, part, arm, coll[arm], coll.get(baseline, {}), rubrics, verdicts, sc, coll)
                parts[part] = {"score": _part_score(steps), "steps": steps}
                flags += [f"{arm}: {part} {f'{int(k):02d}' if k.isdigit() else k}: lens file(s) {st['ignored_lenses']} "
                          "are not lenses of the rubric; ignored" for k, st in steps.items() if st.get("ignored_lenses")]
                flags += [f"{arm}: {part} {int(k):02d}: question log missing; n/a decided by the lenses, not the record"
                          for k, st in steps.items() if "asked" in st and st["asked"] is None]
            dims[dim] = _dimension(dim, parts, w)
            if dims[dim]["score"] is None:
                flags.append(f"{arm}: {dim} unmeasured")
            flags += [f"{arm}: {dim}.{p} unmeasured" for p in dims[dim]["unmeasured_parts"]]
        arms_out[arm] = {"total": _total(dims), "dimensions": dims}
    field_measured = sorted({d for v in arms_out.values() for d, x in v["dimensions"].items() if x["score"] is not None})
    for arm, v in sorted(arms_out.items()):
        gap = [d for d in field_measured if v["dimensions"][d]["score"] is None]
        v["total_partial"] = bool(gap) or v["total"] is None
        if gap:
            flags.append(f"{arm}: total renormalised over its measured dimensions; unmeasured where other arms were "
                         f"measured: {gap} (the total is not like-for-like with the field)")
    methods = _mutation_methods(arms_out)
    if len({m for ms in methods.values() for m in ms}) > 1:
        flags.append("mutation methods mixed (not like-for-like): " + "; ".join(
            f"{a}: " + ", ".join(f"{m} {n}" for m, n in sorted(ms.items())) for a, ms in sorted(methods.items()))
            + f"; `runner score {pass_} --stage remeasure --all` re-measures every step by one method")
    out = paths.scoring_out(pass_) / "scores.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(values.dump({"baseline": baseline, "weights": {"dimensions": w.dimensions, "parts": w.parts},
                                "arms": arms_out, "flags": sorted(flags), "mutation_methods": methods}))
    return out
