"""Load and validate the hand-written scoring inputs under `scoring/` (single sources of truth, owner-editable)."""
from __future__ import annotations
import fnmatch
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from runner import paths


class InputError(ValueError):
    pass


REPORT_DEFAULTS = {"outlier_factor": 3.0}


@dataclass(frozen=True)
class Weights:
    dimensions: dict[str, float]
    parts: dict[str, dict[str, float]]          # dimension -> part -> points (dimensions without parts: absent)
    scales: dict[str, float] = field(default_factory=dict)   # measurement scales; defaults to empty dict if absent
    report: dict[str, float] = field(default_factory=lambda: dict(REPORT_DEFAULTS))   # report.md settings

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
    scales_raw = raw.get("scales", {})
    scales = {}
    for k, v in scales_raw.items():
        # Only accept real numbers (int, float), not bool (which is a subclass of int in Python)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InputError(f"{path}: [scales] {k} must be a number, got {v!r}")
        try:
            fv = float(v)
        except (ValueError, OverflowError) as e:
            raise InputError(f"{path}: [scales] {k} must be a number, got {v!r}") from e
        if not math.isfinite(fv):
            raise InputError(f"{path}: [scales] {k} must be finite, got {fv!r}")
        if k == "size_plateau_fraction" and not 0 < fv < 1:
            raise InputError(f"{path}: [scales] size_plateau_fraction must be between 0 and 1, got {fv}")
        if k == "size_zero_multiple" and fv <= 1:
            raise InputError(f"{path}: [scales] size_zero_multiple must be > 1, got {fv}")
        if k == "ratio_cap" and fv <= 1:
            raise InputError(f"{path}: [scales] ratio_cap must be > 1, got {fv}")
        scales[k] = fv
    report = dict(REPORT_DEFAULTS)
    for k, v in raw.get("report", {}).items():
        if k not in REPORT_DEFAULTS:
            raise InputError(f"{path}: [report] unknown key {k!r} (known: {sorted(REPORT_DEFAULTS)})")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise InputError(f"{path}: [report] {k} must be a finite number, got {v!r}")
        if k == "outlier_factor" and v <= 1:
            raise InputError(f"{path}: [report] outlier_factor must be > 1, got {v}")
        report[k] = float(v)
    return Weights(dims, parts, scales, report)


@dataclass(frozen=True)
class ViolationSeverity:
    """scoring/violations.toml (R36): a severity (0..1) per arm-violation `kind`, `default` for an unlisted one."""
    default: float
    by_kind: dict[str, float]

    def of(self, kind) -> float:
        return self.by_kind.get(kind, self.default) if isinstance(kind, str) else self.default


def _severity(path: Path, what: str, v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1:
        raise InputError(f"{path}: {what} must be a number from 0 to 1, got {v!r}")
    return float(v)


def load_violations(path: Path | None = None) -> ViolationSeverity:
    path = path or paths.SCORING_INPUTS / "violations.toml"
    raw = _toml(path)
    if set(raw) - {"default", "by_kind"} or "default" not in raw or not isinstance(raw.get("by_kind", {}), dict):
        raise InputError(f"{path}: needs `default` and an optional [by_kind] table, nothing else")
    return ViolationSeverity(_severity(path, "default", raw["default"]),
                             {k: _severity(path, f"by_kind.{k}", v) for k, v in sorted(raw.get("by_kind", {}).items())})


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


EVIDENCE_KINDS = {"repo", "diff", "commits", "stale_list", "transcript", "questions", "gates", "setup"}


@dataclass(frozen=True)
class Rubric:
    part: str
    dimension: str
    unit: str
    steps: tuple[int, ...]
    evidence: tuple[str, ...]
    levels: dict[int, str]
    lenses: tuple[dict, ...]
    not_applicable: bool = False    # R5/R27: a judge may answer "not applicable" (step units only)


def load_rubrics(root: Path | None = None) -> dict[str, Rubric]:
    root = root or paths.SCORING_INPUTS / "rubrics"
    out: dict[str, Rubric] = {}
    for f in sorted(root.glob("*.toml")):
        raw = _toml(f)
        levels = {int(k): v for k, v in raw.get("levels", {}).items()}
        lenses = tuple(raw.get("lens", []))
        r = Rubric(part=f.stem, dimension=raw["dimension"], unit=raw.get("unit", "step"),
                   steps=tuple(raw.get("steps", range(1, 8))), evidence=tuple(raw["evidence"]),
                   levels=levels, lenses=lenses, not_applicable=raw.get("not_applicable", False))
        if sorted(levels) != [0, 1, 2, 3, 4] or len(lenses) != 3 or not set(r.evidence) <= EVIDENCE_KINDS \
                or any(set(l) != {"name", "perspective"} for l in lenses) or r.unit not in ("step", "arm"):
            raise InputError(f"{f}: needs levels 0-4, three lenses {{name, perspective}}, known evidence, unit")
        if not isinstance(r.not_applicable, bool) or (r.not_applicable and r.unit != "step"):
            raise InputError(f"{f}: not_applicable must be true or false, and true only for unit = \"step\"")
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
