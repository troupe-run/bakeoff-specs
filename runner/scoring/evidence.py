"""Readers for one arm-step's evidence directory (results/<pass>/<arm>/<NN>/). Pure: no Docker, no git, no LLM.
Every reader returns values.val(...) or values.missing(...), never raises on bad evidence."""
from __future__ import annotations
import gzip
import json
import zlib
import os
import stat
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
    except (OSError, ValueError) as e:            # ValueError: bad JSON, or bytes that are not UTF-8
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


def arm_streams(step_dir: Path) -> list[tuple[int, Path]]:
    """(attempt, path) of every arm turn stream in the step, sorted by attempt then name."""
    td = step_dir / "turns"
    return sorted(((int(m[1]), f) for f in (td.iterdir() if td.is_dir() else []) if (m := _ARM_STREAM.match(f.name))),
                  key=lambda x: (x[0], x[1].name))


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
    except (OSError, EOFError, zlib.error):              # missing, truncated or corrupt (BadGzipFile is an OSError)
        return None


_BG_WAIT = b"Background tasks still running after"
_STDERR_LIMIT = 16 * 1024 * 1024


def _background_wait(p: Path) -> bool:
    """R13: the turn's stderr shows the CLI waited out its background-task ceiling (up to 600 s that no transcript
    entry covers). A missing, linked, non-regular or unreadable file is no flag; at most 16 MiB is decompressed."""
    try:
        if not stat.S_ISREG(os.lstat(p).st_mode):
            return False
        with gzip.open(p, "rb") as f:
            return _BG_WAIT in f.read(_STDERR_LIMIT)
    except (OSError, EOFError, zlib.error):
        return False


def arm_time(step_dir: Path) -> dict:
    td = step_dir / "turns"
    found = sorted((int(m[1]), int(m[2]), f) for f in (td.iterdir() if td.is_dir() else [])
                   if (m := _ARM_STREAM.match(f.name)))
    if not found:
        return values.missing(rel(td), "no arm turn streams")
    attempt = max(a for a, _, _ in found)
    from runner.scoring import phases           # lazy: phases imports evidence (controller ruling R2)
    all_spans = phases.turn_spans(step_dir, attempt)      # the transcripts are parsed once, here
    spans = all_spans
    if spans is not None and len(spans) != sum(1 for a, _, _ in found if a == attempt):
        spans = None                            # prompts do not map one-to-one onto turns: durations only
    turns, prev_usd, secs, unknown_before = [], 0.0, 0.0, False
    for _, _, f in (x for x in found if x[0] == attempt):
        rs = _result_lines(f)
        stem = f.name.removesuffix(".stream.jsonl.gz")
        if not rs:                          # killed turn (e.g. pass 1 ccsdd 05b a1-005, Docker restart 2026-10-05)
            k = _killed_seconds(step_dir, stem, all_spans)
            if k is None:
                return values.missing(rel(f), f"turn {stem}: no result line and no transcript timestamps")
            turns.append({"stem": stem, "seconds": k, "usd": None, "killed": True, "time_source": "transcript"})
            secs += k
            unknown_before = True
            continue
        span = spans[len(turns)] if spans else None
        if span is not None and span[1] > span[0]:              # R12: wall-clock span, subagents included
            seconds, source = span[1] - span[0], "transcript"
        elif all(isinstance(r.get("duration_ms"), (int, float)) for r in rs):
            seconds, source = sum(r["duration_ms"] for r in rs) / 1000, "duration_ms"   # R9: every wake counts
        else:
            return values.missing(rel(f), f"turn {stem}: no usable transcript and a result line has no duration_ms")
        turn = {"stem": stem, "seconds": seconds, "time_source": source}
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
    for turn in turns:
        if _background_wait(td / f"{turn['stem']}.stderr.gz"):
            turn["background_wait"] = True      # time understated by up to 600 s (ruling R13)
    return values.val({"seconds": secs, "attempt": attempt, "turns": turns}, rel(td))


def _killed_seconds(step_dir: Path, stem: str, spans: list[tuple[float, float]] | None) -> float | None:
    """A turn killed before its result line (its container died) still did real work: its length is the span of
    the session transcript entries written while it ran — from the turn's prompt entry (its `turns/<stem>.prompt.md`
    mtime is NOT used: copies lose it) to the last entry before the next turn's prompt. None when the transcripts
    hold no entries for it (the step's time is then missing, not zero). The report flags every killed turn, and its
    cost is unknown (the cumulative total of the next finished turn absorbs it, which the per-turn difference then
    attributes to that turn — flag it too)."""
    from runner.scoring import phases          # lazy: phases imports evidence (controller ruling R2)
    return phases.killed_turn_seconds(step_dir, stem, spans)


def costs(step_dir: Path) -> dict:
    b, a = read_json(step_dir / "cost.json"), read_json(step_dir / "a" / "cost.json")
    if values.is_missing(b):
        return b
    v = b["value"]
    return values.val({"scored_usd": v.get("arm", {}).get("usd"), "po_usd": v.get("po", {}).get("usd"),
                       "discovery_usd": None if values.is_missing(a) else a["value"].get("arm", {}).get("usd")},
                      b["source"])


PARTIAL_UNDER_HALF = "partial: under 50% of sampled mutants checked"
_UNCHECKED = ("not_checked", "check_interrupted")     # no verdict (quality.py: check_interrupted is not one either)


def mutation(m: dict) -> dict:
    """R32: the mutation score over CHECKED mutants only, recomputed here (runner/quality.py, the live instrument,
    keeps its own `score`): `killed / (eligible - unchecked)`, eligible = `total + missing_results - no_tests -
    skipped`, unchecked = `not_checked + check_interrupted + missing_results`, with `partial` and
    `checked_fraction = checked / eligible`. Under half checked is `unmeasured`
    (`PARTIAL_UNDER_HALF`). Crashed and baseline_failed are kept as they are. A summary without counts (an older
    shape) keeps its recorded score."""
    out = {"score": None, "partial": bool(m.get("partial")), "checked_fraction": None, "why": None}
    if m.get("crashed"):
        return out | {"state": "crashed"}
    if m.get("baseline_failed"):
        return out | {"state": "baseline_failed"}
    if not isinstance(m.get("total"), int):
        return out | {"score": m.get("score"), "state": "unmeasured" if m.get("score") is None else "measured"}
    missing = m.get("missing_results") or 0          # sampled names mutmut never reported: not in `total` (R32)
    eligible = m["total"] + missing - m.get("no_tests", 0) - m.get("skipped", 0)
    unchecked = sum(m.get(k, 0) for k in _UNCHECKED) + missing
    checked = eligible - unchecked
    if eligible <= 0:
        return out | {"state": "unmeasured"}
    out |= {"partial": out["partial"] or unchecked > 0, "checked_fraction": checked / eligible}
    if checked / eligible < 0.5:
        return out | {"state": "unmeasured", "why": PARTIAL_UNDER_HALF}
    return out | {"state": "measured", "score": m.get("killed", 0) / checked}


def _remeasure(step_dir: Path) -> tuple[dict | None, str | None, str | None]:
    """(the re-measure's mutation dict, its source) when it is current and measured; otherwise (None, None, why
    ignored) — None for why when there is no remeasure.json at all."""
    r = read_json(step_dir / "quality" / "remeasure.json")
    if values.is_missing(r):
        return None, None, None if r["why"] == "no such file" else r["why"]
    m = r["value"]
    if not isinstance(m, dict):
        return None, None, "unreadable: not an object"
    git = read_json(step_dir / "git.json")
    sha_after = None if values.is_missing(git) else git["value"].get("sha_after")
    if m.get("sha") != sha_after or sha_after is None:
        return None, None, f"stale: remeasure sha {m.get('sha')}, git.json sha_after {sha_after}"
    ev = mutation(m)
    if ev["state"] != "measured":
        return None, None, f"not measured: {ev['why'] or ev['state']}"
    return m, r["source"], None


def quality(step_dir: Path) -> dict:
    """mypy and ruff from `quality/summary.json`. The mutation part (`mutation()`, over checked mutants only) comes
    from `quality/remeasure.json` (Task 20, the whole suite per mutant) when that is for the step's `sha_after` and
    measured; otherwise from the original mutmut run in the summary, and `remeasure_ignored` says why a present
    re-measure was not used. `mutation_source`/`mutation_method` say where the mutation part came from."""
    q = read_json(step_dir / "quality" / "summary.json")
    if values.is_missing(q):
        return q
    v, m = q["value"], q["value"].get("mutation", {})
    m_src, method = q["source"], "mutmut"
    rem, rem_src, ignored = _remeasure(step_dir)
    if rem is not None:
        m, m_src, method = rem, rem_src, rem.get("method", "remeasure")
    ev = mutation(m if isinstance(m, dict) else {})
    return values.val({"mypy_errors": None if v.get("mypy_crashed") else v.get("mypy_errors"),
                       "ruff_findings": None if v.get("ruff_crashed") else v.get("ruff_findings"),
                       "mutation_score": ev["score"], "mutation_state": ev["state"], "mutation_why": ev["why"],
                       "mutation_partial": ev["partial"], "mutation_checked_fraction": ev["checked_fraction"],
                       "mutation_source": m_src, "mutation_method": method, "remeasure_ignored": ignored},
                      q["source"])


def read_jsonl(p: Path) -> tuple[list[dict], int] | None:
    """(objects, skipped malformed lines), or None when the file cannot be read (absent, unreadable, not UTF-8)."""
    try:
        lines = [l for l in p.read_text().splitlines() if l.strip()]
    except (OSError, UnicodeDecodeError):
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
    b = read_jsonl(scored)
    if b is None and os.path.lexists(scored):        # present but unreadable: missing, never "asked none"
        return values.missing(rel(scored), "unreadable (not a readable UTF-8 file)")
    if b is None:
        # R25: drive.py creates questions.jsonl only when a question occurs, so with a run record an absent file
        # means the arm asked none (information); without a run record nothing is known.
        if values.is_missing(run_record(step_dir)):
            return values.missing(rel(scored), "no run.json and no questions.jsonl")
        b = ([], 0)
    a_file = step_dir / "a" / "questions.jsonl"
    a = read_jsonl(a_file)
    items, skipped = [], b[1] + (a[1] if a else 0)
    for run, got in (("a", a), ("b", b)):
        for q in (got[0] if got else []):
            items.append({"run": run, "n": q.get("n"), "kind": q.get("kind"), "answered_by": q.get("answered_by"),
                          "escalated": q.get("escalated", []), "fallback": q.get("fallback", [])})
    return values.val({"items": items, "skipped_lines": skipped, "discovery": "present" if a else
                                                                      "unreadable" if os.path.lexists(a_file) else "absent"},
                      rel(scored))


def violations(step_dir: Path) -> dict:
    r = run_record(step_dir)
    return r if values.is_missing(r) else values.val(r["value"].get("arm_violations", []), r["source"])


def arm_violations(arm_dir: Path) -> dict:
    """R38: the violations in `results/<pass>/<arm>/arm-violations.jsonl` (orchestrate's step-end scans, the checklist's
    link repairs), the arm-level leaf of the violations part. An ABSENT file is none (the writers only create it on a
    violation); an unreadable one, or one with any malformed line, is unmeasured, never zero. Run "a" (discovery)
    entries are dropped. A drift check repeats before and after a restore, a scan repeats per run: setup-drift is
    deduped by (step, run, check), every other kind by (step, run, kind); a record with neither step nor run (a home
    repair) also keys on its path, so two different repairs stay two."""
    f = arm_dir / "arm-violations.jsonl"
    if not os.path.lexists(f):
        return values.val([], rel(f))
    got = read_jsonl(f)
    if got is None or got[1]:
        return values.missing(rel(f), "unreadable: cannot be read as UTF-8" if got is None
                              else f"corrupt: {got[1]} line(s) are not JSON objects")
    out, seen = [], set()
    for v in got[0]:
        if v.get("run") == "a":
            continue
        key = (v.get("step"), v.get("run"), v.get("check") if v.get("kind") == "setup-drift" else None, v.get("kind"),
               v.get("path") if v.get("step") is None and v.get("run") is None else None)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return values.val(out, rel(f))


# --- reported, not scored (spec §3, ruling R36) -------------------------------------------------------------------

def _num(x) -> float:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0


def owner_review(step_dir: Path) -> dict:
    """The owner's time on this step's scored run: Σ owner_seconds over questions.jsonl (approval gates are logged
    there too, kind "approval"; everything else the owner answered is an escalation). Reported, not scored (spec §2).
    With a run record and no questions file the owner spent nothing (R25); without either nothing is known."""
    q = questions(step_dir)
    if values.is_missing(q):
        return q
    got = read_jsonl(step_dir / "questions.jsonl")
    rows = got[0] if got else []
    gate = sum((_num(r.get("owner_seconds")) for r in rows if r.get("kind") == "approval"), 0.0)
    esc = sum((_num(r.get("owner_seconds")) for r in rows if r.get("kind") != "approval"), 0.0)
    return values.val({"seconds": gate + esc, "gates": sum(1 for r in rows if r.get("kind") == "approval"),
                       "gate_seconds": gate, "escalation_seconds": esc}, q["source"])


def tracker(step_dir: Path) -> dict:
    """The tracker snapshot after the step (tracker.json) and, at step 6, the issue round trip's facts
    (tracker-round-trip.json, written by orchestrate; None where absent). Reported, not scored."""
    t = read_json(step_dir / "tracker.json")
    if values.is_missing(t):
        return t
    v = t["value"] if isinstance(t["value"], dict) else {}
    rt = read_json(step_dir / "tracker-round-trip.json")
    return values.val({"backend": v.get("backend"), "initialised": v.get("initialised"),
                       "survives_restore": v.get("survives_restore"),
                       "issues": len(v["issues"]) if isinstance(v.get("issues"), list) else None,
                       "round_trip": None if values.is_missing(rt) else rt["value"]}, t["source"])


def discovery(step_dir: Path) -> dict:
    """Why the step's N.a (discovery) run stopped (a/discovery.json). Its cost is in `costs` (discovery_usd), its
    questions in `questions` (run "a"). Reported, not scored."""
    d = read_json(step_dir / "a" / "discovery.json")
    if values.is_missing(d):
        return d
    v = d["value"] if isinstance(d["value"], dict) else {}
    disc = v.get("discovery") if isinstance(v.get("discovery"), dict) else {}
    return values.val({"outcome": v.get("outcome"), "why": disc.get("why"), "turn": disc.get("turn"),
                       "exchanges": v.get("exchanges")}, d["source"])


def runs(step_dir: Path) -> dict:
    """Re-runs and harness faults from run.json: attempts, interventions, whether the step parked, and each harness
    fault (kind, signature, action, run, attempt). Only the final valid run is scored (spec §7.4)."""
    r = run_record(step_dir)
    if values.is_missing(r):
        return r
    v = r["value"] if isinstance(r["value"], dict) else {}
    faults = [{k: f.get(k) for k in ("kind", "signature", "action", "run", "attempt")}
              for f in v.get("harness_faults") or [] if isinstance(f, dict)]
    return values.val({"attempts": v.get("attempts"), "interventions": list(v.get("interventions") or []),
                       "parked": v.get("park") is not None, "harness_faults": faults}, r["source"])
