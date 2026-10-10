"""Raw measurement -> 0..1 (spec §4). Natural scales as they are; control as the baseline where none exists."""
from __future__ import annotations
import math

# The owner's decision ratings, 1 (wrong or harmful) to 5 (what you'd want); "n/a" is not a score (owner, 2026-10-09).
_RATINGS = {"1": 0.0, "2": 0.25, "3": 0.5, "4": 0.75, "5": 1.0}


def ratio_score(arm: float | None, control: float | None, cap: float = 10.0) -> float | None:
    if not arm or not control or arm <= 0 or control <= 0:
        return None
    x = math.log10(arm / control) / math.log10(cap)          # +1 = cap times worse, -1 = cap times better
    return min(1.0, max(0.0, 0.5 - x / 2))


def churn_score(arm_lines: int, control_lines: int, cap: float = 10.0) -> float | None:
    return ratio_score(arm_lines + 1, control_lines + 1, cap)      # add-one: zero lines are defined


def deduction(count: int | None, per: float) -> float | None:
    return None if count is None else max(0.0, 1.0 - per * count)


def judged(score: float | None) -> float | None:
    return None if score is None else score / 4


def rating(r: str, table: dict[str, float] | None = None) -> float | None:
    """A whole rating from the table; anything between two whole ratings ("3.5", or a reslice mean such as "4.25")
    linearly between its neighbours; n/a (anything else) None."""
    t = table or _RATINGS
    if r in t:
        return t[r]
    try:
        x = float(r)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or str(r).strip().lower() in ("nan", "inf", "-inf"):
        return None
    lo, hi = str(math.floor(x)), str(math.floor(x) + 1)
    if x == math.floor(x):
        return t.get(lo)
    if lo in t and hi in t:
        return t[lo] + (t[hi] - t[lo]) * (x - math.floor(x))
    return None


def rating_table(scales: dict[str, float]) -> dict[str, float]:
    """Map rating_1..rating_5 from scales to the "1".."5" rating keys."""
    return {k: scales.get(f"rating_{k}", v) for k, v in _RATINGS.items()}
