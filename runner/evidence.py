"""Per-step evidence (design §7) and the owner's step summary (OD7; plan Task 20).

`finalise` is the one place that pulls Task 15's turn-loop results, the setup's recorded pins and model
overrides, and the step's own git history into the fixed evidence layout a step's `results/<pass>/<arm>/<NN>/`
directory carries: `run.json` (wall-clock, pins, isolation, research attempts), `cost.json` (arm/PO/harness
apart, unit and source stated), `git.json` (the arm repo's `main`-based state, review F-1), `model-pin.json`
(the arm's own pin report — the PO's own report lives at `po/a<k>-NNN/model-pin.json`, Tasks 7/13), and
`summary.md` (the owner's step review).

Tasks 18 (`runner/hidden.py`) and 19 (`runner/quality.py`) are not landed yet: `hidden` and `quality` are
passed in as their finished results (an object and a dict respectively, see their key/attribute names below)
rather than being computed or imported here.

Ledger ruling 2 (fix round 1): `checklist.recheck` (`runner checklist`, run after an owner `runner shell`
session) commits whatever the owner left dirty under the same neutral identity as every other setup commit
(`gitops.IDENTITY` — never a distinct author), and the arm can write any commit message it likes under that
same identity too. So a commit's subject is NEVER trustworthy evidence of who made it: `evidence` does not
pattern-match `git log`. Instead `checklist.record_owner_shell_commit` writes every sha `recheck` actually
commits into a harness-side record under `p.setup_results` (outside the arm's repo and its home, where the
arm has no write access — `runner/checklist.py`); `owner_shell_shas`/`owner_shell_commit_entries` read and
cross-reference that record by sha.

Fix round 1 HIGH: a parked attempt (`AttemptResult.park`, an `owner.Park`) must be shown, not silently
folded into `outcome == "parked"` — the owner has to act on it. `run.json["park"]` and a prominent line near
the top of `summary.md` carry its `.reason` and `.context`.
"""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from runner import checklist, egress, gitops, images

SOURCE = ("Claude Code 2.1.281 stream-json result.total_cost_usd — client-side estimate "
          "(OAuth subscription; not a bill)")
APPROVAL_WORDS = re.compile(r"\b(approve|approval|sign[- ]?off|proceed|go ahead|LGTM|confirm)\b", re.I)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def mypy_summary_text(quality: dict[str, object]) -> str:
    """The owner-facing mypy phrase: a real count when there is one, otherwise the reason there isn't --
    never "None errors" (fix round 2, item 8: a crashed or timed-out mypy run must say so)."""
    if quality.get("mypy_timed_out"):
        return "timed out"
    n = quality.get("mypy_errors")
    return f"{n} errors" if n is not None else "crashed"


def ruff_summary_text(quality: dict[str, object]) -> str:
    """The owner-facing isolated-ruff phrase: a real count when there is one, otherwise the reason there
    isn't (fix round 3, item 7) -- never a bare `None`."""
    n = quality.get("ruff_findings")
    if n is not None:
        return str(n)
    if quality.get("ruff_timed_out"):
        return "timed out"
    return "crashed"


def ruff_arm_summary_text(quality: dict[str, object]) -> str:
    """The owner-facing arm-config-ruff phrase. "no config" (the arm simply has none — the pass was never
    attempted, and that's not a failure) is distinct from "crashed" (an actual failure trying to run it):
    `run_all` only ever sets `ruff_arm_crashed` to `True` or `None` (never `False`) — `None` means the
    precheck found no config and the pass was skipped outright, `True` means something went wrong either
    finding out or running it (fix round 3, item 7)."""
    n = quality.get("ruff_arm_findings")
    if n is not None:
        return str(n)
    if quality.get("ruff_arm_timed_out"):
        return "timed out"
    if quality.get("ruff_arm_crashed") is None:
        return "no config"
    return "crashed"


def mutation_summary_text(mut: dict[str, object]) -> str:
    """The owner-facing mutation phrase: the score when there is one, otherwise the reason there isn't --
    crashed, baseline failed, no tests, or timed out (fix round 2, item 8) -- never a bare `None`. A
    placeholder reason (`_mutation_placeholder`'s "install failed" or an "error: ..." exception summary,
    fix round 3, item 7) renders with its own specific text rather than collapsing to a generic "crashed"."""
    score = mut.get("score")
    if score is not None:
        return f"{score} ({mut.get('sampling', '')}{', partial' if mut.get('partial') else ''})"
    if mut.get("timed_out"):
        return "timed out"
    if mut.get("baseline_failed"):
        return "baseline failed"
    sampling = mut.get("sampling")
    if sampling == "no tests":
        return "no tests"
    if isinstance(sampling, str) and (sampling == "install failed" or sampling.startswith("error:")):
        return sampling
    return "crashed"


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def cost(turn_lists: dict[str, list]) -> dict:
    out = {"unit": "USD", "source": SOURCE}
    for who, turns in turn_lists.items():
        usage: dict[str, int] = {}
        mu: dict[str, dict] = {}
        for t in turns:
            for k, v in (t.usage or {}).items():
                if isinstance(v, (int, float)):
                    usage[k] = usage.get(k, 0) + v
            for m, v in (t.model_usage or {}).items():
                agg = mu.setdefault(m, {})
                for k, x in v.items():
                    if isinstance(x, (int, float)):
                        agg[k] = agg.get(k, 0) + x
        out[who] = {"usd": round(sum(t.cost_usd for t in turns), 6), "turns": len(turns), "usage": usage,
                    "modelUsage": mu}
    return out


def research_attempts(turns: list, egress_log: str) -> dict:
    """(OD10, review F-8) how many arm turns had a WebSearch/WebFetch permission denial, and which hosts the
    egress proxy refused."""
    denied = sum(1 for t in turns for d in (t.permission_denials or []) if d.get("tool_name") in ("WebSearch", "WebFetch"))
    refused = sorted({h for h, v in egress.decisions(egress_log) if v == "refused"})
    return {"denied_web_tools": denied, "refused_hosts": refused}


def possible_missed_approvals(qa: list[dict]) -> list[dict]:
    """(review C-8) a `continue` reply to an arm message that reads like it was asking for sign-off — the PO
    may have under-escalated it."""
    return [q for q in qa if q.get("kind") == "continue" and APPROVAL_WORDS.search(q.get("arm_message") or "")]


def owner_shell_shas(p) -> set[str]:
    """(ledger ruling 2, fix round 1) shas `checklist.recheck` actually committed, from the harness-side
    record under `p.setup_results` — never from the arm's own (forgeable) git log."""
    f = p.setup_results / checklist.OWNER_SHELL_COMMITS_FILE
    return {e["sha"] for e in json.loads(f.read_text())} if f.is_file() else set()


def owner_shell_commit_entries(log: list[dict], recorded_shas: set[str]) -> list[dict]:
    """Entries of `gitops.log`'s output whose sha is in `recorded_shas` (fix round 1 MEDIUM: matched by sha,
    never by pattern-matching the commit subject — the arm commits under the same identity as `recheck` and
    can write any subject line, including a forged copy of its `" (owner shell adjustments)"` suffix)."""
    return [c for c in log if c.get("sha") in recorded_shas]


def parked_attempt(attempts: list):
    """The attempt that ended in an owner `Park`, if any. A park ends the run for the step at once (Task 15
    ruling 1), so at most one attempt ever carries one — the last, when several attempts ran first."""
    return next((a for a in reversed(attempts) if a.park is not None), None)


def _qa(out: Path) -> list[dict]:
    f = out / "questions.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def _lines(f: Path) -> list[dict]:
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []


def na_section(a: Path) -> list[str]:
    """m-6: the step's N.a in the owner's N.b review — why it stopped, its code check (an `unavailable` check means
    N.a may have run the whole step unnoticed) and its escalations."""
    d = json.loads((a / "discovery.json").read_text()) if (a / "discovery.json").is_file() else None
    if d is None:
        return ["- no N.a record"]
    why = (d.get("discovery") or {}).get("why")
    out = [f"- stopped: {d.get('outcome')}" + (f" ({why} at turn {(d.get('discovery') or {}).get('turn')})" if why else "")]
    cc = d.get("code_check") or {}
    out.append(f"- code check: {cc.get('status') or 'n/a'}" + "".join(
        f"; turn {r.get('turn')}: {r.get('reason')}" for r in (cc.get("reasons") or [])[:5]))
    esc = [q for q in _lines(a / "questions.jsonl") if q.get("escalated")]
    out += [f"- escalation: {', '.join(q['escalated'])} → {q.get('reply')}" for q in esc] or ["- escalations: none"]
    return out


def _gates(out: Path) -> list[dict]:
    f = out / "owner-gates.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def finalise(ctx, *, attempts, extra_turns, hidden, quality, pin, sha_before, started, ended, fault_entries,
             shas, tests_seconds, outcome) -> Path:
    out, p, pins = ctx.out, ctx.paths, ctx.pins
    arm_turns = [t for a in attempts for t in a.turns]
    po_turns = [t for a in attempts for r in a.po_results for t in r.turns]
    harness_turns = [t for ts in extra_turns.values() for t in ts]
    qa, gates = _qa(out), _gates(out)
    egress_log = (out / "egress.log").read_text() if (out / "egress.log").exists() else ""

    st = gitops.state(p)
    log = gitops.log(p, sha_before, st.main or st.head)
    git = {"sha_before": sha_before, "sha_after": st.main, "head": st.head, "branch": st.branch,
           "head_in_main": st.head_in_main, "dirty_at_end": st.dirty, "log": log,
           "diffstat": gitops.diffstat(p, sha_before, st.main or st.head)}
    (out / "git.json").write_text(json.dumps(git, indent=2))

    c = cost({"arm": arm_turns, "po": po_turns, "harness": harness_turns})
    (out / "cost.json").write_text(json.dumps(c, indent=2))
    (out / "model-pin.json").write_text(pin.to_json())

    lock = images.lock() if images.LOCK.exists() else {"arms": {}, "images": {}}
    overrides_f = p.setup_results / "model-overrides.json"
    owner_shell = owner_shell_commit_entries(log, owner_shell_shas(p))
    interventions = [i for a in attempts for i in a.interventions] + \
        [f"owner-shell-commit:{c_['sha'][:8]}" for c_ in owner_shell]

    pa = parked_attempt(attempts)
    park = None
    if pa is not None:
        pk = pa.park
        park = {"attempt": attempts.index(pa) + 1, "prompt": pk.prompt, "context": pk.context,
                "reason": pk.reason, "at": pk.at, "seconds": pk.seconds}

    run = {"pass": ctx.pass_, "arm": ctx.arm.name, "step": ctx.step, "outcome": outcome, "attempts": len(attempts),
           "started_at": _iso(started), "ended_at": _iso(ended),               # epoch seconds (time.time())
           "wall_seconds": round(ended - started, 1),
           "arm_session_seconds": round(sum(t.wall_seconds for t in arm_turns), 1),
           "po_seconds": round(sum(t.wall_seconds for t in po_turns), 1),
           "owner_wait_seconds": round(sum(q.get("owner_seconds", 0.0) for q in qa), 1),
           "tests_seconds": round(tests_seconds, 1),
           "claude_version": pins.claude_version, "model": pins.model, "plugin_route": pins.plugin_route,
           "images": {"arm": lock["arms"].get(ctx.arm.name, {}).get("id"),
                      "tester": lock["images"].get(pins.images["tester"], {}).get("id"),
                      "proxy": lock["images"].get(pins.images["proxy"], {}).get("id")},
           "po_brief_sha256_at_handoff": shas["po_brief_at_handoff"],
           "po_brief_sha256_at_end": sha256_file(ctx.brief_path),
           "contract_sha256": shas["contract"], "step_brief_sha256": shas["step_brief"],
           "interventions": interventions,
           "park": park,
           "breaches": [a.breach for a in attempts if a.breach],
           "research_attempts": research_attempts(arm_turns, egress_log),
           "model_overrides": json.loads(overrides_f.read_text())["declared"] if overrides_f.exists() else [],
           "harness_faults": fault_entries,
           "arm_violations": _lines(out / "arm-violations.jsonl")}
    (out / "run.json").write_text(json.dumps(run, indent=2))

    missed = possible_missed_approvals(qa)
    esc = [q for q in qa if q.get("escalated")]
    sig = [q for q in qa if q.get("significant")]
    mut = (quality.get("mutation") or {})
    lines = [f"# Step {ctx.step} summary — {ctx.arm.name} ({ctx.pass_})", ""]
    if park:                                    # fix round 1 HIGH: prominent — the owner has to act on this
        lines += [f"## PARKED — owner action needed (attempt {park['attempt']})",
                  f"`{park['prompt']}` parked ({park['reason']}): {park['context']}", ""]
    lines += [f"**Outcome:** {outcome} after {len(attempts)} attempt(s); interventions: {run['interventions'] or 'none'}",
             f"**Hidden tests:** {hidden.passed}/{hidden.total} passed; new at this step {hidden.new_passed}/"
             f"{len(hidden.new_at_step)} (discriminating: {hidden.new_discriminating_passed}); arm flakes: {hidden.flaky_arm}",
             f"**Model pin:** {'ok' if pin.ok else 'VIOLATION'} ({pin.assistant_messages} transcript assistant messages)",
             f"**Cost (estimate):** arm ${c['arm']['usd']:.2f} · PO ${c['po']['usd']:.2f} · harness ${c['harness']['usd']:.2f}",
             f"**Time:** {run['wall_seconds']} s wall, {run['owner_wait_seconds']} s waiting on the owner",
             f"**Quality:** not run ({quality['skipped']})" if quality.get("skipped") else
             f"**Quality:** mypy {mypy_summary_text(quality)} · "
             f"ruff {ruff_summary_text(quality)} (arm {ruff_arm_summary_text(quality)}) · "
             f"mutation score {mutation_summary_text(mut)}",
             f"**Research attempts:** {run['research_attempts']}", "", "## Escalations"]
    lines += [f"- {', '.join(q['escalated'])} → {q['reply']}" for q in esc] or ["- none"]
    lines += ["", "## Significant PO answers"] + \
        ([f"- {q['arm_message'][:120]!r} → {str(q['reply'])[:200]}" for q in sig] or ["- none"])
    lines += ["", "## Owner gates"] + \
        ([f"- {g['owner_action']}: {str(g['final_reply'])[:200]}" for g in gates] or ["- none"])
    lines += ["", "## Possible missed approvals (PO said `continue`, the arm used approval wording)"]
    lines += [f"- turn {q['n']}: {q['arm_message'][:200]!r}" for q in missed] or ["- none"]
    lines += ["", "## N.a (discovery)"] + na_section(out / "a")                                          # m-6
    lines += ["", "## Arm violations (A5: the attempt failed; never a harness fault)"]
    lines += [f"- attempt {v.get('attempt')} ({v.get('run')}): {v.get('kind')} {v.get('check') or ''}".rstrip()
              for v in run["arm_violations"]] or ["- none"]
    lines += ["", "## Egress refusals"] + ([f"- {h}" for h in run["research_attempts"]["refused_hosts"]] or ["- none"])
    if run["model_overrides"]:
        lines += ["", "## Method's own model choices (overridden, OD2)"] + \
            [f"- {m['file']}: {m['model']}" for m in run["model_overrides"]]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return out / "summary.md"
