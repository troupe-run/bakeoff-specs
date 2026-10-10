"""Code size for the per-KLOC code-quality parts `types` and `lint` (owner rule, 2026-10-10): `quality/size.json`.

"Lines" are non-blank lines in the `*.py` files the linters checked for that arm at that step. The two linters do
not check the same files (`runner/quality.py`), so each part is normalised by its own linter's lines:

- **lint** — ruff runs as `ruff check --isolated .` from the repo root: every `*.py` it discovers, src AND tests.
  ruff's own discovery skips `.venv` (and git-ignored paths) but, observed with the pinned 0.16.9, NOT hidden
  directories, `build/` or `__pycache__`; we count the files it checks minus `EXCLUDED_DIRS`.
- **types** — mypy runs as `mypy --strict <targets>`, where `quality.targets()` is `["src"]` whenever `src/` exists
  (else the entry-point package, else `.`). So mypy usually checks src only, never tests: `type_lines` counts only
  the files under those targets (mypy's discovery also skips hidden directories, `__pycache__`, `site-packages` and
  `node_modules`), minus `EXCLUDED_DIRS`. Normalising mypy errors by src+tests lines would dilute them by test code
  mypy never looked at.

Two ways to measure, same rules:
- `CONTAINER_SCRIPT` — the quality stage, inside the tester container on the arm's own copy: the file lists come
  from the tools themselves (`ruff --show-files`, mypy's `create_source_list`), so the counted set is exactly what
  was checked. Uses only the harness interpreter (`/opt/harness/bin/python -I`), never the arm's.
- `measure_tree` — a host walk mirroring those rules, used for pass 1, whose quality runs predate size.json: the
  step's tree survives only as the anonymised copy (`anon/<label>/<NN>/repo/`, the committed tree; the anonymiser
  rewrites names only, so line counts match). Untracked files that sat in the arm's working copy are not in it.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

# Never counted, wherever they appear as a directory component: virtualenvs, tool caches, VCS, build output.
EXCLUDED_DIRS = frozenset({".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
                           ".hypothesis", ".tox", ".nox", ".uv-cache", ".git", ".eggs", "build", "dist",
                           "node_modules", "site-packages"})
_MYPY_SKIPS = frozenset({"__pycache__", "site-packages", "node_modules"})    # plus any hidden directory

HOW_TOOLS = ("non-blank lines of the *.py files each tool checked, from the tools' own file lists in the tester "
             "container (lint: `ruff check --isolated --show-files .`, src and tests; types: mypy's sources for "
             "its targets); virtualenvs, caches, .git and build output excluded")
HOW_ANON = ("non-blank lines of *.py in the step's anonymised committed tree (the anonymiser rewrites names only); "
            "lint: every *.py ruff would check from the repo root (src and tests); types: only mypy's targets; "
            "virtualenvs, caches, .git and build output excluded")


def excluded_dir(name: str) -> bool:
    return name in EXCLUDED_DIRS or name.endswith(".egg-info")


def nonblank_lines(f: Path) -> int:
    """Non-blank lines of a regular file (never through a link); anything else counts 0."""
    try:
        if not stat.S_ISREG(os.lstat(f).st_mode):
            return 0
        with open(f, "rb") as h:
            return sum(1 for line in h if line.strip())
    except OSError:
        return 0


def py_files(repo: Path, start: str, *, mypy_rules: bool = False) -> list[Path]:
    """`*.py` under `repo/start` (a directory or one file), links never followed. `mypy_rules` also skips hidden
    directories and mypy's own skips (types); without it, hidden directories are walked as ruff does (lint)."""
    root = repo / start
    try:
        st = os.lstat(root)
    except OSError:
        return []
    if stat.S_ISREG(st.st_mode):
        return [root] if root.suffix == ".py" else []
    if not stat.S_ISDIR(st.st_mode):
        return []
    out = []
    for d, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(x for x in dirs if not excluded_dir(x)
                         and not (mypy_rules and (x.startswith(".") or x in _MYPY_SKIPS)))
        out += [Path(d) / f for f in sorted(files) if f.endswith(".py")]
    return out


def measure_tree(repo: Path, targets: list[str]) -> dict:
    lint = py_files(repo, ".")
    typed = sorted({f for t in targets for f in py_files(repo, t, mypy_rules=True)})
    return {"lint_lines": sum(map(nonblank_lines, lint)), "lint_files": len(lint),
            "type_lines": sum(map(nonblank_lines, typed)), "type_files": len(typed), "targets": list(targets)}


# Run in the tester container as `/opt/harness/bin/python -I -c CONTAINER_SCRIPT <excluded json> <targets...>`,
# cwd the arm's copy. Prints one JSON object; any failure exits nonzero (recorded as a crash, never as 0 lines).
CONTAINER_SCRIPT = r"""
import json, os, stat, subprocess, sys
EXCL = set(json.loads(sys.argv[1])); targets = sys.argv[2:]
def keep(p):
    parts = os.path.normpath(p).split(os.sep)
    return p.endswith(".py") and not any(x in EXCL or x.endswith(".egg-info") for x in parts[:-1])
def lines(f):
    if not stat.S_ISREG(os.lstat(f).st_mode):
        return 0
    with open(f, "rb") as h:
        return sum(1 for l in h if l.strip())
r = subprocess.run(["/opt/harness/bin/ruff", "check", "--isolated", "--show-files", "--no-cache", "."],
                   capture_output=True, text=True)
if r.returncode != 0:
    sys.stderr.write(r.stderr); sys.exit(3)
lint = sorted({os.path.relpath(l.strip()) for l in r.stdout.splitlines() if l.strip()})
from mypy.find_sources import create_source_list
from mypy.options import Options
typed = sorted({os.path.relpath(s.path) for s in create_source_list(targets, Options()) if s.path})
lint = [f for f in lint if keep(f)]; typed = [f for f in typed if keep(f)]
print(json.dumps({"lint_lines": sum(map(lines, lint)), "lint_files": len(lint),
                  "type_lines": sum(map(lines, typed)), "type_files": len(typed), "targets": targets}))
"""


def container_cmd(targets: list[str]) -> list[str]:
    return ["/opt/harness/bin/python", "-I", "-c", CONTAINER_SCRIPT, json.dumps(sorted(EXCLUDED_DIRS)), *targets]


def parse_container(rc: int | None, stdout: str) -> dict | None:
    """The measurement, or None when the run failed (nonzero rc, no JSON object with both line counts)."""
    if rc != 0:
        return None
    for line in reversed(stdout.strip().splitlines()):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if (isinstance(d, dict) and all(isinstance(d.get(k), int) and not isinstance(d.get(k), bool)
                                        for k in ("lint_lines", "type_lines"))):
            return d
        return None
    return None


def record(measured: dict | None, *, how: str, source: str, error: str | None = None) -> dict:
    """The size.json body. A failed measurement keeps `lint_lines`/`type_lines` None and says why (never 0 lines)."""
    if measured is None:
        return {"lint_lines": None, "type_lines": None, "how": how, "source": source,
                "error": error or "size measurement failed"}
    return {**measured, "how": how, "source": source}


# --- pass-1 backfill from the anonymised copies ---------------------------------------------------------------------

def backfill(pass_: str) -> list[Path]:
    """Write `results/<pass>/<arm>/<NN>/quality/size.json` from `anon/<label>/<NN>/repo/` for every step with a
    quality summary. Never overwrites a size.json the quality stage measured itself. The label is never written
    into size.json (results/<arm>/ is arm-named: it would de-anonymise the label)."""
    from runner import paths
    from runner.scoring import collect, judge
    label_of = {arm: label for label, arm in judge.anon_key(pass_).items()}
    anon = paths.scoring_out(pass_) / "anon"
    written = []
    for arm in collect.arms(paths.RESULTS / pass_):
        for d in sorted((paths.RESULTS / pass_ / arm).iterdir()):
            summary = d / "quality" / "summary.json"
            if not (d.is_dir() and d.name.isdigit() and summary.exists()):
                continue
            out = d / "quality" / "size.json"
            try:
                if json.loads(out.read_text()).get("source") == "quality":
                    continue
            except (OSError, ValueError, AttributeError):
                pass
            targets = json.loads(summary.read_text()).get("targets") or ["."]
            repo = anon / label_of[arm] / d.name / "repo" if arm in label_of else None
            if repo is None or not repo.is_dir():
                rec = record(None, how=HOW_ANON, source="anon-backfill", error="no anonymised tree for this step")
            else:
                rec = record(measure_tree(repo, targets), how=HOW_ANON, source="anon-backfill")
            out.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
            written.append(out)
    return written
