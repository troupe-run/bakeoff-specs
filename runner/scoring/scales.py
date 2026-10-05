"""Raw measurement -> 0..1 (spec §4). Natural scales as they are; control as the baseline where none exists."""
from __future__ import annotations
import math

_RATINGS = {"good": 1.0, "acceptable": 0.67, "poor": 0.0}


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
    return (table or _RATINGS).get(r)


def rating_table(scales: dict[str, float]) -> dict[str, float]:
    """Map rating_good/rating_acceptable/rating_poor from scales to good/acceptable/poor rating keys."""
    return {
        "good": scales.get("rating_good", 1.0),
        "acceptable": scales.get("rating_acceptable", 0.67),
        "poor": scales.get("rating_poor", 0.0),
    }
