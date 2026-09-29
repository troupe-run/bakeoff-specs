"""The owner in the loop (design §8): terminal prompts for Martin, and a scripted stand-in for dry runs.

Every method that could reach a real owner returns the seconds spent answering — owner time is evidence.
Every answer must be traceable to whether it came from the real owner (`Owner`, at a terminal) or the
scripted owner (`ScriptedOwner`, dry-run arms only); `ScriptedOwner.bind` refuses a real arm outright, and
every `ScriptedOwner` answering method refuses to run at all unless it has been bound, so the two can never
be confused in evidence.

Owner standing instruction for unattended periods: anything blocked is parked and the run moves on to the
next arm/round. `Owner` implements that "not available" outcome directly, as a `Park` (design §8, this file):

- **unattended mode** (`Owner(unattended=True, ...)`, or set `owner.unattended = True` later): every prompt
  method returns a `Park` immediately, before showing anything or reading any input.
- **EOF** (stdin closed): caught wherever the owner would be read from, and returns a `Park` instead of
  letting `EOFError` propagate. No prompt method raises on EOF.
- **a per-prompt timeout** (`Owner(timeout=<seconds>, ...)`, `None` = wait forever, the default): if the
  owner's answer took longer than `timeout` seconds (by the injected `clock`), the prompt parks rather than
  blocking the run indefinitely.
- **owner choice**: at every keystroke prompt, one key parks after a confirm — "p" everywhere except
  `step_review`, which already uses "p" for "pause the run here" (a normal, non-park outcome); there the park
  key is "k" instead, so the pre-existing pause semantics are not silently overloaded.

Every park is recorded (`Owner.parks`, and returned to the caller) as a
`Park(prompt, context, reason, at, seconds)` — `prompt` names which method was parked, `context` is a short,
self-explaining summary of what was being asked (e.g. the question's first line, or which item/gate it was),
`reason` is one of `"unattended" | "eof" | "timeout" | "owner-choice"`, `at` is a wall-clock timestamp
(`now_fn`, default `time.time`), and `seconds` is owner time spent before the park (evidence, same as a
normal answer). Callers (Task 23's `run_arm`) check `isinstance(result, Park)` and park the arm, moving on to
the next arm/round, rather than trying to make sense of a normal-shaped reply — and can read a park record
on its own, without cross-referencing the run, thanks to `context`.

`ScriptedOwner` never parks — a dry run has no owner to wait for at all, so every one of its answers is
instant (0.0s), drawn from a small TOML script, and only ever produced once `.bind(arm)` has confirmed the
arm is a dry run.
"""
from __future__ import annotations
import re, time, tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Park:
    """Recorded whenever a prompt could not (or would not) be answered by the owner. The run parks the arm
    and moves on to the next arm/round rather than blocking. `seconds` is owner time spent before parking —
    it is evidence just like a normal answer's seconds, even when the outcome is "no answer". `context` makes
    the record understandable on its own (in a log, a ledger, a report) without cross-referencing the run."""
    prompt: str    # which Owner method was parked, e.g. "gate", "escalation"
    context: str   # a short summary of what was being asked, e.g. the question's first line or an item id
    reason: str    # "unattended" | "eof" | "timeout" | "owner-choice"
    at: float      # wall-clock timestamp when the park was recorded (Owner's `now_fn`, default time.time)
    seconds: float


class _ParkSignal(Exception):
    """Internal control-flow signal only: never escapes a public `Owner` method. Every method catches this
    at its own boundary and converts it into a `Park` return value."""
    def __init__(self, reason: str):
        self.reason = reason


def _first_line(text: str) -> str:
    """A short, non-empty summary line for `Park.context` — the first non-blank line of `text`."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return "(empty)"


class Owner:
    """The owner at the terminal. Every prompt is timed from first shown to last input line, and every
    prompt can park instead of answering (see the module docstring)."""

    def __init__(self, input_fn: Callable[..., str] = input, out: Callable[[str], None] = print,
                 clock: Callable[[], float] = time.monotonic, now_fn: Callable[[], float] = time.time,
                 unattended: bool = False, timeout: float | None = None):
        self._in, self._out, self._clock, self._now = input_fn, out, clock, now_fn
        self.unattended = unattended
        self.timeout = timeout
        self.parks: list[Park] = []

    # -- park machinery -----------------------------------------------------------------------------------

    def _park(self, prompt_name: str, reason: str, t0: float, context: str) -> Park:
        p = Park(prompt=prompt_name, context=context, reason=reason, at=self._now(), seconds=self._clock() - t0)
        self.parks.append(p)
        self._out(f"PARKED [{prompt_name}] ({reason}) — {context} — recorded; the run moves on to the next "
                   "arm/round.")
        return p

    def _read_checked(self, prompt_name: str, t0: float, io_prompt: str = "") -> str:
        """Read one line, applying the timeout/EOF park rules. Never raises past this method except the
        internal `_ParkSignal`, which every public method catches at its own boundary."""
        if self.timeout is not None and (self._clock() - t0) > self.timeout:
            raise _ParkSignal("timeout")
        try:
            line = self._in(io_prompt)
        except EOFError:
            raise _ParkSignal("eof")
        if self.timeout is not None and (self._clock() - t0) > self.timeout:
            raise _ParkSignal("timeout")
        return line

    def _confirm_park(self, prompt_name: str, t0: float) -> bool:
        try:
            ans = self._read_checked(prompt_name, t0, "Park this prompt instead of answering? [y/N] ")
        except _ParkSignal:
            return True   # EOF/timeout while confirming the park: just park, don't ask again
        return ans.strip().lower() in ("y", "yes")

    def _choice_checked(self, prompt_name: str, t0: float, io_prompt: str, park_key: str = "p") -> str:
        """Read a single keystroke, honouring the park-by-choice key (with a confirm) in a loop."""
        while True:
            k = self._read_checked(prompt_name, t0, io_prompt).strip().lower()
            if k == park_key:
                if self._confirm_park(prompt_name, t0):
                    raise _ParkSignal("owner-choice")
                continue
            return k

    def _lines_checked(self, prompt: str, prompt_name: str, t0: float) -> str:
        self._out(prompt + " (end with a line holding only '.'; 'p' alone on the first line parks)")
        lines: list[str] = []
        while True:
            line = self._read_checked(prompt_name, t0)
            if not lines and line.strip().lower() == "p":
                if self._confirm_park(prompt_name, t0):
                    raise _ParkSignal("owner-choice")
                continue
            if line == ".":
                break
            lines.append(line)
        return "\n".join(lines).strip()

    def _text_checked(self, prompt_name: str, t0: float, io_prompt: str, park_key: str = "p") -> str:
        """Read one free-text line, first checking it against the park-by-choice key (with a confirm). Used
        where the answer is a single line of free text (not a keystroke, not a multi-line block) — e.g. an
        item's note, or the substitute bug's title — so the returned text's case and content are otherwise
        preserved untouched."""
        while True:
            line = self._read_checked(prompt_name, t0, io_prompt)
            if line.strip().lower() == park_key:
                if self._confirm_park(prompt_name, t0):
                    raise _ParkSignal("owner-choice")
                continue
            return line

    # -- prompts --------------------------------------------------------------------------------------------

    def escalation(self, question: str, context: str) -> tuple[str, float] | Park:
        t0 = self._clock()
        ctx = _first_line(question)
        if self.unattended:
            return self._park("escalation", "unattended", t0, ctx)
        try:
            self._out("=" * 72 + "\nESCALATION — the PO brief does not answer this:\n" + question)
            self._out("--- the arm's message (last 40 lines) ---\n" + "\n".join(context.splitlines()[-40:]))
            answer = self._lines_checked("Your answer (it is added to the PO brief)", "escalation", t0)
            return answer, self._clock() - t0
        except _ParkSignal as e:
            return self._park("escalation", e.reason, t0, ctx)

    def gate(self, arm_message: str, decision, repo_changes: str) -> tuple[str, str, float] | Park:
        t0 = self._clock()
        ctx = _first_line(arm_message)
        if self.unattended:
            return self._park("gate", "unattended", t0, ctx)
        try:
            self._out("=" * 72 + "\nOWNER GATE — the arm asks for approval.")
            self._out("--- the arm's message (last 60 lines) ---\n" + "\n".join(arm_message.splitlines()[-60:]))
            self._out(f"--- PO draft verdict (approved={decision.approved}) ---\n{decision.reply}")
            self._out("--- repo changes since the step began ---\n" + (repo_changes or "(none)"))
            while True:
                k = self._choice_checked("gate", t0,
                                          "[Enter] accept · e = override · d = show changes again · p = park: ")
                if k == "":
                    return decision.reply, "accept", self._clock() - t0
                if k == "e":
                    reply = self._lines_checked("Your reply to the arm", "gate", t0)
                    return reply, "override", self._clock() - t0
                if k == "d":
                    self._out(repo_changes or "(none)")
        except _ParkSignal as e:
            return self._park("gate", e.reason, t0, ctx)

    def confirm(self, text: str) -> bool | Park:
        t0 = self._clock()
        ctx = _first_line(text)
        if self.unattended:
            return self._park("confirm", "unattended", t0, ctx)
        try:
            k = self._choice_checked("confirm", t0, text + " [y/N] · p = park: ")
            return k in ("y", "yes")
        except _ParkSignal as e:
            return self._park("confirm", e.reason, t0, ctx)

    def items(self, items: list[tuple[str, str]]) -> dict[str, tuple[bool, str, float]] | Park:
        t0 = self._clock()
        ctx = f"{len(items)} item(s) to review"
        if self.unattended:
            return self._park("items", "unattended", t0, ctx)
        out: dict[str, tuple[bool, str, float]] = {}
        try:
            for iid, text in items:
                it0 = self._clock()
                ctx = f"{iid}: {text}"
                k = self._choice_checked("items", t0, f"{iid}: {text}\n  ok? [y/n] · p = park: ")
                ok = k in ("y", "yes")
                note = self._text_checked("items", t0, "  note (optional) · p = park: ").strip()
                out[iid] = (ok, note, self._clock() - it0)
            return out
        except _ParkSignal as e:
            return self._park("items", e.reason, t0, ctx)

    def setup_reply(self, text: str) -> tuple[str, float] | Park:
        t0 = self._clock()
        ctx = _first_line(text)
        if self.unattended:
            return self._park("setup_reply", "unattended", t0, ctx)
        try:
            self._out("--- setup session says (last 40 lines) ---\n" + "\n".join(text.splitlines()[-40:]))
            k = self._choice_checked("setup_reply", t0, "[Enter] = move on · r = reply · p = park: ")
            reply = self._lines_checked("Your reply", "setup_reply", t0) if k == "r" else ""
            return reply, self._clock() - t0
        except _ParkSignal as e:
            return self._park("setup_reply", e.reason, t0, ctx)

    def step_review(self, summary_md: str) -> tuple[str, float] | Park:
        """Note: "p" here means "pause the run after this step" (a normal outcome, not a Park) — it was
        already in use before this module had a park concept. The park-by-choice key here is "k" instead."""
        t0 = self._clock()
        ctx = _first_line(summary_md)
        if self.unattended:
            return self._park("step_review", "unattended", t0, ctx)
        try:
            self._out(summary_md)
            k = self._choice_checked("step_review", t0,
                                      "[Enter] continue to the next step · p = pause here · k = park: ",
                                      park_key="k")
            return ("pause" if k == "p" else "continue"), self._clock() - t0
        except _ParkSignal as e:
            return self._park("step_review", e.reason, t0, ctx)

    def reclassify(self, what: str, detail: str) -> str | Park:
        t0 = self._clock()
        ctx = _first_line(what)
        if self.unattended:
            return self._park("reclassify", "unattended", t0, ctx)
        try:
            self._out(f"First runaway breach for this arm: {what}\n{detail}")
            k = self._choice_checked("reclassify", t0,
                                      "Count it as the arm's outcome (a) or as a harness fault (h)? [a/h] · "
                                      "p = park: ")
            return "harness" if k == "h" else "arm"
        except _ParkSignal as e:
            return self._park("reclassify", e.reason, t0, ctx)

    def substitute_bug(self, arm, precheck_summary: str) -> tuple[str, str, str, str, str, float] | Park:
        """Step-6 fallback (preflight B5): the planted bug already passes on the step-5 commit. The owner
        either keeps it (plan A still runs) or picks a substitute bug — with its own acceptance test, so
        Task 23 can prove the substitute FAILS on the arm's step-5 commit before it is delivered."""
        t0 = self._clock()
        ctx = f"{arm.name}: {_first_line(precheck_summary)}"
        if self.unattended:
            return self._park("substitute_bug", "unattended", t0, ctx)
        try:
            self._out("=" * 72 + f"\nSTEP 6 PRE-CHECK ({arm.name}) — the planted bug already passes "
                                  "on the step-5 commit.")
            self._out("--- pre-check summary ---\n" + precheck_summary)
            k = self._choice_checked("substitute_bug", t0,
                                      "[Enter] keep the planted bug · s = substitute a different bug · "
                                      "p = park: ")
            if k != "s":
                return "planted", "", "", "", "", self._clock() - t0
            title = self._text_checked("substitute_bug", t0, "Substitute bug title · p = park: ").strip()
            body = self._lines_checked("Substitute bug body", "substitute_bug", t0)
            why = self._lines_checked("Why this substitute", "substitute_bug", t0)
            test_body = self._lines_checked(
                "Acceptance test (a pytest file body) — must FAIL on the arm's step-5 commit and pass once "
                "the substitute is fixed", "substitute_bug", t0)
            return "substitute", title, body, why, test_body, self._clock() - t0
        except _ParkSignal as e:
            return self._park("substitute_bug", e.reason, t0, ctx)


class ScriptedOwner:
    """Dry runs only: answers come from a TOML script, never from a person, and never park (there is no
    owner to be unavailable). `bind` refuses a real arm so a scripted answer can never be mistaken for the
    real owner's in evidence; every answering method additionally refuses to run at all until `bind` has
    succeeded, so an unbound `ScriptedOwner` cannot silently answer for anything."""

    def __init__(self, script: Path):
        self.s = tomllib.loads(Path(script).read_text())
        self._paused: set[int] = set()
        self._bound = False

    def bind(self, arm) -> "ScriptedOwner":
        if not arm.dry:
            raise PermissionError("the scripted owner may only answer for dry-run arms")
        self._bound = True
        return self

    def _require_bound(self) -> None:
        if not self._bound:
            raise PermissionError("the scripted owner must be bound to a dry arm first: call .bind(arm)")

    @property
    def escalation_answer(self) -> str:
        self._require_bound()
        return self.s["escalations"]["default"]

    def escalation(self, question, context):
        self._require_bound()
        return self.escalation_answer, 0.0

    def gate(self, arm_message, decision, repo_changes):
        self._require_bound()
        g = self.s.get("gates", {}).get("default", "accept")
        if g == "accept":
            return decision.reply, "accept", 0.0
        if g.startswith("override") and ":" in g:
            return g.split(":", 1)[1], "override", 0.0
        raise ValueError(f"ScriptedOwner: [gates].default={g!r} must be 'accept' or 'override:<reply>'")

    def confirm(self, text):
        self._require_bound()
        return bool(self.s.get("confirm", {}).get("default", True))

    def items(self, items):
        self._require_bound()
        v = bool(self.s.get("items", {}).get("default", True))
        return {i: (v, "scripted", 0.0) for i, _ in items}

    def setup_reply(self, text):
        self._require_bound()
        return self.s.get("setup", {}).get("default", ""), 0.0

    def step_review(self, summary_md):
        self._require_bound()
        m = re.search(r"Step (\d+)", summary_md)
        step = int(m.group(1)) if m else 0
        if step in self.s.get("review", {}).get("pause_after", []) and step not in self._paused:
            self._paused.add(step)
            return "pause", 0.0
        return self.s.get("review", {}).get("default", "continue"), 0.0

    def reclassify(self, what, detail):
        self._require_bound()
        return self.s.get("reclassify", {}).get("default", "arm")

    def substitute_bug(self, arm, precheck_summary):
        self._require_bound()
        sub = self.s.get("substitute", {})
        choice = sub.get("default", "planted")
        if choice != "substitute":
            return "planted", "", "", "", "", 0.0
        return ("substitute", sub.get("title", ""), sub.get("body", ""), sub.get("why", ""),
                sub.get("test_body", ""), 0.0)
