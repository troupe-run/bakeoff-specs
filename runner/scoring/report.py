"""Stage: scores.json + collected records (+ optional decisions, owner notes) -> report.md (spec §11). Deterministic.

Read top-down: bottom line, scorecard, dimensions, decisions, time and cost, confidence, then one appendix per arm.
Cells that could not be measured show "—" (never 0); their reasons are in the arm appendices."""
from __future__ import annotations
import json
import statistics
from pathlib import Path
from runner import paths
from runner.scoring import aggregate, confidence, decisions, inputs, values

DASH = "—"
# Footnote markers on a time cell: where the seconds are approximate.
KILLED, BACKGROUND, APPROX = "‡", "§", "~"
BLINDING = ("Blinding is partial: judges and the owner's decision ratings saw anonymised labels, but arm-specific "
            "vocabulary (command names, file layouts, spec formats) can still identify the method.")
PREREG = ("This scoring is not fully pre-registered: the what-goes-stale lists, rubrics and the review of tests every "
          "arm fails were written after steps 1–5's results were seen and before steps 6–7's (spec §9).")


def outliers(vals: dict[str, float | None], factor: float) -> dict[str, str]:
    xs = sorted(v for v in vals.values() if v is not None)
    if len(xs) < 3:
        return {}
    med = xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
    return {a: ("high" if v >= factor * med else "low") for a, v in sorted(vals.items())
            if v is not None and (v >= factor * med or v <= med / factor)}


# ---- small formatting helpers ------------------------------------------------------------------------------

def _v(leaf):
    return None if leaf is None or values.is_missing(leaf) else leaf["value"]


def _mark(kind: str | None) -> str:
    return {"high": "▲", "low": "▼"}.get(kind or "", "")


def _num(x: float | None, fmt: str = ".1f") -> str:
    return DASH if x is None else format(x, fmt)


def _pct(x: float) -> str:
    r = round(x * 100)
    return "0%" if r == 0 else f"{r:+d}%"


def _mins(s: float | None) -> str:
    return DASH if s is None else f"{s / 60:.1f} min"


def _usd(x: float | None) -> str:
    return DASH if x is None else f"${x:.2f}"


def _table(head: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] + ["---:"] * (len(head) - 1)) + "|"]
    return out + ["| " + " | ".join(r) + " |" for r in rows] + [""]


def _src(source: str) -> str:
    """Collected sources are repo-relative (results/<pass>/...); the report sits in results/<pass>/scoring/."""
    return f"([src](../../../{source}))"


def _steps_of(coll: dict) -> list[int]:
    return sorted({n for recs in coll.values() for n in recs})


# ---- bottom line -------------------------------------------------------------------------------------------

def _total(arm: dict) -> str:
    """An arm's total; † when its measured dimensions differ from the field's (R34: renormalised, not like-for-like)."""
    return _num(arm["total"]) + ("†" if arm.get("total_partial") else "")


def _ranked_lines(scores: dict, conf: dict) -> list[str]:
    out, rank = [], 1
    for g in conf["groups"]:
        span = f"{rank}–{rank + len(g) - 1}" if len(g) > 1 else f"{rank}"
        label = f"{span} (within noise)" if len(g) > 1 else span
        out.append(f"{label}: " + " · ".join(f"{a} {_total(scores['arms'][a])}" for a in g))
        rank += len(g)
    return out


def _strengths(scores: dict) -> list[str]:
    """Per arm: the dimension furthest above / below the field mean of (score / max), in points of that dimension."""
    arms = scores["arms"]
    dims = sorted({d for a in arms.values() for d in a["dimensions"]})
    frac = {a: {d: v["dimensions"][d]["score"] / v["dimensions"][d]["max"] for d in dims
                if v["dimensions"][d]["score"] is not None} for a, v in arms.items()}
    mean = {d: statistics.mean(f[d] for f in frac.values() if d in f) for d in dims if any(d in f for f in frac.values())}
    lines = []
    for a in sorted(arms):
        diffs = {d: frac[a][d] - mean[d] for d in frac[a]}
        if len(diffs) < 2:
            continue
        hi, lo = max(sorted(diffs), key=lambda d: diffs[d]), min(sorted(diffs), key=lambda d: diffs[d])
        lines.append(f"   - {a}: strongest {hi} ({_pct(diffs[hi])} of its weight vs the field mean), "
                     f"weakest {lo} ({_pct(diffs[lo])})")
    return lines


def _totals(coll: dict) -> dict[str, dict]:
    out = {}
    for arm, recs in sorted(coll.items()):
        row = {"seconds": 0.0, "usd": 0.0, "po": 0.0, "disc": 0.0, "n": {"seconds": 0, "usd": 0, "po": 0, "disc": 0},
               "m": len(recs)}
        for r in recs.values():
            t, c = _v(r.get("time")), _v(r.get("cost")) or {}
            for k, x in (("seconds", (t or {}).get("seconds")), ("usd", c.get("scored_usd")),
                         ("po", c.get("po_usd")), ("disc", c.get("discovery_usd"))):
                if x is not None:
                    row[k] += x
                    row["n"][k] += 1
        out[arm] = row
    return out


def _total_outliers(coll: dict, factor: float) -> dict[str, dict[str, str]]:
    t = _totals(coll)
    return {m: outliers({a: (r[k] if r["n"][k] == r["m"] else None) for a, r in t.items()}, factor)   # † sums are left out
            for m, k in (("time", "seconds"), ("cost", "usd"))}


def _bottom_line(scores: dict, conf: dict, coll: dict, pass_: str, factor: float) -> list[str]:
    out = ["## Bottom line", ""]
    out += [f"- {l}" for l in _ranked_lines(scores, conf)] + [""]
    groups = [g for g in conf["groups"] if len(g) > 1]
    findings = [("The order is settled for every arm." if not groups else
                 f"{len(groups)} group(s) of arms are within noise of each other and should not be ranked "
                 f"against one another; {len(conf['order_changes'])} weight/judge variant(s) change the order.")]
    st = _strengths(scores)
    findings.append("Relative to the field mean (share of each dimension's weight):" + "".join("\n" + l for l in st)
                    if st else "Relative to the field mean: too few measured dimensions to name strengths.")
    ol = _total_outliers(coll, factor)
    findings.append(f"Time and cost outliers (≥{factor:g}× or ≤1/{factor:g}× the median, arm totals): "
                    f"{len(ol['time'])} on time, {len(ol['cost'])} on cost; see Time and cost.")
    unm = [f for f in scores["flags"] if "unmeasured" in f]
    findings.append(f"{len(unm)} unmeasured dimension/part flag(s); those cells carry † and their weight is shared "
                    f"among the measured parts." if unm else "No unmeasured dimensions or parts.")
    methods = scores.get("mutation_methods", {})
    if len({m for ms in methods.values() for m in ms}) > 1:
        findings.append("Mutation scores mix methods, so they are not like-for-like across arms ("
                        + "; ".join(f"{a}: " + ", ".join(f"{m} {n}" for m, n in sorted(ms.items()))
                                    for a, ms in sorted(methods.items()))
                        + " scored steps); `--stage remeasure --all` re-measures every step by one method.")
    out += [f"{i}. {f}" for i, f in enumerate(findings, 1)] + [""]
    out += [f"**Blinding.** {BLINDING}", "", f"**Pre-registration.** {PREREG}", ""]
    notes = paths.scoring_out(pass_) / "report-notes.md"
    if notes.exists():
        out += [notes.read_text().rstrip("\n"), ""]
    return out


# ---- scorecard ---------------------------------------------------------------------------------------------

def _scorecard(scores: dict, factor: float) -> list[str]:
    arms = scores["arms"]
    dims = list(next(iter(arms.values()))["dimensions"]) if arms else []
    cols = {d: outliers({a: arms[a]["dimensions"][d]["score"] for a in arms}, factor) for d in dims}
    rows = []
    for a in sorted(arms):
        cells = []
        for d in dims:
            dd = arms[a]["dimensions"][d]
            cells.append(_num(dd["score"]) + ("†" if dd["unmeasured_parts"] or dd["score"] is None else "")
                         + _mark(cols[d].get(a)))
        rows.append([a] + cells + [_total(arms[a])])
    head = ["arm"] + [f"{d} /{arms[next(iter(arms))]['dimensions'][d]['max']:g}" for d in dims] + ["total /100"]
    return ["## Scorecard", ""] + _table(head, rows) + [
        "† a part of this dimension is unmeasured (its weight went to the measured parts); — nothing measured; "
        f"▲/▼ ≥{factor:g}× / ≤1/{factor:g}× the median of the arms. A total is 100 × the measured dimensions' scores over "
        "their weights (an unmeasured dimension is left out, never counted as 0); † on a total: that arm's measured "
        "dimensions differ from the field's, so it is not like-for-like.", ""]


# ---- dimensions --------------------------------------------------------------------------------------------

def _dimensions(scores: dict) -> list[str]:
    arms = sorted(scores["arms"])
    out = ["## Dimensions", ""]
    w = scores["weights"]
    for dim, mx in w["dimensions"].items():
        out += [f"### {dim} (/{mx:g})", ""]
        parts = list(scores["arms"][arms[0]]["dimensions"][dim]["parts"])
        pts = lambda p: f" ({w['parts'][dim][p]:g} pts)" if dim in w["parts"] else ""
        out += _table(["part"] + arms, [[p + pts(p)] + [_num(scores["arms"][a]["dimensions"][dim]["parts"][p]["score"], ".2f")
                                                       for a in arms] for p in parts])
        rows = []
        for p in parts:
            keys = sorted({k for a in arms for k in scores["arms"][a]["dimensions"][dim]["parts"][p]["steps"]},
                          key=lambda k: (not k.isdigit(), int(k) if k.isdigit() else 0, k))
            for k in keys:
                cells = []
                for a in arms:
                    st = scores["arms"][a]["dimensions"][dim]["parts"][p]["steps"].get(k)
                    cells.append(DASH if st is None else _num(st["score"], ".2f")
                                 + ("*" if st.get("disputed") else "") + ("°" if "owner" in st else ""))
                rows.append([f"{p} · {'arm' if k == 'arm' else 'step ' + k}"] + cells)
        out += _table(["part · step"] + arms, rows)
        out += ["Scores are 0–1. * judges disagreed by 2+ points; ° the owner's verdict was used. — unmeasured or "
                "not applicable; the reason is in the arm's appendix.", ""]
    return out


# ---- decision review ---------------------------------------------------------------------------------------

def _decisions(pass_: str) -> list[str]:
    d = paths.scoring_out(pass_) / "decisions"
    f = d / "ratings.json"
    if not f.exists():
        return []
    topics = json.loads(f.read_text()).get("topics", [])
    asked = {}
    tf = d / "topics.json"
    if tf.exists():
        asked = {t.get("id"): t.get("question", "") for t in json.loads(tf.read_text()).get("topics", [])}
    n_arms = len({a for t in topics for r in t["routes"] for a in r["arms"]})
    lines = {k: [] for k in decisions.KINDS}
    for t in topics:
        kind = decisions.kind(t, n_arms)
        q = t.get("question") or asked.get(t.get("id")) or t.get("id", "?")
        routes = "; ".join(f"{r.get('route', '?')} [{', '.join(r['arms'])}: {r.get('rating', DASH)}]" for r in t["routes"])
        lines[kind].append(f"- {q} {routes}")
    out = ["## Decision review", ""]
    for kind, title in (("one-off", "One-offs"), ("divergent", "Divergent"), ("unanimous", "Unanimous")):
        out += [f"### {title} ({len(lines[kind])})", ""] + lines[kind] + [""]
    return out


# ---- time and cost -----------------------------------------------------------------------------------------

def _turn_marks(t: dict | None) -> str:
    marks = ""
    turns = (t or {}).get("turns", [])
    if any(x.get("killed") for x in turns):
        marks += KILLED
    if any(x.get("background_wait") for x in turns):
        marks += BACKGROUND
    if any(x.get("time_source") == "duration_ms" for x in turns):
        marks += APPROX
    return marks


class _Acc:
    """A sum that remembers how many occurrences contributed, so a partial sum can be marked."""
    def __init__(self):
        self.sum, self.n, self.seen = 0.0, 0, 0

    def add(self, x) -> None:
        self.seen += 1
        if x is not None:
            self.sum += x
            self.n += 1

    def cell(self, fmt, gaps: bool) -> str:
        return fmt(self.sum if self.n else None) + ("†" if gaps or (self.n and self.n < self.seen) else "")


def _phase_tables(coll: dict) -> list[str]:
    arms = sorted(coll)
    meth: dict[str, dict[str, list[_Acc]]] = {a: {} for a in arms}
    common: dict[str, dict[str, list[_Acc]]] = {a: {} for a in arms}
    gaps = {a: {"method": 0, "common": 0} for a in arms}       # steps whose phases leaf is missing
    for a in arms:
        for r in coll[a].values():
            ph = r.get("phases", {})
            m = _v(ph.get("method"))
            if m is None:
                gaps[a]["method"] += 1
            for x in m or []:
                s = meth[a].setdefault(x.get("label", "?"), [_Acc(), _Acc()])
                s[0].add(x.get("seconds"))
                s[1].add(x.get("usd"))
            c = _v(ph.get("common"))
            if c is None:
                gaps[a]["common"] += 1
            for p in ((c or {}).get("seconds") or {}):
                x = common[a].setdefault(p, [_Acc(), _Acc()])
                x[0].add(c["seconds"][p])
                x[1].add((c.get("usd") or {}).get(p))
    out = ["### Phase split, method view (the arm's own step labels, all steps)", ""]
    rows = []
    for a in arms:
        g = gaps[a]["method"] > 0
        for label, (s, u) in sorted(meth[a].items()):
            rows.append([a + ("†" if g else ""), label, s.cell(_mins, g), u.cell(_usd, g)])
        if g and not meth[a]:
            rows.append([a + "†", DASH, DASH, DASH])
    out += _table(["arm", "label", "time", "cost"], rows) if rows else ["No method phases measured.", ""]
    out += ["### Phase split, common view (same phases for every arm, all steps)", ""]
    phases = sorted({p for a in arms for p in common[a]})
    rows = []
    for a in arms:
        g = gaps[a]["common"] > 0
        rows.append([a + ("†" if g else "")] + [(common[a][p][0].cell(_mins, g) + " / " + common[a][p][1].cell(_usd, g))
                                              if p in common[a] else DASH for p in phases])
    if phases:
        out += _table(["arm"] + phases, rows)
    else:
        out += ["No common phases measured" + "".join(f"; {a}† has a step with no common phases" for a in arms
                                                      if gaps[a]["common"]) + ".", ""]
    out += ["† a step's phases are missing or partly unmeasured (see the arm's appendix); the sum leaves it out, "
            "never counts it as 0.", ""]
    return out


def _time_cost(coll: dict, factor: float) -> list[str]:
    arms = sorted(coll)
    out = ["## Time and cost", ""]
    for n in _steps_of(coll):
        out += [f"### Step {n}", ""]
        secs, usd, rows = {}, {}, []
        recs = {a: coll[a].get(n) for a in arms}
        for a in arms:
            r = recs[a]
            t = _v(r.get("time")) if r else None
            secs[a] = t.get("seconds") if t else None
            usd[a] = (_v(r.get("cost")) or {}).get("scored_usd") if r else None
        ot, oc = outliers(secs, factor), outliers(usd, factor)
        for a in arms:
            t = _v(recs[a].get("time")) if recs[a] else None
            rows.append([a, _mins(secs[a]) + _turn_marks(t) + _mark(ot.get(a)), _usd(usd[a]) + _mark(oc.get(a))])
        out += _table(["arm", "time", "cost (scored)"], rows)
    t, ol = _totals(coll), _total_outliers(coll, factor)
    out += ["### All steps (per arm)", ""]
    rows = []
    for a in arms:
        r = t[a]
        part = lambda k: "†" if r["n"][k] < r["m"] else ""
        rows.append([a, _mins(r["seconds"] if r["n"]["seconds"] else None) + part("seconds") + _mark(ol["time"].get(a)),
                     _usd(r["usd"] if r["n"]["usd"] else None) + part("usd") + _mark(ol["cost"].get(a)),
                     _usd(r["po"] if r["n"]["po"] else None) + part("po"),
                     _usd(r["disc"] if r["n"]["disc"] else None) + part("disc")])
    out += _table(["arm", "time", "cost (scored)", "PO cost", "discovery cost"], rows)
    out += _phase_tables(coll)
    out += [f"{KILLED} a turn was killed; {BACKGROUND} a turn includes a background wait; {APPROX} a turn's time comes "
            "from the stream's duration_ms, not wall-clock (approximate). † some steps have no value and are left out "
            f"of the sum (never counted as 0); — not measured. ▲/▼ ≥{factor:g}× / ≤1/{factor:g}× the median of the arms.", ""]
    return out


# ---- confidence --------------------------------------------------------------------------------------------

def _confidence(scores: dict, conf: dict) -> list[str]:
    out = ["## Confidence", "",
           "Each arm's total across every variant: weights ±5 per dimension, disputed judgements at each single "
           "lens's extreme, and both together (spec §10). Order is also checked pairwise: an arm's disputed items at "
           "their low extreme against the arm below it at its high extreme (\"judges a low / b high\").", ""]
    rows = [[a, _total(scores["arms"][a]), _num(conf["intervals"][a][0]), _num(conf["intervals"][a][1])]
            for a in conf["ranking"]]
    out += _table(["arm", "reported", "lowest", "highest"], rows)
    out += ["### Variants that change the order", ""]
    out += ([f"- {c['variant']}: {' > '.join(c['order'])}" for c in conf["order_changes"]]
            if conf["order_changes"] else ["None: no variant changes the order."]) + [""]
    out += ["### Flags", ""] + ([f"- {f}" for f in scores["flags"]] or ["None."]) + [""]
    return out


# ---- appendix ----------------------------------------------------------------------------------------------

def _f(x) -> str:
    return DASH if x is None else str(x)


NOT_LIKE_FOR_LIKE = ("Mutation scores marked \"via whole-suite-per-mutant\" (the Task 20 re-measure) are not "
                     "like-for-like with \"via mutmut\": mutmut leaves a mutant no test covers out of the score, while "
                     "the whole suite per mutant counts it as survived.")


def _quality_text(name: str, v: dict, source: str) -> str:
    """mypy and ruff link the summary; the mutation part links its own source (a re-measure when one was used,
    R32) and names its method, partial runs their checked share, and a present but unused re-measure why."""
    m = f"mutation {_f(v.get('mutation_score'))} ({v.get('mutation_state')}"
    m += f": {v['mutation_why']})" if v.get("mutation_why") else ")"
    if v.get("mutation_method"):
        m += f" via {v['mutation_method']}"
    if v.get("mutation_partial"):
        cf = v.get("mutation_checked_fraction")
        m += ", partial" + (f", {round(cf * 100)}% checked" if isinstance(cf, (int, float)) else "")
    m += f" {_src(v.get('mutation_source') or source)}"
    if v.get("remeasure_ignored"):
        m += f"; re-measure ignored: {v['remeasure_ignored']}"
    return f"{name}: mypy {_f(v.get('mypy_errors'))}, ruff {_f(v.get('ruff_findings'))} {_src(source)}; {m}"


def _leaf_text(name: str, leaf: dict | None) -> str:
    if leaf is None:
        return f"{name}: {DASH} (no record)"
    if values.is_missing(leaf):
        return f"{name}: {DASH} ({leaf['why']}; expected at `{leaf['missing']}`)"
    v, link = leaf["value"], _src(leaf["source"])
    if name == "hidden" and isinstance(v, dict) and "passed" in v:
        return f"{name}: {v['passed']}/{v['total']} passed, {len(v.get('excluded', []))} excluded {link}"
    if name == "regressions" and isinstance(v, dict):
        return f"{name}: rate {_f(v.get('rate'))} {link}"
    if name == "quality" and isinstance(v, dict):
        return _quality_text(name, v, leaf["source"])
    if name == "time" and isinstance(v, dict):
        return f"{name}: {_mins(v.get('seconds'))}, attempt {_f(v.get('attempt'))}, {len(v.get('turns', []))} turn(s) {link}"
    if name == "cost" and isinstance(v, dict):
        return (f"{name}: scored {_usd(v.get('scored_usd'))}, PO {_usd(v.get('po_usd'))}, discovery "
                f"{_usd(v.get('discovery_usd'))} {link}")
    if name == "churn" and isinstance(v, dict):
        return f"{name}: {_f(v.get('lines'))} lines in {len(v.get('files', []))} file(s) {link}"
    if name == "questions" and isinstance(v, dict):
        return f"{name}: {len(v.get('items', []))} item(s), {v.get('skipped_lines', 0)} skipped line(s) {link}"
    if name == "violations" and isinstance(v, list):
        return f"{name}: {len(v)} {link}"
    return f"{name}: {json.dumps(v, sort_keys=True)} {link}"


def _lens_lines(pass_: str, arm: str) -> list[str]:
    root = paths.scoring_out(pass_) / "judged"
    out = []
    for f in sorted(root.glob(f"*/{arm}/*/*.json")) if root.is_dir() else []:
        part, _, key, lens = f.relative_to(root).parts[0], f.parts[-3], f.parts[-2], f.stem
        rel = f.relative_to(paths.scoring_out(pass_))
        try:
            j = json.loads(f.read_text())
            j.get("status")
        except (OSError, ValueError, AttributeError):
            out.append(f"- {part} · {key} · {lens}: unreadable ([file]({rel.as_posix()}))")
            continue
        ev = "; ".join(str(e) for e in j.get("evidence", [])) or "no evidence cited"
        out.append(f"- {part} · {key} · {lens}: {j.get('status')} score {_f(j.get('score'))} — {ev} "
                   f"([file]({rel.as_posix()}))" + (f" — {j['notes']}" if j.get("notes") else ""))
    return out


def _appendix(pass_: str, arm: str, scores: dict, recs: dict[int, dict]) -> list[str]:
    out = [f"## Appendix: {arm}", ""]
    if any(_v(r.get("quality")) and _v(r.get("quality")).get("mutation_method") not in (None, "mutmut")
           for r in recs.values()):
        out += [f"*{NOT_LIKE_FOR_LIKE}*", ""]
    for n, r in sorted(recs.items()):
        out += [f"### Step {n}", ""]
        for name in sorted(k for k in r if k not in ("arm", "step", "phases")):
            out.append(f"- {_leaf_text(name, r[name])}")
        for sub in sorted(r.get("phases", {})):
            out.append(f"- {_leaf_text('phases.' + sub, r['phases'][sub])}")
        out.append("")
    lens = _lens_lines(pass_, arm)
    out += ["### Lens verdicts", ""] + (lens or ["No judged parts for this arm."]) + [""]
    return out


# ---- entry points ------------------------------------------------------------------------------------------

def render(pass_: str) -> str:
    scores = json.loads((paths.scoring_out(pass_) / "scores.json").read_text())
    if not scores["arms"]:
        return f"# Pass {pass_} — scorecard\n\n## Bottom line\n\nNo arms collected: nothing to report.\n"
    conf, coll = confidence.check(scores), aggregate.collected(pass_)
    factor = inputs.load_weights().report["outlier_factor"]
    parts = [[f"# Pass {pass_} — scorecard", ""], _bottom_line(scores, conf, coll, pass_, factor),
             _scorecard(scores, factor), _dimensions(scores), _decisions(pass_), _time_cost(coll, factor),
             _confidence(scores, conf)]
    parts += [_appendix(pass_, a, scores, coll.get(a, {})) for a in sorted(scores["arms"])]
    return "\n".join(l for sec in parts for l in sec).rstrip("\n") + "\n"


def run(pass_: str) -> Path:
    out = paths.scoring_out(pass_) / "report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(pass_))
    return out
