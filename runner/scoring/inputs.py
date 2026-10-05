"""Load and validate the hand-written scoring inputs under `scoring/` (single sources of truth, owner-editable)."""
from __future__ import annotations
import fnmatch
import re
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


EVIDENCE_KINDS = {"repo", "diff", "stale_list", "transcript", "questions", "gates", "setup"}


@dataclass(frozen=True)
class Rubric:
    part: str
    dimension: str
    unit: str
    steps: tuple[int, ...]
    evidence: tuple[str, ...]
    levels: dict[int, str]
    lenses: tuple[dict, ...]


def load_rubrics(root: Path | None = None) -> dict[str, Rubric]:
    root = root or paths.SCORING_INPUTS / "rubrics"
    out: dict[str, Rubric] = {}
    for f in sorted(root.glob("*.toml")):
        raw = _toml(f)
        levels = {int(k): v for k, v in raw.get("levels", {}).items()}
        lenses = tuple(raw.get("lens", []))
        r = Rubric(part=f.stem, dimension=raw["dimension"], unit=raw.get("unit", "step"),
                   steps=tuple(raw.get("steps", range(1, 8))), evidence=tuple(raw["evidence"]),
                   levels=levels, lenses=lenses)
        if sorted(levels) != [0, 1, 2, 3, 4] or len(lenses) != 3 or not set(r.evidence) <= EVIDENCE_KINDS \
                or any(set(l) != {"name", "perspective"} for l in lenses) or r.unit not in ("step", "arm"):
            raise InputError(f"{f}: needs levels 0-4, three lenses {{name, perspective}}, known evidence, unit")
        out[r.part] = r
    return out


@dataclass(frozen=True)
class Exclusions:
    defects: frozenset[str]
    reviewed: frozenset[str]
    entries: list[dict]


def load_excluded(path: Path | None = None) -> Exclusions:
    path = path or paths.SCORING_INPUTS / "excluded-tests.toml"
    raw = _toml(path) if path.exists() else {}
    entries = raw.get("test", [])
    for e in entries:
        if set(e) != {"id", "verdict", "reason", "decided"} or e["verdict"] not in ("defect", "hard"):
            raise InputError(f"{path}: bad entry {e!r}")
    return Exclusions(frozenset(e["id"] for e in entries if e["verdict"] == "defect"),
                      frozenset(e["id"] for e in entries), entries)


@dataclass(frozen=True)
class PhaseRules:
    """Common-phase classifier rules (scoring/phases.toml). Globs are repo-relative fnmatch patterns (`/**` also
    matches the directory itself); the rest are compiled regexes."""
    spec_globs: tuple[str, ...]
    test_globs: tuple[str, ...]
    test_commands: tuple[re.Pattern, ...]       # at the start of a Bash call's simple commands, prefixes stripped
    command_prefixes: tuple[re.Pattern, ...]    # wrappers stripped from a simple command's start (uv run, env, ...)
    test_calls: tuple[re.Pattern, ...]          # over the code a Bash call feeds an interpreter: test runs from code
    review_markers: tuple[re.Pattern, ...]      # over a Skill/Task/Agent call's input, or a turn's method label
    failure_markers: tuple[re.Pattern, ...]     # over a test command's output: failures set rework mode (R11)
    write_commands: tuple[re.Pattern, ...]      # over a Bash command, heredoc bodies removed; (?P<path>) = target
    write_calls: tuple[re.Pattern, ...]         # over the code a Bash call feeds an interpreter; same groups
    code_interpreters: tuple[re.Pattern, ...]   # command words whose heredoc body / -c string is code


_PHASE_GLOBS = ("spec_globs", "test_globs")
_PHASE_REGEXES = ("test_commands", "command_prefixes", "test_calls", "review_markers", "failure_markers", "write_commands",
                  "write_calls", "code_interpreters")


def load_phase_rules(path: Path | None = None) -> PhaseRules:
    path = path or paths.SCORING_INPUTS / "phases.toml"
    raw = _toml(path)
    keys = set(_PHASE_GLOBS + _PHASE_REGEXES)
    if set(raw) != keys or not all(isinstance(raw[k], list) and all(isinstance(x, str) for x in raw[k])
                                   for k in keys):
        raise InputError(f"{path}: needs exactly the string lists {sorted(keys)}")
    try:
        rx = {k: tuple(re.compile(x) for x in raw[k]) for k in _PHASE_REGEXES}
    except re.error as e:
        raise InputError(f"{path}: bad regex: {e}") from e
    return PhaseRules(spec_globs=tuple(raw["spec_globs"]), test_globs=tuple(raw["test_globs"]), **rx)
