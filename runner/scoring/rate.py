"""Rating the decision sheet in chat (owner, 2026-10-09): show one topic, write the owner's ratings back into
`rating-sheet.md`. The sheet stays the record, so a sitting can stop anywhere and the import is unchanged.

    python -m runner.scoring.rate <pass> next               # the first topic with an unrated route, printed
    python -m runner.scoring.rate <pass> show T4
    python -m runner.scoring.rate <pass> set T4 4 2 5 n/a [--reason 2 "breaks on negative numbers"]...
    python -m runner.scoring.rate <pass> progress

Only the blind sheet is read or written: never `.import/` or `anon-key.json`."""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
from runner.scoring import decisions as dz


def sheet_path(pass_: str) -> Path:
    return dz._dir(pass_) / "rating-sheet.md"


def _sections(md: str) -> list[tuple[str, int, int]]:
    """(topic id, first line, end line) for every `## <id>` topic outside fenced blocks."""
    lines, plain = md.splitlines(), dz._unfenced(md)
    heads = [(i, m[1]) for i, line in enumerate(plain) if (m := dz._H2.match(line))]
    tops = [i for i, line in enumerate(plain) if line.startswith("# ")]
    out = []
    for k, (i, tid) in enumerate(heads):
        end = min([j for j, _ in heads[k + 1:]] + [j for j in tops if j > i] + [len(lines)])
        out.append((tid, i, end))
    return out


def show(md: str, tid: str) -> str:
    lines = md.splitlines()
    for t, a, b in _sections(md):
        if t == tid:
            return "\n".join(lines[a:b]).rstrip() + "\n"
    raise KeyError(f"{tid}: no such topic on the sheet")


def _route_lines(md: str, a: int, b: int) -> dict[int, dict[str, int]]:
    """{route no: {"rating": line index, "reason": line index}} within one topic, outside fences."""
    plain = dz._unfenced(md)
    out: dict[int, dict[str, int]] = {}
    route: dict[str, int] | None = None
    for i in range(a, b):
        if m := dz._H3.match(plain[i]):
            route = out.setdefault(int(m[1]), {})
        elif plain[i].startswith("###"):
            route = None
        elif route is not None and (m := dz._FIELD.match(plain[i])):
            route.setdefault(m[1].lower(), i)
    return out


def rated(md: str, tid: str) -> dict[int, str]:
    lines = md.splitlines()
    for t, a, b in _sections(md):
        if t == tid:
            return {n: m[2].strip() for n, f in _route_lines(md, a, b).items()
                    if "rating" in f and (m := dz._FIELD.match(lines[f["rating"]]))}
    raise KeyError(f"{tid}: no such topic on the sheet")


def set_ratings(md: str, tid: str, ratings: list[str], reasons: dict[int, str] | None = None) -> str:
    """`md` with topic `tid`'s routes rated in order (one rating per route, all of them) and the given reasons; a
    reason never given leaves that route's reason line as it was."""
    reasons = reasons or {}
    lines = md.splitlines()
    sec = [(a, b) for t, a, b in _sections(md) if t == tid]
    if not sec:
        raise KeyError(f"{tid}: no such topic on the sheet")
    routes = _route_lines(md, *sec[0])
    if len(ratings) != len(routes):
        raise ValueError(f"{tid} has {len(routes)} route(s); got {len(ratings)} rating(s)")
    norm = [dz._rating(r) for r in ratings]
    if bad := [r for r, n in zip(ratings, norm) if n not in dz.RATINGS]:
        raise ValueError(f"not on the scale (1-5 or n/a): {', '.join(bad)}")
    if extra := sorted(set(reasons) - set(routes)):
        raise ValueError(f"{tid} has no route {extra}")
    for (n, f), r in zip(sorted(routes.items()), norm):
        if "rating" not in f or "reason" not in f:
            raise ValueError(f"{tid} route {n}: its rating or reason line is missing from the sheet")
        lines[f["rating"]] = f"rating: {r}"
        if n in reasons:
            lines[f["reason"]] = f"reason: {re.sub(r'\s+', ' ', reasons[n]).strip()}"
    return "\n".join(lines) + ("\n" if md.endswith("\n") else "")


def fields(md: str, tid: str) -> dict[int, dict[str, str]]:
    """{route no: {"rating": text, "reason": text}} as written in topic `tid` (blank when not filled)."""
    lines = md.splitlines()
    for t, a, b in _sections(md):
        if t == tid:
            return {n: {k: (m[2].strip() if (m := dz._FIELD.match(lines[i])) else "") for k, i in f.items()}
                    for n, f in _route_lines(md, a, b).items()}
    return {}


def carry(old: str, new: str) -> str:
    """`new` with every rating and reason the owner wrote in `old` copied to the same topic and route."""
    lines = new.splitlines()
    for tid, a, b in _sections(new):
        was = fields(old, tid)
        for n, f in _route_lines(new, a, b).items():
            for k, i in f.items():
                if (v := was.get(n, {}).get(k, "")):
                    lines[i] = f"{k}: {v}"
    return "\n".join(lines) + ("\n" if new.endswith("\n") else "")


def progress(md: str) -> dict:
    done, todo = 0, []
    for tid, _, _ in _sections(md):
        r = rated(md, tid)
        if r and all(v for v in r.values()):
            done += 1
        else:
            todo.append(tid)
    return {"rated": done, "unrated": len(todo), "next": todo[0] if todo else None}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m runner.scoring.rate")
    ap.add_argument("pass_", metavar="pass")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("progress")
    sub.add_parser("next")
    s = sub.add_parser("show")
    s.add_argument("topic")
    st = sub.add_parser("set")
    st.add_argument("topic")
    st.add_argument("ratings", nargs="+")
    st.add_argument("--reason", nargs=2, action="append", default=[], metavar=("ROUTE", "TEXT"))
    ns = ap.parse_args(argv)
    f = sheet_path(ns.pass_)
    md = f.read_text(encoding="utf-8")
    try:
        if ns.cmd == "progress":
            print(progress(md))
        elif ns.cmd == "next":
            nxt = progress(md)["next"]
            print(show(md, nxt) if nxt else "every topic is rated")
        elif ns.cmd == "show":
            print(show(md, ns.topic), end="")
        else:
            out = set_ratings(md, ns.topic, ns.ratings, {int(n): t for n, t in ns.reason})
            dz._write(f, out)
            print(f"{ns.topic}: {rated(out, ns.topic)}")
    except (KeyError, ValueError) as e:
        print(f"rate: {e.args[0] if e.args else e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
