"""One step for one arm (design §5, §7, §9; plan Task 22): attempts, scoring, harness faults and the stop rule.

`run_step(ctx, first_message, extra=None, run="b")` drives ONE of the step's two runs (design §5, owner 2026-09-29):

- **run "a" (N.a, discovery):** one attempt with `drive.run_attempt(..., stop_at_first_gate_or_code=True)`, which
  ends at the arm's first approval request or its first edit to code outside its spec and docs paths. No hidden
  tests, no quality, no scoring. The evidence stays under `ctx.out`, which must be the step's `a/` directory
  (`results/<pass>/<arm>/<NN>/a/`): transcripts, questions, `discovery.json`, `cost.json`, `model-pin.json`. The
  pre-step snapshot is then restored (and `ctx.later_sent` reset) so N.b starts from the same commit.
- **run "b" (N.b, scored):** attempts to completion, the hidden tests on committed `main` after each, and
  `evidence.finalise` once the step is decided.

Classification (design §9, brief table, binding rulings):

- An attempt's transcripts are ALWAYS collected and pin-checked, including when it raised a `HarnessFault`
  (ruling 3: its turns are on `fault.attempt_result`). `verify_pin` always gets the runner-captured streams with
  their outcomes and collection's skipped entries (ruling 4). Behind a raised fault, an off-pin model is what the
  ledger records, except under `infra-auth` / `credential-persisted` (the hand edit's precedence).
- A harness fault (raised by drive, found by the pin check, a failed container from the runner —
  `docker.ContainerError` or `subprocess.SubprocessError` — as `infra-container`; any other exception is a runner
  bug and propagates (fix round 1 L-1), or the owner reclassifying the arm's first runaway breach, OD14 B) goes to
  the ledger
  (`faults.record`). The second identical one halts (`Halt`). Otherwise the owner confirms the fix (`Paused` if
  not, or if they park), every attempt since the last restore is parked under `attempts/<k>-harness-<kind>/`, the
  step snapshot is restored, `ctx.later_sent` is reset to 0 so CR-B is sent again (ruling 2), and the arm gets
  its full three attempts again (review C-3).
- **The tests phase (run b, final fix batch A1)**: everything after the attempt — idle wait, export and install,
  hidden tests, quality, evidence — is fault-handled like the attempt: a container, git or subprocess error there
  is `infra-hidden` / `infra-quality` / `infra-evidence` (the prep's network failure is `infra-sync`, A2), ledgered
  (a repeat halts), and after the owner's fix the SAME commit is tested again, never a new arm session. The attempt
  is persisted in `tests-pending.json` first, so an owner park there returns a parked step (`parked.json` phase
  "tests") and a park, decline, halt or crash resumes at the tests on the next `run_step` (the caller must not
  restore while the file exists). An arm with no committed `main` is its own outcome: all-failed, one attempt.
- A drive outcome of `parked` is not a fault (ruling 1): `parked.json` records it and the step returns
  `status="parked"` — no hidden tests, not counted as an arm attempt.
- **On `Halt`, `Paused` or a `parked` result, stepflow leaves the tree mid-step** (nothing is restored, so the
  owner can inspect it): the caller (Task 23) must restore the existing pre-step snapshot (`ctx.snapshot`, or the
  step's) before the step runs again (review I-2).
- Hidden tests (run b): a harness flake (flaky on the reference too) is `flaky-test:<nodeid>` and a hidden
  `harness-fault` attribution is `infra-hidden:<why>`; both are ledger faults that RE-TEST the same commit after
  the owner's fix (no new arm session). `arm-resource` (re-run once by `hidden`, then all-failed) and `arm-output`
  (all-failed) are the arm's results, never harness faults; every resource exhaustion is recorded per (pass,
  step, arm) with `faults.record_resource` for Task 23's cross-arm count (`limits.suite_resource_arms`).
- `new_discriminating_passed == 0` is no progress: the next attempt gets `messages.no_progress` in the same
  session; after `limits.attempts_no_progress` (3) the arm stops at this step (`arm-result.json`, OD3).

`hand_edit(ctx, step1_tests)` wraps `handedit.apply` (called once per arm before step 2's first run, Task 23) with
the same ledger rule; every try's teammate turns are kept on the returned `HandEdit.turns`, which the caller passes
to `run_step(..., extra={"teammate": edit.turns})` (ruling 7).
"""
from __future__ import annotations
import json, re, shutil, subprocess, time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from runner import checklist, docker, drive, evidence, faults, gitops, handedit, handoff, hidden, preflight, quality, \
    repo, secrets, transcripts
from runner.faults import HarnessFault
from runner.owner import Park

RUNS = ("a", "b")


class Halt(Exception):
    """The same harness fault twice since the last owner resolution: the whole bake-off halts (design §9)."""


class Paused(Exception):
    """The owner declined (or parked) a harness-fault prompt: the step stops here, the fault is recorded, the tree is
    left as it is. `park` carries the owner's `Park` when they parked."""

    def __init__(self, reason: str = "", park: Park | None = None):
        super().__init__(reason)
        self.park = park


@dataclass
class StepOutcome:
    status: str                  # run b: "done" | "stopped" | "parked"; run a: "discovered" | "parked"
    attempts: int                # arm attempts since the last harness restore (run a: 1, or 0 when parked)
    hidden: hidden.Summary | None = None
    quality: dict = field(default_factory=dict)
    park: Park | None = None
    run: str = "b"
    attempt_outcome: str | None = None       # drive's outcome of the last attempt
    discovery: dict | None = None            # run a: why the discovery run stopped (drive's `AttemptResult.discovery`)


# ---- evidence moves --------------------------------------------------------------------------------------------

def park(out: Path, k: int, label: str) -> None:
    """Move attempt k's evidence under attempts/<k>-<label>/. Hidden results always; for a harness label also its
    turns, transcripts, PO files and its questions / owner-gates lines, so a faulted attempt leaves nothing on top."""
    dest = out / "attempts" / f"{k}-{label}"; dest.mkdir(parents=True, exist_ok=True)
    earlier = out / "attempts" / f"{k}-no-progress"
    if label.startswith("harness-") and earlier.exists():      # a no-progress attempt later discarded by a fault
        shutil.move(str(earlier), str(dest / "no-progress"))
    if (out / "hidden").exists():
        shutil.move(str(out / "hidden"), str(dest / "hidden"))
    if label.startswith("harness-"):
        for f in list((out / "turns").glob(f"*-a{k}-*")) if (out / "turns").exists() else []:
            (dest / "turns").mkdir(exist_ok=True); shutil.move(str(f), str(dest / "turns" / f.name))
        if (out / "transcripts" / f"a{k}").exists():
            shutil.move(str(out / "transcripts" / f"a{k}"), str(dest / "transcripts"))
        for d in list((out / "po").glob(f"a{k}-*")) if (out / "po").exists() else []:
            (dest / "po").mkdir(exist_ok=True); shutil.move(str(d), str(dest / "po" / d.name))
        for name in ("questions.jsonl", "owner-gates.jsonl"):
            f = out / name
            if f.exists():
                keep, moved = [], []
                for l in f.read_text().splitlines():
                    if l.strip():
                        (moved if json.loads(l).get("attempt") == k else keep).append(l)
                f.write_text("".join(x + "\n" for x in keep))
                if moved:
                    (dest / name).write_text("".join(x + "\n" for x in moved))
    (dest / "attempt.json").write_text(json.dumps({"attempt": k, "label": label}))


# ---- the owner ------------------------------------------------------------------------------------------------

def _confirm_or_pause(ctx, text: str) -> None:
    got = ctx.owner.confirm(text)
    if isinstance(got, Park):
        raise Paused(f"the owner parked: {text}", park=got)
    if not got:
        raise Paused(f"the owner declined: {text}")


def wait_idle(ctx) -> None:
    detail = ""
    for _ in range(20):
        ok, detail = preflight.idle()
        if ok:
            return
        time.sleep(30)
    _confirm_or_pause(ctx, f"The machine is not idle ({detail}). Run the hidden tests anyway?")


def _breach_seen(ctx) -> bool:
    f = ctx.paths.results / "breaches.json"
    return f.exists() and bool(json.loads(f.read_text()))


def _note_breach(ctx, what: str, verdict: str) -> None:
    f = ctx.paths.results / "breaches.json"; f.parent.mkdir(parents=True, exist_ok=True)
    prior = json.loads(f.read_text()) if f.exists() else []
    f.write_text(json.dumps(prior + [{"step": ctx.step, "breach": what, "owner": verdict}], indent=2))


# ---- pins -----------------------------------------------------------------------------------------------------

def _evidence_pin(ctx, attempt: int, before: dict, ar) -> transcripts.PinReport:
    """Collect attempt `attempt`'s transcripts (every container has exited) and pin-check them with the runner's
    own streams (ruling 4). The report is kept beside the transcripts, so `park` moves it with them."""
    skipped: list[dict] = []
    dest = ctx.out / "transcripts" / f"a{attempt}"
    files = transcripts.collect(ctx.paths.config_dir, before, dest, skipped=skipped)
    streams = {t.stream_path: t.outcome for t in (ar.turns if ar is not None else []) if t.stream_path}
    pin = transcripts.verify_pin(files, list(streams), ctx.pins, unsafe=skipped, stream_outcomes=streams)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "model-pin.json").write_text(pin.to_json())
    return pin


def _pin_fault(pin) -> HarnessFault | None:
    """A clean attempt's pin report as a fault: never passes vacuously (as drive's check of the PO's report)."""
    if (f := faults.classify_pin(pin, "arm")):
        return f
    if not pin.ok:
        return HarnessFault("model-pin", "unverified", f"arm: unverified streams {pin.unverified_streams}")
    if pin.stream_assistant_messages == 0:
        return HarnessFault("model-pin", "no-stream-evidence", "arm: no runner-captured stream was inspected")
    return None


def _behind(f: HarnessFault, pin) -> HarnessFault:
    """The fault to record for an attempt that RAISED `f` (ruling 3). An off-pin model in its evidence wins over
    everything but a credential fault (the hand edit's precedence); a missing-evidence report does not (the fault
    may have come before any assistant message)."""
    if f.kind in ("infra-auth", "credential-persisted") or not pin.violations:
        return f
    pf = faults.classify_pin(pin, "arm")
    if pf is None:
        return f
    return HarnessFault(pf.kind, pf.signature, f"{pf.detail}; the attempt raised {f.kind}: {f.signature}")


def _faulted(ctx, f: HarnessFault, attempt: int, before: dict, ar) -> HarnessFault:
    """The fault to record for an attempt that raised `f`. If collecting or pin-checking its evidence fails too,
    the ORIGINAL fault is still what is recorded, with the evidence error as a note (fix round 1 L-2)."""
    try:
        pin = _evidence_pin(ctx, attempt, before, ar)
    except Exception as e:
        note = f"collecting the attempt's evidence failed too: {e!r}"
        f.add_note(note)
        f.detail = f"{f.detail}; {note}" if f.detail else note
        return f
    return _behind(f, pin)


# ---- faults ---------------------------------------------------------------------------------------------------

def _sig(text: str | None) -> str:
    first = (text or "").removeprefix("harness-fault:").strip().splitlines()
    return re.sub(r"\d", "", first[0] if first else "").strip()[:80] or "unknown"


def _record(ctx, f: HarnessFault, attempt: int, run: str | None) -> None:
    if faults.record(f, ctx.pass_, ctx.arm.name, ctx.step, attempt, run=run) == "halt":
        raise Halt(faults.halted(ctx.pass_)) from f


def _restore_target(ctx):
    return ctx.snapshot if ctx.snapshot is not None else ctx.step


def _restore(ctx) -> None:
    repo.restore(ctx.paths, _restore_target(ctx))
    ctx.later_sent = 0                        # ruling 2: the re-run re-sends the first message, and CR-B with it


def _handle_fault(ctx, f: HarnessFault, parked: list[int], run: str) -> None:
    for k in parked:
        park(ctx.out, k, f"harness-{f.kind}")
    _record(ctx, f, parked[-1] if parked else 0, run)
    _confirm_or_pause(ctx, f"Harness fault {f.kind}: {f.signature}. Fix it, then re-run step {ctx.step} "
                           f"({run}) from its snapshot now?")
    _restore(ctx)


# ---- hidden tests (run b) ---------------------------------------------------------------------------------------

def _hidden_run(ctx, prep, attempt: int, install_failed: bool) -> hidden.Summary:
    s = hidden.run(ctx.paths, prep.hidden_copy, ctx.step, ctx.out, install_failed,
                   install=hidden.install_record(prep.prep.get("hidden")))
    if s.attribution == "arm-resource":                         # died of resources twice: all-failed
        faults.record_resource(ctx.pass_, ctx.arm.name, ctx.step, attempt, "repeat", s.resource_evidence)
    elif len(s.resource_evidence) >= 2:                          # died once, the re-run completed
        faults.record_resource(ctx.pass_, ctx.arm.name, ctx.step, attempt, "once", s.resource_evidence)
    return s


def _settle(ctx, prep, summary: hidden.Summary, attempt: int, install_failed: bool) -> hidden.Summary:
    """Harness problems with the tests themselves: record, let the owner fix, re-test the SAME commit."""
    while True:
        if not summary.scoreable:                                # ruling 5: a hidden harness-fault is infra
            f = HarnessFault("infra-hidden", _sig(summary.attribution), summary.attribution or "")
            _record(ctx, f, attempt, "b")
            _confirm_or_pause(ctx, f"Hidden-test harness fault: {summary.attribution}. Fix it, then re-test "
                                   f"this commit?")
        elif summary.flaky:                                      # harness flakes only (review C-2)
            flaky = [t for t, o in summary.tests.items() if o == "flaky"]
            for t in flaky:
                _record(ctx, HarnessFault("flaky-test", hidden.to_nodeid(t)), attempt, "b")
            _confirm_or_pause(ctx, f"Hidden test(s) flaky on the reference too: {flaky}. Fix, then re-test "
                                   f"this commit?")
        else:
            return summary
        summary = _hidden_run(ctx, prep, attempt, install_failed)          # same SHA, no new session


def _arm_result(ctx, summary: hidden.Summary) -> None:
    f = ctx.paths.results / "arm-result.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"stopped_at": ctx.step,
                             "reason": f"no progress in {ctx.pins.limits.attempts_no_progress} attempts",
                             "last_hidden": asdict(summary)}, indent=2))


# ---- the tests phase (run b, after the arm's attempt): faults, parks, resume (final fix batch A1) -----------------
# Everything after the arm's attempt — waiting for an idle machine, exporting and installing `main`, the hidden tests,
# quality, the evidence — is the harness's own work. A container, git or subprocess error there is a harness fault
# of that phase (`infra-hidden`, `infra-quality`, `infra-evidence`; `infra-sync` is raised by `hidden` itself, A2):
# recorded in the ledger (the second identical one halts), and after the owner's fix the SAME commit is tested
# again — never a new arm session. The attempt is persisted in `tests-pending.json` before the tests phase starts,
# so a park, a pause, a halt or a crash there resumes at the tests: the caller must NOT restore the snapshot when
# the file exists (orchestrate), and the next `run_step` goes straight back to the tests.
INFRA_ERRORS = (docker.ContainerError, subprocess.SubprocessError, hidden.HiddenError, gitops.GitError)
PENDING = "tests-pending.json"


def _turn_out(t) -> dict:
    return {"session_id": t.session_id, "outcome": t.outcome, "cost_usd": t.cost_usd, "usage": t.usage,
            "model_usage": t.model_usage, "wall_seconds": t.wall_seconds,
            "stream_path": str(t.stream_path) if t.stream_path else None,
            "permission_denials": list(t.permission_denials or [])}


def _turn_in(d: dict):
    from runner.session import TurnResult
    return TurnResult(d.get("session_id"), d.get("outcome", "ok"), "", {}, None, float(d.get("cost_usd") or 0.0),
                      d.get("usage") or {}, d.get("model_usage") or {}, float(d.get("wall_seconds") or 0.0), [],
                      Path(d["stream_path"]) if d.get("stream_path") else None, None,
                      list(d.get("permission_denials") or []))


def _attempt_out(ar) -> dict:
    """What `evidence.finalise` and the next attempt need from an attempt, as JSON."""
    return {"outcome": ar.outcome, "session_id": ar.session_id, "turns": [_turn_out(t) for t in ar.turns],
            "po_turns": [[_turn_out(t) for t in r.turns] for r in ar.po_results], "exchanges": ar.exchanges,
            "interventions": list(ar.interventions), "breach": ar.breach, "retries": ar.retries,
            "park": asdict(ar.park) if ar.park is not None else None}


def _attempt_in(d: dict):
    from types import SimpleNamespace
    return drive.AttemptResult(d["outcome"], d.get("session_id"), turns=[_turn_in(t) for t in d.get("turns", [])],
                               po_results=[SimpleNamespace(turns=[_turn_in(t) for t in ts])
                                           for ts in d.get("po_turns", [])],
                               exchanges=int(d.get("exchanges") or 0), interventions=list(d.get("interventions") or []),
                               breach=d.get("breach"), retries=int(d.get("retries") or 0),
                               park=Park(**d["park"]) if d.get("park") else None)


def _save_pending(ctx, rec: dict) -> None:
    from runner import fsutil
    fsutil.write_json(ctx.out / PENDING, rec)


def _load_pending(ctx) -> dict | None:
    f = ctx.out / PENDING
    return json.loads(f.read_text()) if f.is_file() else None


def _clear_pending(ctx) -> None:
    (ctx.out / PENDING).unlink(missing_ok=True)


def _phase(ctx, kind: str, attempt: int, what: str, fn, pend: dict | None = None):
    """`fn()` under the tests-phase fault rule: a harness fault (or a container/git/subprocess error, as `kind`)
    is recorded (a repeat halts), the owner fixes it and `fn` runs again on the same commit. An owner park or
    decline raises `Paused`, which `run_step` turns into a parked step (park) or lets through (decline)."""
    while True:
        try:
            return fn()
        except HarnessFault as f:
            fault = f
        except INFRA_ERRORS as e:
            fault = HarnessFault(kind, _sig(str(e)), repr(e)[:500])
        if pend is not None:                           # recorded in hidden/summary.json (A2)
            pend.setdefault("retests", []).append({"kind": fault.kind, "signature": fault.signature,
                                                   "detail": fault.detail[:300]})
            _save_pending(ctx, pend)
        _record(ctx, fault, attempt, "b")
        _confirm_or_pause(ctx, f"Harness fault {fault.kind}: {fault.signature} ({what}). Fix it, then {what} again "
                               f"on the same commit (no new arm session)?")


# ---- arm-caused events (final fix batch A5, owner): arm violations, never the harness ledger, never a halt ---------
ARM_DRIFT = ("common.git-identity", "common.origin", "common.no-foreign-plugins")   # checks the arm itself can break
VIOLATIONS = "arm-violations.jsonl"


def _arm_checks(ctx, attempt: int, run: str) -> list[dict]:
    """After the arm's attempt: setup drift the arm caused (git identity or origin changed, a plugin installed —
    the step-mode verify's ARM_DRIFT checks) and the arm's OWN GitHub token in the evidence (redacted in place,
    in the step's evidence and the arm's transcripts). Each is an arm violation in `arm-violations.jsonl`; the
    caller fails the attempt. Other step checks stay orchestrate's (`setup-drift` harness faults)."""
    found = [{"kind": "setup-drift", "check": c.id, "detail": c.detail[:300]}
             for c in checklist.verify(ctx.paths, ctx.arm, "step") if c.status == "fail" and c.id in ARM_DRIFT]
    files = secrets.redact([ctx.out, ctx.paths.config_dir], secrets.own_pat_values(ctx.paths, ctx.arm, ctx.cred))
    if files:
        found.append({"kind": "own-token-in-evidence", "files": files[:50]})
    with open(ctx.out / VIOLATIONS, "a") as fh:
        for v in found:
            fh.write(json.dumps({"at": time.time(), "run": run, "attempt": attempt, **v}) + "\n")
    return found


def _resource(ctx, attempt: int, ar) -> None:
    """A5: an arm session killed for memory is the owner's resource rule (`hidden`'s, for the session): re-run once
    by drive, then all-failed; every occurrence counts towards `suite_resource_arms`."""
    ev = [[f"session-oom:turn {e.get('turn')} exit {e.get('exit')}"] for e in ar.resource_events]
    if ar.outcome == "arm-resource":
        faults.record_resource(ctx.pass_, ctx.arm.name, ctx.step, attempt, "repeat", ev)
    elif ev:
        faults.record_resource(ctx.pass_, ctx.arm.name, ctx.step, attempt, "once", ev)


def _failed_why(pend: dict) -> str | None:
    if pend["ar"]["outcome"] == "arm-resource":
        return "arm-resource: session"
    kinds = sorted({v["kind"] for v in pend.get("violations") or []})
    return f"arm-violation: {','.join(kinds)}" if kinds else None


def _tests(ctx, attempt: int, pend: dict):
    """wait for idle, then the hidden tests on the attempt's commit. Returns (summary, prep or None)."""
    if "violations" not in pend:
        pend["violations"] = _phase(ctx, "infra-verify", attempt, "check the arm's setup and evidence",
                                    lambda: _arm_checks(ctx, attempt, "b"), pend)
        _save_pending(ctx, pend)
    if (why := _failed_why(pend)):                     # A5: the attempt fails, all-failed, arm code never run
        s = _phase(ctx, "infra-hidden", attempt, "score the attempt",
                   lambda: hidden.all_failed(ctx.paths, ctx.step, ctx.out, why), pend)
        if ctx.acceptance is not None:
            s.acceptance = {"outcome": "failed", "detail": why, "regressions": [], "progress": False}
            s.write(ctx.out)
        return s, None
    wait_idle(ctx)
    if "sha" not in pend:
        pend["sha"] = _phase(ctx, "infra-hidden", attempt, "read the arm's main",
                             lambda: gitops.main_sha(ctx.paths))
        _save_pending(ctx, pend)
    sha = pend["sha"]
    if sha is None:                                    # no committed main: the arm's own outcome, all-failed
        s = _phase(ctx, "infra-hidden", attempt, "score the attempt",
                   lambda: hidden.all_failed(ctx.paths, ctx.step, ctx.out, hidden.NO_MAIN), pend)
        if ctx.acceptance is not None:
            s.acceptance = {"outcome": "failed", "detail": hidden.NO_MAIN, "regressions": [], "progress": False}
            s.write(ctx.out)
        return s, None

    def go():
        prep = hidden.prepare(ctx.paths, sha, f"{ctx.step:02d}-a{attempt}", ctx.out, with_quality=True)
        install_failed = not prep.prep.get("hidden", {}).get("ok", False)
        s = _settle(ctx, prep, _hidden_run(ctx, prep, attempt, install_failed), attempt, install_failed)
        if ctx.acceptance is not None:
            s.acceptance = _acceptance(ctx, prep, s, install_failed)
            s.write(ctx.out)
        return s, prep
    summary, prep = _phase(ctx, "infra-hidden", attempt, "run the hidden tests", go, pend)
    if pend.get("retests"):
        summary.harness_retests = list(pend["retests"])
        summary.write(ctx.out)
    return summary, prep


# ---- outcomes that end the step without scoring ------------------------------------------------------------------

def _parked(ctx, attempt: int, ar, pk: Park, arm_attempts: int, run: str, phase: str = "attempt") -> StepOutcome:
    (ctx.out / "parked.json").write_text(json.dumps(
        {"run": run, "phase": phase, "attempt": attempt, "arm_attempts_before": arm_attempts,
         "outcome": ar.outcome if ar else None, "park": asdict(pk),
         "code_check": getattr(ar, "code_check", None) if run == "a" else None}, indent=2))
    return StepOutcome("parked", arm_attempts, park=pk, run=run, attempt_outcome=ar.outcome if ar else None)


def _discovered(ctx, attempt: int, ar, pin, t0: float, extra: dict, violations: list | None = None) -> StepOutcome:
    out = ctx.out
    po_turns = [t for r in ar.po_results for t in r.turns]
    (out / "cost.json").write_text(json.dumps(evidence.cost(
        {"arm": ar.turns, "po": po_turns, "harness": [t for ts in extra.values() for t in ts]}), indent=2))
    (out / "model-pin.json").write_text(pin.to_json())
    (out / "discovery.json").write_text(json.dumps(
        {"run": "a", "pass": ctx.pass_, "arm": ctx.arm.name, "step": ctx.step, "outcome": ar.outcome,
         "discovery": ar.discovery, "code_check": ar.code_check, "attempt": attempt,
         "harness_restores": attempt - 1, "breach": ar.breach,
         "exchanges": ar.exchanges, "interventions": ar.interventions, "model_pin_ok": pin.ok,
         "sha_before": ctx.sha_before, "started": t0, "ended": time.time(), "arm_violations": violations or [],
         "resource_events": ar.resource_events,
         "harness_faults": [e for e in faults.for_step(ctx.pass_, ctx.arm.name, ctx.step) if e.get("run") == "a"]},
        indent=2))
    _restore(ctx)                                    # N.b starts from the same pre-step commit (design §5)
    return StepOutcome("discovered", 1, run="a", attempt_outcome=ar.outcome, discovery=ar.discovery)


# ---- the step -------------------------------------------------------------------------------------------------

def run_step(ctx, first_message: str, extra: dict | None = None, run: str = "b") -> StepOutcome:
    if run not in RUNS:
        raise ValueError(f"run is 'a' (discovery) or 'b' (scored), not {run!r}")
    if run == "a" and ctx.out.name != "a":
        raise ValueError(f"run a keeps its evidence under the step's a/ directory, not {ctx.out}")
    extra, t0 = extra or {}, time.time()
    ctx.run = run                                    # A3: drive and the tracker use N.a's discovery repo
    attempt, arm_attempts, history, since_restore = 0, 0, [], []
    message, resume = first_message, None
    lim = ctx.pins.limits
    kw = {"stop_at_first_gate_or_code": True} if run == "a" else {}
    pend = _load_pending(ctx) if run == "b" else None
    while True:
        if pend is not None:                         # resume at the tests: the attempt already ran (A1)
            attempt, arm_attempts, t0 = pend["attempt"], pend["arm_attempts"], pend["t0"]
            since_restore = list(pend["since_restore"])
            history = [_attempt_in(d) for d in pend["history"]]
            ar = _attempt_in(pend["ar"])
            pin = transcripts.PinReport(**pend["pin"])
            ctx.later_sent = int(pend.get("later_sent", ctx.later_sent))
        else:
            attempt += 1
            before = transcripts.snapshot(ctx.paths.config_dir)
            owner_park: Park | None = None
            try:
                try:
                    ar = drive.run_attempt(ctx, attempt, message, resume, **kw)
                except HarnessFault as f:
                    raise _faulted(ctx, f, attempt, before, getattr(f, "attempt_result", None))
                except checklist.NotReady:
                    raise                                # a precondition, never a fault: the caller refuses the arm
                except (docker.ContainerError, subprocess.SubprocessError) as e:     # a failed container (L-1)
                    f = HarnessFault("infra-container", _sig(str(e)), repr(e)[:500])
                    raise _faulted(ctx, f, attempt, before, None) from e
                pin = _evidence_pin(ctx, attempt, before, ar)
                if (pf := _pin_fault(pin)):
                    raise pf
                if run == "b" and ar.breach and lim.owner_reclassifies_first_breach and not _breach_seen(ctx):  # OD14 B
                    verdict = ctx.owner.reclassify(ar.breach, f"step {ctx.step}, attempt {attempt}")
                    if isinstance(verdict, Park):
                        owner_park = verdict
                    else:
                        _note_breach(ctx, ar.breach, verdict)
                        if verdict == "harness":
                            raise HarnessFault("runaway", ar.breach,
                                               f"owner reclassified the first breach (step {ctx.step})")
            except HarnessFault as f:
                _handle_fault(ctx, f, since_restore + [attempt], run)
                since_restore, arm_attempts, history = [], 0, []                                    # review C-3
                if ctx.on_restore is not None:          # step 6: the old issue is superseded, a new one created
                    first_message = ctx.on_restore() or first_message
                message, resume = first_message, None
                continue
            if owner_park is not None:
                return _parked(ctx, attempt, ar, owner_park, arm_attempts, run)
            if ar.outcome == "parked":                                                          # ruling 1
                return _parked(ctx, attempt, ar, ar.park, arm_attempts, run)
            _resource(ctx, attempt, ar)
            if run == "a":
                try:
                    violations = _arm_checks(ctx, attempt, "a")
                except INFRA_ERRORS as e:              # N.a is unscored: record that the check could not run
                    violations = [{"kind": "check-unavailable", "detail": repr(e)[:300]}]
                return _discovered(ctx, attempt, ar, pin, t0, extra, violations)
            arm_attempts += 1
            since_restore.append(attempt)
            pend = {"attempt": attempt, "arm_attempts": arm_attempts, "since_restore": since_restore, "t0": t0,
                    "history": [_attempt_out(a) for a in history], "ar": _attempt_out(ar),
                    "pin": json.loads(pin.to_json()), "later_sent": ctx.later_sent}
            _save_pending(ctx, pend)
        try:
            got = _decide(ctx, attempt, arm_attempts, history, ar, pin, t0, extra, pend)
        except Paused as x:
            if x.park is None:
                raise                                    # the owner declined: the tests resume when run again
            return _parked(ctx, attempt, ar, x.park, arm_attempts, run, phase="tests")
        drift = any(v.get("kind") == "setup-drift" for v in pend.get("violations") or [])
        pend = None
        if drift:                                        # A5: the arm's drift is repaired by the step's restore
            _restore(ctx)
        if got is not None:
            return got
        park(ctx.out, attempt, "no-progress")
        history.append(ar)
        message, resume = handoff.MESSAGES["no_progress"], ar.session_id
        if drift:                                        # a fresh session from the restored tree
            if ctx.on_restore is not None:
                first_message = ctx.on_restore() or first_message
            message, resume = first_message, None


def _acceptance(ctx, prep, s: hidden.Summary, install_failed: bool) -> dict:
    """A4 (owner): a substitute step-6 bug is scored by the owner's acceptance test on this commit, beside the
    standard suite. Progress = the test passes AND no hidden test that passed on the step-5 commit (the precheck
    baseline) fails now. The test reaches the tester like the hidden suite (streamed into the uid-1000 0700
    /harness, never mounted, never in the arm's home or work). An install failure is the arm's: the test fails,
    unrun. A run that did not complete is the harness's (`infra-hidden`, re-tested on the same commit)."""
    base = ctx.acceptance.get("baseline") or {}
    regressions = sorted(t for t, o in base.items() if o == "passed" and s.tests.get(t) not in ("passed", "flaky"))
    if install_failed:
        return {"outcome": "failed", "detail": "install failed", "regressions": regressions, "progress": False}
    r = hidden.run_acceptance(ctx.paths, prep.hidden_copy, ctx.step, ctx.acceptance["body"])
    if r.get("outcome") == "error":
        raise HarnessFault("infra-hidden", "acceptance test did not complete", str(r.get("detail"))[:500])
    return {**r, "regressions": regressions, "progress": r.get("outcome") == "passed" and not regressions}


def _decide(ctx, attempt, arm_attempts, history, ar, pin, t0, extra, pend) -> StepOutcome | None:
    """The tests phase of one arm attempt and the step's decision; None = no progress, the next attempt follows."""
    lim = ctx.pins.limits
    t_tests = time.time()
    summary, prep = _tests(ctx, attempt, pend)
    tests_s = time.time() - t_tests
    progressed = summary.acceptance["progress"] if summary.acceptance is not None \
        else summary.new_discriminating_passed > 0                 # A4: a substitute is scored by its test
    if not (progressed or arm_attempts >= lim.attempts_no_progress):
        _clear_pending(ctx)
        return None
    q = _phase(ctx, "infra-quality", attempt, "run quality",
               lambda: quality.run_all(ctx.paths, prep, ctx.out, ctx.pins)) if prep is not None \
        else {"skipped": summary.attribution}
    outcome = "done" if progressed else "stopped"
    _phase(ctx, "infra-evidence", attempt, "write the step's evidence", lambda: evidence.finalise(
        ctx, attempts=history + [ar], extra_turns=extra, hidden=summary, quality=q, pin=pin,
        sha_before=ctx.sha_before, started=t0, ended=time.time(),
        fault_entries=[e for e in faults.for_step(ctx.pass_, ctx.arm.name, ctx.step)
                       if e.get("run") != "a"],     # L-5: run b and step-level
        shas=ctx.shas, tests_seconds=tests_s, outcome=outcome))
    if outcome == "stopped":
        _arm_result(ctx, summary)
    _clear_pending(ctx)
    return StepOutcome(outcome, arm_attempts, summary, q, attempt_outcome=ar.outcome)


# ---- the step-2 hand edit ---------------------------------------------------------------------------------------

def hand_edit(ctx, step1_tests: dict[str, str]) -> handedit.HandEdit:
    """`handedit.apply` under the ledger rule: a fault (after its own second try, where it retries) is recorded;
    the second identical one halts; otherwise the owner fixes it and the hand edit runs again from `02-pre-edit`
    (apply restores it on every failure). Every try's teammate turns end up on the returned `HandEdit.turns`."""
    prior: list = []
    while True:
        try:
            edit = handedit.apply(ctx, step1_tests)
        except HarnessFault as f:
            prior += list(getattr(f, "hand_edit_turns", None) or [])
            f.hand_edit_turns = prior
            _record(ctx, f, 0, None)
            _confirm_or_pause(ctx, f"Hand edit failed ({f.kind}: {f.signature}). Fix it, then run it again from "
                                   f"{handedit.PRE_EDIT}?")
            continue
        edit.turns = prior + list(edit.turns)
        return edit
