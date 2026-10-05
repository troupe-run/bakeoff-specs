"""Spec §10: does the order change if weights move ±5, if disputed judgements go to their extreme lens, or both?"""
from __future__ import annotations

# A weight variant equal to an earlier one within this tolerance (per dimension) is dropped as a duplicate.
VARIANT_DEDUPE_TOL = 1e-9
# In check(), b has overtaken a (ranked before b at base) only when t[a] - t[b] < -CHECK_TOL (ruling R20).
CHECK_TOL = 1e-9


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
            new = max(0.0, min(100.0, dims_w[dim] + delta))  # Cap at 100
            rest = {k: v for k, v in dims_w.items() if k != dim}
            rest_sum = sum(rest.values())

            # Skip if we can't renormalize (others sum to 0)
            if rest_sum == 0 and new < 100:
                continue

            if rest_sum > 0:
                scale = (100 - new) / rest_sum
                variant = {**{k: v * scale for k, v in rest.items()}, dim: new}
            else:
                # If rest_sum is 0, just set this dim and zeros for others
                variant = {k: 0.0 for k in dims_w}
                variant[dim] = new

            # Check for duplicates by comparing the weights dict (with tolerance for float arithmetic)
            is_duplicate = False
            for _, existing in out:
                # Compare each weight with tolerance
                all_dims = set(variant.keys()) | set(existing.keys())
                if all(abs(variant.get(d, 0) - existing.get(d, 0)) < VARIANT_DEDUPE_TOL for d in all_dims):
                    is_duplicate = True
                    break

            if not is_duplicate:
                out.append((f"{dim} {delta:+d}", variant))

    return out


def check(scores: dict) -> dict:
    """Ruling R20: for each variant, a pair (a, b) with a before b in the base ranking has changed iff b is now
    clearly ahead (t[a] - t[b] < -CHECK_TOL), whatever the base gap. A variant with any changed pair is recorded
    with its order. Groups join both arms of every changed pair and every arm ranked between them."""
    dims_w, parts_w, arms = scores["weights"]["dimensions"], scores["weights"]["parts"], scores["arms"]
    base = {a: total(v, dims_w, parts_w, "median") for a, v in arms.items()}
    ranking = sorted(arms, key=lambda a: (-base[a], a))
    intervals = {a: [base[a], base[a]] for a in arms}
    changes = []
    reach = list(range(len(ranking)))  # reach[i]: lowest-ranked index that i swapped with (itself if none)
    for name, w in weight_variants(dims_w):
        for mode in ("median", "low", "high"):
            t = {a: total(v, w, parts_w, mode) for a, v in arms.items()}
            for a in arms:
                intervals[a] = [min(intervals[a][0], t[a]), max(intervals[a][1], t[a])]
            changed = [(i, j) for i in range(len(ranking)) for j in range(i + 1, len(ranking))
                       if t[ranking[i]] - t[ranking[j]] < -CHECK_TOL]
            for i, j in changed:
                reach[i] = max(reach[i], j)
            if changed:
                changes.append({"variant": f"{name}, judges {mode}",
                                "order": sorted(arms, key=lambda a: (-t[a], a))})
    groups: list[list[str]] = []
    end = -1
    for k, a in enumerate(ranking):
        if k > end:
            groups.append([])
        groups[-1].append(a)
        end = max(end, reach[k])
    return {"ranking": ranking, "intervals": intervals, "groups": groups, "order_changes": changes}
