"""Readers for one arm-step's evidence directory (results/<pass>/<arm>/<NN>/). Pure: no Docker, no git, no LLM.
Every reader returns values.val(...) or values.missing(...), never raises on bad evidence."""
from __future__ import annotations
import gzip
import json
import re
from pathlib import Path
from runner import paths
from runner.scoring import values


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(paths.REPO_ROOT))
    except ValueError:
        return str(p)


def read_json(p: Path) -> dict:
    try:
        return values.val(json.loads(p.read_text()), rel(p))
    except FileNotFoundError:
        return values.missing(rel(p), "no such file")
    except (OSError, json.JSONDecodeError) as e:
        return values.missing(rel(p), f"unreadable: {e}")


def hidden_summary(step_dir: Path) -> dict:
    return read_json(step_dir / "hidden" / "summary.json")


def all_fail(pass_dir: Path, arms: list[str]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for step in range(1, 8):
        failing: set[str] | None = None
        for arm in arms:
            s = hidden_summary(pass_dir / arm / f"{step:02d}")
            if values.is_missing(s) or not s["value"].get("scoreable", True):
                continue
            f = {t for t, o in s["value"].get("tests", {}).items() if o != "passed"}
            failing = f if failing is None else failing & f
        if failing:
            out[step] = sorted(failing)
    return out


# --- evidence readers: run, time, cost, quality, questions, violations ---------------------------------------------
_ARM_STREAM = re.compile(r"^arm-a(\d+)-(\d+)\.stream\.jsonl\.gz$")


def run_record(step_dir: Path) -> dict:
    return read_json(step_dir / "run.json")


def _result_lines(p: Path) -> list[dict] | None:
    """Every result line of a turn's stream, in order (a turn whose background agents wake the main loop ends each
    wake with its own result line); None when the stream cannot be read."""
    try:
        with gzip.open(p, "rt", errors="replace") as f:
            out = []
            for line in f:
                if '"type":"result"' in line.replace(" ", ""):
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(o, dict):
                        out.append(o)
            return out
    except (OSError, EOFError):
        return None


def arm_time(step_dir: Path) -> dict:
    td = step_dir / "turns"
    found = sorted((int(m[1]), int(m[2]), f) for f in (td.iterdir() if td.is_dir() else [])
                   if (m := _ARM_STREAM.match(f.name)))
    if not found:
        return values.missing(rel(td), "no arm turn streams")
    attempt = max(a for a, _, _ in found)
    turns, prev_usd, secs, unknown_before = [], 0.0, 0.0, False
    for _, _, f in (x for x in found if x[0] == attempt):
        rs = _result_lines(f)
        stem = f.name.removesuffix(".stream.jsonl.gz")
        if not rs:                          # killed turn (e.g. pass 1 ccsdd 05b a1-005, Docker restart 2026-10-05)
            k = _killed_seconds(step_dir, stem)
            if k is None:
                return values.missing(rel(f), f"turn {stem}: no result line and no transcript timestamps")
            turns.append({"stem": stem, "seconds": k, "usd": None, "killed": True})
            secs += k
            unknown_before = True
            continue
        if not all(isinstance(r.get("duration_ms"), (int, float)) for r in rs):
            return values.missing(rel(f), f"turn {stem}: result line has no duration_ms")
        seconds = sum(r["duration_ms"] for r in rs) / 1000    # R9: every wake of the turn is real time
        turn = {"stem": stem, "seconds": seconds}
        cum = rs[-1].get("total_cost_usd")                      # cumulative: the turn's last result line
        if isinstance(cum, (int, float)):
            turn["usd"] = max(0.0, float(cum) - prev_usd)
            if unknown_before:
                turn["absorbs_previous"] = True
            prev_usd, unknown_before = float(cum), False
        else:
            turn["usd"] = None
            unknown_before = True
        turns.append(turn)
        secs += seconds
    return values.val({"seconds": secs, "attempt": attempt, "turns": turns}, rel(td))


def _killed_seconds(step_dir: Path, stem: str) -> float | None:
    """A turn killed before its result line (its container died) still did real work: its length is the span of
    the session transcript entries written while it ran — from the turn's prompt entry (its `turns/<stem>.prompt.md`
    mtime is NOT used: copies lose it) to the last entry before the next turn's prompt. None when the transcripts
    hold no entries for it (the step's time is then missing, not zero). The report flags every killed turn, and its
    cost is unknown (the cumulative total of the next finished turn absorbs it, which the per-turn difference then
    attributes to that turn — flag it too)."""
    from runner.scoring import phases          # lazy: phases imports evidence (controller ruling R2)
    return phases.killed_turn_seconds(step_dir, stem)


def costs(step_dir: Path) -> dict:
    b, a = read_json(step_dir / "cost.json"), read_json(step_dir / "a" / "cost.json")
    if values.is_missing(b):
        return b
    v = b["value"]
    return values.val({"scored_usd": v.get("arm", {}).get("usd"), "po_usd": v.get("po", {}).get("usd"),
                       "discovery_usd": None if values.is_missing(a) else a["value"].get("arm", {}).get("usd")},
                      b["source"])


def quality(step_dir: Path) -> dict:
    q = read_json(step_dir / "quality" / "summary.json")
    if values.is_missing(q):
        return q
    v, m = q["value"], q["value"].get("mutation", {})
    state = ("crashed" if m.get("crashed") else "baseline_failed" if m.get("baseline_failed")
             else "unmeasured" if m.get("score") is None else "measured")
    return values.val({"mypy_errors": None if v.get("mypy_crashed") else v.get("mypy_errors"),
                       "ruff_findings": None if v.get("ruff_crashed") else v.get("ruff_findings"),
                       "mutation_score": m.get("score"), "mutation_state": state}, q["source"])


def _jsonl(p: Path) -> list[dict]:
    try:
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _jsonl(p: Path) -> tuple[list[dict], int] | None:
    """(objects, skipped malformed lines), or None when the file cannot be read."""
    try:
        lines = [l for l in p.read_text().splitlines() if l.strip()]
    except OSError:
        return None
    out, skipped = [], 0
    for l in lines:
        try:
            o = json.loads(l)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if isinstance(o, dict):
            out.append(o)
        else:
            skipped += 1
    return out, skipped


def questions(step_dir: Path) -> dict:
    scored = step_dir / "questions.jsonl"
    b = _jsonl(scored)
    if b is None:
        return values.missing(rel(scored), "absent or unreadable")
    a = _jsonl(step_dir / "a" / "questions.jsonl")
    items, skipped = [], b[1] + (a[1] if a else 0)
    for run, got in (("a", a), ("b", b)):
        for q in (got[0] if got else []):
            items.append({"run": run, "n": q.get("n"), "kind": q.get("kind"), "answered_by": q.get("answered_by"),
                          "escalated": q.get("escalated", []), "fallback": q.get("fallback", [])})
    return values.val({"items": items, "skipped_lines": skipped, "discovery": "present" if a else "absent"},
                      rel(scored))


def violations(step_dir: Path) -> dict:
    r = run_record(step_dir)
    return r if values.is_missing(r) else values.val(r["value"].get("arm_violations", []), r["source"])
