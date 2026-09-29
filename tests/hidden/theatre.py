"""Build and read theatre directories with exact bytes (no newline translation)."""
from __future__ import annotations
from pathlib import Path

def build(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return root

def read(root: Path, rel: str) -> str:
    with open(root / rel, encoding="utf-8", newline="") as fh:
        return fh.read()

def snapshot(root: Path, rels: list[str]) -> dict[str, str]:
    return {rel: read(root, rel) for rel in rels}

def share_with_arm(root: Path, top: Path) -> None:
    """Tester mode (runner/hidden.py): the arm's CLI runs under its own uid, so the theatre it works in is opened
    to it (0777) and every directory from `top` down to it gets traverse-only (+x) — nothing else, and nothing
    above `top`. The harness's own results dir stays 0700."""
    root.chmod(0o777)
    for d in root.parents:
        d.chmod(d.stat().st_mode | 0o111)
        if d == top:
            break
