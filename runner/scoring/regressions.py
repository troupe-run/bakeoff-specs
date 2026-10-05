"""Coping with change, regressions part: earlier steps' hidden tests that passed at N-1 and fail at N. Keyed by
test id, so new tests, renamed parametrisations and tests that already failed are never regressions."""
from __future__ import annotations


def compute(prev: dict[str, str] | None, cur: dict[str, str], excluded: frozenset[str]) -> dict:
    prev = {t: o for t, o in (prev or {}).items() if t not in excluded}
    earlier = [t for t in sorted(prev) if t in cur and t not in excluded]
    passing_before = [t for t in earlier if prev[t] == "passed"]
    regressed = [t for t in passing_before if cur[t] != "passed"]
    rate = None if not passing_before else 1 - len(regressed) / len(passing_before)
    return {"earlier_total": len(earlier), "earlier_passing_before": len(passing_before),
            "regressed": regressed, "rate": rate}
