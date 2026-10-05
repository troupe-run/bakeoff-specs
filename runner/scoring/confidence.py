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
            tolerance = 1e-9
            for _, existing in out:
                # Compare each weight with tolerance
                all_dims = set(variant.keys()) | set(existing.keys())
                if all(abs(variant.get(d, 0) - existing.get(d, 0)) < tolerance for d in all_dims):
                    is_duplicate = True
                    break

            if not is_duplicate:
                out.append((f"{dim} {delta:+d}", variant))

    return out


def check(scores: dict) -> dict:
    dims_w, parts_w, arms = scores["weights"]["dimensions"], scores["weights"]["parts"], scores["arms"]
    base = {a: total(v, dims_w, parts_w, "median") for a, v in arms.items()}
    ranking = sorted(arms, key=lambda a: (-base[a], a))
    intervals = {a: [base[a], base[a]] for a in arms}
    changes = []

    # Track which pairs of arms flip relative order
    flips = set()  # Set of (a, b) tuples representing pairs that flip
    tolerance = 1e-9

    for name, w in weight_variants(dims_w):
        for mode in ("median", "low", "high"):
            t = {a: total(v, w, parts_w, mode) for a, v in arms.items()}
            for a in arms:
                intervals[a] = [min(intervals[a][0], t[a]), max(intervals[a][1], t[a])]
            order = sorted(arms, key=lambda a: (-t[a], a))

            if order != ranking:
                changes.append({"variant": f"{name}, judges {mode}", "order": order})
                # Track which pairs flipped (with tolerance for float noise)
                for i in range(len(ranking)):
                    for j in range(i + 1, len(ranking)):
                        arm_i, arm_j = ranking[i], ranking[j]
                        base_score_i = base[arm_i]
                        base_score_j = base[arm_j]
                        variant_score_i = t[arm_i]
                        variant_score_j = t[arm_j]

                        # Check if relative order flipped
                        base_diff = base_score_i - base_score_j
                        variant_diff = variant_score_i - variant_score_j

                        # If signs differ (and neither is within tolerance of 0), it's a flip
                        if abs(base_diff) > tolerance and abs(variant_diff) > tolerance:
                            if base_diff * variant_diff < 0:  # Different signs = flip
                                flips.add((min(arm_i, arm_j), max(arm_i, arm_j)))

    # Build groups using flips: if a and c flip, all arms between them in ranking join the group
    groups: list[list[str]] = []
    in_group = set()

    for i, a in enumerate(ranking):
        if a in in_group:
            continue

        # Start a new group with arm a
        group = [a]
        in_group.add(a)

        # Find all arms that should be in this group due to flips
        # An arm is in the group if it flips with a, or with something already in the group
        changed = True
        while changed:
            changed = False
            for j in range(len(ranking)):
                b = ranking[j]
                if b in in_group:
                    continue
                # Check if b flips with any arm in the current group
                for arm_in_group in group:
                    flip_key = (min(arm_in_group, b), max(arm_in_group, b))
                    if flip_key in flips:
                        # b flips with something in the group, add it
                        group.append(b)
                        in_group.add(b)
                        changed = True
                        break

        # Ensure groups stay contiguous in base ranking by including all arms between min and max
        if group:
            min_rank = min(ranking.index(a) for a in group)
            max_rank = max(ranking.index(a) for a in group)
            for k in range(min_rank, max_rank + 1):
                if ranking[k] not in in_group:
                    group.append(ranking[k])
                    in_group.add(ranking[k])
            # Re-sort group to base ranking order
            group.sort(key=lambda x: ranking.index(x))

        groups.append(group)

    return {"ranking": ranking, "intervals": intervals, "groups": groups, "order_changes": changes}
