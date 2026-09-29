"""The product-owner agent (design §7, OD7, OD21; plan Task 13).

The PO answers every arm message from a fixed brief (`scenario/po-brief.md`), classifies approval requests for the
owner gates, and escalates what the brief does not cover. Each decision is ONE fresh, isolated Claude session:

- image: the base image (the dry-run image for dry arms) — the caller passes it (`PoContext.image`);
- `--setting-sources ""`, tools `Read,Glob,Grep`, egress Anthropic only (`pins.egress_po`);
- its own home `state/<pass>/po-home/<arm>` and its own inbox (`Paths.inbox("po")`);
- mounts (OD21, enforced by `check_mounts`): the arm's whole `/work` READ-ONLY (so worktree specs/plans can be
  reviewed) and six read-only files under `/po` — never hidden tests, the reference, scratch or another arm.

Escalations (`escalate`): the owner answers (or parks — `owner.Park` is never an answer: it is recorded in
`<out>/po/parked-escalations.jsonl` and returned for the caller to park the arm); a real answer is appended to the
brief with question, answer, date, pass, the arm that first raised it and whether the owner was real or scripted,
and committed on real passes. Pass 1 grows the brief; pass 2 re-runs every arm from the full brief.

Step 5 (binding requirement for Tasks 13/15/23): `step_view` gives the PO CR-A only until CR-B has been sent to
the arm, and the contract with the In-include section only from then on (or from the start in OD6 A mode).
"""
from __future__ import annotations
import json, re, shutil, time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from runner import config, credentials, egress, gitops, handoff, owner as owner_mod, paths as paths_mod, session, transcripts
from runner.config import Pins
from runner.docker import Mount
from runner.paths import Paths, REAL_PASSES
from runner.transcripts import PinReport

KINDS = {"question", "approval", "next_command", "continue", "step_done"}
PROTOCOL = config.CONFIG_DIR / "po-protocol.md"
CONTINUE = "Please continue."
MESSAGE = "Read /po/protocol.md and follow it."
TRANSIENT = ("no_result", "is_error")        # retried in place with limits.transient_backoff (review C-5)
AT_ONCE = ("auth_failed", "timeout")         # never retried: a credential fault / a hung PO is the harness's
TOOLS = "Read,Glob,Grep"
PO_FILES = ("protocol.md", "po-brief.md", "contract.md", "step.md", "qa.md", "message.md")
SOURCES = {"real": "the real owner", "scripted": "the scripted owner"}
SECTION = "## Escalated answers"


class ProtocolError(ValueError):
    """The PO's reply is unusable (after the second session, from `decide`). `po_result` carries the evidence."""
    po_result: "PoResult | None" = None


class SessionError(RuntimeError):
    """The PO session itself failed (API error, no result, auth, timeout) — an infrastructure fault, never a
    protocol one (review C-5). `po_result` carries the turns so far."""

    def __init__(self, outcome: str, detail: str = ""):
        super().__init__(f"PO session {outcome}: {detail[:200]}")
        self.outcome, self.detail = outcome, detail
        self.po_result: PoResult | None = None


# --- protocol ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Answer:
    question: str
    reply: str | None
    escalate: bool
    cited: str | None


@dataclass(frozen=True)
class Decision:
    kind: str
    reply: str | None
    answers: list[Answer]
    approved: bool | None
    command: str | None
    arguments: str
    significant: bool

    @property
    def escalated(self) -> list[str]:
        return [a.question for a in self.answers if a.escalate]


def _extract(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ProtocolError("no JSON object in PO reply")
    try:
        o = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ProtocolError(f"PO reply is not valid JSON: {e}") from e
    if not isinstance(o, dict):
        raise ProtocolError("PO reply is not a JSON object")
    return o


def _opt_str(v, what: str) -> str | None:
    if v is not None and not isinstance(v, str):
        raise ProtocolError(f"{what} must be a string or null")
    return v


def parse(text: str) -> Decision:
    o = _extract(text)
    try:
        raw_answers = o.get("answers") or []
        if not isinstance(raw_answers, list) or not all(isinstance(a, dict) for a in raw_answers):
            raise ProtocolError("answers must be a list of objects")
        answers = [Answer(str(a["question"]), _opt_str(a.get("reply"), "answer reply"), bool(a.get("escalate")),
                          _opt_str(a.get("cited"), "cited")) for a in raw_answers]
        approved = o.get("approved")
        if approved is not None and not isinstance(approved, bool):
            raise ProtocolError("approved must be true, false or null")
        d = Decision(o["kind"], _opt_str(o.get("reply"), "reply"), answers, approved,
                     _opt_str(o.get("command"), "command"), str(o.get("arguments") or ""), bool(o.get("significant")))
    except (KeyError, TypeError) as e:
        raise ProtocolError(f"malformed: {e}") from e
    if d.kind not in KINDS:
        raise ProtocolError(f"unknown kind {d.kind!r}")
    if d.kind == "question":
        if not d.answers:
            raise ProtocolError("a question needs at least one answer entry")
        for a in d.answers:
            if not a.question.strip():
                raise ProtocolError("every answer entry names its question")
            if a.escalate and a.reply is not None:
                raise ProtocolError("an escalated entry has reply null")
            if not a.escalate and not (a.reply or "").strip():
                raise ProtocolError("a non-escalated entry needs a reply")
    if d.kind == "approval" and (d.approved is None or not (d.reply or "").strip()):
        raise ProtocolError("approval needs approved true/false and a verdict")
    if d.kind == "next_command" and not (d.command and d.command.strip()):
        raise ProtocolError("next_command needs a command")
    if d.kind == "continue" and d.reply != CONTINUE:
        raise ProtocolError("continue reply must be exactly 'Please continue.'")
    if d.kind == "step_done" and d.reply is not None:
        raise ProtocolError("step_done has reply null")
    return d


# --- what the PO sees at a step (step 5: CR-A only until CR-B is sent) ------------------------------------------

def _cr_parts(brief: str) -> tuple[str, str]:
    parts = re.split(r"(?m)^(?=## )", brief)
    cr_a = next(p for p in parts if p.startswith("## CR-A")).rstrip()
    cr_b = next(p for p in parts if p.startswith("## CR-B")).rstrip()
    return cr_a, cr_b


def step_view(step: int, step_brief: str, contract: str, *, crb_sent: bool = False,
              delivery: str | None = None) -> tuple[str, str]:
    """(step brief, contract sections in force) for the PO's `PoContext` at `step`.

    Step 5 with OD6 B (`delivery == "two-requests"`, the scenario default): until CR-B has been sent to the arm
    (`crb_sent`, drive state — Task 15 recomputes the view when it sends CR-B), the PO sees exactly what the arm
    was sent for CR-A (`title_a` + the CR-A section; the brief's own heading would pre-announce two requests) and
    the contract without the In-include section. Once CR-B is sent: both requests as the arm received them, and
    the contract with `after_crb=True`. OD6 A (`"one-message"`): the whole brief and `after_crb=True` from the
    start. Any other step: the brief verbatim and `handoff.in_force(step, contract)`."""
    if step != 5:
        return step_brief, handoff.in_force(step, contract)
    delivery = delivery or handoff.STEP5["delivery"]
    if delivery == "one-message":
        return step_brief, handoff.in_force(5, contract, after_crb=True)
    if delivery != "two-requests":
        raise ValueError(f"unknown step-5 delivery {delivery!r}")
    cr_a, cr_b = _cr_parts(step_brief)
    seen = f"{handoff.STEP5['title_a']}\n\n{cr_a}\n"
    if crb_sent:
        seen += f"\n{handoff.STEP5['cr_b_intro']}\n\n{cr_b}\n"
    return seen, handoff.in_force(5, contract, after_crb=crb_sent)


# --- the PO session ---------------------------------------------------------------------------------------------

@dataclass
class PoResult:
    decision: Decision
    turns: list = field(default_factory=list)
    pin: PinReport | None = None
    retries: int = 0


@dataclass
class PoContext:
    pass_: str
    arm: str
    step: int
    attempt: int
    paths: Paths
    image: str
    dry: bool
    contract_in_force: str      # see step_view
    step_brief: str             # see step_view
    qa_so_far: list[dict]
    out_dir: Path
    pins: Pins | None = None    # preflight M11: limits come from here when given (dry-run overrides), else load_pins()


def _qa_md(qa: list[dict]) -> str:
    return "\n\n".join(f"Q{i}: {q.get('arm_message', '')}\nA{i} ({q.get('answered_by', '?')}): {q.get('reply')}"
                       for i, q in enumerate(qa, 1)) or "(nothing yet)"


def check_mounts(mounts: list[Mount], p: Paths) -> None:
    """OD21: the PO sees the arm's /work read-only and nothing of the hidden tests, the reference, the arm's
    scratch (where hidden-test copies are prepared) or any other arm. Raises PermissionError otherwise."""
    root = paths_mod.REPO_ROOT.resolve()
    forbidden = [root / "tests", root / "reference", p.scratch.resolve(), p.snapshots.resolve()]
    allowed_state = [p.work.resolve(), p.po_home.resolve(), p.inbox("po").resolve()]
    state = paths_mod.STATE.resolve()
    for m in mounts:
        host = Path(m.host).resolve()
        if any(host == f or host.is_relative_to(f) for f in forbidden) or "hidden" in m.ctr:
            raise PermissionError(f"the PO may not see {m.host} (OD21: no hidden tests, reference or scratch)")
        if host.is_relative_to(state) and not any(host == a or host.is_relative_to(a) for a in allowed_state):
            raise PermissionError(f"the PO may not see {m.host} (OD21: only this arm's /work)")
        if m.ctr == "/work" and not m.ro:
            raise PermissionError("the PO's /work must be read-only (OD21)")
        if m.ctr.startswith("/po") and not m.ro:
            raise PermissionError("the PO's inputs must be read-only")


def _mounts(ctx: PoContext, d: Path) -> list[Mount]:
    return [Mount(ctx.paths.po_home, "/home/actor", False), Mount(ctx.paths.work, "/work", True),
            *(Mount(d / f, f"/po/{f}", True) for f in PO_FILES)]


def decide(ctx: PoContext, arm_message: str, cred, n: int, brief_path: Path) -> PoResult:
    """One PO decision on the arm's latest message. A fresh session per try: a second one after an unusable reply
    (then `ProtocolError`); a non-ok session is retried in place with `limits.transient_backoff`, then
    `SessionError` (never `ProtocolError`); `auth_failed`/`timeout` raise `SessionError` at once. Inputs, turns,
    the decision, the collected transcripts and `model-pin.json` land in `<out>/po/a<attempt>-<n:03d>/` — the
    transcripts and pin report on every exit, including failures."""
    pins = ctx.pins or config.load_pins()
    arm = config.load_arm(ctx.arm)
    d = ctx.out_dir / "po" / f"a{ctx.attempt}-{n:03d}"; d.mkdir(parents=True, exist_ok=True)  # attempts never collide
    shutil.copy(PROTOCOL, d / "protocol.md"); shutil.copy(brief_path, d / "po-brief.md")
    (d / "contract.md").write_text(ctx.contract_in_force); (d / "step.md").write_text(ctx.step_brief)
    (d / "qa.md").write_text(_qa_md(ctx.qa_so_far)); (d / "message.md").write_text(arm_message)
    home = ctx.paths.po_home; (home / ".claude").mkdir(parents=True, exist_ok=True)
    ctx.paths.work.mkdir(parents=True, exist_ok=True)
    mounts = _mounts(ctx, d)
    check_mounts(mounts, ctx.paths)
    env = credentials.session_env(pins, arm, role="po", isolated=True, tools=TOOLS)
    before = transcripts.snapshot(home / ".claude")
    res = PoResult(decision=None)                                    # type: ignore[arg-type]
    backoff = list(pins.limits.transient_backoff)
    last_err, parse_tries, k = None, 0, 0
    try:
        with egress.Stage(ctx.pass_, ctx.arm, "po", pins.egress_po, ctx.out_dir / "egress-po.log") as st:
            while True:
                k += 1
                msg = MESSAGE
                if last_err:
                    msg += f"\n\nYour previous reply could not be used ({last_err}). Reply with one JSON object only."
                t = session.Turn(ctx.pass_, ctx.arm, ctx.step, ctx.attempt, n * 100 + k, ctx.image, msg, env,
                                 mounts, st.net, True, ctx.paths.container_repo, ctx.paths.inbox("po"), "po",
                                 ctx.dry, home / ".claude")
                r = session.run_turn(t, cred, d, pins.limits.turn_seconds)
                res.turns.append(r)
                if r.outcome in AT_ONCE:
                    raise SessionError(r.outcome, r.final_text)
                if r.outcome in TRANSIENT:
                    if not backoff:
                        raise SessionError(r.outcome, r.final_text)
                    res.retries += 1
                    time.sleep(backoff.pop(0))
                    continue
                try:
                    dec = parse(r.final_text)
                except ProtocolError as e:
                    parse_tries += 1
                    if parse_tries >= 2:
                        raise
                    last_err = str(e)
                    continue
                res.decision = dec
                (d / "decision.json").write_text(json.dumps(asdict(dec), indent=2))
                return res
    except (ProtocolError, SessionError) as e:
        e.po_result = res
        raise
    finally:
        skipped: list[dict] = []
        files = transcripts.collect(home / ".claude", before, d / "transcripts", skipped=skipped)
        streams = {x.stream_path: x.outcome for x in res.turns if x.stream_path}
        res.pin = transcripts.verify_pin(files, list(streams), pins, unsafe=skipped, stream_outcomes=streams)
        (d / "model-pin.json").write_text(res.pin.to_json())


# --- escalation and brief growth --------------------------------------------------------------------------------

@dataclass(frozen=True)
class Escalation:
    question: str
    answer: str
    seconds: float
    source: str                 # "real" | "scripted"


def _source(o) -> str:
    return "scripted" if isinstance(o, owner_mod.ScriptedOwner) else "real"


def _record_park(out_dir: Path, park: "owner_mod.Park", question: str, pass_: str, arm: str, step: int) -> None:
    f = out_dir / "po" / "parked-escalations.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps({"question": question, "pass": pass_, "arm": arm, "step": step, **asdict(park)}) + "\n")


def escalate(o, question: str, context: str, *, brief_path: Path, pass_: str, arm: str, step: int,
             out_dir: Path, source: str | None = None) -> "Escalation | owner_mod.Park":
    """Ask the owner (`owner.Owner` or a bound `owner.ScriptedOwner`) a question the brief does not answer.

    A `Park` (unattended, EOF, timeout, owner's choice) — or an empty answer, which is recorded as a park with
    reason "empty-answer" — is never treated as an answer: it is appended to `<out_dir>/po/parked-escalations.jsonl`
    and returned so the caller parks the arm and moves on. A real answer is appended to the brief (with whether
    the owner was real or scripted; `source` overrides the type-based guess) and committed on real passes."""
    got = o.escalation(question, context)
    if not isinstance(got, owner_mod.Park):
        answer, secs = got
        if not (answer or "").strip():
            got = owner_mod.Park("escalation", " ".join(question.split())[:200], "empty-answer", time.time(), secs)
    if isinstance(got, owner_mod.Park):
        _record_park(out_dir, got, question, pass_, arm, step)
        return got
    src = source or _source(o)
    append_escalation(brief_path, question, answer, pass_, arm, step, source=src)
    commit_brief(brief_path, pass_, arm, step)
    return Escalation(question, answer, secs, src)


def append_escalation(brief: Path, question: str, answer: str, pass_: str, arm: str, step: int, *,
                      source: str, today: str | None = None) -> None:
    """Append one escalated answer to the brief's `## Escalated answers` section: question, answer, date, pass,
    the arm that first raised it, the step, and whether the real or the scripted owner answered (never guessed:
    `source` is required). A multi-line answer stays inside its bullet (continuation lines indented)."""
    if isinstance(answer, owner_mod.Park) or not isinstance(answer, str):
        raise TypeError(f"an escalation answer must be the owner's text, not {type(answer).__name__}")
    if not answer.strip():
        raise ValueError("an empty owner answer is not an answer")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {sorted(SOURCES)}, not {source!r}")
    today = today or datetime.now(timezone.utc).date().isoformat()
    q = " ".join(question.split())
    a_lines = [l.rstrip() for l in answer.strip().splitlines()]
    meta = f" _({today}; {pass_}; first raised by {arm} at step {step}; answered by {SOURCES[source]})_"
    entry = f"- **Q:** {q} **A:** {a_lines[0]}"
    if len(a_lines) > 1:
        entry += "\n" + "\n".join(("  " + l) if l else "" for l in a_lines[1:])
    entry += meta + "\n"
    text = brief.read_text()
    m = re.search(rf"(?m)^{re.escape(SECTION)}\s*$", text)
    if not m:
        raise ValueError(f"brief has no '{SECTION}' section")
    nxt = re.search(r"(?m)^## ", text[m.end():])
    if nxt is None:
        brief.write_text(text.rstrip("\n") + "\n" + entry)
    else:
        cut = m.end() + nxt.start()
        head, tail = text[:cut].rstrip("\n"), text[cut:]
        brief.write_text(head + "\n" + entry + "\n" + tail)


def commit_brief(brief: Path, pass_: str, arm: str, step: int) -> None:
    """Real passes only: the brief is harness state and its history is evidence. Commits exactly this path."""
    if pass_ in REAL_PASSES:
        gitops.commit_harness_file(brief, f"PO brief: escalated answer ({pass_}, {arm} step {step})")
