"""Plan 3 Task 19: the owner's review queue. The owner checks every disputed judgement, every judgement that decides
the top-two order, and a seeded sample of the rest, blind to which arm it is (the sheet shows labels only; the
import maps them back through `anon-key.json`). Verdicts land in `review/verdicts.jsonl`, the file aggregate reads."""
from __future__ import annotations
import copy
import json
import math
import random
import re
from datetime import date
from pathlib import Path
from runner import paths
from runner.scoring import anonymise, confidence, inputs, judge, values

SAMPLE = 0.10


def _iter_judged(scores: dict):
    """(part, arm, step key, step) for every judged step (one that carries lenses), sorted."""
    for arm in sorted(scores["arms"]):
        for d in scores["arms"][arm]["dimensions"].values():
            for part, p in d["parts"].items():
                for key, st in p["steps"].items():
                    if st.get("lenses"):
                        yield part, arm, key, st


def _step_id(key: str) -> int | str:
    return int(key) if key.isdigit() else key


def _forced(scores: dict, arm: str, part: str, key: str, value: float) -> dict[str, float]:
    """Every arm's total with the one step's score forced (median mode, base weights)."""
    arms = copy.deepcopy(scores["arms"])
    for d in arms[arm]["dimensions"].values():
        if part in d["parts"] and key in d["parts"][part]["steps"]:
            d["parts"][part]["steps"][key]["score"] = value
    w = scores["weights"]
    return {a: confidence.total(v, w["dimensions"], w["parts"], "median") for a, v in arms.items()}


def _swings_top_two(top: list[str], t: dict[str, float]) -> bool:
    """The top-two order changes when the second is clearly ahead of the first, or any other arm is clearly ahead of
    either (CHECK_TOL, as in confidence.check)."""
    first, second = top
    if t[first] - t[second] < -confidence.CHECK_TOL:
        return True
    return any(t[c] - t[second] > confidence.CHECK_TOL for c in t if c not in top)


def queue(scores: dict, seed: str, sample: float = SAMPLE) -> list[dict]:
    ranking = confidence.check(scores)["ranking"] if len(scores["arms"]) >= 2 else []
    top = ranking[:2]
    items, rest = [], []
    for part, arm, key, st in _iter_judged(scores):
        if "owner" in st:
            continue                                            # already decided by the owner
        item = {"part": part, "arm": arm, "step": _step_id(key), "lenses": dict(st["lenses"])}
        if st.get("disputed"):
            items.append(item | {"reason": "disputed"})
        elif len(top) == 2 and any(_swings_top_two(top, _forced(scores, arm, part, key, f(st["lenses"].values()) / 4))
                                   for f in (min, max)):
            items.append(item | {"reason": "decides top two"})
        else:
            rest.append(item)
    k = math.ceil(sample * len(rest)) if sample > 0 else 0
    picked = random.Random(seed).sample(rest, min(k, len(rest)))
    items += [i | {"reason": "sample"} for i in picked]
    return sorted(items, key=lambda i: (i["part"], i["arm"], i["step"] == "arm", str(i["step"]).zfill(3)))


# ---- the sheet ------------------------------------------------------------------------------------------------------

def _dir(pass_: str) -> Path:
    return paths.scoring_out(pass_) / "review"


def _map_file(pass_: str) -> Path:
    """Item numbers -> part, label, step: kept out of the owner's way, never shown on the sheet."""
    return _dir(pass_) / ".import" / "review-sheet.json"


def _verdicts_file(pass_: str) -> Path:
    return _dir(pass_) / "verdicts.jsonl"


_FIELD = re.compile(r"^[ \t]*(?:[-*][ \t]+)?(score|reason)[ \t]*:(.*)$", re.I)
_ITEM = re.compile(r"^##\s+Item\s+(\d+)\b")


def _quote(text) -> str:
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    return "\n".join("> " + l for l in (text.strip().splitlines() or [""]))        # a quote line can never be a field


def _lens_block(pass_: str, part: str, arm: str, nn: str, terms) -> str:
    d = paths.scoring_out(pass_) / "judged" / part / arm / nn
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            j = json.loads(f.read_text())
        except json.JSONDecodeError:
            j = {"status": "unreadable"}
        out.append(f"### {f.stem}: score {j.get('score')} ({j.get('status')})\n\n"
                   f"Evidence:\n\n{_quote(anonymise.scrub(_text(j.get('evidence')), terms))}\n\n"
                   f"Notes:\n\n{_quote(anonymise.scrub(_text(j.get('notes')), terms))}\n")
    return "\n".join(out) or "(no lens verdicts on disk)\n"


def _text(x) -> str:
    return "" if x is None else x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)


def _scores(pass_: str) -> dict:
    f = paths.scoring_out(pass_) / "scores.json"
    if not f.exists():
        raise inputs.InputError(f"{f} is missing: run `runner score {pass_} --stage aggregate` first")
    return json.loads(f.read_text())


def sheet(pass_: str) -> Path:
    """review/review-sheet.md: label, rubric levels, lens verdicts, blank `score:` / `reason:` per queued item. Refuses
    to overwrite a sheet the owner has started."""
    md = _dir(pass_) / "review-sheet.md"
    if md.exists() and any((m := _FIELD.match(l)) and m[2].strip() for l in md.read_text().splitlines()):
        raise inputs.InputError(f"{md} already holds answers: move it aside to write a fresh sheet")
    key = judge.anon_key(pass_)
    label_of = {a: lab for lab, a in key.items()}
    scores = _scores(pass_)
    rubrics = inputs.load_rubrics()
    terms = anonymise.pass_terms(sorted(set(key.values()) | set(scores["arms"])))
    items = queue(scores, pass_)
    missing = sorted({i["arm"] for i in items if i["arm"] not in label_of})
    if missing:
        raise inputs.InputError(f"{missing} not in anon-key.json: run the anonymise stage first")
    items.sort(key=lambda i: (i["part"], label_of[i["arm"]], i["step"] == "arm", str(i["step"]).zfill(3)))
    body, mapping = [], []
    for n, i in enumerate(items, 1):
        lab, nn = label_of[i["arm"]], ("arm" if i["step"] == "arm" else f"{i['step']:02d}")
        where = "whole arm" if nn == "arm" else f"step {nn}"
        levels = "\n".join(f"- {lv}: {rubrics[i['part']].levels[lv]}" for lv in range(5)) if i["part"] in rubrics else ""
        body.append(f"## Item {n}: {i['part']}, {lab}, {where}\n\nRubric levels:\n\n{levels}\n\n"
                    f"{_lens_block(pass_, i['part'], i['arm'], nn, terms)}\n"
                    f"Your verdict (a whole number 0 to 4, and a reason):\n\nscore:\nreason:\n")
        mapping.append({"item": n, "part": i["part"], "label": lab, "step": i["step"]})
    head = ("# Review sheet\n\nFill in `score:` (0 to 4) and `reason:` for every item, then run the review-import "
            "stage. Every item needs both.\n\n")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(head + "\n".join(body) if items else head + "Nothing to review.\n", encoding="utf-8")
    _map_file(pass_).parent.mkdir(parents=True, exist_ok=True)
    _map_file(pass_).write_text(values.dump({"items": mapping}))
    return md


# ---- the import -----------------------------------------------------------------------------------------------------

def _parse(text: str) -> tuple[dict[int, dict], list[str]]:
    got: dict[int, dict] = {}
    problems: list[str] = []
    cur = None
    for line in text.splitlines():
        if m := _ITEM.match(line):
            n = int(m[1])
            if n in got:
                problems.append(f"item {n}: appears twice on the sheet")
                cur = {}
            else:
                cur = got[n] = {}
        elif (m := _FIELD.match(line)) and cur is not None:
            f = m[1].lower()
            if f in cur:
                problems.append(f"item {next(k for k, v in got.items() if v is cur)}: two {f} lines")
            else:
                cur[f] = m[2].strip()
    return got, problems


def _score(raw: str | None):
    if raw is None or not raw:
        return None, "is blank"
    if not re.fullmatch(r"[0-4]", raw.strip("`* ")):
        return None, f"must be a whole number 0 to 4, got {raw!r}"
    return int(raw.strip("`* ")), None


def import_sheet(pass_: str, today: date | None = None) -> Path:
    """Validates the filled sheet and appends one row per item to review/verdicts.jsonl (real arm names). On any
    problem nothing is written."""
    md, mp = _dir(pass_) / "review-sheet.md", _map_file(pass_)
    for f in (md, mp):
        if not f.exists():
            raise inputs.InputError(f"{f} is missing: run the review-sheet stage first")
    structure = json.loads(mp.read_text())["items"]
    parsed, problems = _parse(md.read_text(encoding="utf-8"))
    known = {i["item"] for i in structure}
    problems += [f"item {n}: not on the review sheet's list" for n in sorted(set(parsed) - known)]
    answers = {}
    for it in structure:
        n = it["item"]
        if n not in parsed:
            problems.append(f"item {n}: missing from the sheet")
            continue
        score, why = _score(parsed[n].get("score"))
        if why:
            problems.append(f"item {n}: score {why}")
        reason = parsed[n].get("reason", "")
        if not reason:
            problems.append(f"item {n}: reason is blank")
        answers[n] = (score, reason)
    if problems:
        raise inputs.InputError("the review sheet has problems:\n" + "\n".join(f"- {p}" for p in problems))
    arm_of = judge.anon_key(pass_)
    existing = _existing(pass_)
    decided = f"owner {(today or date.today()).isoformat()}"
    rows = []
    for it in structure:
        if it["label"] not in arm_of:
            raise inputs.InputError(f"item {it['item']}: label {it['label']!r} not in anon-key.json")
        score, reason = answers[it["item"]]
        row = {"part": it["part"], "arm": arm_of[it["label"]], "step": it["step"], "score": score, "reason": reason,
               "decided": decided}
        k = (row["part"], row["arm"], str(row["step"]))
        if k in existing:
            raise inputs.InputError(f"item {it['item']}: duplicate verdict for {k} (already in {_verdicts_file(pass_)})")
        existing.add(k)
        rows.append(row)
    f = _verdicts_file(pass_)
    old = f.read_text() if f.exists() else ""
    if old and not old.endswith("\n"):
        old += "\n"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(old + "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows))
    return f


def _existing(pass_: str) -> set[tuple]:
    """Keys of the verdicts already on file, validated exactly as aggregate validates them."""
    from runner.scoring import aggregate
    return set(aggregate._verdicts(pass_))
