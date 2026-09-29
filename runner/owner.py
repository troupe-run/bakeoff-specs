"""The owner in the loop (design §8): terminal prompts for Martin, and a scripted stand-in for dry runs.

Every method that could reach a real owner returns the seconds spent answering — owner time is evidence.
Every answer must be traceable to whether it came from the real owner (`Owner`, at a terminal) or the
scripted owner (`ScriptedOwner`, dry-run arms only); `ScriptedOwner.bind` refuses a real arm outright so the
two can never be confused in evidence.

Owner standing instruction for unattended periods: anything blocked is parked and the run moves on to the
next arm/round. `ScriptedOwner` is that "not available" stand-in — every one of its answers is instant (0.0s)
and drawn from a small TOML script, never from a blocking prompt.
"""
from __future__ import annotations
import re, time, tomllib
from pathlib import Path
from typing import Callable


class Owner:
    """The owner at the terminal. Every prompt is timed from first shown to last input line."""

    def __init__(self, input_fn: Callable[..., str] = input, out: Callable[[str], None] = print,
                 clock: Callable[[], float] = time.monotonic):
        self._in, self._out, self._clock = input_fn, out, clock

    def _lines(self, prompt: str) -> str:
        self._out(prompt + " (end with a line holding only '.')")
        lines = []
        while (l := self._in("")) != ".":
            lines.append(l)
        return "\n".join(lines).strip()

    def escalation(self, question: str, context: str) -> tuple[str, float]:
        t0 = self._clock()
        self._out("=" * 72 + "\nESCALATION — the PO brief does not answer this:\n" + question)
        self._out("--- the arm's message (last 40 lines) ---\n" + "\n".join(context.splitlines()[-40:]))
        answer = self._lines("Your answer (it is added to the PO brief)")
        return answer, self._clock() - t0

    def gate(self, arm_message: str, decision, repo_changes: str) -> tuple[str, str, float]:
        t0 = self._clock()
        self._out("=" * 72 + "\nOWNER GATE — the arm asks for approval.")
        self._out("--- the arm's message (last 60 lines) ---\n" + "\n".join(arm_message.splitlines()[-60:]))
        self._out(f"--- PO draft verdict (approved={decision.approved}) ---\n{decision.reply}")
        self._out("--- repo changes since the step began ---\n" + (repo_changes or "(none)"))
        while True:
            k = self._in("[Enter] accept · e = override · d = show changes again: ").strip().lower()
            if k == "":
                return decision.reply, "accept", self._clock() - t0
            if k == "e":
                return self._lines("Your reply to the arm"), "override", self._clock() - t0
            if k == "d":
                self._out(repo_changes or "(none)")

    def confirm(self, text: str) -> bool:
        return self._in(text + " [y/N] ").strip().lower() in ("y", "yes")

    def items(self, items: list[tuple[str, str]]) -> dict[str, tuple[bool, str, float]]:
        out = {}
        for iid, text in items:
            t0 = self._clock()
            ok = self._in(f"{iid}: {text}\n  ok? [y/n] ").strip().lower() in ("y", "yes")
            note = self._in("  note (optional): ").strip()
            out[iid] = (ok, note, self._clock() - t0)
        return out

    def setup_reply(self, text: str) -> tuple[str, float]:
        t0 = self._clock()
        self._out("--- setup session says (last 40 lines) ---\n" + "\n".join(text.splitlines()[-40:]))
        k = self._in("[Enter] = move on · r = reply: ").strip().lower()
        reply = self._lines("Your reply") if k == "r" else ""
        return reply, self._clock() - t0

    def step_review(self, summary_md: str) -> tuple[str, float]:
        t0 = self._clock()
        self._out(summary_md)
        k = self._in("[Enter] continue to the next step · p = pause here: ").strip().lower()
        return ("pause" if k == "p" else "continue"), self._clock() - t0

    def reclassify(self, what: str, detail: str) -> str:
        self._out(f"First runaway breach for this arm: {what}\n{detail}")
        k = self._in("Count it as the arm's outcome (a) or as a harness fault (h)? [a/h] ").strip().lower()
        return "harness" if k == "h" else "arm"

    def substitute_bug(self, arm, precheck_summary: str) -> tuple[str, str, str, str, float]:
        """Step-6 fallback (preflight B5): the planted bug already passes on the step-5 commit. The owner
        either keeps it (plan A still runs) or picks a substitute bug to plant instead."""
        t0 = self._clock()
        self._out("=" * 72 + f"\nSTEP 6 PRE-CHECK ({arm.name}) — the planted bug already passes "
                              "on the step-5 commit.")
        self._out("--- pre-check summary ---\n" + precheck_summary)
        k = self._in("[Enter] keep the planted bug · s = substitute a different bug: ").strip().lower()
        if k != "s":
            return "planted", "", "", "", self._clock() - t0
        title = self._in("Substitute bug title: ").strip()
        body = self._lines("Substitute bug body")
        why = self._lines("Why this substitute")
        return "substitute", title, body, why, self._clock() - t0


class ScriptedOwner:
    """Dry runs only: answers come from a TOML script, never from a person. `bind` refuses a real arm so a
    scripted answer can never be mistaken for the real owner's in evidence."""

    def __init__(self, script: Path):
        self.s = tomllib.loads(Path(script).read_text())
        self._paused: set[int] = set()

    def bind(self, arm) -> "ScriptedOwner":
        if not arm.dry:
            raise PermissionError("the scripted owner may only answer for dry-run arms")
        return self

    @property
    def escalation_answer(self) -> str:
        return self.s["escalations"]["default"]

    def escalation(self, question, context):
        return self.escalation_answer, 0.0

    def gate(self, arm_message, decision, repo_changes):
        g = self.s.get("gates", {}).get("default", "accept")
        return (decision.reply, "accept", 0.0) if g == "accept" else (g.split(":", 1)[1], "override", 0.0)

    def confirm(self, text):
        return bool(self.s.get("confirm", {}).get("default", True))

    def items(self, items):
        v = bool(self.s.get("items", {}).get("default", True))
        return {i: (v, "scripted", 0.0) for i, _ in items}

    def setup_reply(self, text):
        return self.s.get("setup", {}).get("default", ""), 0.0

    def step_review(self, summary_md):
        m = re.search(r"Step (\d+)", summary_md)
        step = int(m.group(1)) if m else 0
        if step in self.s.get("review", {}).get("pause_after", []) and step not in self._paused:
            self._paused.add(step)
            return "pause", 0.0
        return self.s.get("review", {}).get("default", "continue"), 0.0

    def reclassify(self, what, detail):
        return self.s.get("reclassify", {}).get("default", "arm")

    def substitute_bug(self, arm, precheck_summary):
        sub = self.s.get("substitute", {})
        choice = sub.get("default", "planted")
        if choice != "substitute":
            return "planted", "", "", "", 0.0
        return "substitute", sub.get("title", ""), sub.get("body", ""), sub.get("why", ""), 0.0
