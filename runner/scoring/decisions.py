"""Decision review (spec §8): extract every decision per label × step, align them into topics across labels, render a
blind rating sheet for the owner, import the owner's ratings back under real arm names.

Stages and files (all under `scoring_out/decisions/`):
- `extract` -> `extracted/<label>/<NN>.json`: a list of `{"decision", "options", "reason", "recorded_at"}`, or (never
  silently empty) `{"status": "extract_failed" | "input_missing", "why", "raw"?}`.
- `align` -> `topics.json` = `{"topics": [{"id", "question", "routes": [{"route", "labels", "reason_given", "outcome",
  "proposed", "proposed_why"}]}]}`; every label with no route in a topic is then added, deterministically, to a
  `"not considered"` route. Its single input is written to `anon/_decisions/align/extracted.json` (labels only,
  scrubbed again), so the container judge's one-item mount rule holds.
- `sheet` -> `rating-sheet.md` (the owner's blind view: numbered routes, no labels, no arm names) and
  `rating-sheet.json` (the same structure with labels, for import; no arm names).
- `import_ratings` -> `ratings.json` = `{"topics": [{"id", "routes": [{"route", "arms", "rating", "reason"}]}]}` (the
  Task 11 format). Only this stage reads `anon-key.json`.

Labels are the `Arm X` directories anonymise wrote; no stage before import knows which arm is which."""
from __future__ import annotations
import copy, json, os, re
from pathlib import Path
from runner import paths
from runner.scoring import anonymise, collect, inputs, judge, values

RATINGS = ("good", "acceptable", "poor", "out_of_scope")
NOT_CONSIDERED = "not considered"
KINDS = ("one-off", "divergent", "unanimous")
ALIGN_ITEM = "_decisions/align"                 # under anon/: <item>/<file>, the depth check_mounts requires
_SOURCES = ("diff.patch", "gates.md", "questions.md", "repo/", "transcript.md")
_LABEL = re.compile(r"^Arm [A-Z]$")
_STEP = re.compile(r"^\d\d$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# Owner notes recorded against their topic (spec §8), given to the aligner for its proposed ratings.
OWNER_NOTES = ("With TROUPE_ACTOR unset and no login name, the owner would rather the command fail than record a null "
               "or unknown actor (owner, 2026-10-05).",)


class SheetError(inputs.InputError):
    """The filled rating sheet has problems; the message lists each one by topic id and route number."""


def _dir(pass_: str) -> Path:
    return paths.scoring_out(pass_) / "decisions"


def _write(f: Path, text: str) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, f)                                       # never a half-written file a resume would skip


# ---- topics: not considered, kind ----------------------------------------------------------------------------------

def _members(r: dict) -> list[str]:
    return list(r["labels"] if "labels" in r else r.get("arms", []))


def fill_not_considered(topic: dict, labels: list[str]) -> dict:
    """A copy of `topic` in which every label without a route sits on a `"not considered"` route (last), carrying the
    aligner's `not_considered` proposal when it gave one."""
    t = copy.deepcopy(topic)
    nc_note = t.pop("not_considered", None) or {}
    routes = [r for r in t["routes"] if r["route"] != NOT_CONSIDERED]
    old = [l for r in t["routes"] if r["route"] == NOT_CONSIDERED for l in r["labels"]]
    taken = {l for r in routes for l in r["labels"]}
    rest = sorted({*old, *(l for l in labels if l not in taken)})
    if rest:
        nc = {"route": NOT_CONSIDERED, "labels": rest, "reason_given": "", "outcome": ""}
        if nc_note.get("proposed"):
            nc |= {"proposed": nc_note["proposed"], "proposed_why": nc_note.get("why", "")}
        routes.append(nc)
    t["routes"] = routes
    return t


def kind(topic: dict, n_labels: int) -> str:
    """one-off: exactly one label (or arm) took a route other than "not considered"; unanimous: one route holds every
    label; else divergent. Reads `labels` (topics, sheet) or `arms` (ratings.json)."""
    taken = [m for r in topic["routes"] if r["route"] != NOT_CONSIDERED for m in _members(r)]
    if len(taken) == 1:
        return "one-off"
    if any(r["route"] != NOT_CONSIDERED and len(set(_members(r))) == n_labels for r in topic["routes"]):
        return "unanimous"
    return "divergent"


# ---- JSON replies --------------------------------------------------------------------------------------------------

def _json_value(text: str):
    s = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.S)
    if fence:
        s = fence[1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    m = re.search(r"[\[{].*[\]}]", s, re.S)
    if not m:
        raise judge.BadReply("needs one JSON value")
    try:
        return json.loads(m[0])
    except json.JSONDecodeError as e:
        raise judge.BadReply(f"not JSON: {e}") from e


def _str(o: dict, k: str, where: str, *, nonempty: bool = False) -> str:
    v = o.get(k)
    if not isinstance(v, str) or (nonempty and not v.strip()):
        raise judge.BadReply(f"{where}: \"{k}\" must be a{' non-empty' if nonempty else ''} string")
    return v


def parse_decisions(text: str) -> list[dict]:
    """One JSON array of `{"decision", "options": [str], "reason", "recorded_at": str | "unrecorded"}` ([] allowed)."""
    v = _json_value(text)
    if not isinstance(v, list):
        raise judge.BadReply("needs one JSON array of decisions")
    out = []
    for i, d in enumerate(v, 1):
        where = f"decision {i}"
        if not isinstance(d, dict):
            raise judge.BadReply(f"{where} is not an object")
        opts = d.get("options")
        if not isinstance(opts, list) or not all(isinstance(o, str) for o in opts):
            raise judge.BadReply(f"{where}: \"options\" must be a list of strings ([] if none were recorded)")
        out.append({"decision": _str(d, "decision", where, nonempty=True), "options": opts,
                    "reason": _str(d, "reason", where), "recorded_at": _str(d, "recorded_at", where, nonempty=True)})
    return out


def parse_topics(text: str, labels: list[str]) -> list[dict]:
    """One JSON object `{"topics": [...]}`: unique slug ids, a question, routes each held by known labels (a label on
    at most one route per topic, never a "not considered" route: that is added afterwards), a proposed rating per
    route and, when some label has no route, for not considering the topic."""
    v = _json_value(text)
    if not isinstance(v, dict) or not isinstance(v.get("topics"), list):
        raise judge.BadReply('needs one JSON object {"topics": [...]}')
    seen: set[str] = set()
    out = []
    for i, t in enumerate(v["topics"], 1):
        if not isinstance(t, dict):
            raise judge.BadReply(f"topic {i} is not an object")
        tid = _str(t, "id", f"topic {i}", nonempty=True)
        if not _ID.match(tid) or tid in seen:
            raise judge.BadReply(f"topic {i}: id {tid!r} must be a unique lowercase slug (a-z, 0-9, -)")
        seen.add(tid)
        routes, held = t.get("routes"), set()
        if not isinstance(routes, list) or not routes:
            raise judge.BadReply(f"topic {tid}: needs at least one route")
        rs = []
        for k, r in enumerate(routes, 1):
            where = f"topic {tid} route {k}"
            if not isinstance(r, dict):
                raise judge.BadReply(f"{where} is not an object")
            name = _str(r, "route", where, nonempty=True)
            if name.strip().lower() == NOT_CONSIDERED:
                raise judge.BadReply(f"{where}: do not list a \"not considered\" route; it is added afterwards")
            ls = r.get("labels")
            if not isinstance(ls, list) or not ls or any(l not in labels for l in ls):
                raise judge.BadReply(f"{where}: \"labels\" must be a non-empty list drawn from {labels}")
            if held & set(ls):
                raise judge.BadReply(f"{where}: {sorted(held & set(ls))} already hold another route in this topic; "
                                     "describe a change of course as one route")
            held |= set(ls)
            if r.get("proposed") not in RATINGS:
                raise judge.BadReply(f"{where}: \"proposed\" must be one of {', '.join(RATINGS)}")
            rs.append({"route": name, "labels": sorted(ls), "reason_given": _str(r, "reason_given", where),
                       "outcome": _str(r, "outcome", where), "proposed": r["proposed"],
                       "proposed_why": _str(r, "proposed_why", where)})
        topic = {"id": tid, "question": _str(t, "question", f"topic {tid}", nonempty=True), "routes": rs}
        if set(labels) - held:
            nc = t.get("not_considered")
            if not isinstance(nc, dict) or nc.get("proposed") not in RATINGS:
                raise judge.BadReply(f"topic {tid}: needs \"not_considered\": {{\"proposed\": one of "
                                     f"{', '.join(RATINGS)}, \"why\": str}} (some labels never raised it)")
            topic["not_considered"] = {"proposed": nc["proposed"], "why": _str(nc, "why", f"topic {tid} not_considered")}
        out.append(topic)
    return out


def _ask(j: judge.Judge, prompt: str, d: Path, files: list[str], parse, what: str):
    """`judge.ask_with_retry`'s pattern: one more ask with the parse error appended; a second bad reply is
    `(None, why, raw)`, never an empty answer."""
    reply = j.ask(prompt, d, files)
    try:
        return parse(reply), "", reply
    except judge.BadReply as e:
        reply = j.ask(f"{prompt}\n\nYour previous reply could not be used ({e}). Reply with {what} only.", d, files)
        try:
            return parse(reply), "", reply
        except judge.BadReply as e2:
            return None, str(e2), reply


# ---- extract -------------------------------------------------------------------------------------------------------

def labels(pass_: str) -> list[str]:
    anon = paths.scoring_out(pass_) / "anon"
    return sorted(d.name for d in anon.iterdir() if d.is_dir() and _LABEL.match(d.name)) if anon.is_dir() else []


def _steps(pass_: str, label: str) -> list[str]:
    d = paths.scoring_out(pass_) / "anon" / label
    return sorted(c.name for c in d.iterdir() if c.is_dir() and _STEP.match(c.name))


def extracted_path(pass_: str, label: str, nn: str) -> Path:
    return _dir(pass_) / "extracted" / label / f"{nn}.json"


def _record(f: Path):
    """The extraction as written (list or status dict), or None when absent or unreadable."""
    try:
        return json.loads(f.read_text()) if f.exists() else None
    except (OSError, ValueError):
        return None


def _unfinished(f: Path, retry_failed: bool) -> bool:
    r = _record(f)
    if isinstance(r, list):
        return False
    status = r.get("status") if isinstance(r, dict) else None
    return status is None or status == "input_missing" or (retry_failed and status == "extract_failed")


def _present(d: Path) -> list[str]:
    named = judge._missing_json(d) if d.is_dir() else {}
    return [f for f in _SOURCES if f not in named and (d / f).exists()]


def extract_prompt(files: list[str]) -> str:
    listing = "\n".join(f"- /judge/{f}" for f in files)
    return ("You are reading one step of Arm X's work in a blind comparison of software development methods; you do "
            "not know which method it used and must not guess.\n\n"
            "List every decision visible in this step: each small change of direction or choice where options could "
            "have been weighed. Look in the gate messages (choices offered to the owner to confirm), the questions "
            "and their answers (including answers given by fallback or escalation), the specs, plans and decision "
            "records in the repository, the transcript, and the diff and code - including choices made silently in "
            "code or tests that nothing records. Do not judge the decisions; only record them.\n\n"
            f"Your inputs (read-only; use Read, Glob and Grep):\n{listing}\n\n"
            "For each decision give: \"decision\" (what was decided), \"options\" (the alternatives considered, if "
            "any were recorded; [] if none), \"reason\" (the reason given; \"\" if none), \"recorded_at\" (where it "
            "is recorded: path:line, commit sha, gate message or transcript line; \"unrecorded\" when it is visible "
            "only in the code).\n\n"
            "Reply with exactly one JSON array and nothing else ([] if there are none):\n"
            '[{"decision": "...", "options": ["..."], "reason": "...", "recorded_at": "..."}, ...]')


def _extract_items(pass_: str):
    anon = paths.scoring_out(pass_) / "anon"
    return [(lab, nn, anon / lab / nn) for lab in labels(pass_) for nn in _steps(pass_, lab)]


def extract(pass_: str, j: judge.Judge, *, retry_failed: bool = False) -> Path:
    """One call per unfinished label × step (resumable), each list written as it lands."""
    for lab, nn, d in _extract_items(pass_):
        f = extracted_path(pass_, lab, nn)
        if not _unfinished(f, retry_failed):
            continue
        files = _present(d)
        if not files:
            _write(f, values.dump({"status": "input_missing", "why": f"none of {', '.join(_SOURCES)} is present"}))
            continue
        got, why, raw = _ask(j, extract_prompt(files), d, files, parse_decisions, "one JSON array")
        _write(f, values.dump(got if got is not None else {"status": "extract_failed", "why": why, "raw": raw}))
    return _dir(pass_) / "extracted"


# ---- align ---------------------------------------------------------------------------------------------------------

def _arms(pass_: str) -> list[str]:
    d = paths.RESULTS / pass_
    return collect.arms(d) if d.is_dir() else []


def _scrub_obj(o, terms):
    if isinstance(o, str):
        return anonymise.scrub(o, terms)
    if isinstance(o, list):
        return [_scrub_obj(x, terms) for x in o]
    if isinstance(o, dict):
        return {k: _scrub_obj(v, terms) for k, v in o.items()}
    return o


def align_prompt(labs: list[str]) -> str:
    notes = "\n".join(f"- {n}" for n in OWNER_NOTES)
    return ("You are aligning design decisions across the arms of a blind comparison of software development methods. "
            f"The arms are labelled {', '.join(labs)}; you do not know which method any of them used and must not "
            "guess.\n\n"
            "Your input (read-only): /judge/extracted.json = {label: {step: [decisions]}}; each decision has "
            "\"decision\", \"options\", \"reason\" and \"recorded_at\". A label or step that is absent had nothing "
            "extracted.\n\n"
            "Group the decisions into topics: one topic per question that was decided (for example: check an "
            "environment variable before loading; which library; an id format; where nested overrides go). Every "
            "decision belongs to a topic, including ones only a single label decided. Within a topic, each different "
            "answer is a route; list the labels that took it. A label sits on at most one route per topic: if it "
            "changed course at a later step, describe that as one route (\"X, reworked to Y at step 5\"). Never list "
            "a \"not considered\" route: labels that never raised the topic are added afterwards.\n\n"
            "For each route give \"reason_given\" (the reasoning the arms recorded), \"outcome\" (what became of it at "
            "later steps: kept, reworked at step N, or unknown) and a proposed rating with a one-line why: good, "
            "acceptable, poor, or out_of_scope (not a real choice, or does not matter). For each topic that some "
            "labels never raised, also propose a rating for not considering it: if the topic mattered, missing it is "
            "a weakness; if it did not, not considering it can be acceptable.\n\n"
            f"Recorded preferences of the owner:\n{notes}\n\n"
            "Reply with exactly one JSON object and nothing else:\n"
            '{"topics": [{"id": "<lowercase-slug>", "question": "<the question decided>", '
            '"not_considered": {"proposed": "<rating>", "why": "<one line>"}, '
            '"routes": [{"route": "<the answer>", "labels": ["Arm A"], "reason_given": "...", "outcome": "...", '
            '"proposed": "<rating>", "proposed_why": "<one line>"}]}]}')


def align(pass_: str, j: judge.Judge) -> Path:
    """One call over every extracted list -> topics.json, each topic filled with its "not considered" route."""
    labs, collected, unrun = labels(pass_), {}, []
    for lab, nn, _ in _extract_items(pass_):
        r = _record(extracted_path(pass_, lab, nn))
        if r is None:
            unrun.append(f"{lab}/{nn}")
        elif isinstance(r, list):
            collected.setdefault(lab, {})[nn] = r
    if unrun:
        raise inputs.InputError(f"no extraction yet for {', '.join(unrun)}: run the decisions-extract stage first")
    item = paths.scoring_out(pass_) / "anon" / ALIGN_ITEM
    terms = anonymise.pass_terms(_arms(pass_))
    _write(item / "extracted.json", values.dump(_scrub_obj(collected, terms)))
    got, why, raw = _ask(j, align_prompt(labs), item, ["extracted.json"], lambda t: parse_topics(t, labs),
                         "one JSON object")
    failed = _dir(pass_) / "align-failed.json"
    if got is None:
        _write(failed, values.dump({"status": "align_failed", "why": why, "raw": raw}))
        raise inputs.InputError(f"the alignment failed twice ({why}); recorded in {failed}: re-run decisions-align")
    failed.unlink(missing_ok=True)
    out = _dir(pass_) / "topics.json"
    _write(out, values.dump({"topics": [fill_not_considered(t, labs) for t in sorted(got, key=lambda t: t["id"])]}))
    return out


# ---- the rating sheet ----------------------------------------------------------------------------------------------

def _ordered(topics: list[dict]) -> list[dict]:
    """The sheet's structure: topics one-offs, divergent, unanimous (then by id); routes by text, "not considered"
    last, numbered from 1."""
    n = len({l for t in topics for r in t["routes"] for l in _members(r)})
    out = []
    for t in topics:
        rs = sorted(t["routes"], key=lambda r: (r["route"] == NOT_CONSIDERED, r["route"]))
        out.append({"id": t["id"], "question": t.get("question", ""), "kind": kind(t, n),
                    "routes": [{"route_no": i, "route": r["route"], "labels": sorted(_members(r)),
                                "reason_given": r.get("reason_given", ""), "outcome": r.get("outcome", ""),
                                "proposed": r.get("proposed", ""), "proposed_why": r.get("proposed_why", "")}
                               for i, r in enumerate(rs, 1)]})
    return sorted(out, key=lambda t: (KINDS.index(t["kind"]), t["id"]))


def _cleaner(arms: list[str]):
    terms = anonymise.pass_terms(arms)
    names = [re.escape(a) for a in sorted(arms, key=len, reverse=True) if a]
    own = re.compile(rf"(?<![A-Za-z0-9])(?:{'|'.join(names)})(?![A-Za-z0-9])", re.I) if names else None

    def clean(s) -> str:
        s = anonymise.scrub(re.sub(r"\s+", " ", str(s or "")).strip(), terms)
        s = re.sub(r"\bArms? [A-Z]\b", "another arm", s)
        return own.sub("an arm", s) if own else s
    return clean


def _failed_line(failed: list[dict]) -> str:
    if not failed:
        return "Extraction: every step's decisions were extracted."
    by_step: dict[str, int] = {}
    for f in failed:
        by_step[f["step"]] = by_step.get(f["step"], 0) + 1
    steps = ", ".join(f"step {s}" + (f" ×{n}" if n > 1 else "") for s, n in sorted(by_step.items()))
    n = len(failed)
    return (f"Extraction: **{n} extraction{' failed' if n == 1 else 's failed'}** ({steps}); "
            f"{'its' if n == 1 else 'their'} decisions are not on this sheet. Re-run decisions-extract with --retry-failed, then decisions-align and decisions-sheet.")


def render_sheet(topics: list[dict], arms: list[str], failed: list[dict] = ()) -> str:
    """The owner's blind view: numbered routes with their text, reasoning, outcome and proposed rating; blank `rating:`
    and `reason:` lines. No labels; judge-written text is flattened to one line and scrubbed of every arm name given
    (and every configured method name) as a second guard."""
    clean = _cleaner(list(arms))
    out = ["# Decision review: rating sheet", "",
           "Rate every route, one-offs first. After `rating:` write one of good, acceptable, poor or out_of_scope "
           "(not a real choice, or does not matter); after `reason:` write one line - it becomes cited evidence. "
           "Leave the `##` and `### Route` headings as they are.", "",
           "Routes are anonymous: which arm took which route is hidden. \"not considered\" is a route too: if the "
           "topic mattered, missing it is a weakness; if it did not, not considering it can be acceptable and "
           "deciding it may have been over-engineering. `proposed:` is the aligning judge's suggestion; your rating "
           "decides.", "", _failed_line(list(failed)), ""]
    groups = _ordered(topics)
    for k, title in zip(KINDS, ("One-offs", "Divergent", "Unanimous")):
        ts = [t for t in groups if t["kind"] == k]
        out += [f"# {title} ({len(ts)})", ""]
        for t in ts:
            out += [f"## {t['id']}", "", f"**Question:** {clean(t['question'])}  ", f"**Kind:** {k}", ""]
            for r in t["routes"]:
                prop = f"{r['proposed']} - {clean(r['proposed_why'])}" if r["proposed"] else "(none)"
                out += [f"### Route {r['route_no']}", "",
                        f"- Route: {clean(r['route'])}",
                        f"- Reasoning given: {clean(r['reason_given']) or '(none)'}",
                        f"- Outcome: {clean(r['outcome']) or '(none)'}",
                        f"- proposed: {prop}", "",
                        "rating:", "reason:", ""]
    return "\n".join(out)


def _failures(pass_: str) -> list[dict]:
    out = []
    for lab, nn, _ in _extract_items(pass_):
        r = _record(extracted_path(pass_, lab, nn))
        if isinstance(r, dict):
            out.append({"label": lab, "step": nn, "status": r.get("status", "?"), "why": r.get("why", "")})
    return out


def sheet(pass_: str) -> Path:
    """rating-sheet.md + rating-sheet.json from topics.json. Refuses to overwrite a sheet the owner has started."""
    tf, md = _dir(pass_) / "topics.json", _dir(pass_) / "rating-sheet.md"
    if not tf.exists():
        raise inputs.InputError(f"{tf} is missing: run the decisions-align stage first")
    if md.exists() and re.search(r"^[ \t]*(?:[-*][ \t]+)?(?:rating|reason)[ \t]*:[ \t]*\S", md.read_text(), re.I | re.M):
        raise inputs.InputError(f"{md} already holds ratings: move it aside to write a fresh sheet")
    topics, failed = json.loads(tf.read_text())["topics"], _failures(pass_)
    _write(md, render_sheet(topics, _arms(pass_), failed))
    _write(md.with_suffix(".json"), values.dump({"topics": _ordered(topics), "failed": failed}))
    return md


_H2 = re.compile(r"^##\s+(\S.*?)\s*$")
_H3 = re.compile(r"^###\s+Route\s+(\d+)\s*$", re.I)
_FIELD = re.compile(r"^[ \t]*(?:[-*][ \t]+)?(rating|reason)[ \t]*:(.*)$", re.I)


def _rating(raw: str) -> str:
    return re.sub(r"[\s-]+", "_", raw.strip().strip("`*").strip().lower())


def parse_sheet(md: str) -> dict[str, list[dict]]:
    """{topic id: [{"route_no", "rating", "reason"}]} from a filled sheet. Raises SheetError listing every problem
    as `<topic id> route <n>: ...`."""
    got: dict[str, dict[int, dict]] = {}
    problems: list[str] = []
    topic, route = None, None
    for line in md.splitlines():
        if m := _H2.match(line):
            topic, route = m[1], None
            if topic in got:
                problems.append(f"{topic}: the topic appears twice")
            got.setdefault(topic, {})
        elif m := _H3.match(line):
            if topic is None:
                problems.append(f"Route {m[1]}: outside a topic")
                continue
            n = int(m[1])
            if n in got[topic]:
                problems.append(f"{topic} route {n}: rated twice (its heading appears twice)")
                route = {"route_no": n}                         # a throwaway: the first one stands
            else:
                route = got[topic][n] = {"route_no": n}
        elif (m := _FIELD.match(line)) and topic is not None:
            field = m[1].lower()
            if route is None:
                problems.append(f"{topic}: a {field} line outside a route")
            elif field in route:
                problems.append(f"{topic} route {route['route_no']}: two {field} lines")
            else:
                route[field] = m[2].strip()
    out: dict[str, list[dict]] = {}
    for tid, routes in got.items():
        if not routes:
            problems.append(f"{tid}: no routes")
        for n, r in sorted(routes.items()):
            raw = r.get("rating") or ""
            if not raw:
                problems.append(f"{tid} route {n}: no rating")
            elif _rating(raw) not in RATINGS:
                problems.append(f"{tid} route {n}: rating {raw!r} is not one of {', '.join(RATINGS)}")
            if not r.get("reason"):
                problems.append(f"{tid} route {n}: no reason")
            out.setdefault(tid, []).append({"route_no": n, "rating": _rating(raw), "reason": r.get("reason", "")})
    if problems:
        raise SheetError("the rating sheet has problems:\n" + "\n".join(f"- {p}" for p in problems))
    return out


def import_ratings(pass_: str) -> Path:
    """Validates the filled sheet against rating-sheet.json and writes ratings.json under real arm names."""
    d = _dir(pass_)
    md, js = d / "rating-sheet.md", d / "rating-sheet.json"
    for f in (md, js):
        if not f.exists():
            raise inputs.InputError(f"{f} is missing: run the decisions-sheet stage first")
    parsed = parse_sheet(md.read_text(encoding="utf-8"))
    structure = json.loads(js.read_text())["topics"]
    problems = []
    for t in structure:
        rated = {r["route_no"]: r for r in parsed.get(t["id"], [])}
        if t["id"] not in parsed:
            problems.append(f"{t['id']}: missing from the sheet")
            continue
        nos = {r["route_no"] for r in t["routes"]}
        problems += [f"{t['id']} route {n}: no rating" for n in sorted(nos - set(rated))]
        problems += [f"{t['id']} route {n}: not on the sheet" for n in sorted(set(rated) - nos)]
    problems += [f"{tid}: not on the sheet" for tid in sorted(set(parsed) - {t["id"] for t in structure})]
    if problems:
        raise SheetError("the rating sheet has problems:\n" + "\n".join(f"- {p}" for p in problems))
    key = judge.anon_key(pass_)
    out = []
    for t in sorted(structure, key=lambda t: t["id"]):
        rated = {r["route_no"]: r for r in parsed[t["id"]]}
        routes = []
        for r in t["routes"]:
            unknown = [l for l in r["labels"] if l not in key]
            if unknown:
                raise inputs.InputError(f"{t['id']} route {r['route_no']}: {unknown} not in anon-key.json")
            o = rated[r["route_no"]]
            routes.append({"route": r["route"], "arms": sorted(key[l] for l in r["labels"]), "rating": o["rating"],
                           "reason": o["reason"]})
        out.append({"id": t["id"], "routes": routes})
    f = d / "ratings.json"
    _write(f, values.dump({"topics": out}))
    return f


# ---- the estimate --------------------------------------------------------------------------------------------------

def estimate(pass_: str, *, retry_failed: bool = False) -> dict:
    """Model calls the extract and align stages would make now (parse retries not counted): one per unfinished
    label × step with inputs present, plus one alignment when any extraction will run or topics.json is absent."""
    calls, size = 0, 0
    items = _extract_items(pass_)
    for lab, nn, d in items:
        if not _unfinished(extracted_path(pass_, lab, nn), retry_failed):
            continue
        files = _present(d)
        if files:
            calls += 1
            size += sum(judge._size(d / f) for f in files)
    if items and (calls or not (_dir(pass_) / "topics.json").exists()):
        calls += 1
    return {"calls": calls, "input_mb": round(size / 1e6, 3)}
