"""Decision reslice (owner, 2026-10-10): on some topics arms on the same ROUTE behaved differently, and the owner rated
BEHAVIOUR GROUPS instead of routes (`decisions/reslice.json`). The sheet keeps placeholder route ratings; this stage
finds which group each arm's behaviour falls in, so decisions-import can rate those topics PER ARM.

Per topic in reslice.json (sequential, resumable; `decisions/reslice/<topic id>.json`):
1. **plan** - the topic's decision-context plan, reused unchanged (`plan_for`): the `plan` an `ok` context record
   holds, or - for a record written before plans were kept - recovered from the context's plan-call replies.
2. **run** - that plan against EVERY label's final code (`context.ArmRunner`), each label's results scrubbed exactly
   as decisions-context scrubs them. Identical results are merged into numbered outcomes, so no label reaches a judge.
3. **classify** - one judge call: each outcome into exactly one of each question's groups (by the owner's group
   descriptions; never the ratings), or "none" with a reason.

Then `reslice-ratings.json` = {sheet id: {label: {"groups": {question: group | "none"}, "rating": float | null}}} (a
label with a "none" also carries `"none_of_these": {question: reason}`), the rating being the mean of the chosen
groups' ratings without the n/a (null) ones (null when every one is null, or when any question is "none"), and the
BLIND `reslice-summary.md`: counts per group, per question and per route number, never a label or an arm.

Like decisions-context, nothing here reads `anon-key.json` except `ArmRunner`."""
from __future__ import annotations
import json, re
from pathlib import Path
from runner import paths
from runner.scoring import context as cx, decisions as dz, inputs, judge, leakcheck, values

ITEM_PREFIX = "_decisions/reslice-"
NONE = "none"
_TOPIC = re.compile(r"^T\d+$")
_QID = re.compile(r"^[A-Za-z0-9][\w.-]*$")


def spec_path(pass_: str) -> Path:
    return dz._dir(pass_) / "reslice.json"


def out_dir(pass_: str) -> Path:
    return dz._dir(pass_) / "reslice"


def out_path(pass_: str, tid: str) -> Path:
    return out_dir(pass_) / f"{tid}.json"


def ratings_path(pass_: str) -> Path:
    return dz._dir(pass_) / "reslice-ratings.json"


def summary_path(pass_: str) -> Path:
    return dz._dir(pass_) / "reslice-summary.md"


def item_dir(pass_: str, tid: str) -> Path:
    return paths.scoring_out(pass_) / "anon" / f"{ITEM_PREFIX}{tid}"


# ---- reslice.json ----------------------------------------------------------------------------------------------------

def _valid_rating(r) -> bool:
    return r is None or (isinstance(r, (int, float)) and not isinstance(r, bool) and 1 <= r <= 5
                         and float(r * 2).is_integer())


def parse_spec(obj) -> dict:
    """reslice.json, validated strictly: {"T<n>": {"questions": [{"id", "text", "groups": [{"id", "rating",
    "description"}]}]}}; ratings 1-5 in half steps or null (n/a). Raises InputError listing every problem."""
    problems: list[str] = []
    if not isinstance(obj, dict) or not obj:
        raise inputs.InputError("reslice.json must be a non-empty JSON object of sheet topic ids")
    for tid, t in obj.items():
        if not _TOPIC.match(str(tid)):
            problems.append(f"{tid}: not a sheet topic id (T<n>)")
            continue
        if not isinstance(t, dict) or set(t) != {"questions"} or not isinstance(t["questions"], list) \
                or not t["questions"]:
            problems.append(f'{tid}: must be {{"questions": [...]}} with at least one question and no other key')
            continue
        qids: set[str] = set()
        for k, q in enumerate(t["questions"], 1):
            where = f"{tid} question {k}"
            if not isinstance(q, dict) or set(q) != {"id", "text", "groups"}:
                problems.append(f'{where}: must have exactly "id", "text" and "groups"')
                continue
            if not isinstance(q["id"], str) or not _QID.match(q["id"]) or q["id"] in qids:
                problems.append(f"{where}: id {q['id']!r} must be a unique word (letters, digits, _ . -)")
            qids.add(q["id"]) if isinstance(q["id"], str) else None
            where = f"{tid} {q['id']}"
            if not isinstance(q["text"], str) or not q["text"].strip():
                problems.append(f'{where}: "text" must be a non-empty string')
            gs = q["groups"]
            if not isinstance(gs, list) or not gs:
                problems.append(f'{where}: "groups" must list at least one group')
                continue
            gids: set[str] = set()
            for g in gs:
                if not isinstance(g, dict) or set(g) != {"id", "rating", "description"}:
                    problems.append(f'{where}: each group has exactly "id", "rating" and "description"')
                    continue
                gid = g["id"]
                if not isinstance(gid, str) or not _QID.match(gid) or gid in gids or gid.lower() == NONE:
                    problems.append(f"{where}: group id {gid!r} must be a unique word, never {NONE!r}")
                gids.add(gid) if isinstance(gid, str) else None
                if not _valid_rating(g["rating"]):
                    problems.append(f"{where} group {gid}: rating {g['rating']!r} must be 1-5 in half steps or null")
                if not isinstance(g["description"], str) or not g["description"].strip():
                    problems.append(f'{where} group {gid}: "description" must be a non-empty string')
    if problems:
        raise inputs.InputError("reslice.json has problems:\n" + "\n".join(f"- {p}" for p in problems))
    return obj


def load_spec(pass_: str) -> dict | None:
    """The validated reslice.json, or None when there is none."""
    f = spec_path(pass_)
    if not f.exists():
        return None
    try:
        obj = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        raise inputs.InputError(f"{f} is not JSON: {e}") from None
    return parse_spec(obj)


def classify_view(topic_spec: dict) -> dict:
    """What the judge sees of a topic's reslice: questions and group descriptions, never the owner's ratings."""
    return {"questions": [{"id": q["id"], "text": q["text"],
                           "groups": [{"id": g["id"], "description": g["description"]} for g in q["groups"]]}
                          for q in topic_spec["questions"]]}


def rating(topic_spec: dict, groups: dict[str, str]) -> float | None:
    """Mean of the chosen groups' ratings, the n/a (null) ones left out; None when all are null or any is "none"."""
    by = {q["id"]: {g["id"]: g["rating"] for g in q["groups"]} for q in topic_spec["questions"]}
    if any(groups.get(q) in (None, NONE) for q in by):
        return None
    rs = [by[q][groups[q]] for q in by if by[q][groups[q]] is not None]
    return sum(rs) / len(rs) if rs else None


# ---- the plan --------------------------------------------------------------------------------------------------------

def _calls_dir(pass_: str, tid: str) -> Path:
    """Where ContainerJudge kept the context calls for topic `tid` (`judge-calls/<item relative to anon>/`)."""
    return paths.scoring_out(pass_) / "judge-calls" / f"{cx.ITEM_PREFIX}{tid}"


def _ran(plan: dict) -> dict:
    return {k: plan[k] for k in ("files", "commands", "show", "passwd")}


def kept_plan(pass_: str, tid: str) -> dict | None:
    """The plan the context's results.json kept (the last one run for the topic); one written before plans could
    unset the account entry has no "passwd", which then was always true."""
    kept = cx._record(cx.item_dir(pass_, tid) / "results.json")
    kept = kept.get("plan") if isinstance(kept, dict) else None
    return {"passwd": True, **kept} if isinstance(kept, dict) else None


def plan_for(pass_: str, t: dict) -> tuple[dict | None, str]:
    """(plan, where it came from) or (None, why not) for the sheet-ordered topic `t`. Only an `ok`, runnable context
    record written for the topic's current routes counts. A record that keeps its `plan` gives it; an older one is
    recovered from its plan-call replies: those that parse (`context.parse_plan`) to a runnable plan whose `why` is the
    record's `plan_why`. One distinct plan among them is it; several are told apart by the plan the context's
    results.json kept (the last one run), else the topic is reported, never guessed."""
    rec = cx._record(cx.out_path(pass_, t["id"]))
    if not isinstance(rec, dict) or rec.get("status") != "ok":
        return None, "no written decision context"
    if rec.get("routes") != cx.fingerprint(t):
        return None, "its decision context was written for other routes (re-run decisions-context)"
    if not rec.get("runnable", True):
        return None, "its decision context had nothing to run"
    if isinstance(rec.get("plan"), dict):
        return rec["plan"], "context record"
    found: list[dict] = []
    for reply in sorted(_calls_dir(pass_, t["id"]).glob("*/reply.md")):
        try:
            p = cx.parse_plan(reply.read_text(encoding="utf-8"))
        except (judge.BadReply, OSError):
            continue
        if p["runnable"] and p["why"] == rec.get("plan_why") and p not in found:
            found.append(p)
    if len(found) == 1:
        return found[0], "plan-call reply"
    if not found:
        return None, "no plan-call reply matches its context (plan not kept, not recoverable)"
    kept = kept_plan(pass_, t["id"])
    match = [p for p in found if kept is not None and _ran(p) == kept]
    if len(match) == 1:
        return match[0], "plan-call reply matching the context's results"
    return None, f"{len(found)} different plan-call replies match its context and none is told apart"


# ---- classify --------------------------------------------------------------------------------------------------------

def classify_prompt() -> str:
    return (
        "You are classifying behaviour in a blind comparison of several implementations of the same CLI. The same "
        "example commands were run against each implementation's final code; implementations that produced identical "
        "results were merged into one numbered outcome.\n\n"
        "Inputs (read-only; Read, Glob, Grep): /judge/questions.json (one or more questions, each with behaviour "
        "groups the owner described) and /judge/results.json (\"plan\": the files created first and the steps run, "
        "in order, in a fresh directory; \"outcomes\": for each numbered outcome, per step: exit code, stdout, "
        "stderr, and the shown files that step changed - null means deleted. A step with \"hand_edit\" is a file "
        "edited by hand, \"sleep\" a pause, \"symlink\" a symlink the harness made and \"list\" a listing of files; "
        "none of these ran the program. \"watch\": \"start\"/\"stop\" started and signalled `config watch` in the "
        "background).\n\n"
        "For EVERY outcome and EVERY question, choose the ONE group whose description matches what that outcome's "
        "results show. Judge only by the results, never by what an implementation might intend. When no group fits "
        "(or the results cannot show it, e.g. a command failed before the behaviour was reached), answer \"none\" and "
        "say why in one line. Never name an implementation, arm, method or tool.\n\n"
        "Reply with exactly one JSON object and nothing else, keyed by outcome number then question id:\n"
        '{"outcomes": {"1": {"Q1": {"group": "<group id>", "why": "<one line>"}}, '
        '"2": {"Q1": {"group": "none", "why": "<why no group fits>"}}}}')


def parse_classified(text: str, outcomes: list[str], topic_spec: dict, labels: list[str],
                     arms: list[str] | tuple[str, ...] = ()) -> dict[str, dict[str, dict]]:
    """{outcome: {question: {"group", "why"}}}: every outcome, every question, a known group or "none" (with a
    reason); nothing else. A reply naming an arm or a method is refused."""
    v = dz._json_value(text)
    if not isinstance(v, dict) or set(v) != {"outcomes"} or not isinstance(v["outcomes"], dict):
        raise judge.BadReply('needs one JSON object {"outcomes": {...}}')
    got = {str(k): x for k, x in v["outcomes"].items()}
    if set(got) != set(outcomes):
        raise judge.BadReply(f'"outcomes" must hold exactly the outcomes {sorted(outcomes, key=int)}')
    groups = {q["id"]: [g["id"] for g in q["groups"]] for q in topic_spec["questions"]}
    out: dict[str, dict[str, dict]] = {}
    for o in sorted(got, key=int):
        per = got[o]
        if not isinstance(per, dict) or set(per) != set(groups):
            raise judge.BadReply(f"outcome {o}: must answer exactly the questions {sorted(groups)}")
        out[o] = {}
        for q, a in per.items():
            if not isinstance(a, dict) or not set(a) <= {"group", "why"} or not isinstance(a.get("group"), str):
                raise judge.BadReply(f'outcome {o} {q}: must be {{"group": <id>, "why": <one line>}}')
            why = a.get("why", "")
            if not isinstance(why, str):
                raise judge.BadReply(f'outcome {o} {q}: "why" must be a string')
            if a["group"] == NONE:
                if not why.strip():
                    raise judge.BadReply(f'outcome {o} {q}: "none" needs a "why"')
            elif a["group"] not in groups[q]:
                raise judge.BadReply(f"outcome {o} {q}: group {a['group']!r} is not one of {groups[q]} or {NONE!r}")
            out[o][q] = {"group": a["group"], "why": why}
    texts = [a["why"] for per in out.values() for a in per.values()]
    if refs := [c for x in texts for c in leakcheck.label_refs(x, labels)]:
        raise judge.BadReply(f"the text names an arm ({'; '.join(refs[:3])}): never name one")
    if hits := leakcheck.check_text("\n".join(texts), list(arms), []):
        raise judge.BadReply(f"the text names a method or tool ({hits[0]}): never name one")
    return out


def outcomes(results: dict[str, list[dict]]) -> tuple[list[dict], dict[str, str]]:
    """Identical results merged: ([{"outcome": "1", "results": [...]}], {label: outcome}), numbered in label order."""
    out: list[dict] = []
    of: dict[str, str] = {}
    for lab in sorted(results):
        for o in out:
            if o["results"] == results[lab]:
                of[lab] = o["outcome"]
                break
        else:
            out.append({"outcome": str(len(out) + 1), "results": results[lab]})
            of[lab] = out[-1]["outcome"]
    return out, of


# ---- the stage -------------------------------------------------------------------------------------------------------

def _topics_by_sheet(pass_: str) -> dict[str, dict]:
    return {t["sheet_id"]: t for t in cx._topics(pass_)}


def _labels(t: dict) -> list[str]:
    return sorted({lab for r in t["routes"] for lab in r["labels"]})


def _unfinished(pass_: str, t: dict, topic_spec: dict, retry_failed: bool) -> bool:
    r = cx._record(out_path(pass_, t["id"]))
    if not isinstance(r, dict) or r.get("routes") != cx.fingerprint(t) or r.get("questions") != classify_view(
            topic_spec) or r.get("sheet_id") != t["sheet_id"]:
        return True                       # never written, unreadable, or for routes or group descriptions that changed
    return r.get("status") != "ok" and retry_failed


def _check_topics(spec: dict, by_sheet: dict[str, dict]) -> None:
    if missing := sorted(set(spec) - set(by_sheet), key=lambda x: int(x[1:])):
        raise inputs.InputError(f"reslice.json names topics not on the sheet: {', '.join(missing)}")


def run(pass_: str, j: judge.Judge, runner: cx.Runner, *, retry_failed: bool = False,
        only: list[str] | None = None, redo: bool = False) -> dict:
    """Every unfinished topic of reslice.json (or only the sheet / topic ids in `only`; `redo` with `only` classifies
    them again), one at a time. A topic's record is written only when it lands (`context._land`: an `ok` record
    replaces an earlier one, kept as `<id>.<n>.json`; a failure never replaces an `ok` one). An exception (a pin
    violation, a judge session failure) stops the stage with every earlier output intact. reslice-ratings.json and
    reslice-summary.md are rewritten from the records after every topic and at the end."""
    if redo and not only:
        raise inputs.InputError("--redo needs --only: name the topics to classify again")
    spec = load_spec(pass_)
    if spec is None:
        raise inputs.InputError(f"{spec_path(pass_)} is missing: nothing to reslice")
    by_sheet = _topics_by_sheet(pass_)
    _check_topics(spec, by_sheet)
    arms, labs = dz._arms(pass_), dz.labels(pass_)
    todo = [by_sheet[s] for s in sorted(spec, key=lambda x: int(x[1:]))
            if not only or s in only or by_sheet[s]["id"] in only]
    pending = [t for t in todo if (redo and only) or _unfinished(pass_, t, spec[t["sheet_id"]], retry_failed)]
    counts = {"written": 0, "failed": 0, "skipped": len(todo) - len(pending)}
    if pending:                                     # every label's code answering before anything is spent
        runner.ready(sorted({lab for t in pending for lab in _labels(t)}))
    for t in pending:
        ts = spec[t["sheet_id"]]
        f = out_path(pass_, t["id"])
        rec = {"sheet_id": t["sheet_id"], "routes": cx.fingerprint(t), "questions": classify_view(ts)}
        plan, source = plan_for(pass_, t)
        if plan is None:
            cx._land(f, {**rec, "status": "reslice_failed", "why": f"plan: {source}"})
            counts["failed"] += 1
            continue
        results: dict[str, list[dict]] = {}
        try:
            for lab in _labels(t):
                results[lab] = cx._scrub_results(runner.run(lab, plan), arms)
        except cx.RunFailed as e:               # the harness's failure: never a classification
            cx._land(f, {**rec, "status": "reslice_failed", "why": f"run: {e}"})
            counts["failed"] += 1
            continue
        outs, of = outcomes(results)
        item = item_dir(pass_, t["id"])
        dz._write(item / "questions.json", values.dump(classify_view(ts)))
        dz._write(item / "results.json", values.dump({"plan": _ran(plan), "outcomes": outs}))
        got, why, raw = dz._ask(j, classify_prompt(), item, ["questions.json", "results.json"],
                                lambda x: parse_classified(x, [o["outcome"] for o in outs], ts, labs, arms),
                                "one JSON object")
        if got is None:
            cx._land(f, {**rec, "status": "reslice_failed", "why": f"classify: {why}", "raw": raw})
            counts["failed"] += 1
            continue
        cx._land(f, {**rec, "status": "ok", "plan_source": source, "plan": plan, "outcomes": got,
                     "labels": {lab: of[lab] for lab in sorted(of)}})
        counts["written"] += 1
        write_outputs(pass_, spec, by_sheet)
    write_outputs(pass_, spec, by_sheet)
    return counts


def _current(pass_: str, t: dict, topic_spec: dict) -> dict | None:
    r = cx._record(out_path(pass_, t["id"]))
    if isinstance(r, dict) and r.get("status") == "ok" and not _unfinished(pass_, t, topic_spec, False):
        return r
    return None


def label_ratings(topic_spec: dict, rec: dict) -> dict[str, dict]:
    """{label: {"groups", "rating"[, "none_of_these"]}} from an ok record and the CURRENT ratings in reslice.json."""
    out = {}
    for lab, o in rec["labels"].items():
        per = rec["outcomes"][o]
        groups = {q: a["group"] for q, a in per.items()}
        e: dict = {"groups": groups, "rating": rating(topic_spec, groups)}
        if none := {q: a["why"] for q, a in per.items() if a["group"] == NONE}:
            e["none_of_these"] = none
        out[lab] = e
    return out


def write_outputs(pass_: str, spec: dict, by_sheet: dict[str, dict]) -> tuple[Path, Path]:
    """reslice-ratings.json (current ok records only) and the blind reslice-summary.md."""
    ratings, lines = {}, ["# Decision reslice: behaviour groups", "",
                          "Per topic: how many arms fell in each behaviour group, per question and per route. No arm "
                          "is named. \"none\" means no group fitted; such an arm keeps its route's rating.", ""]
    clean = dz._cleaner(dz._arms(pass_))
    for sid in sorted(spec, key=lambda x: int(x[1:])):
        t, ts = by_sheet[sid], spec[sid]
        lines += [f"## {sid}", ""]
        rec = _current(pass_, t, ts)
        if rec is None:
            r = cx._record(out_path(pass_, t["id"]))
            why = ("not classified yet" if not isinstance(r, dict)
                   else "classified for other routes or group descriptions: run decisions-reslice again"
                   if r.get("status") == "ok" else r.get("why", ""))
            fail = cx._record(cx.failed_path(out_path(pass_, t["id"])))
            lines += [f"_Not classified: {clean(why)}_", ""]
            if isinstance(fail, dict):
                lines += [f"_Last attempt failed: {clean(fail.get('why', ''))}_", ""]
            continue
        per = ratings[sid] = label_ratings(ts, rec)
        if isinstance(fail := cx._record(cx.failed_path(out_path(pass_, t["id"]))), dict):
            lines += [f"_A later attempt failed ({clean(fail.get('why', ''))}); these are the earlier results._", ""]
        route_of = {lab: r["route_no"] for r in t["routes"] for lab in r["labels"]}
        for q in ts["questions"]:
            order = [g["id"] for g in q["groups"]] + [NONE]
            tally = {g: sum(1 for e in per.values() if e["groups"][q["id"]] == g) for g in order}
            lines.append(f"- {sid} {q['id']} ({clean(q['text'])}): "
                         + ", ".join(f"{g} {n}" for g, n in tally.items() if n or g != NONE))
            for rno in sorted({route_of[lab] for lab in per}):
                rt = {g: sum(1 for lab, e in per.items() if route_of[lab] == rno and e["groups"][q["id"]] == g)
                      for g in order}
                lines.append(f"  - Route {rno}: " + ", ".join(f"{g} {n}" for g, n in rt.items() if n))
            whys = [clean(rec["outcomes"][o][q["id"]]["why"]) for o in sorted(set(rec["labels"].values()), key=int)
                    if rec["outcomes"][o][q["id"]]["group"] == NONE]
            lines += [f"  - none of these: {w}" for w in whys]
        lines.append("")
    text = "\n".join(lines)
    if leaks := leakcheck.check_text(text, dz._arms(pass_), dz.labels(pass_)):
        raise inputs.InputError(f"the reslice summary would unblind the owner ({len(leaks)} hit(s)); nothing written:\n"
                                + "\n".join(f"- {x}" for x in leaks[:40]))
    dz._write(ratings_path(pass_), values.dump(ratings))
    dz._write(summary_path(pass_), text)
    return ratings_path(pass_), summary_path(pass_)


def estimate(pass_: str, *, retry_failed: bool = False, only: list[str] | None = None, redo: bool = False) -> dict:
    """One classify call per unfinished topic (parse retries not counted)."""
    try:
        spec, by_sheet = load_spec(pass_), _topics_by_sheet(pass_)
    except inputs.InputError:
        return {"calls": 0, "topics": 0}
    if spec is None:
        return {"calls": 0, "topics": 0}
    n = sum(1 for s in spec if s in by_sheet and (not only or s in only or by_sheet[s]["id"] in only)
            and ((redo and only) or _unfinished(pass_, by_sheet[s], spec[s], retry_failed)))
    return {"calls": n, "topics": n}
