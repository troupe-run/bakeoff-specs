"""Spec §10: does the order change if weights move ±5, if disputed judgements go to their extreme lens, or both?"""
from __future__ import annotations


def _step_score(st: dict, mode: str) -> float | None:
    if mode != "median" and st.get("disputed") and "owner" not in st and st.get("lenses"):
        return (min if mode == "low" else max)(st["lenses"].values()) / 4
    return st.get("score")


def _part(part: dict, mode: str) -> float | None:
    xs = [s for s in (_step_score(st, mode) for st in part["steps"].values()) if s is not None]
    return sum(xs) / len(xs) if xs else None


def total(arm: dict, dims_w: dict, parts_w: dict, mode: str) -> float:
    t = 0.0
    for dim, d in arm["dimensions"].items():
        shares = parts_w.get(dim) or {p: 1.0 for p in d["parts"]}
        measured = {p: s for p, s in ((p, _part(v, mode)) for p, v in d["parts"].items()) if s is not None}
        if measured:
            t += dims_w[dim] * sum(shares[p] * s for p, s in measured.items()) / sum(shares[p] for p in measured)
    return t


def weight_variants(dims_w: dict) -> list[tuple[str, dict]]:
    out = [("base", dict(dims_w))]
    for dim in sorted(dims_w):
        for delta in (5, -5):
            new = max(0.0, dims_w[dim] + delta)
            rest = {k: v for k, v in dims_w.items() if k != dim}
            scale = (100 - new) / sum(rest.values())
            out.append((f"{dim} {delta:+d}", {**{k: v * scale for k, v in rest.items()}, dim: new}))
    return out


def check(scores: dict) -> dict:
    dims_w, parts_w, arms = scores["weights"]["dimensions"], scores["weights"]["parts"], scores["arms"]
    base = {a: total(v, dims_w, parts_w, "median") for a, v in arms.items()}
    ranking = sorted(arms, key=lambda a: (-base[a], a))
    intervals = {a: [base[a], base[a]] for a in arms}
    changes = []
    for name, w in weight_variants(dims_w):
        for mode in ("median", "low", "high"):
            t = {a: total(v, w, parts_w, mode) for a, v in arms.items()}
            for a in arms:
                intervals[a] = [min(intervals[a][0], t[a]), max(intervals[a][1], t[a])]
            order = sorted(arms, key=lambda a: (-t[a], a))
            if order != ranking:
                changes.append({"variant": f"{name}, judges {mode}", "order": order})
    groups: list[list[str]] = []
    for a in ranking:
        if groups and intervals[a][1] >= intervals[groups[-1][-1]][0]:
            groups[-1].append(a)
        else:
            groups.append([a])
    return {"ranking": ranking, "intervals": intervals, "groups": groups, "order_changes": changes}
