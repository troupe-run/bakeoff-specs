"""Decision review (spec §8): extract every decision per label × step, align them into topics across labels, render a
blind rating sheet for the owner, import the owner's ratings back under real arm names.

Stages and files (all under `scoring_out/decisions/`):
- `extract` -> `extracted/<label>/<NN>.json`: a list of `{"decision", "options", "reason", "recorded_at"}`, or (never
  silently empty) `{"status": "extract_failed" | "input_missing", "why", "raw"?}`.
- `align` -> `topics.json` = `{"topics": [{"id", "question", "routes": [{"route", "labels", "reason_given", "outcome",
  "proposed", "proposed_why"}]}], "dropped": [{"label", "decisions"}]}`; every label with no route in a topic is then
  added, deterministically, to a `"not considered"` route - unless one of its steps has no extraction (failed, allowed
  with `--allow-failed`, or input missing), or the aligner placed none of its decisions on any route (I6): then to
  an UNRATED `"no evidence"` route, never a rated one (R29). Its
  single input is written to `anon/_decisions/align/extracted.json` (labels only, scrubbed again), so the container
  judge's one-item mount rule holds.
- `sheet` -> `rating-sheet.md` (the owner's blind view: topics `T1`, `T2`, ... and numbered routes; no labels, no arm
  names, no aligner ids) and `.import/rating-sheet.json` (the import map: the same structure with ids and labels; no
  arm names).
- `import_ratings` -> `ratings.json` = `{"topics": [{"id", "kind", "routes": [{"route", "arms", "rating", "reason", "outcome"}]}]}` (the
  Task 11 format). Only this stage reads `anon-key.json`.

Labels are the `Arm X` directories anonymise wrote; no stage before import knows which arm is which."""
from __future__ import annotations
import copy, json, os, re
from pathlib import Path
from runner import paths
from runner.scoring import anonymise, collect, inputs, judge, leakcheck, values

# owner, 2026-10-09: 1-5 with anchors, half steps allowed ("can we do 3.5?"); n/a is not scored
RATINGS = ("1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5", "n/a")
NA = "n/a"
_NA_FORMS = ("n/a", "na", "-1", "n.a.", "n.a")     # "-1" was the owner's own suggestion for out of scope
ANCHORS = (("5", "what you'd want; nothing better was available"),
           ("4", "sound, with a minor cost or a missed nicety"),
           ("3", "works, but with a real cost or risk you'd want fixed"),
           ("2", "a problem: wrong for some realistic case"),
           ("1", "wrong or harmful: loses data, misleads, or breaks a stated preference"),
           ("n/a", "not a real choice, or it does not matter"))


def _anchor_text() -> str:
    return "; ".join(f"{k} = {v}" for k, v in ANCHORS)
NOT_CONSIDERED = "not considered"
NO_EVIDENCE = "no evidence"                     # unrated: a label whose extraction failed or had no input (R29)
_RESERVED = (NOT_CONSIDERED, NO_EVIDENCE)
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


def fill_not_considered(topic: dict, labels: list[str], no_evidence=()) -> dict:
    """A copy of `topic` in which every label without a route sits on a `"not considered"` route, carrying the
    aligner's `not_considered` proposal when it gave one - or, for a label in `no_evidence` (a step of it could not be
    extracted), on an unrated `"no evidence"` route, last."""
    t = copy.deepcopy(topic)
    nc_note = t.pop("not_considered", None) or {}
    routes = [r for r in t["routes"] if r["route"] not in _RESERVED]
    old = {n: [l for r in t["routes"] if r["route"] == n for l in r["labels"]] for n in _RESERVED}
    taken = {l for r in routes for l in r["labels"]}
    free = {*old[NOT_CONSIDERED], *old[NO_EVIDENCE], *(l for l in labels if l not in taken)}
    ne = sorted(l for l in free if l in no_evidence or l in old[NO_EVIDENCE])
    nc = sorted(free - set(ne))
    if nc:
        r = {"route": NOT_CONSIDERED, "labels": nc, "reason_given": "", "outcome": ""}
        if nc_note.get("proposed"):
            r |= {"proposed": nc_note["proposed"], "proposed_why": nc_note.get("why", "")}
        routes.append(r)
    if ne:
        routes.append({"route": NO_EVIDENCE, "labels": ne, "reason_given": "", "outcome": "", "unrated": True})
    t["routes"] = routes
    return t


def kind(topic: dict, n_labels: int) -> str:
    """one-off: exactly one label (or arm) took a route other than "not considered" / "no evidence"; unanimous: one
    route holds every label that has evidence; else divergent. Reads `labels` (topics, sheet) or `arms` (ratings)."""
    real = [r for r in topic["routes"] if r["route"] not in _RESERVED]
    no_ev = {m for r in topic["routes"] if r["route"] == NO_EVIDENCE for m in _members(r)}
    if sum(len(_members(r)) for r in real) == 1:
        return "one-off"
    if any(len(set(_members(r))) == n_labels - len(no_ev) for r in real):
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
        routes, held, names = t.get("routes"), set(), set()
        if not isinstance(routes, list) or not routes:
            raise judge.BadReply(f"topic {tid}: needs at least one route")
        rs = []
        for k, r in enumerate(routes, 1):
            where = f"topic {tid} route {k}"
            if not isinstance(r, dict):
                raise judge.BadReply(f"{where} is not an object")
            name = _str(r, "route", where, nonempty=True)
            key = re.sub(r"\s+", " ", name).strip().lower()
            if key in _RESERVED:
                raise judge.BadReply(f"{where}: do not list a \"{key}\" route; it is added afterwards")
            if key in names:
                raise judge.BadReply(f"{where}: the route {name.strip()!r} appears twice in this topic")
            names.add(key)
            ls = r.get("labels")
            if not isinstance(ls, list) or not ls or any(l not in labels for l in ls):
                raise judge.BadReply(f"{where}: \"labels\" must be a non-empty list drawn from {labels}")
            if held & set(ls):
                raise judge.BadReply(f"{where}: {sorted(held & set(ls))} already hold another route in this topic; "
                                     "describe a change of course as one route")
            held |= set(ls)
            if (proposed := _rating(r.get("proposed"))) not in RATINGS:
                raise judge.BadReply(f"{where}: \"proposed\" must be one of {', '.join(RATINGS)}")
            rs.append({"route": name, "labels": sorted(ls), "reason_given": _str(r, "reason_given", where),
                       "outcome": _str(r, "outcome", where), "proposed": proposed,
                       "proposed_why": _str(r, "proposed_why", where)})
        topic = {"id": tid, "question": _str(t, "question", f"topic {tid}", nonempty=True), "routes": rs}
        texts = [topic["question"]] + [r[k] for r in rs for k in ("route", "reason_given", "outcome", "proposed_why")]
        if set(labels) - held:
            nc = t.get("not_considered")
            if not isinstance(nc, dict) or _rating(nc.get("proposed")) not in RATINGS:
                raise judge.BadReply(f"topic {tid}: needs \"not_considered\": {{\"proposed\": one of "
                                     f"{', '.join(RATINGS)}, \"why\": str}} (some labels never raised it)")
            topic["not_considered"] = {"proposed": _rating(nc["proposed"]), "why": _str(nc, "why", f"topic {tid} not_considered")}
            texts.append(topic["not_considered"]["why"])
        if refs := [c for x in texts for c in leakcheck.label_refs(x, labels)]:
            raise judge.BadReply(f"topic {tid}: the text names an arm ({'; '.join(refs[:3])}): never name an arm or "
                                 "its letter in any text; say \"one arm\", \"two arms\" or \"the other arms\"")
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


def _key_record(pass_: str) -> Path:
    """The digest of the anon-key.json the extractions were made under (R37): labels are per key."""
    return _dir(pass_) / "extracted" / "key.sha256"


def _recorded(f: Path) -> str | None:
    try:
        return f.read_text().strip() or None
    except OSError:
        return None


def extract(pass_: str, j: judge.Judge, *, retry_failed: bool = False) -> Path:
    """One call per unfinished label × step (resumable), each list written as it lands. Records the key's digest on
    its first run and refuses to add to extractions made under another key (R37)."""
    rec = _key_record(pass_)
    if (old := _recorded(rec)) is not None:
        judge.check_key(pass_, old, f"{_dir(pass_) / 'extracted'}")
    else:
        _write(rec, judge.key_digest(pass_) + "\n")
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
            "The owner rates these routes blind: never name an arm or its label in ANY text field - not \"Arm C\", "
            "not a bare letter (\"C fixed it\", \"A pins it\", \"(D also copies)\") - and never say which arm did what "
            "inside a route. Where arms on one route differ in detail, say \"one arm also ...\" or \"two arms ...\".\n\n"
            "For each route give \"reason_given\" (the reasoning the arms recorded), \"outcome\" (what became of it at "
            "later steps: kept, reworked at step N, or unknown) and a proposed rating with a one-line why, on this "
            f"scale: {_anchor_text()}. For each topic that some "
            "labels never raised, also propose a rating for not considering it: if the topic mattered, missing it is "
            "a weakness; if it did not, not considering it can be acceptable.\n\n"
            f"Recorded preferences of the owner:\n{notes}\n\n"
            "Reply with exactly one JSON object and nothing else:\n"
            '{"topics": [{"id": "<lowercase-slug>", "question": "<the question decided>", '
            '"not_considered": {"proposed": "<rating>", "why": "<one line>"}, '
            '"routes": [{"route": "<the answer>", "labels": ["Arm A"], "reason_given": "...", "outcome": "...", '
            '"proposed": "<rating>", "proposed_why": "<one line>"}]}]}')


def align(pass_: str, j: judge.Judge, *, allow_failed: bool = False) -> Path:
    """One call over every extracted list -> topics.json, each topic filled with its "not considered" route and, for
    labels with a step that could not be extracted, an unrated "no evidence" route. Refuses while an extraction has
    not run, and while one failed unless `allow_failed`. Labels with decisions that the aligner put on no route at
    all are recorded under `dropped`."""
    judge.check_key(pass_, _recorded(_key_record(pass_)), f"{_dir(pass_) / 'extracted'}")      # R37
    labs, collected, unrun, failed, no_ev = labels(pass_), {}, [], [], set()
    for lab, nn, _ in _extract_items(pass_):
        r = _record(extracted_path(pass_, lab, nn))
        if r is None:
            unrun.append(f"{lab}/{nn}")
        elif isinstance(r, list):
            collected.setdefault(lab, {})[nn] = r
        else:
            no_ev.add(lab)
            if r.get("status") != "input_missing":
                failed.append(f"{lab}/{nn}")
    if unrun:
        raise inputs.InputError(f"no extraction yet for {', '.join(unrun)}: run the decisions-extract stage first")
    if failed and not allow_failed:
        raise inputs.InputError(f"extraction failed for {', '.join(failed)}: re-run decisions-extract --retry-failed, "
                                "or pass --allow-failed to align without them (they become unrated \"no evidence\")")
    item = paths.scoring_out(pass_) / "anon" / ALIGN_ITEM
    terms = anonymise.pass_terms(_arms(pass_))
    _write(item / "extracted.json", values.dump(_scrub_obj(collected, terms)))
    got, why, raw = _ask(j, align_prompt(labs), item, ["extracted.json"], lambda t: parse_topics(t, labs),
                         "one JSON object")
    failed_f = _dir(pass_) / "align-failed.json"
    if got is None:
        _write(failed_f, values.dump({"status": "align_failed", "why": why, "raw": raw}))
        raise inputs.InputError(f"the alignment failed twice ({why}); recorded in {failed_f}: re-run decisions-align")
    failed_f.unlink(missing_ok=True)
    placed = {l for t in got for r in t["routes"] for l in r["labels"]}
    dropped = [{"label": lab, "decisions": n} for lab in sorted(collected)
               if lab not in placed and (n := sum(len(v) for v in collected[lab].values()))]
    # I6: a label whose decisions the aligner placed on no route at all is not "not considered" (it may well have
    # decided the topic): it goes on the unrated "no evidence" route, like a failed extraction (R29).
    no_ev |= {d["label"] for d in dropped}
    out = _dir(pass_) / "topics.json"
    _write(out, values.dump({"topics": [fill_not_considered(t, labs, no_ev) for t in sorted(got, key=lambda t: t["id"])],
                             "dropped": dropped}))
    return out


# ---- the rating sheet ----------------------------------------------------------------------------------------------

def _ordered(topics: list[dict]) -> list[dict]:
    """The sheet's structure: topics one-offs, divergent, unanimous (then by id); routes by text, "not considered"
    last, numbered from 1."""
    n = len({l for t in topics for r in t["routes"] for l in _members(r)})
    out = []
    for t in topics:
        rated = sorted((r for r in t["routes"] if r["route"] != NO_EVIDENCE),
                       key=lambda r: (r["route"] == NOT_CONSIDERED, r["route"]))
        out.append({"id": t["id"], "question": t.get("question", ""), "kind": kind(t, n),
                    "routes": [{"route_no": i, "route": r["route"], "labels": sorted(_members(r)),
                                "reason_given": r.get("reason_given", ""), "outcome": r.get("outcome", ""),
                                "proposed": r.get("proposed", ""), "proposed_why": r.get("proposed_why", "")}
                               for i, r in enumerate(rated, 1)],
                    "no_evidence": sorted(m for r in t["routes"] if r["route"] == NO_EVIDENCE for m in _members(r))})
    out.sort(key=lambda t: (KINDS.index(t["kind"]), t["id"]))
    for i, t in enumerate(out, 1):
        t["sheet_id"] = f"T{i}"                        # the sheet never shows the aligner's id (it may name an arm)
    return out


def _cleaner(arms: list[str], flatten: bool = True):
    """Judge-written text for the sheet: scrubbed of every arm name and label, flattened to one line (or, with
    `flatten=False`, every space and line break kept: a file's content)."""
    terms = anonymise.pass_terms(arms)
    # `control` is an ordinary English word (anonymise's rule): its repo name is scrubbed by pass_terms, the word is not
    names = [re.escape(a) for a in sorted(arms, key=len, reverse=True) if a and a != "control"]
    own = re.compile(rf"(?<![A-Za-z0-9])(?:{'|'.join(names)})(?![A-Za-z0-9])", re.I) if names else None

    def clean(s) -> str:
        s = str(s or "")
        s = anonymise.scrub(re.sub(r"\s+", " ", s).strip() if flatten else s, terms)
        s = re.sub(r"\bArms? [A-Z]\b", "another arm", s)
        return own.sub("an arm", s) if own else s
    return clean


def _steps_text(rs: list[dict]) -> str:
    by_step: dict[str, int] = {}
    for f in rs:
        by_step[f["step"]] = by_step.get(f["step"], 0) + 1
    return ", ".join(f"step {s}" + (f" ×{n}" if n > 1 else "") for s, n in sorted(by_step.items()))


def _failed_lines(failed: list[dict], dropped: list[dict]) -> list[str]:
    bad = [f for f in failed if f["status"] != "input_missing"]
    gone = [f for f in failed if f["status"] == "input_missing"]
    out = []
    if bad:
        n = len(bad)
        out += [f"Extraction: {n} extraction{' failed' if n == 1 else 's failed'} ({_steps_text(bad)}); "
                f"{'its' if n == 1 else 'their'} decisions are not on this sheet. Re-run decisions-extract with "
                "--retry-failed, then decisions-align and decisions-sheet.", ""]
    if gone:
        n = len(gone)
        out += [f"Inputs: {n} step{' had' if n == 1 else 's had'} no evidence ({_steps_text(gone)}): nothing could be "
                "extracted there.", ""]
    if bad or gone:
        out += ["An arm with such a step is never shown as \"not considered\": where it took no route, it is listed "
                "under an unrated \"No evidence\" heading, with no rating to give.", ""]
    else:
        out += ["Extraction: every step's decisions were extracted.", ""]
    if dropped:
        k, d = len(dropped), sum(x["decisions"] for x in dropped)
        out += [f"Alignment: the aligner placed no decision of {k} arm{'' if k == 1 else 's'} on any topic: "
                f"{d} decision{'' if d == 1 else 's'} dropped.", ""]
    return out


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")          # CommonMark: indented 4+ is code, not a fence


def _open_fence(md: str) -> bool:
    """A fence opened and never closed (e.g. by the owner's own edit): everything after it would be hidden."""
    return _unfenced(md, report_open=True) == []


def _unfenced(md: str, report_open: bool = False) -> list[str]:
    """The sheet's lines with every line inside a fenced block blanked: a file shown in a topic's context (which may
    hold "rating:" or "## x") is never read as the owner's input. With `report_open`, [] when a fence is left open."""
    out: list[str] = []
    fence = None
    for line in md.splitlines():
        m = _FENCE.match(line)
        if fence is None and m:
            fence = m[1][0] * len(m[1])
            out.append("")
        elif fence is not None:
            if m and m[1].startswith(fence):
                fence = None
            out.append("")
        else:
            out.append(line)
    if report_open and fence is not None:
        return []
    return out


def _fenced(text: str, indent: str = "") -> list[str]:
    run = max((len(m) for m in re.findall(r"~+", text)), default=0)
    fence = indent + "~" * max(3, run + 1)
    return [fence, *(indent + line for line in text.rstrip("\n").splitlines()), fence]


def _result_lines(n: str, text: str, clean, block) -> list[str]:
    """One route's result: on one line, or - when it holds line breaks (a file's lines) - its first line, then the
    rest exactly as written in a fenced block under it (owner, 2026-10-09: "I don't understand the `prompt: |2`
    thing" - the flattened ` / ` form hid the file's indentation)."""
    head, sep, rest = text.strip("\n").partition("\n")
    if not sep:
        return [f"- Route {n}: {clean(head)}"]
    return [f"- Route {n}: {clean(head)}", "", *_fenced(block(rest), "  "), ""]


def render_context(ctx: dict | None, clean, block=lambda x: x) -> list[str]:
    """A topic's context block: what is at stake, each example with every route's result, the trade-off."""
    if not ctx:
        return ["_No behaviour context for this topic._", ""]
    c = ctx["context"]
    out = [f"**What's at stake:** {clean(c['stakes'])}", ""]
    if c["examples"]:
        out += ["**What each route does** (run against every arm's final code):", ""]
        for i, e in enumerate(c["examples"], 1):
            how = "observed" if e["observed"] else "inferred, not run"
            out += [f"**Example {i}:** {clean(e['input'])} _({how})_", ""]
            if e["before"].strip():
                out += ["Starting file:", "", *_fenced(block(e["before"])), ""]
            for n, r in sorted(e["results"].items(), key=lambda x: int(x[0])):
                out += _result_lines(n, r, clean, block)
            out.append("")
    if c.get("in_practice", "").strip():
        out += [f"**In practice:** {clean(c['in_practice'])}", ""]
    out += [f"**Trade-off:** {clean(c['tradeoff'])}", ""]
    return out


def render_sheet(topics: list[dict], arms: list[str], failed: list[dict] = (), dropped: list[dict] = (),
                 contexts: dict[str, dict] | None = None) -> str:
    """The owner's blind view: numbered routes with their text, reasoning, outcome and proposed rating; blank `rating:`
    and `reason:` lines. No labels; judge-written text is flattened to one line and scrubbed of every arm name given
    (and every configured method name) as a second guard."""
    clean, block = _cleaner(list(arms)), _cleaner(list(arms), flatten=False)
    out = ["# Decision review: rating sheet", "",
           "Rate every route, one-offs first. Read the whole topic - every route - before rating any of it. After "
           "`rating:` write 1-5 (half steps such as 3.5 allowed) or n/a; after `reason:` you may write one line (optional) - it becomes cited "
           "evidence. Leave the `##` and `### Route` headings as they are.", "",
           "| Rating | Meaning |", "|---|---|", *(f"| {k} | {v} |" for k, v in ANCHORS), "",
           "Routes are anonymous: which arm took which route is hidden. \"not considered\" is a route too: if the "
           "topic mattered, missing it is a weakness; if it did not, not considering it can be acceptable and "
           "deciding it may have been over-engineering. `proposed:` is the aligning judge's suggestion; your rating "
           "decides.", "", *_failed_lines(list(failed), list(dropped))]
    groups = _ordered(topics)
    for k, title in zip(KINDS, ("One-offs", "Divergent", "Unanimous")):
        ts = [t for t in groups if t["kind"] == k]
        out += [f"# {title} ({len(ts)})", ""]
        for t in ts:
            out += [f"## {t['sheet_id']}", "", f"**Question:** {clean(t['question'])}  ", f"**Kind:** {k}", ""]
            if contexts is not None:
                out += render_context(contexts.get(t["id"]), clean, block)
            for r in t["routes"]:
                prop = f"{r['proposed']} - {clean(r['proposed_why'])}" if r["proposed"] else "(none)"
                out += [f"### Route {r['route_no']}", "",
                        f"- Route: {clean(r['route'])}",
                        f"- Reasoning given: {clean(r['reason_given']) or '(none)'}",
                        f"- Outcome: {clean(r['outcome']) or '(none)'}",
                        f"- proposed: {prop}", "",
                        "rating:", "reason:", ""]
            if t["no_evidence"]:
                n = len(t["no_evidence"])
                out += ["### No evidence (unrated)", "",
                        f"- {n} arm{'' if n == 1 else 's'} took no route here and had a step whose decisions could not "
                        "be extracted: whether they considered it is unknown. Nothing to rate.", ""]
    return "\n".join(out)


def _failures(pass_: str) -> list[dict]:
    out = []
    for lab, nn, _ in _extract_items(pass_):
        r = _record(extracted_path(pass_, lab, nn))
        if isinstance(r, dict):
            out.append({"label": lab, "step": nn, "status": r.get("status", "?"), "why": r.get("why", "")})
    return out


def _structure(topics: list[dict]) -> list:
    return [[t["id"], t["sheet_id"], [[r["route_no"], r["route"], r["labels"]] for r in t["routes"]]] for t in topics]


def sheet(pass_: str) -> Path:
    """rating-sheet.md + rating-sheet.json from topics.json. A sheet the owner has started is rewritten (e.g. with new
    context) only when its topics and routes are unchanged, and then every rating and reason is carried across;
    otherwise it is refused."""
    tf, md = _dir(pass_) / "topics.json", _dir(pass_) / "rating-sheet.md"
    if not tf.exists():
        raise inputs.InputError(f"{tf} is missing: run the decisions-align stage first")
    started = md.exists() and (_open_fence(md.read_text()) or bool(re.search(
        r"^[ \t]*(?:[-*][ \t]+)?(?:rating|reason)[ \t]*:[ \t]*\S", "\n".join(_unfenced(md.read_text())), re.I | re.M)))
    aligned = json.loads(tf.read_text())
    if started:
        old_map = _record(_import_map(pass_))
        same = isinstance(old_map, dict) and _structure(old_map.get("topics", [])) == _structure(_ordered(aligned["topics"]))
        if _open_fence(md.read_text()) or not same:
            raise inputs.InputError(f"{md} already holds ratings: move it aside to write a fresh sheet")
    failed = _failures(pass_)
    topics, dropped = aligned["topics"], aligned.get("dropped", [])
    from runner.scoring import context                     # lazy: context imports this module
    text = render_sheet(topics, _arms(pass_), failed, dropped, context.load(pass_, _ordered(topics)))
    if leaks := leakcheck.check_text(text, _arms(pass_), labels(pass_)):
        raise inputs.InputError(f"the rating sheet would unblind the owner ({len(leaks)} hit(s)); nothing written:\n"
                                + "\n".join(f"- {x}" for x in leaks[:40]))
    if started:
        from runner.scoring import rate                     # lazy: rate imports this module
        text = rate.carry(md.read_text(encoding="utf-8"), text)
    _write(md, text)
    _write(_import_map(pass_), values.dump({"topics": _ordered(topics), "failed": failed, "dropped": dropped,
                                            "key_sha256": judge.key_digest(pass_)}))      # R37
    return md


def _import_map(pass_: str) -> Path:
    """Sheet topic and route numbers -> aligner ids and labels: kept out of the owner's way, never shown on the sheet."""
    return _dir(pass_) / ".import" / "rating-sheet.json"


_H2 = re.compile(r"^##\s+(\S.*?)\s*$")
_H3 = re.compile(r"^###\s+Route\s+(\d+)\s*$", re.I)
_FIELD = re.compile(r"^[ \t]*(?:[-*][ \t]+)?(rating|reason)[ \t]*:(.*)$", re.I)


def _rating(raw) -> str:
    """"4", 4, " 4 ", "**4**" -> "4"; "N/A", "na", "-1" -> "n/a"; anything else is returned (lower-cased) to be
    refused by the caller."""
    s = str(raw if raw is not None else "").strip().strip("`*").strip().lower()
    if re.fullmatch(r"[1-5](?:\.0|\.5)?", s):
        s = s.removesuffix(".0")                      # "4.0" is "4"; "3.5" stays
    return NA if s in _NA_FORMS else s


def parse_sheet(md: str) -> dict[str, list[dict]]:
    """{topic id: [{"route_no", "rating", "reason"}]} from a filled sheet. Raises SheetError listing every problem
    as `<topic id> route <n>: ...`."""
    got: dict[str, dict[int, dict]] = {}
    problems: list[str] = []
    topic, route = None, None
    for line in _unfenced(md):
        if m := _H2.match(line):
            topic, route = m[1], None
            if topic in got:
                problems.append(f"{topic}: the topic appears twice")
            got.setdefault(topic, {})
        elif line.startswith("###") and not _H3.match(line):
            route = None                                        # e.g. "No evidence (unrated)": nothing to rate
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
            # the reason is optional (owner, 2026-10-09); when given it is cited as evidence
            out.setdefault(tid, []).append({"route_no": n, "rating": _rating(raw), "reason": r.get("reason", "")})
    if problems:
        raise SheetError("the rating sheet has problems:\n" + "\n".join(f"- {p}" for p in problems))
    return out


def import_ratings(pass_: str) -> Path:
    """Validates the filled sheet against rating-sheet.json and writes ratings.json under real arm names."""
    d = _dir(pass_)
    md, js = d / "rating-sheet.md", _import_map(pass_)
    for f in (md, js):
        if not f.exists():
            raise inputs.InputError(f"{f} is missing: run the decisions-sheet stage first")
    mp = json.loads(js.read_text())
    judge.check_key(pass_, mp.get("key_sha256"), f"{md}")        # R37: labels map back only under the same key
    parsed = parse_sheet(md.read_text(encoding="utf-8"))
    structure = mp["topics"]
    problems = []
    for t in structure:
        sid = t["sheet_id"]
        rated = {r["route_no"]: r for r in parsed.get(sid, [])}
        if sid not in parsed:
            problems.append(f"{sid}: missing from the sheet")
            continue
        nos = {r["route_no"] for r in t["routes"]}
        problems += [f"{sid} route {n}: no rating" for n in sorted(nos - set(rated))]
        problems += [f"{sid} route {n}: not on the sheet" for n in sorted(set(rated) - nos)]
    problems += [f"{tid}: not on the sheet" for tid in sorted(set(parsed) - {t["sheet_id"] for t in structure})]
    if problems:
        raise SheetError("the rating sheet has problems:\n" + "\n".join(f"- {p}" for p in problems))
    resliced = _resliced(pass_, structure)
    key = judge.anon_key(pass_)
    out, warnings = [], []
    for t in sorted(structure, key=lambda t: t["id"]):
        rated = {r["route_no"]: r for r in parsed[t["sheet_id"]]}
        routes = []
        for r in t["routes"]:
            unknown = [l for l in r["labels"] if l not in key]
            if unknown:
                raise inputs.InputError(f"{t['sheet_id']} route {r['route_no']}: {unknown} not in anon-key.json")
            o = rated[r["route_no"]]
            base = {"route": r["route"], "rating": o["rating"], "reason": o["reason"],
                    "outcome": r.get("outcome", "")}                          # spec §8.6: shown, not scored
            if t["sheet_id"] not in resliced:
                routes.append({**base, "arms": sorted(key[l] for l in r["labels"])})
                continue
            got, warn = _reslice_routes(t["sheet_id"], r, base, resliced[t["sheet_id"]], key)
            routes += got
            warnings += warn
        out.append({"id": t["id"], "kind": t["kind"], "routes": routes})   # the sheet's kind, never recomputed
    f = d / "ratings.json"
    _write(f, values.dump({"topics": out, **({"warnings": warnings} if warnings else {})}))
    return f


def _rating_text(x: float | None) -> str:
    """A reslice rating as ratings.json writes ratings: "4", "3.5", "4.25"; None (every group n/a) is "n/a"."""
    return NA if x is None else f"{x:.3f}".rstrip("0").rstrip(".")


def _resliced(pass_: str, structure: list[dict]) -> dict[str, dict]:
    """{sheet id: {label: reslice entry}} for every topic of reslice.json, checked against the sheet and against the
    CURRENT group ratings; {} when there is no reslice.json. Refuses while a resliced topic is unclassified or its
    ratings are stale, so a placeholder route rating is never imported in its place unnoticed."""
    from runner.scoring import reslice                    # lazy: reslice imports this module
    spec = reslice.load_spec(pass_)
    if spec is None:
        return {}
    sheet_ids = {t["sheet_id"]: t for t in structure}
    if missing := sorted(set(spec) - set(sheet_ids)):
        raise inputs.InputError(f"reslice.json names topics not on the sheet: {', '.join(missing)}")
    f = reslice.ratings_path(pass_)
    got = _record(f)
    if not isinstance(got, dict):
        raise inputs.InputError(f"{f} is missing: run the decisions-reslice stage first")
    problems = []
    for sid in sorted(spec, key=lambda x: int(x[1:])):
        entries = got.get(sid)
        if not isinstance(entries, dict):
            problems.append(f"{sid}: not classified (run decisions-reslice)")
            continue
        on_routes = {l for r in sheet_ids[sid]["routes"] for l in r["labels"]}
        if stray := sorted(set(entries) - on_routes):
            problems.append(f"{sid}: classified for labels not on its routes {stray} (run decisions-reslice)")
        for lab, e in entries.items():
            if reslice.rating(spec[sid], e.get("groups", {})) != e.get("rating"):
                problems.append(f"{sid}: its ratings differ from reslice.json's (run decisions-reslice; no new "
                                "model calls)")
                break
    if problems:
        raise inputs.InputError("the reslice cannot be imported:\n" + "\n".join(f"- {p}" for p in problems))
    return {sid: got[sid] for sid in spec}


def _reslice_routes(sid: str, r: dict, base: dict, entries: dict[str, dict], key: dict) -> tuple[list[dict], list[dict]]:
    """One sheet route of a resliced topic: its arms rated per arm from their behaviour groups, arms with the same
    groups together; an arm classified "none" (or not at all) keeps the route's rating, with a warning."""
    by: dict[tuple, dict] = {}
    warnings = []
    for lab in r["labels"]:
        e = entries.get(lab)
        if e is None or any(g == "none" for g in e["groups"].values()):
            why = ("not classified" if e is None else "none of these: "
                   + "; ".join(f"{q}: {w}" for q, w in sorted(e.get("none_of_these", {}).items())))
            warnings.append({"topic": sid, "route_no": r["route_no"], "arm": key[lab],
                             "why": f"kept the route's rating ({why})"})
            k = ("route",)
            by.setdefault(k, {**base, "arms": [], "warning": "kept the route's rating: no behaviour group fitted"})
        else:
            k = ("groups", tuple(sorted(e["groups"].items())))
            reason = "; ".join(f"{q}: behaviour group {g}" for q, g in sorted(e["groups"].items()))
            by.setdefault(k, {**base, "rating": _rating_text(e["rating"]), "reason": reason, "arms": [],
                              "groups": dict(sorted(e["groups"].items())), "route_rating": base["rating"]})
        by[k]["arms"].append(key[lab])
    out = []
    for x in by.values():
        x["arms"] = sorted(x["arms"])
        out.append(x)
    return out, warnings


# ---- the estimate --------------------------------------------------------------------------------------------------

def estimate(pass_: str, *, retry_failed: bool = False) -> dict:
    """Model calls the extract and align stages would make now (parse retries not counted): one per unfinished
    label × step with inputs present, plus ONE alignment call whenever there is anything to align - each run of
    decisions-align, a re-run included, makes one call."""
    extract_calls, size = 0, 0
    items = _extract_items(pass_)
    for lab, nn, d in items:
        if not _unfinished(extracted_path(pass_, lab, nn), retry_failed):
            continue
        files = _present(d)
        if files:
            extract_calls += 1
            size += sum(judge._size(d / f) for f in files)
    align_calls = 1 if items else 0
    return {"calls": extract_calls + align_calls, "extract_calls": extract_calls, "align_calls": align_calls,
            "input_mb": round(size / 1e6, 3)}
