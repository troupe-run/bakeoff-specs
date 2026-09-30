"""The turn loop for ONE attempt at a step (design §7; plan Task 15).

OD19: one arm session per attempt, resumed every turn; a fresh session only before a command the arm's config
cites in `fresh_session_before`. After each arm turn the product-owner agent (`po.decide`) classifies the arm's
message and the runner replies: PO answers, owner escalations (appended to the brief), owner approval gates
(OD7), the method's own next command (review F-2), "Please continue.", or — when the PO says the step is done —
any pending closer (OD24 B export, then `must_run`), the one-time commit nudge (OD4 A), a pending CR-B (OD6 B),
and only then the end of the attempt.

What ends an attempt:
  done      the PO said step_done and nothing was pending
  stalled   more than `limits.exchanges_per_attempt` exchanges (OD14; `breach="exchanges"`)
  timeout   an arm turn ran over `limits.turn_seconds` (`breach="turn_seconds"`)
  discovery-stop
            (only with `stop_at_first_gate_or_code=True`: the N.a discovery run, design §5 / Task 22 ruling 6)
            the PO classified the arm's message as an approval request (the owner is NOT asked; the entry is
            logged with `owner_action="discovery-stop"`), or an arm turn authored code outside the arm's spec
            paths and the pinned docs paths (`outside_spec`; checked before the PO sees the turn). "Authored" is
            `gitops.changed_since` against `gitops.content_state` taken once at the attempt's start, after
            `recover` (and so after any restore): a path counts only when its content is a blob that was not at
            that path then, so what an earlier step left behind never counts (fix rounds 1-2, I-1). If the check
            cannot run, the attempt goes on: `AttemptResult.code_check` records it as "unavailable" with the
            reason — never a harness fault, so an arm's own git state can never halt the bake-off.
            At step 5 the PO classifies every arm message BEFORE a CR-B pre-emption in this mode (fix round
            1, L-3), so a gate on the pre-empted turn still stops the run; CR-B timing is unchanged from N.b.
            `AttemptResult.discovery` says which, at which turn
  parked    an owner prompt (gate or escalation) returned `owner.Park` — recorded, never treated as an answer,
            never appended to the brief (Task 15 ruling 1); the caller parks the arm and moves on. With several
            escalations in one message, answers the owner gave BEFORE the park are real answers and stay
            appended to the brief (and committed on real passes); only the parked question is not. The entry's
            `answered_by` names who did answer ("po", "owner", "po+owner"; "runner" when nobody did)
and every harness fault is raised as `faults.HarnessFault` (with `.attempt_result` carrying the turns so far,
for evidence). Transient API errors are retried in place first (review C-4).

Rulings honoured here (Task 15): the setup must be clean and green before any turn (`checklist.require_clean_
green`) and an interrupted restore is recovered before the arm's home is touched (`repo.recover`); the PO's pin
report is checked on every decision and never passes vacuously; `auth_failed` is `infra-auth` for the arm and the
PO alike and takes precedence over everything else about the turn; at step 5 the PO sees CR-A only until CR-B has
been sent (`po.step_view(..., crb_sent=...)`, which needs `StepCtx.contract`). This module never collects
transcripts: the caller (Task 22 `stepflow`) does, after `run_attempt` returns, when every container has exited.
"""
from __future__ import annotations
import dataclasses, fnmatch, json, re, subprocess, time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from runner import checklist, commands, config, credentials, docker, egress, faults, gitops, handoff, \
    owner as owner_mod, po, repo, session, transcripts
from runner.config import Arm, Pins
from runner.docker import Mount
from runner.faults import HarnessFault
from runner.paths import Paths

MESSAGES = handoff.MESSAGES
EXPORT_COMMAND = "/speckit-taskstoissues"            # OD24: the only export command; used when arm.export_after is set
# Fix round 1: an HTTP status is only read IN CONTEXT ("API Error: 529", "status 503", "HTTP 502",
# "500 Internal ...") — never any number that happens to lie in 500-599 ("max_tokens 512").
_STATUS = r"(?:API Error:?|status(?: code)?:?|HTTP(?:/\d(?:\.\d)?)?)\s*"
_SERVER_REASON = r"(?:Internal|Bad Gateway|Service Unavailable|Gateway Time-?out|overloaded|server error)"
TRANSIENT_RE = re.compile(rf"{_STATUS}5\d\d\b|\b5\d\d\s+{_SERVER_REASON}|overloaded|\bapi_error\b|rate.?limit|"
                          r"timed? ?out|ECONNRESET|socket hang up", re.I)
# A clear client error (4xx other than 408 timeout / 429 rate limit) is the request's fault: never retried,
# whatever `api_retry` events preceded it.
CLIENT_ERROR_RE = re.compile(rf"{_STATUS}4(?!08|29)\d\d\b|\binvalid_request_error\b", re.I)


@dataclass
class StepCtx:
    pass_: str
    arm: Arm
    step: int
    paths: Paths
    pins: Pins
    out: Path
    contract_in_force: str      # the PO's contract view when `contract` is None (never at step 5)
    step_brief: str             # the step's brief, verbatim (step 5: with both `## CR-A` and `## CR-B`)
    brief_path: Path
    cred: object
    owner: object
    sha_before: str
    later_messages: list[str] = field(default_factory=list)
    sleep: Callable[[float], None] = time.sleep
    shas: dict = field(default_factory=dict)          # po_brief_at_handoff, contract, step_brief (evidence)
    snapshot: int | str | None = None                 # the snapshot a harness re-run restores (None = the step)
    on_restore: Callable[[], str | None] | None = None # after a harness restore: returns a new first message (step 6)
    contract: str | None = None  # the FULL contract: the PO's view is then `po.step_view` (required at step 5)
    later_sent: int = 0          # how many `later_messages` were sent (drive state across attempts; a harness
                                 # restore that re-sends the first message must reset it to 0)
    acceptance: dict | None = None  # N.b at step 6 with a substitute bug (A4): {"body": the owner's acceptance test,
                                 # "baseline": the precheck's hidden outcomes on the step-5 commit}
    run: str = "b"               # "a" (N.a discovery) | "b" (N.b scored): N.a's GitHub tracker is the arm's
                                 # discovery repo (final fix batch A3; set by stepflow.run_step)


@dataclass
class AttemptResult:
    outcome: Literal["done", "stalled", "timeout", "parked", "discovery-stop"]
    session_id: str | None
    turns: list = field(default_factory=list)
    po_results: list = field(default_factory=list)
    exchanges: int = 0
    interventions: list[str] = field(default_factory=list)
    breach: str | None = None
    retries: int = 0
    park: owner_mod.Park | None = None
    discovery: dict | None = None        # discovery-stop: {"why": "approval"|"code", "turn": n[, "paths": [...]]}
    code_check: dict | None = None       # discovery mode: {"status": "ok"|"unavailable", "reasons": [{turn, reason}]}


class _Parked(Exception):
    def __init__(self, park: owner_mod.Park):
        self.park = park


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sig(text: str) -> str:
    first = text.splitlines()[0] if text else ""
    return re.sub(r"\d", "", first)[:80]


def _transient(r: session.TurnResult) -> str | None:
    """Why the turn failed transiently, or None. `no_result`; an `is_error` whose text reads like an API
    overload/5xx (in context)/rate limit/timeout; or an `is_error` after Claude Code's own `api_retry` events (a retry storm
    it gave up on — `TurnResult.retries`), which is the API's failure, not the arm's. A clear 4xx (not 408/429)
    is never transient, even after `api_retry` events."""
    if r.outcome == "no_result":
        return "no_result"
    if r.outcome != "is_error":
        return None
    if CLIENT_ERROR_RE.search(r.final_text or ""):
        return None
    if TRANSIENT_RE.search(r.final_text or ""):
        return _sig(r.final_text)
    if r.retries:
        last = r.retries[-1] if isinstance(r.retries[-1], dict) else {}
        return f"api-retry:{last.get('error') or 'unknown'}"
    return None


def _invoked(cmd: str, turns: list) -> bool:
    """Did the arm itself invoke `cmd` as a Skill during this attempt? One reader: transcripts.invoked_skills
    (preflight m10). Plugin prefixes are ignored (`/opsx:apply` matches `openspec:opsx:apply`'s last part)."""
    want = cmd.split()[0].lstrip("/").split(":")[-1]
    return any(s.split(":")[-1] == want for t in turns if t.stream_path
               for s in transcripts.invoked_skills(t.stream_path))


def _answered_by(by: set[str]) -> str:
    """"po", "owner" or "po+owner" (fix round 1 ruling: the interface's order); "runner" when nobody answered."""
    return "+".join(w for w in ("po", "owner") if w in by) or "runner"


def _cited(answers) -> str | None:
    """The PO's citations for the entries it answered, "; "-joined; None when nothing was cited."""
    return "; ".join(a.cited for a in answers if a.cited and a.cited.strip()) or None


def _log(qa: list, path: Path, entry: dict) -> None:
    qa.append(entry)
    with open(path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _gate_log(ctx: StepCtx, entry: dict) -> None:
    with open(ctx.out / "owner-gates.jsonl", "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _po_view(ctx: StepCtx) -> tuple[str, str]:
    """(step brief, contract in force) for the PO now. Ruling 3: at step 5, CR-A only until CR-B is sent."""
    if ctx.contract is not None:
        return po.step_view(ctx.step, ctx.step_brief, ctx.contract, crb_sent=ctx.later_sent > 0)
    if ctx.step == 5:
        raise ValueError("step 5 needs StepCtx.contract (the full contract): the PO's view depends on whether "
                         "CR-B has been sent (po.step_view), and a precomputed contract would leak or hide it")
    return ctx.step_brief, ctx.contract_in_force


def _check_po_pin(pin) -> None:
    """Ruling 4: the PO's pin report (made by po.decide from its transcripts AND the runner-captured streams)
    must exist, be ok, and show stream evidence — a missing or stream-less report never passes vacuously."""
    if pin is None:
        raise HarnessFault("model-pin", "no-report", "po: the decision came back without a pin report")
    if (f := faults.classify_pin(pin, "po")):
        raise f
    if not pin.ok:
        raise HarnessFault("model-pin", "unverified", f"po: unverified streams {pin.unverified_streams}")
    if pin.stream_assistant_messages == 0:
        raise HarnessFault("model-pin", "no-stream-evidence",
                           "po: the pin report inspected no runner-captured stream (verify_pin needs the streams)")


def _turn(ctx: StepCtx, st, attempt: int, n: int, message: str, resume: str | None) -> session.TurnResult:
    p, pins, arm = ctx.paths, ctx.pins, ctx.arm
    image = pins.images["dryrun"] if arm.dry else arm.image
    env = credentials.session_env(pins, arm, role="arm", isolated=False, resume=resume or "",
                                  mcp=(p.home / ".bk-mcp.json").exists(), pass_=ctx.pass_, disc=ctx.run == "a")
    t = session.Turn(ctx.pass_, arm.name, ctx.step, attempt, n, image, message, env,
                     [Mount(p.home, p.container_home, False), Mount(p.work, "/work", False)], st.net, True,
                     p.container_repo, p.inbox("arm"), "arm", arm.dry, p.config_dir)
    return session.run_turn(t, ctx.cred, ctx.out, pins.limits.turn_seconds)


def _closers(ctx: StepCtx, sent: list[str], turns: list) -> list[str]:
    arm, out = ctx.arm, []
    ran = lambda c: c in sent or _invoked(c, turns)
    if arm.export_after and ran(arm.export_after) and not ran(EXPORT_COMMAND):
        out.append(EXPORT_COMMAND)
    out += [c for c in arm.must_run if not ran(c)]
    return out


def _not_on_main(ctx: StepCtx) -> bool:
    s = gitops.state(ctx.paths)
    return s.dirty or not s.head_in_main or s.main == ctx.sha_before


def _next_later(ctx: StepCtx) -> str:
    text = ctx.later_messages[ctx.later_sent]
    ctx.later_sent += 1
    return handoff.entry_message(ctx.arm, ctx.step, text)


def _matches(path: str, pattern: str) -> bool:
    return path.startswith(pattern) if pattern.endswith("/") else fnmatch.fnmatchcase(path, pattern)


def outside_spec(changed: list[str], arm: Arm, pins: Pins) -> list[str]:
    """The changed paths that are code for the N.a discovery stop: under none of the arm's `spec_paths` and none
    of the pinned `discovery_paths` (a `/`-ended entry is a directory prefix, anything else an fnmatch pattern)."""
    pats = [s.path for s in arm.spec_paths] + [s.path for s in pins.discovery_paths]
    return [c for c in changed if not any(_matches(c, pat) for pat in pats)]


def run_attempt(ctx: StepCtx, attempt: int, message: str, resume: str | None = None, *,
                stop_at_first_gate_or_code: bool = False) -> AttemptResult:
    checklist.require_clean_green(ctx.paths)                  # ruling 8: never drive a dirty or non-green setup
    repo.recover(ctx.paths)                                   # ruling 6: before the arm's home/work is touched
    if ctx.run == "a":                                        # A3: N.a's tracker is the arm's discovery repo
        checklist.install_disc_pat(ctx.paths, ctx.arm, ctx.pass_)
    _po_view(ctx)                                             # ruling 3: refuse a step-5 ctx before any turn
    res = AttemptResult("stalled", resume)
    try:
        baseline = None
        if stop_at_first_gate_or_code:                                                     # I-1
            res.code_check = {"status": "ok", "reasons": []}
            baseline = _code_check(res, 0, lambda: gitops.content_state(ctx.paths)) or {}
        return _run(ctx, attempt, message, res, baseline)
    except HarnessFault as f:
        f.attempt_result = res                                # the turns so far are evidence
        raise


CODE_CHECK_ERRORS = (docker.ContainerError, subprocess.SubprocessError, ValueError, UnicodeError, KeyError)


def _code_check(res: AttemptResult, turn: int, fn):
    """Run one part of the discovery code check; if it cannot run, record why and return None (fix round 2)."""
    try:
        return fn()
    except CODE_CHECK_ERRORS as e:
        res.code_check["status"] = "unavailable"
        res.code_check["reasons"].append({"turn": turn, "reason": f"{type(e).__name__}: {e}"[:500]})
        return None


def _run(ctx: StepCtx, attempt: int, message: str, res: AttemptResult,
         baseline: dict | None = None) -> AttemptResult:
    discovery = baseline is not None
    pins, arm, p = ctx.pins, ctx.arm, ctx.paths
    ctx.out.mkdir(parents=True, exist_ok=True)
    qa_path = ctx.out / "questions.jsonl"
    qa = [json.loads(l) for l in qa_path.read_text().splitlines()] if qa_path.exists() else []
    sent: list[str] = []                                      # leading commands of every message sent this attempt
    turns_ended = 0
    cr_b_after = int(handoff.STEP5.get("cr_b_after_turn", 2))
    po_image = pins.images["dryrun"] if arm.dry else pins.images["base"]
    source = "scripted" if isinstance(ctx.owner, owner_mod.ScriptedOwner) else "real"      # ruling 2

    def send(msg: str, sid: str | None) -> session.TurnResult:
        r = _turn(ctx, st, attempt, len(res.turns) + 1, msg, sid)
        res.turns.append(r)
        if (lead := commands.leading(msg)):
            sent.append(lead)
        if r.outcome == "auth_failed":                       # a credential fault: before anything else (ruling 4)
            raise HarnessFault("infra-auth", "authentication_failed", f"arm turn {len(res.turns)}")
        if r.credential_files:                               # review S-3
            raise HarnessFault("credential-persisted", r.credential_files[0], ", ".join(r.credential_files))
        return r

    with egress.Stage(ctx.pass_, arm.name, "run", pins.egress_run_common + arm.egress_run, ctx.out / "egress.log") as st:
        while True:
            lead = commands.leading(message)
            if lead and any(lead == f["command"] for f in arm.fresh_session_before):     # OD19 B
                res.session_id = None
                res.interventions.append(f"fresh-session:{lead}")
            r = send(message, res.session_id)
            backoff = list(pins.limits.transient_backoff)
            while (why := _transient(r)) and backoff:                                    # review C-4
                res.retries += 1
                res.interventions.append(f"transient-retry:{why}")
                ctx.sleep(backoff.pop(0))
                sid = r.session_id or res.session_id
                r = send(MESSAGES["resume_after_error"] if sid else message, sid)
            if r.outcome == "timeout":
                res.outcome, res.breach = "timeout", "turn_seconds"
                return res
            if r.outcome in ("is_error", "no_result"):
                why = _transient(r)
                raise HarnessFault(f"infra-{r.outcome}", why or _sig(r.final_text) or r.outcome,
                                   (r.final_text or "")[:500])
            res.session_id = r.session_id or res.session_id
            res.exchanges += 1; turns_ended += 1
            changed = _code_check(res, len(res.turns), lambda: gitops.changed_since(p, baseline)) \
                if baseline else None                                                    # {} = no baseline
            if changed and (code := outside_spec(changed, arm, pins)):
                res.outcome = "discovery-stop"                                           # N.a: first code edit
                res.discovery = {"why": "code", "turn": len(res.turns), "paths": code[:50]}
                return res
            if res.exchanges > pins.limits.exchanges_per_attempt:                        # OD14
                res.outcome, res.breach = "stalled", "exchanges"
                return res
            base = {"attempt": attempt, "n": len(res.turns), "at": _now(), "arm_message": r.final_text,
                    "escalated": [], "significant": False, "cited": None, "approved": None,
                    "owner_action": None, "owner_seconds": 0.0, "po_cost_usd": 0.0, "po_retries": 0}
            pending_later = ctx.later_sent < len(ctx.later_messages)
            preempt = pending_later and turns_ended >= cr_b_after
            if preempt and not discovery:                                                # OD6 B
                message = _next_later(ctx)
                _log(qa, qa_path, {**base, "kind": "preempted", "reply": message, "answered_by": "runner"})
                res.interventions.append("step5-cr-b")
                continue
            brief_view, contract_view = _po_view(ctx)
            try:
                pr = po.decide(po.PoContext(ctx.pass_, arm.name, ctx.step, attempt, p, po_image, arm.dry,
                                            contract_view, brief_view, qa, ctx.out, pins=pins),
                               r.final_text, ctx.cred, len(res.turns), ctx.brief_path)
            except po.ProtocolError as e:
                raise HarnessFault("po-protocol", "unparseable", str(e)) from e
            except po.SessionError as e:
                if e.outcome == "auth_failed":                                           # ruling 4
                    raise HarnessFault("infra-auth", "authentication_failed", f"po: {e.detail[:200]}") from e
                raise HarnessFault(f"infra-po-{e.outcome}", _sig(e.detail) or e.outcome, e.detail[:500]) from e
            res.po_results.append(pr)
            _check_po_pin(pr.pin)                                                        # ruling 4 (review C-6)
            dec = pr.decision
            entry = {**base, "kind": dec.kind, "significant": dec.significant, "approved": dec.approved,
                     "po_cost_usd": sum(t.cost_usd for t in pr.turns), "po_retries": pr.retries, "answered_by": "po"}
            if discovery and dec.kind == "approval":                                     # N.a: first gate
                _log(qa, qa_path, {**entry, "answered_by": "runner", "owner_action": "discovery-stop",
                                   "reply": None})
                res.outcome = "discovery-stop"
                res.discovery = {"why": "approval", "turn": len(res.turns)}
                return res
            if preempt:                                   # N.a at step 5: the PO has seen the turn (L-3); now CR-B
                message = _next_later(ctx)
                _log(qa, qa_path, {**entry, "kind": "preempted", "po_kind": dec.kind, "reply": message,
                                   "answered_by": "runner"})
                res.interventions.append("step5-cr-b")
                continue
            try:
                reply = _reply(ctx, dec, r, entry, res, sent, source)
            except _Parked as pk:                                                        # ruling 1
                if dec.kind != "question":
                    entry["answered_by"] = "runner"      # nothing was answered; the runner parked the attempt
                entry |= {"owner_action": "park", "park": asdict(pk.park), "reply": None}
                entry["owner_seconds"] += pk.park.seconds
                if dec.kind == "approval":
                    _gate_log(ctx, {**entry, "po_verdict": dec.reply, "final_reply": None})
                _log(qa, qa_path, entry)
                res.outcome, res.park = "parked", pk.park
                return res
            if reply is None:
                _log(qa, qa_path, {**entry, "reply": None})
                res.outcome = "done"
                return res
            _log(qa, qa_path, {**entry, "reply": reply})
            message = reply


def _reply(ctx: StepCtx, dec, r: session.TurnResult, entry: dict, res: AttemptResult, sent: list[str],
           source: str) -> str | None:
    """The runner's reply to the arm for the PO's decision (None = the attempt is done). Updates `entry`.
    Raises `_Parked` when an owner prompt parks."""
    p, arm = ctx.paths, ctx.arm
    if dec.kind == "question":                                                           # review F-12
        # PO-answered entries first, then escalations in order. A park on a later escalation ends the attempt,
        # but answers the owner already gave stay appended to the brief (they are real answers, fix round 1).
        parts, by = [], set()
        entry["cited"] = _cited([a for a in dec.answers if not a.escalate])
        for i, a in enumerate(dec.answers):
            if not a.escalate:
                by.add("po"); parts.append((i, a.question, a.reply))
        entry["answered_by"] = _answered_by(by)
        for i, a in enumerate(dec.answers):
            if not a.escalate:
                continue
            entry["escalated"].append(a.question)
            got = po.escalate(ctx.owner, a.question, r.final_text, brief_path=ctx.brief_path, pass_=ctx.pass_,
                              arm=arm.name, step=ctx.step, out_dir=ctx.out, source=source)
            if isinstance(got, owner_mod.Park):
                raise _Parked(got)
            entry["owner_seconds"] += got.seconds; by.add("owner")
            entry["answered_by"] = _answered_by(by)
            parts.append((i, a.question, got.answer))
        parts.sort()
        return parts[0][2] if len(parts) == 1 else "\n\n".join(f"On “{q}”: {ans}" for _, q, ans in parts)
    if dec.kind == "approval":                                                           # OD7
        changes = gitops.diffstat(p, ctx.sha_before, "HEAD") + "\n" + gitops.worktree_diffstat(p)
        got = ctx.owner.gate(r.final_text, dec, changes)
        if isinstance(got, owner_mod.Park):
            raise _Parked(got)
        reply, action, secs = got
        entry |= {"answered_by": "po" if action == "accept" else "owner", "owner_action": action,
                  "owner_seconds": secs}
        _gate_log(ctx, {**entry, "po_verdict": dec.reply, "final_reply": reply})
        return reply
    if dec.kind == "next_command":                                                       # review F-2
        inv = commands.invocation(dec.command or "", dec.arguments, commands.installed(p, arm))
        if inv:
            return inv
        res.interventions.append(f"next_command-not-installed:{dec.command}")
        return MESSAGES["continue"]
    if dec.kind == "continue":
        return MESSAGES["continue"]
    closers = _closers(ctx, sent, res.turns)                                             # step_done
    if closers:
        entry["answered_by"] = "runner"
        return closers[0]
    if MESSAGES["commit_on_main"] and "commit_on_main" not in res.interventions and _not_on_main(ctx):   # OD4 A
        entry["answered_by"] = "runner"; res.interventions.append("commit_on_main")
        return MESSAGES["commit_on_main"]
    if ctx.later_sent < len(ctx.later_messages):                                         # OD6 B, before its turn
        entry["answered_by"] = "runner"; res.interventions.append("step5-cr-b")
        return _next_later(ctx)
    return None
