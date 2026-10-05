"""Readers for one arm-step's evidence directory (results/<pass>/<arm>/<NN>/). Pure: no Docker, no git, no LLM.
Every reader returns values.val(...) or values.missing(...), never raises on bad evidence."""
from __future__ import annotations
import json
from pathlib import Path
from runner import paths
from runner.scoring import values


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(paths.REPO_ROOT))
    except ValueError:
        return str(p)


def read_json(p: Path) -> dict:
    try:
        return values.val(json.loads(p.read_text()), rel(p))
    except FileNotFoundError:
        return values.missing(rel(p), "no such file")
    except (OSError, json.JSONDecodeError) as e:
        return values.missing(rel(p), f"unreadable: {e}")


def hidden_summary(step_dir: Path) -> dict:
    return read_json(step_dir / "hidden" / "summary.json")


def all_fail(pass_dir: Path, arms: list[str]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for step in range(1, 8):
        failing: set[str] | None = None
        for arm in arms:
            s = hidden_summary(pass_dir / arm / f"{step:02d}")
            if values.is_missing(s) or not s["value"].get("scoreable", True):
                continue
            f = {t for t, o in s["value"].get("tests", {}).items() if o != "passed"}
            failing = f if failing is None else failing & f
        if failing:
            out[step] = sorted(failing)
    return out
