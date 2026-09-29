"""Product-owner protocol types (design §... , plan Task 13).

Placeholder: Task 13 (running in a parallel worktree) owns `runner/po.py` in full — the protocol markdown,
`PoContext`, `parse`, `decide`, `SessionError`, etc. Task 14 (this worktree) only needs the `Decision`/`Answer`
shapes to time and record owner gate replies against a PO draft verdict. The dataclasses below are copied
verbatim from the plan's Task 13 text so the shape matches exactly; Task 13's real module supersedes this file
at integration (its `Decision`/`Answer` are byte-identical, so the merge is a no-op on this part).
"""
from __future__ import annotations
from dataclasses import dataclass


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
