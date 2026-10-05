"""Load and validate the hand-written scoring inputs under `scoring/` (single sources of truth, owner-editable)."""
from __future__ import annotations
import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path
from runner import paths


class InputError(ValueError):
    pass


@dataclass(frozen=True)
class Weights:
    dimensions: dict[str, float]
    parts: dict[str, dict[str, float]]          # dimension -> part -> points (dimensions without parts: absent)

    def part_share(self, dim: str, part: str) -> float:
        return self.parts[dim][part] / self.dimensions[dim]


def _toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise InputError(f"{path}: {e}") from e


def load_weights(path: Path | None = None) -> Weights:
    path = path or paths.SCORING_INPUTS / "weights.toml"
    raw = _toml(path)
    dims = {k: float(v) for k, v in raw.get("dimensions", {}).items()}
    if abs(sum(dims.values()) - 100) > 1e-9:
        raise InputError(f"{path}: dimension weights must sum to 100, got {sum(dims.values())}")
    parts = {d: {k: float(v) for k, v in ps.items()} for d, ps in raw.get("parts", {}).items()}
    for d, ps in parts.items():
        if d not in dims:
            raise InputError(f"{path}: parts for unknown dimension {d!r}")
        if abs(sum(ps.values()) - dims[d]) > 1e-9:
            raise InputError(f"{path}: parts of {d} sum to {sum(ps.values())}, not {dims[d]}")
    return Weights(dims, parts)


_KINDS = {"requirement", "test", "doc", "code"}


@dataclass(frozen=True)
class StaleList:
    step: int
    stale: list[dict]
    legitimate: list[str]


def load_stale(step: int, root: Path | None = None) -> StaleList | None:
    if step == 1:
        return None
    path = (root or paths.SCORING_INPUTS / "stale") / f"step-{step:02d}.toml"
    raw = _toml(path)
    stale = raw.get("stale", [])
    for i in stale:
        if set(i) != {"id", "kind", "what", "why"} or i["kind"] not in _KINDS:
            raise InputError(f"{path}: bad stale item {i!r}")
    legit = raw.get("legitimate", {}).get("paths", [])
    if not legit:
        raise InputError(f"{path}: [legitimate] paths is empty")
    return StaleList(step, stale, legit)


def legitimate(path: str, s: StaleList) -> bool:
    """`**` matches across directories (fnmatch's `*` already does); patterns are repo-relative."""
    return any(fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, pat.replace("/**", "")) for pat in s.legitimate)
