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
