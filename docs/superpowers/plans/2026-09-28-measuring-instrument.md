# bakeoff-specs Plan 1 — the measuring instrument

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything the bake-off measures arms *against* — the CLI contract, the seven step briefs, the
product-owner brief, the hidden acceptance tests for every step, and a reference implementation that proves
each step's hidden tests are passable and that they detect the behaviour's absence.

**Architecture:** Hidden tests are black-box: they build a throwaway theatre directory, invoke the arm's
`troupe config …` CLI as a subprocess (the command prefix is injectable, so Plan 2 can point it into a
container), and assert on stdout, exit code, and the exact bytes of files afterwards. Each test declares the
range of steps it is valid for, so one suite serves all seven steps (step 3 retires a step-1 behaviour).
A reference implementation, ported from spike A, gates each behaviour on the step that introduces it
(environment variable `TROUPE_REF_STEP`, default 7). A validation script proves suite N passes on the
reference at step N, and that every test *first valid* at step N fails on the reference at step N-1.

**Tech Stack:** Python 3.12, uv, pytest, ruamel.yaml 0.19.x, eventsourcing 9.5.x, watchfiles, jsonschema.

**Spec:** [`docs/design.md`](../../design.md) (approved 2026-09-28). Prior art: `../spike-config-roundtrip/`
(FINDINGS.md, `src/spike_config_roundtrip/surgical.py`), `../spike-claude-docker/FINDINGS.md`.

**Scope:** this is Plan 1 of 3. Plan 2 (runner: container stage, arm setup and checklists, PO agent, gates,
evidence, model-pin verification) and Plan 3 (scoring and judging) are written after this plan's review.

## Owner decisions needed before Task 2 (proposed defaults — confirm or change)

- **D1 — Step 5 override syntax.** Step 5 says new keys under an included subtree go to the *including* file
  as an override. A scalar `coder: file:agents/coder.yaml` has nowhere to put an override, so the scenario
  must define one. Proposed: an include may also be written in mapping form with an `$include` key, and
  sibling keys are overrides that deep-merge over the included content:
  ```yaml
  coder:
    $include: file:agents/coder.yaml
    temperature: 0.3        # override, lives in troupe.yml
  ```
  Setting a new key under `coder` when it is still in scalar form converts it to mapping form.
- **D2 — Step 6's bug needs to be absent from step 1's contract.** The design doc lists the alias rule under
  step 1. But step 6 is a *planted bug* about aliases: if step 1's contract already specifies alias handling,
  there is no bug to report. Proposed: step 1's contract is **silent on aliases** (a naive implementation
  will then silently change the anchor, as spike A's first version did), and the owner's alias rule becomes
  step 6's expected fix. Design doc §11 is amended accordingly.
- **D3 — The harness repo is public, and so are the hidden tests.** An arm with web search could find
  `troupe-run/bakeoff-specs` and read the hidden tests, the reference implementation and the step sequence
  (the design doc is already public). Proposed: make `troupe-run/bakeoff-specs` **private until the bake-off
  concludes**, then public. (Alternative: keep it public and deny WebSearch/WebFetch to every arm — but some
  methods research the web legitimately, and the design doc has already leaked the sequence.)

- **D4 — "below the trailing comment" for mapping keys too.** The owner chose that an item appended to a list
  that ends with a comment goes *below* the comment. The same situation arises when a key is added to a
  mapping that ends with a comment (e.g. a comment at the end of the file). Proposed: apply the same rule to
  mapping keys, for consistency — a new entry, list item or key, goes below its collection's trailing comment.

## Global Constraints

- Python `>=3.12`, managed with `uv`; `eventsourcing` for the event store and projection (design §3.1).
- Config at `<theatre>/.troupe/troupe.yml` or `.yaml` (design §3.1).
- Arms run `uv run troupe config …` from the repo root with `--theatre <dir>` (default: cwd) (design §3.2).
- Step 1 write-back is **byte-surgical**: only the changed value's bytes differ; tab-before-end-of-line-comment
  files and multi-document files are out of contract (design §11).
- Step 1 write-back rules (design §11): folded paragraph re-wrapped to its previous width; folded value
  gaining an indented line is refused; new keys copy neighbours' quoting; appended list item goes below a
  trailing comment; only the changed line's end-of-line comment is re-aligned (old column, or one space).
- Hidden tests never enter an arm repo (design §6).
- Each step's hidden suite includes all earlier still-valid tests (design §4).

## Review Focus

1. **A step's new tests pass against an implementation that lacks the behaviour** (the tests are vacuous).
   Covered by Task 12's negative validation: every test first valid at step N must fail on the reference
   run with `TROUPE_REF_STEP=N-1`.
2. **Byte assertions that are too loose** (asserting parsed values instead of file bytes, so a reformatting
   arm passes). Every write-back test compares whole-file bytes to a golden file (Task 4).
3. **Flaky watcher tests** (timing). Step 2 tests poll with a deadline instead of sleeping (Task 6), and
   Task 12 runs the step 2 suite 5 times.
4. **A contract that is ambiguous where tests are exact** (e.g. how `show` prints a float, trailing
   newlines). The contract states each output rule and Task 3 pins each with a test.
5. **Tests that depend on implementation details** (where an arm stores events, how it names files).
   Tests touch only the CLI and the theatre's config files; `.troupe/` contents other than config files are
   never read (Task 1's driver enforces this by construction).

## File Structure

```
bakeoff-specs/
  pyproject.toml                    # harness project: pytest + helpers (not the reference impl)
  scenario/
    contract.md                     # the CLI contract, per step
    steps/01-greenfield.md … 07-model-change.md   # step briefs handed to arms
    po-brief.md                     # product-owner agent's fixed brief
  tests/hidden/
    conftest.py                     # --impl, --step options; theatre + cli fixtures; step markers
    driver.py                       # run_cli(): command prefix, theatre dir, result object
    theatre.py                      # build a theatre from a dict of relative path -> text
    golden/step1/<case>/{before/,after/,cmd.txt}   # write-back corpus with exact expected bytes
    test_step1_show.py  test_step1_set.py  test_step1_writeback.py  test_step1_history.py
    test_step2_sync.py  test_step3_get_show.py  test_step4_lineage.py
    test_step5_overrides.py  test_step6_aliases.py  test_step7_remote_schema.py
  reference/                        # a uv project shaped exactly like an arm repo
    pyproject.toml                  # entry point: troupe = "troupe_ref.cli:main"
    src/troupe_ref/
      cli.py        # argparse front end; exit codes
      loader.py     # includes, provenance (from spike config.py)
      surgical.py   # byte-surgical write engine (from spike surgical.py, rules amended)
      store.py      # eventsourcing application: ConfigChanged events, history
      service.py    # reconcile/set orchestration (from spike service.py)
      step.py       # STEP = int(os.environ.get("TROUPE_REF_STEP", "7")); every step-gated branch reads it
  harness/
    validate_suites.py              # Task 12: positive and negative suite validation
```

---

### Task 1: Harness project, test driver, step selection, reference skeleton

**Files:**
- Create: `pyproject.toml`, `.gitignore`
- Create: `tests/__init__.py`, `tests/hidden/__init__.py`, `tests/selftest/__init__.py` (all empty), `tests/hidden/driver.py`, `tests/hidden/theatre.py`, `tests/hidden/conftest.py`
- Create: `tests/selftest/test_driver.py`, `tests/selftest/fake_troupe.py`
- Create: `reference/pyproject.toml`, `reference/src/troupe_ref/__init__.py` (empty), `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Produces: `driver.Result(code: int, out: str, err: str)`; `driver.Cli(prefix: list[str])` with
  `__call__(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None, timeout: float = 60) -> Result`
  (always places `--theatre <dir>` directly after the subcommand) and
  `spawn(self, sub: str, *args: str, theatre: Path, env=None) -> subprocess.Popen` for long-running `watch`;
  `theatre.build(root: Path, files: dict[str, str]) -> Path` (writes exact text, no newline translation, returns root);
  `theatre.read(root: Path, rel: str) -> str` (exact text); `theatre.snapshot(root: Path, rels: list[str]) -> dict[str, str]`;
  fixtures `cli: Cli`, `tmp_theatre: Path` (an empty directory); marker `@pytest.mark.steps(first, last=7)`;
  pytest options `--impl <dir>` (default `reference/`), `--step <1-7>` (default 7), `--cmd-prefix "<shell words>"`.

- [ ] **Step 1: Create the harness `pyproject.toml` and `.gitignore`**

```toml
# pyproject.toml
[project]
name = "bakeoff-specs"
version = "0"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["pytest>=8.3", "pyyaml>=6.0"]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers"
```

```gitignore
.venv/
__pycache__/
.pytest_cache/
reference/.venv/
results/**/tmp/
```

- [ ] **Step 2: Write the driver self-test against a fake CLI**

```python
# tests/selftest/fake_troupe.py — stands in for an arm; echoes argv and env as JSON
import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "actor": os.environ.get("TROUPE_ACTOR")}))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
```

```python
# tests/selftest/test_driver.py
import json, sys
from pathlib import Path
from tests.hidden.driver import Cli
from tests.hidden import theatre

FAKE = [sys.executable, str(Path(__file__).with_name("fake_troupe.py"))]

def test_theatre_goes_directly_after_subcommand(tmp_path):
    r = Cli(FAKE)("set", "a.b", "1", theatre=tmp_path)
    assert json.loads(r.out)["argv"] == ["config", "set", "--theatre", str(tmp_path), "a.b", "1"]

def test_exit_code_and_env_are_passed_through(tmp_path):
    r = Cli(FAKE)("show", "x", theatre=tmp_path, env={"FAKE_EXIT": "5", "TROUPE_ACTOR": "agent:a1"})
    assert r.code == 5
    assert json.loads(r.out)["actor"] == "agent:a1"

def test_build_writes_exact_bytes_including_crlf_and_no_final_newline(tmp_path):
    theatre.build(tmp_path, {".troupe/troupe.yml": "a: 1\r\nb: 2"})
    assert (tmp_path / ".troupe/troupe.yml").read_bytes() == b"a: 1\r\nb: 2"
    assert theatre.read(tmp_path, ".troupe/troupe.yml") == "a: 1\r\nb: 2"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/selftest -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.hidden.driver'`

- [ ] **Step 4: Implement the driver and theatre helpers**

```python
# tests/hidden/driver.py
"""Runs an arm's `troupe config` CLI as a black box. Only stdout, stderr, exit code and theatre files are observable."""
from __future__ import annotations
import os, subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

class Cli:
    def __init__(self, prefix: list[str]):
        self.prefix = prefix

    def _argv(self, sub: str, args: tuple[str, ...], theatre: Path) -> list[str]:
        return [*self.prefix, "config", sub, "--theatre", str(theatre), *args]

    def _env(self, env: dict[str, str] | None) -> dict[str, str]:
        merged = dict(os.environ)
        merged.pop("TROUPE_ACTOR", None)  # tests set identity explicitly
        merged.update(env or {})
        return merged

    def __call__(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None,
                 timeout: float = 60) -> Result:
        p = subprocess.run(self._argv(sub, args, theatre), capture_output=True, text=True,
                           env=self._env(env), timeout=timeout)
        return Result(p.returncode, p.stdout, p.stderr)

    def spawn(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
        return subprocess.Popen(self._argv(sub, args, theatre), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=self._env(env), start_new_session=True)
```

```python
# tests/hidden/theatre.py
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
```

- [ ] **Step 5: Run the self-test to verify it passes**

Run: `uv run pytest tests/selftest -v`
Expected: 3 passed

- [ ] **Step 6: Write the step-selection conftest and a self-test for it**

```python
# tests/hidden/conftest.py
from __future__ import annotations
import shlex
from pathlib import Path
import pytest
from .driver import Cli

REPO = Path(__file__).resolve().parents[2]

def pytest_addoption(parser):
    parser.addoption("--impl", default=str(REPO / "reference"), help="arm repo root (uv project)")
    parser.addoption("--step", type=int, default=7, help="scenario step whose suite to run (1-7)")
    parser.addoption("--cmd-prefix", default=None, help='overrides the command, e.g. "docker exec arm uv run troupe"')

def pytest_configure(config):
    config.addinivalue_line("markers", "steps(first, last=7): scenario steps this test is valid for")

def pytest_collection_modifyitems(config, items):
    step = config.getoption("--step")
    keep, drop = [], []
    for item in items:
        if not str(item.fspath).startswith(str(Path(__file__).parent)):
            keep.append(item)
            continue
        m = item.get_closest_marker("steps")
        if m is None:
            raise pytest.UsageError(f"{item.nodeid}: every hidden test needs @pytest.mark.steps(first, last)")
        first, last = m.args[0], (m.args[1] if len(m.args) > 1 else 7)
        (keep if first <= step <= last else drop).append(item)
    config.hook.pytest_deselected(items=drop)
    items[:] = keep

@pytest.fixture(scope="session")
def cli(request) -> Cli:
    prefix = request.config.getoption("--cmd-prefix")
    if prefix:
        return Cli(shlex.split(prefix))
    return Cli(["uv", "run", "--quiet", "--project", request.config.getoption("--impl"), "troupe"])

@pytest.fixture
def tmp_theatre(tmp_path) -> Path:
    return tmp_path
```

```python
# tests/hidden/test_selection_selftest.py
import pytest

@pytest.mark.steps(1, 2)
def test_selftest_only_steps_1_and_2():
    pass

@pytest.mark.steps(3)
def test_selftest_steps_3_onwards():
    pass
```

- [ ] **Step 7: Verify selection works**

Run: `uv run pytest tests/hidden/test_selection_selftest.py --step 2 -v`
Expected: 1 passed, 1 deselected (`test_selftest_only_steps_1_and_2`)
Run: `uv run pytest tests/hidden/test_selection_selftest.py --step 3 -v`
Expected: 1 passed, 1 deselected (`test_selftest_steps_3_onwards` passes)
Then delete `tests/hidden/test_selection_selftest.py` (it would otherwise count as a hidden test).

- [ ] **Step 8: Create the reference skeleton**

```toml
# reference/pyproject.toml
[project]
name = "troupe-ref"
version = "0"
requires-python = ">=3.12"
dependencies = ["ruamel.yaml>=0.19.1,<0.20", "eventsourcing>=9.5.5,<9.6", "watchfiles>=1.3", "jsonschema[format]>=4.26"]

[project.scripts]
troupe = "troupe_ref.cli:main"

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

```python
# reference/src/troupe_ref/cli.py
"""Reference implementation CLI. Exit codes per scenario/contract.md."""
from __future__ import annotations
import argparse, sys

EXIT_OK, EXIT_USAGE, EXIT_REFUSED, EXIT_LOAD, EXIT_PATH = 0, 2, 3, 4, 5

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="troupe")
    top = p.add_subparsers(dest="area", required=True)
    config = top.add_parser("config").add_subparsers(dest="sub", required=True)
    for name in ("show", "set", "history"):
        sp = config.add_parser(name)
        sp.add_argument("--theatre", default=".")
        sp.add_argument("args", nargs="*")
    return p

def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    print(f"troupe config {ns.sub}: not implemented", file=sys.stderr)
    return 99

if __name__ == "__main__":
    sys.exit(main())
```

Run: `cd reference && uv sync && uv run troupe config show --theatre /tmp x; echo "exit=$?"`
Expected: `troupe config show: not implemented` and `exit=99`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore tests reference
git commit -m "Harness: black-box CLI driver, step selection, reference skeleton"
```

---

### Task 2: Scenario documents — contract, step briefs, product-owner brief

These are the documents arms receive (contract sections and step briefs) or that the PO agent answers from.
They are **owner-reviewed before any arm runs**. The contract below assumes D1, D2 and D4 are accepted as
proposed; if the owner changes one, change the matching section here *and* the tests in the owning task.

**Files:**
- Create: `scenario/contract.md`, `scenario/steps/01-greenfield.md` … `scenario/steps/07-model-change.md`, `scenario/po-brief.md`
- Modify: `docs/design.md` §11 (move the alias rule from step 1 to step 6, per D2)

**Interfaces:**
- Produces: the exit codes, output formats and path syntax every later task's tests assert on.

- [ ] **Step 1: Write `scenario/contract.md`** with exactly this content:

````markdown
# troupe config — CLI contract

Hidden acceptance tests use only what this document specifies. Each step's brief says which sections are in
force; sections marked "from step N" do not apply before step N.

## General (from step 1)

- **Invocation:** `troupe config <subcommand> --theatre <dir> [arguments]`, run as `uv run troupe …` from the
  repository root. `--theatre` defaults to the current directory.
- **Config file:** `<dir>/.troupe/troupe.yml` or `<dir>/.troupe/troupe.yaml`. Neither, or both → exit 4.
- **State:** the implementation may keep state only under `<dir>/.troupe/`, and must not create or modify any
  file other than as this contract's write-back rules require.
- **Paths:** keys separated by `.`; a segment of digits indexes a list (0-based). Keys that contain `.`, and
  mappings with digit-only keys, are out of contract.
- **Values on the command line:** `VALUE` is parsed as a single YAML 1.2 (core schema) flow node: `0.2` is a
  float, `true` a boolean, `null` null, `abc` and `"0.2"` strings, `{a: 1}` a mapping, `[a, b]` a list, and
  `"line one\nline two\n"` a multi-line string.
- **Printing a scalar:** a string is printed exactly, followed by `\n` unless it already ends with `\n`;
  booleans as `true`/`false`; null as `null`; integers in decimal; floats as Python's `repr()` (e.g. `0.2`).
- **Exit codes:** `0` success · `2` usage error · `3` write refused (no file changed) · `4` configuration cannot
  be loaded · `5` path not found, or the path is the wrong kind of node for the command. On any non-zero exit,
  stdout is empty and stderr has a message naming the offending path or file.
- **Out of contract** (behaviour undefined, never tested): files with a TAB before an end-of-line comment,
  multi-document files, YAML anchors/aliases/merge keys (until step 6), concurrent writers.

## Includes (from step 1)

- A string value that starts with `file:` is an **include** of the path after `file:`, relative to the
  directory of the file containing it.
- Target ending `.yml` or `.yaml`: its content is embedded as if written in place of the string.
  Any other target: the value is the target file's exact text.
- Includes are recursive. A missing target, or a cycle, → exit 4.

## `show PATH` (step 1 and 2)

Prints the value at `PATH` if it is a scalar (a text include is a string). A mapping or list → exit 5.

## `set PATH VALUE` (from step 1)

Updates the configuration and writes the change back to the files, **byte-surgically**: after a successful
`set`, the only bytes that differ in any file are those this section requires to change.

Where the change is written:
1. An existing value is changed in the file that contains it. For a text include, the target file's
   content becomes `VALUE` exactly (`VALUE` must then be a string, else exit 3).
2. A new key is written into the file containing the deepest existing ancestor mapping of `PATH`; missing
   intermediate mappings are created there. *(Changed at step 5.)*
3. `PATH` ending in the index equal to a list's length appends to that list. A larger index → exit 5.
4. Replacing the value at a path whose whole value comes from an include (e.g. `agents.coder` when it is
   `file:agents/coder.yaml`) → exit 3.

How it is written:
- A changed scalar keeps its quoting style if that style can represent the new value; otherwise plain if
  possible, else single-quoted, else double-quoted.
- A new key, and a new string value, copy the quoting style of the preceding sibling key or value; with no
  sibling, plain (or the minimal quoting the text needs).
- A new collection value is written in block style at the file's indentation (default 2), unless its parent
  is a flow collection, in which case it is written in flow style.
- A multi-line string replacing a plain or quoted scalar is written as a literal block (`|`, with `|-` when
  the value has no trailing newline). A block scalar keeps its indicator and chomping unless the value's
  trailing newlines require a different chomping.
- **Folded (`>`) values:** paragraphs whose text is unchanged keep their bytes. A changed paragraph is
  re-wrapped, greedily by word, at the width of the longest content line of that paragraph before the
  change (a single word longer than the width takes a line of its own). A change that would put a
  more-indented line into a folded value → exit 3.
- **New entries and trailing comments:** a new list item or mapping key goes after the collection's last
  entry *and below any comment lines that follow it* before the next less-indented line.
- **End-of-line comments:** when a changed value's length changes, the comment on that line is moved back to
  its previous column; if the new value reaches that column, exactly one space separates value and comment.
  No other line changes.

## `history [PATH]` (from step 1)

Prints the configuration's events as JSON Lines, oldest first; with `PATH`, only events whose path equals
`PATH` or starts with `PATH.`. Each line is an object with at least:
`{"seq": <int from 1>, "op": "import" | "set" | "remove", "path": "<dotted>", "old": <json>, "new": <json>}`.
- Events are per **leaf** (a scalar, including a text-include string; list items are `list.0`, `list.1`, …).
- The first command run against a theatre imports it: one `import` event per leaf, `old` null.
- A `set` emits one `set` event per leaf whose value it changes or creates, and one `remove` event (`new`
  null) per leaf that no longer exists. A `set` that changes nothing emits nothing.

## Sync with files (from step 2)

- `troupe config watch --theatre <dir>` runs in the foreground until SIGINT or SIGTERM (then exits 0). Once it
  is watching, it prints one line `watching <dir>` to stdout and flushes. Within 2 seconds of any change to
  the config file or an included file, it reconciles.
- **Reconcile:** compare the files with the configuration and emit a `set`/`remove` event for each leaf that
  differs. A formatting-only or comment-only edit emits nothing.
- Every other command except `history` reconciles first, so edits made while nothing was running are picked
  up. `history` never reconciles: it reports what has been recorded.
- A `set` while `watch` runs emits exactly the `set`'s own events; its write-back produces no further events.
- An include added by a hand edit is followed; its leaves appear as `set` events.

## `get` and `show` (from step 3 — replaces "show PATH (step 1 and 2)")

- `get PATH` prints a scalar as `show` did in step 1. A mapping or list → exit 5, and stderr mentions
  `config show`.
- `show [PATH]` prints a scalar like `get`; a mapping or list is printed as YAML (block style, includes
  resolved, text includes as literal blocks). `PATH` omitted → the whole configuration.
- `show [PATH] --sources` prints the same YAML with an end-of-line comment `# from <file>` on every line that
  holds a scalar, where `<file>` is the file the scalar comes from, relative to the theatre directory, with
  `/` separators.

## Lineage (from step 4)

Every `history` event also has:
- `"actor"`: `{"kind": "human" | "agent" | "unknown", "id": <string or null>}`
- `"via"`: `"import"` | `"cli"` | `"file"`
- `"at"`: RFC 3339 UTC timestamp ending in `Z`

A CLI command's actor comes from the `TROUPE_ACTOR` environment variable, `human:<id>` or `agent:<id>`
(anything else → exit 2); unset → `{"kind": "human", "id": <login name>}`. Imports and file-originated events
have actor `{"kind": "unknown", "id": null}`.

## Overrides (from step 5 — replaces rule 2 under `set`)

- An include may be written in **mapping form**: a mapping with an `$include` key whose value is the include
  string. Its other keys are **overrides**: the value is the included content deep-merged with the overrides
  (mappings merge recursively; scalars and lists in the override replace).
- A new key whose deepest existing ancestor comes from an included file is written as an override in the
  *including* file. A scalar-form include is first converted to mapping form, keeping any end-of-line comment
  on the key's line:
  `coder: file:agents/coder.yaml  # c` → `coder:  # c` / `  $include: file:agents/coder.yaml` / `  temperature: 0.3`
- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).
- Setting an existing value that is overridden changes the override; one that is not overridden is still
  changed in the file it comes from.

## Aliases (from step 6)

- Setting a path whose value is defined at an anchor (`&name`) changes it at the anchor, and so everywhere
  the alias is used.
- Setting a path reached **through an alias** (`*name`) → exit 3; stderr mentions `--expand-alias`.
- `set --expand-alias PATH VALUE` replaces that alias with a block-style copy of the anchored node, puts the
  end-of-line comment `# expanded from *<name> by troupe` on the key's line (two spaces before `#`), and then
  sets the value in the copy. Nothing else changes; other aliases still refer to the anchor.
- Merge keys (`<<`) are never written.

## Remote includes and schema (from step 7)

- A string starting `https://` or `http://` is also an include; it is fetched when the configuration loads
  (YAML if the URL path ends `.yml`/`.yaml`, otherwise text). A failed fetch → exit 4.
- Changing a value that comes from a remote include → exit 3; stderr contains the include string exactly as
  written in the local file. (New keys under a remote include become local overrides, per step 5.)
- `<dir>/.troupe/troupe.schema.json` (JSON Schema 2020-12), if present, describes the configuration. A string
  whose schema — found through `properties`, `items` and `additionalProperties` — has `"format": "uri"` is a
  literal, not an include. A string tagged `!literal` is a literal.
- The loaded configuration must validate against the schema, else exit 4. A `set` that would make it invalid
  → exit 3.
- `set PATH VALUE` where `VALUE` is a string that would be read as an include and the schema does not mark
  `PATH` as `format: uri` writes it tagged `!literal`, unless `--include` is given.
````

- [ ] **Step 2: Write the seven step briefs.** Each is what the arm receives as the user's request, in its
  own workflow. Each brief ends with the line `The CLI contract sections in force are listed below; the full
  contract is attached.` followed by the section names. Content:

`scenario/steps/01-greenfield.md`:
```markdown
# Step 1 — troupe configuration: load, show, set

troupe is an AI orchestration tool. Each project ("theatre") keeps its configuration in `.troupe/troupe.yml`,
which can be split across files with includes. Build the configuration subsystem:

- Load the configuration, following includes.
- Hold the configuration as an event-sourced projection, using the `eventsourcing` library, persisted under
  `.troupe/` so it survives between commands.
- `troupe config show PATH` prints a setting's value.
- `troupe config set PATH VALUE` changes a setting and writes the change back into whichever file it lives
  in. People edit these files by hand and review their diffs, so a write-back must change only the bytes of
  the value being changed — comments, formatting, quoting and layout elsewhere must be untouched.
- `troupe config history [PATH]` lists the changes.

Python 3.12+, managed with uv; the CLI must run as `uv run troupe config …` from the repository root.

Contract sections in force: General; Includes; show PATH (step 1 and 2); set PATH VALUE; history [PATH].
```

`scenario/steps/02-sync.md`:
```markdown
# Step 2 — keep files and configuration in sync

People edit `.troupe/` files directly, in their editor, while troupe is running. Add
`troupe config watch`, which picks up those edits as they happen, and make every command pick up edits made
while nothing was running. When troupe itself writes a change back to a file, that must not be picked up
again as a new change.

Contract sections added: Sync with files.
```
(Before handing over this brief, the runner in Plan 2 makes an unannounced hand edit to the arm's repository,
defined in Plan 2. The brief deliberately does not mention it: whether the method notices is what is measured.)

`scenario/steps/03-get-show.md`:
```markdown
# Step 3 — `get` for values, `show` for anything

We are changing `show`. From now on:
- `troupe config get PATH` prints a single value — what `show` used to do.
- `troupe config show [PATH]` prints either a value or a whole section as YAML, and with `--sources` says
  which file each value comes from.

Contract sections added: get and show (replaces "show PATH (step 1 and 2)").
```

`scenario/steps/04-lineage.md`:
```markdown
# Step 4 — lineage

We need to know who changed what, how, and when. Every configuration change must record whether a human or
an agent made it (and which one), whether it came from the CLI or a file edit, and when.

Contract sections added: Lineage.
```

`scenario/steps/05-overrides.md` — delivered as **two change requests at the same time**:
```markdown
# Step 5 — two change requests (both arrived this week)

## CR-A: keep shared includes shared
Included files are shared between projects. Adding a new setting under an included section must no longer
modify the shared file: it should be added in the including file, as an override. Existing settings still
change where they live.

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: Overrides (replaces rule 2 under "set PATH VALUE").
```

`scenario/steps/06-bug-alias.md` — delivered as a **bug issue in the arm's tracker**, titled
"Setting one agent's model changed another agent's model":
```markdown
Our troupe.yml shares settings between agents with a YAML anchor:

    defaults: &d
      model: opus
    coder:
      settings: *d
    reviewer:
      settings: *d

I ran `troupe config set coder.settings.model sonnet` and now `reviewer` uses sonnet too, and `defaults`
changed. I only meant to change coder.

Expected: changing `defaults.model` changes everyone (that's what the anchor is for). Changing
`coder.settings.model` should not silently change anyone else — refuse, and let me explicitly ask for coder's
copy to be expanded so I can override it.

Contract sections added: Aliases.
```

`scenario/steps/07-model-change.md`:
```markdown
# Step 7 — remote includes and a schema

- Includes can now point at `https://` URLs (shared team configuration). They are read-only from troupe's
  point of view: refuse changes to their values, and tell the user which include line to change instead.
- The configuration is described by a JSON Schema at `.troupe/troupe.schema.json`. Some settings are URLs
  that must never be treated as includes; the schema marks those with `"format": "uri"`, and a `!literal` tag
  marks any other value that must be taken literally.

Contract sections added: Remote includes and schema.
```

- [ ] **Step 3: Write `scenario/po-brief.md`**

```markdown
# Product-owner brief

You are the product owner for troupe's configuration subsystem in a methodology bake-off. Answer the
engineer's questions and approval requests from this brief only.

## How to answer
- If the contract (`scenario/contract.md`, sections in force for the current step) or this brief answers the
  question, answer from it, citing the section.
- If neither does, reply exactly `ESCALATE: <the question, restated in one sentence>` and nothing else.
- Approve plans and specs that are consistent with the contract and the step brief. If one contradicts
  them, say which section and why, and do not approve.
- Never volunteer information about later steps. Never write code or edit files.

## Standing answers
- Users are developers who hand-edit these YAML files and review diffs; byte-surgical write-back matters
  more than speed.
- Performance: configurations are small (under 1,000 leaves, under 50 files). No performance targets.
- Platforms: macOS and Linux. Windows is out of scope.
- Error message wording is free, but must name the path or file involved.
- Anything the contract marks out of contract: the engineer may choose, and should say what they chose.
- `get` on a section (step 3+): error pointing at `config show`. `show` renders the merged view; `--sources`
  shows provenance.

## Escalated answers
(Appended during the bake-off: question, answer, date, arm that first raised it.)
```

- [ ] **Step 4: Amend `docs/design.md` §11 for D2.** In the "step 1 write-back rules" list, replace the
  bullet beginning `**anchors and aliases:**` with:
  `- **anchors and aliases** are out of step 1's contract, so step 6's bug is real; the owner's alias rule
  (refuse through an alias; expand only on confirmation; never write merge keys) is step 6's expected fix.`

- [ ] **Step 5: Owner review gate.** Stop. Ask the owner to review `scenario/` and confirm D1–D4. Do not
  start Task 3 until the owner approves.

- [ ] **Step 6: Commit**

```bash
git add scenario docs/design.md
git commit -m "Scenario: CLI contract, seven step briefs, product-owner brief"
```

---

### Task 3: Step 1 — loading, includes, `show`

**Files:**
- Create: `tests/hidden/test_step1_load_show.py`
- Create: `reference/src/troupe_ref/step.py`, `reference/src/troupe_ref/loader.py`
- Modify: `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `cli`, `tmp_theatre` fixtures; `theatre.build/read` (Task 1).
- Produces: `troupe_ref.step.STEP: int`; `troupe_ref.loader.load(theatre: Path) -> Config` (the spike's
  `Config`, constructed on the resolved config file); `troupe_ref.loader.LoadError(Exception)`;
  `troupe_ref.cli.print_scalar(value) -> str` (the contract's scalar formatting).

- [ ] **Step 1: Write the failing hidden tests**

```python
# tests/hidden/test_step1_load_show.py
import pytest
from .theatre import build

CFG = ".troupe/troupe.yml"

def show(cli, t, path):
    return cli("show", path, theatre=t)

@pytest.mark.steps(1)
@pytest.mark.parametrize("yaml_value, printed", [
    ("demo", "demo\n"), ('"quoted"', "quoted\n"), ("42", "42\n"), ("0.2", "0.2\n"),
    ("true", "true\n"), ("null", "null\n"), ("yes", "yes\n"),   # YAML 1.2: `yes` is a string
])
def test_show_prints_scalars_per_contract(cli, tmp_theatre, yaml_value, printed):
    build(tmp_theatre, {CFG: f"v: {yaml_value}\n"})
    r = show(cli, tmp_theatre, "v")
    assert (r.code, r.out) == (0, printed)

@pytest.mark.steps(1)
def test_show_nested_path_and_list_index(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "agents:\n  coder:\n    tools:\n      - bash\n      - edit\n"})
    assert show(cli, tmp_theatre, "agents.coder.tools.1").out == "edit\n"

@pytest.mark.steps(1)
def test_troupe_yaml_extension_is_accepted(cli, tmp_theatre):
    build(tmp_theatre, {".troupe/troupe.yaml": "v: 1\n"})
    assert show(cli, tmp_theatre, "v").out == "1\n"

@pytest.mark.steps(1)
def test_yaml_include_is_embedded_recursively_relative_to_including_file(cli, tmp_theatre):
    build(tmp_theatre, {
        CFG: "agents:\n  coder: file:agents/coder.yaml\n",
        ".troupe/agents/coder.yaml": "model: opus\nlimits: file:limits.yml\n",
        ".troupe/agents/limits.yml": "max_tokens: 8000\n",
    })
    assert show(cli, tmp_theatre, "agents.coder.model").out == "opus\n"
    assert show(cli, tmp_theatre, "agents.coder.limits.max_tokens").out == "8000\n"

@pytest.mark.steps(1)
def test_text_include_value_is_the_exact_file_text(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:prompts/p.md\n", ".troupe/prompts/p.md": "# Coder\n\nWrite tests.\n"})
    assert show(cli, tmp_theatre, "prompt").out == "# Coder\n\nWrite tests.\n"

@pytest.mark.steps(1)
def test_text_include_without_final_newline_gets_one_when_printed(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.txt\n", ".troupe/p.txt": "one line"})
    assert show(cli, tmp_theatre, "prompt").out == "one line\n"

@pytest.mark.steps(1)
@pytest.mark.parametrize("files", [
    {},                                                   # no config file
    {CFG: "a: 1\n", ".troupe/troupe.yaml": "a: 2\n"},     # both config files
    {CFG: "a: [1, 2\n"},                                  # invalid YAML
    {CFG: "a: file:missing.yaml\n"},                      # missing include
    {CFG: "a: file:x.yaml\n", ".troupe/x.yaml": "b: file:troupe.yml\n"},  # include cycle
], ids=["none", "both", "invalid", "missing-include", "cycle"])
def test_unloadable_configuration_exits_4_with_empty_stdout(cli, tmp_theatre, files):
    build(tmp_theatre, files)
    (tmp_theatre / ".troupe").mkdir(exist_ok=True)
    r = show(cli, tmp_theatre, "a")
    assert r.code == 4 and r.out == "" and r.err.strip()

@pytest.mark.steps(1)
def test_missing_include_error_names_the_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: file:missing.yaml\n"})
    assert "missing.yaml" in show(cli, tmp_theatre, "a").err

@pytest.mark.steps(1)
def test_unknown_path_exits_5_and_names_the_path(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    r = show(cli, tmp_theatre, "nope.deeper")
    assert (r.code, r.out) == (5, "") and "nope.deeper" in r.err

@pytest.mark.steps(1, 2)
def test_show_on_a_mapping_exits_5_before_step_3(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a:\n  b: 1\n"})
    r = show(cli, tmp_theatre, "a")
    assert (r.code, r.out) == (5, "")
```

`steps(1)` means steps 1 to 7: `show` of a scalar keeps its meaning at every step, so these tests stay in
every later suite. Only the mapping test ends at step 2.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step1_load_show.py --step 1 -q`
Expected: all FAIL (the skeleton exits 99).

- [ ] **Step 3: Port the loader from spike A**

```bash
cp ../spike-config-roundtrip/src/spike_config_roundtrip/config.py reference/src/troupe_ref/config.py
cp ../spike-config-roundtrip/src/spike_config_roundtrip/surgical.py reference/src/troupe_ref/surgical.py
cp ../spike-config-roundtrip/src/spike_config_roundtrip/service.py reference/src/troupe_ref/service.py
```
In the three copied files replace `from .surgical` / `from .config` imports as needed (they are already
relative) and remove `import pytest` if present. Then gate spike features that belong to later steps: in
`config.py`, change `INCLUDE_RE` use in `Config._child` to:

```python
from .step import STEP
REMOTE = ("http://", "https://")

# in Config._child, replace the include test with:
        is_ref = isinstance(v, str) and INCLUDE_RE.match(v) and (STEP >= 7 or not str(v).startswith(REMOTE))
        if STEP >= 7 and isinstance(v, TaggedScalar) and v.tag.value == LITERAL_TAG:
            self.provenance[merged_path] = Provenance(source, inner, "yaml", line)
            return str(v.value)
        if is_ref and not (STEP >= 7 and schema_says_literal_uri(schema)):
```

```python
# reference/src/troupe_ref/step.py
import os
STEP = int(os.environ.get("TROUPE_REF_STEP", "7"))
```

```python
# reference/src/troupe_ref/loader.py
from __future__ import annotations
from pathlib import Path
from .config import Config, ConfigError

class LoadError(Exception):
    pass

def config_file(theatre: Path) -> Path:
    found = [p for p in (theatre / ".troupe/troupe.yml", theatre / ".troupe/troupe.yaml") if p.exists()]
    if len(found) != 1:
        raise LoadError(f"{theatre / '.troupe'}: expected exactly one of troupe.yml / troupe.yaml, found {len(found)}")
    return found[0]

def load(theatre: Path) -> Config:
    try:
        return Config(config_file(theatre))
    except LoadError:
        raise
    except (ConfigError, OSError, Exception) as e:  # ruamel parse errors, missing files, cycles
        raise LoadError(str(e)) from e
```

- [ ] **Step 4: Implement `show` in the CLI**

```python
# reference/src/troupe_ref/cli.py — replace main() and add helpers
import json
from pathlib import Path
from .loader import LoadError, load
from .step import STEP

def print_scalar(v) -> str:
    if isinstance(v, bool):
        return "true\n" if v else "false\n"
    if v is None:
        return "null\n"
    if isinstance(v, float):
        return repr(v) + "\n"
    s = str(v)
    return s if s.endswith("\n") else s + "\n"

class PathError(Exception):
    pass

def lookup(data, path: str):
    node = data
    for seg in path.split("."):
        if isinstance(node, list) and seg.isdigit() and int(seg) < len(node):
            node = node[int(seg)]
        elif isinstance(node, dict) and seg in node:
            node = node[seg]
        else:
            raise PathError(f"{path}: no such setting")
    return node

def cmd_show(cfg, args) -> tuple[int, str]:
    value = lookup(cfg.merged, args[0])
    if isinstance(value, (dict, list)):
        raise PathError(f"{args[0]}: is a section, not a value")
    return EXIT_OK, print_scalar(value)

COMMANDS = {"show": cmd_show}

def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    try:
        cfg = load(Path(ns.theatre))
        code, out = COMMANDS[ns.sub](cfg, ns.args)
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr); return EXIT_LOAD
    except PathError as e:
        print(f"error: {e}", file=sys.stderr); return EXIT_PATH
    sys.stdout.write(out)
    return code
```

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/hidden/test_step1_load_show.py --step 1 -q`
Expected: 20 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/hidden/test_step1_load_show.py reference
git commit -m "Step 1 hidden tests and reference: loading, includes, show"
```

---

### Task 4: Step 1 — byte-surgical write-back corpus

The golden corpus is the core of step 1. It starts from spike A's 64-case corpus, which the spike verified
case by case, removes cases that are out of step 1's contract, and changes the expected bytes where the
owner's decisions differ from what the spike did. **Goldens are written by hand here, never generated from
the reference** — generating them would make the reference its own oracle.

**Files:**
- Create: `tests/hidden/writeback_corpus.py` (from `../spike-config-roundtrip/tests/q9_corpus.py`)
- Create: `tests/hidden/test_step1_writeback.py`
- Modify: `reference/src/troupe_ref/surgical.py`, `reference/src/troupe_ref/config.py`, `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `Case(name, group, before, ops, after, expect, note)` and `CASES` from the copied corpus module.
- Produces: `cli set PATH VALUE` in the reference; `troupe_ref.cli.parse_value(text: str) -> object`.

- [ ] **Step 1: Copy the corpus and remove out-of-contract cases**

```bash
cp ../spike-config-roundtrip/tests/q9_corpus.py tests/hidden/writeback_corpus.py
```
Delete these cases from `tests/hidden/writeback_corpus.py` (they move to later steps or are out of contract):
- `"TAB before an EOL comment (valid YAML 1.2)"` — out of contract
- the multi-document case (`"a: 1\n---\nb: 2\n"`) — out of contract
- `"!literal tag kept on set"` and `"tag + anchor on one scalar"` — step 7 (Task 11 re-adds the first)
- `"anchored scalar: anchor kept, alias follows"` and `"value inside a merge-key base"` — aliases are out of
  step 1's contract (D2); Task 10 re-adds the anchor case

- [ ] **Step 2: Change the expected bytes where the owner's rules differ from the spike**

Replace each case's `after` (and `expect`/`note`) with exactly:

```python
# folded paragraph re-wrapped to its previous width (longest content line "Second para" = 11 columns)
case("folded > change second paragraph, first stays wrapped", G,
     "desc: >\n  This is a long\n  wrapped paragraph.\n\n  Second para\n  here.\nnext: 1\n",
     [("desc", "This is a long wrapped paragraph.\nSecond paragraph changed.\n")],
     "desc: >\n  This is a long\n  wrapped paragraph.\n\n  Second\n  paragraph\n  changed.\nnext: 1\n",
     note="changed paragraph re-wrapped greedily at 11 columns; a word wider than that takes its own line")
# width 7 ("one two")
case("folded >- change", G,
     "summary: >-\n  one two\n  three\nnext: 1\n",
     [("summary", "one two four")],
     "summary: >-\n  one two\n  four\nnext: 1\n")
# folded value gaining a more-indented line is refused
case("folded value gains a more-indented line -> refused", G,
     "d: >\n  para one\nn: 1\n", [("d", "para one\n  indented\n")], "d: >\n  para one\nn: 1\n",
     expect="error")
# end-of-line comments return to their old column (b: '#' at col 11; c: '#' at col 6, value now reaches col 5)
case("EOL comments with varied spacing (1 space, 6 spaces)", G,
     "a: 1 # one space\nb: 22      # six\nc: x  # two\n",
     [("b", 7), ("c", "yy")],
     "a: 1 # one space\nb: 7       # six\nc: yy # two\n")
# appended list item goes below the trailing comment
case("comments between list items; change + append", G,
     "l:\n  - a\n  # between\n  - b\n  # after last\nnext: 1\n",
     [("l.1", "c"), ("l.2", "d")],
     "l:\n  - a\n  # between\n  - c\n  # after last\n  - d\nnext: 1\n")
# D4: new mapping key goes below the mapping's trailing comment
case("comments inside nested mappings; change + add", G,
     "outer:\n  # c1\n  inner:\n    # c2\n    k: v  # c3\n    # c4\n  other: 1\n",
     [("outer.inner.k", "w"), ("outer.inner.new", 1)],
     "outer:\n  # c1\n  inner:\n    # c2\n    k: w  # c3\n    # c4\n    new: 1\n  other: 1\n")
case("comment at end of file; change + add root key", G,
     "a: 1\nb: 2\n# trailing comment\n",
     [("b", 3), ("c", 4)],
     "a: 1\nb: 3\n# trailing comment\nc: 4\n")
# new keys copy their neighbours' quoting
case("JSON-style file (it's YAML too): change + add", G,
     '{"a": 1, "b": [1, 2]}\n', [("a", 5), ("c", 6)], '{"a": 5, "b": [1, 2], "c": 6}\n')
```

Then search the remaining cases for any other `after` that places a new entry *above* a trailing comment, or
keeps an end-of-line comment's spacing after a value length change, and apply the same two rules by hand.
Record every case you change, with its old and new `after`, in the commit message.

- [ ] **Step 3: Add rule cases the spike corpus lacks**

Append to `tests/hidden/writeback_corpus.py`:

```python
G = "owner rules"
case("new string value copies the preceding sibling's double quotes", G,
     'a: "x"\nb: "y"\n', [("c", "z")], 'a: "x"\nb: "y"\nc: "z"\n')
case("new key copies single-quoted sibling key style", G,
     "'a': 1\n", [("b", 2)], "'a': 1\n'b': 2\n")
case("new key in a mapping with no siblings is plain", G,
     "m: {}\n", [("m.k", "v")], "m: {k: v}\n")
case("comment column kept when value shrinks", G,
     "model: claude-opus-5-5 # m\n", [("model", "opus")], "model: opus            # m\n")
case("comment column: value grows past it -> one space", G,
     "model:   opus        # default model\nbudget:  5           # USD\n",
     [("model", "claude-opus-5-5")],
     "model:   claude-opus-5-5 # default model\nbudget:  5           # USD\n")
case("folded: unchanged paragraphs keep bytes when another paragraph changes", G,
     "d: >\n  one\n  two\n\n  three\n  four\nn: 1\n",
     [("d", "one two\nthree four five\n")],
     "d: >\n  one\n  two\n\n  three\n  four\n  five\nn: 1\n",
     note="second paragraph width 5; 'three four five' wraps to three/four/five")
case("append to a list with no trailing comment", G,
     "l:\n  - a\nn: 1\n", [("l.1", "b")], "l:\n  - a\n  - b\nn: 1\n")
case("index beyond list length is refused as path error", G,
     "l:\n  - a\n", [("l.5", "b")], "l:\n  - a\n", expect="path")
```

- [ ] **Step 4: Write the hidden test that drives the corpus through the CLI**

```python
# tests/hidden/test_step1_writeback.py
import json
import pytest
from .theatre import build, read
from .writeback_corpus import CASES

CFG = ".troupe/troupe.yml"

def arg(value) -> str:
    # JSON is valid YAML flow syntax, so this passes exact values (types, newlines) through the contract's parser
    return json.dumps(value)

@pytest.mark.steps(1)
@pytest.mark.parametrize("c", CASES, ids=[c.name for c in CASES])
def test_writeback_is_byte_surgical(cli, tmp_theatre, c):
    build(tmp_theatre, {CFG: c.before})
    codes = [cli("set", path, arg(value), theatre=tmp_theatre).code for path, value in c.ops]
    expected_code = {"error": 3, "path": 5}.get(c.expect, 0)
    assert codes[-1] == expected_code, codes
    assert read(tmp_theatre, CFG) == c.after

@pytest.mark.steps(1)
def test_text_include_set_replaces_target_text_exactly(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md  # c\n", ".troupe/p.md": "one\ntwo\n"})
    assert cli("set", "prompt", arg("one\n2\nthree\n"), theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/p.md") == "one\n2\nthree\n"
    assert read(tmp_theatre, CFG) == "prompt: file:p.md  # c\n"

@pytest.mark.steps(1)
def test_text_include_rejects_non_string(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md\n", ".troupe/p.md": "x\n"})
    r = cli("set", "prompt", "5", theatre=tmp_theatre)
    assert r.code == 3 and read(tmp_theatre, ".troupe/p.md") == "x\n"

@pytest.mark.steps(1)
def test_value_in_nested_include_is_written_to_that_file_only(cli, tmp_theatre):
    files = {CFG: "agents:\n  coder: file:agents/coder.yaml  # the coder\n",
             ".troupe/agents/coder.yaml": "model: 'opus'  # quoted\nlimits: file:limits.yaml\n",
             ".troupe/agents/limits.yaml": "max_tokens: 8000  # cap\n"}
    build(tmp_theatre, files)
    assert cli("set", "agents.coder.limits.max_tokens", "16000", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/agents/limits.yaml") == "max_tokens: 16000  # cap\n"
    for rel in (CFG, ".troupe/agents/coder.yaml"):
        assert read(tmp_theatre, rel) == files[rel]

@pytest.mark.steps(1, 4)   # step 5 changes where new keys go
def test_new_key_goes_to_file_of_deepest_existing_ancestor(cli, tmp_theatre):
    files = {CFG: "agents:\n  coder: file:agents/coder.yaml\n", ".troupe/agents/coder.yaml": "model: opus\n"}
    build(tmp_theatre, files)
    assert cli("set", "agents.coder.budget.daily_usd", "5", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/agents/coder.yaml") == "model: opus\nbudget:\n  daily_usd: 5\n"
    assert read(tmp_theatre, CFG) == files[CFG]

@pytest.mark.steps(1)
def test_replacing_a_whole_include_is_refused(cli, tmp_theatre):
    files = {CFG: "coder: file:coder.yaml\n", ".troupe/coder.yaml": "model: opus\n"}
    build(tmp_theatre, files)
    r = cli("set", "coder", "flat", theatre=tmp_theatre)
    assert r.code == 3 and read(tmp_theatre, CFG) == files[CFG]

@pytest.mark.steps(1)
def test_set_persists_and_show_reflects_it(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    cli("set", "a", "2", theatre=tmp_theatre)
    assert cli("show", "a", theatre=tmp_theatre).out == "2\n"
```

- [ ] **Step 5: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step1_writeback.py --step 1 -q`
Expected: all FAIL (no `set` yet).

- [ ] **Step 6: Implement `set` in the reference CLI**

```python
# reference/src/troupe_ref/cli.py — additions
from ruamel.yaml import YAML
from .config import ConfigError, ReadOnlyIncludeError
from .surgical import RejectedSet, SpliceError

class Refused(Exception):
    pass

def parse_value(text: str):
    y = YAML(typ="safe")          # YAML 1.2 core schema
    return y.load(text)

def cmd_set(cfg, args) -> tuple[int, str]:
    path, raw = args[0], args[1]
    value = parse_value(raw)
    try:
        cfg.set(path, value)
    except (RejectedSet, SpliceError, ReadOnlyIncludeError) as e:
        raise Refused(f"{path}: {e}") from e
    except IndexError as e:
        raise PathError(f"{path}: {e}") from e
    return EXIT_OK, ""

COMMANDS["set"] = cmd_set
# in main(): add `except Refused as e: print(f"error: {e}", file=sys.stderr); return EXIT_REFUSED`
```

In `config.py`, make `Config.set` raise `IndexError` for an index greater than the list length, and
`RejectedSet` when `PATH` is exactly an include site (a key in `self.include_sites`) and the new value is not
itself an include reference.

- [ ] **Step 7: Change `surgical.py` to the owner's rules until the corpus passes.** Work case by case with
  `uv run pytest tests/hidden/test_step1_writeback.py --step 1 -q -x`. The changes, by function:
  - `_folded_source_lines(value)` / `_folded_paragraph_groups(src_lines)`: for each changed paragraph,
    compute `width = max(len(line.strip()) for line in old paragraph lines)` and wrap the new paragraph text
    greedily by word at `width` (`textwrap.wrap(text, width, break_long_words=False, break_on_hyphens=False)`).
  - `surgical_set` on a folded scalar: if any line of the new value starts with a space or tab, raise
    `RejectedSet("folded value cannot hold a more-indented line")` instead of switching to `|`.
  - Insertion point for new keys and list items: after the collection's last entry **and** any comment-only
    lines that follow it at an indentation ≥ the entry's, up to the next less-indented non-blank line.
    Delete `_steal_trailing_comment` from `config.py` (it exists to do the opposite).
  - Rendering new keys and new string values: read the style of the preceding sibling's key and value
    (`ScalarEvent.style`: `None` plain, `"'"` single, `'"'` double) and render the new one in that style if
    it can represent the text, else fall back to the minimal style.
  - End-of-line comments: after splicing a value on a line with a comment, set the number of spaces before
    `#` to `max(1, old_comment_column - new_value_end_column)`.

- [ ] **Step 8: Run the whole step 1 suite**

Run: `uv run pytest tests/hidden --step 1 -q`
Expected: all pass. Also run the spike's sweep against the reference to catch regressions the corpus misses:
`cp ../spike-config-roundtrip/tests/test_q9_sweep.py reference/tests/` (fix its imports to `troupe_ref`),
then `cd reference && uv run pytest tests -q` — expect 0 fallbacks; policy refusals are fine.

- [ ] **Step 9: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 1 write-back corpus with owner rules; reference passes it"
```

---

### Task 5: Step 1 — event-sourced projection, `history`, persistence

**Files:**
- Create: `tests/hidden/history.py` (helper), `tests/hidden/test_step1_history.py`
- Create: `reference/src/troupe_ref/store.py`
- Modify: `reference/src/troupe_ref/service.py`, `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `cli`, `tmp_theatre`, `build`, `read`.
- Produces: `tests/hidden/history.py: events(cli, theatre, path=None, env=None) -> list[dict]` (parses JSON
  Lines, asserts exit 0); reference `store.ConfigStore(theatre: Path)` with `.values() -> dict[str, object]`,
  `.record(op: str, path: str, old, new, **lineage) -> None`, `.history(path: str | None) -> list[dict]`,
  `.exists() -> bool`; `service.Service(theatre: Path)` with `.ensure_imported()`, `.reconcile(via: str) -> int`,
  `.set(path: str, value, **opts) -> int`.

- [ ] **Step 1: Write the helper and failing tests**

```python
# tests/hidden/history.py
import json

def events(cli, theatre, path=None, env=None) -> list[dict]:
    args = [path] if path else []
    r = cli("history", *args, theatre=theatre, env=env)
    assert r.code == 0, r.err
    return [json.loads(line) for line in r.out.splitlines() if line.strip()]

def core(e: dict) -> tuple:
    return (e["op"], e["path"], e["old"], e["new"])
```

```python
# tests/hidden/test_step1_history.py
import pytest
from .history import core, events
from .theatre import build

CFG = ".troupe/troupe.yml"

@pytest.mark.steps(1)
def test_first_command_imports_every_leaf(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb:\n  c: x\nl:\n  - p\n  - q\nprompt: file:p.md\n", ".troupe/p.md": "hi\n"})
    evs = events(cli, tmp_theatre)
    assert sorted(core(e) for e in evs) == sorted([
        ("import", "a", None, 1), ("import", "b.c", None, "x"),
        ("import", "l.0", None, "p"), ("import", "l.1", None, "q"),
        ("import", "prompt", None, "hi\n")])
    assert [e["seq"] for e in evs] == list(range(1, 6))

@pytest.mark.steps(1)
def test_set_records_one_event_per_changed_leaf_and_seq_continues(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb: 2\n"})
    cli("set", "a", "10", theatre=tmp_theatre)
    cli("set", "b", "20", theatre=tmp_theatre)
    evs = events(cli, tmp_theatre)
    assert [core(e) for e in evs[-2:]] == [("set", "a", 1, 10), ("set", "b", 2, 20)]
    assert [e["seq"] for e in evs] == list(range(1, len(evs) + 1))

@pytest.mark.steps(1)
def test_set_to_the_same_value_records_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    before = events(cli, tmp_theatre)
    assert cli("set", "a", "1", theatre=tmp_theatre).code == 0
    assert events(cli, tmp_theatre) == before

@pytest.mark.steps(1)
def test_replacing_a_section_with_a_value_records_removes_and_a_set(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "m:\n  x: 1\n  y: 2\n"})
    cli("set", "m", "flat", theatre=tmp_theatre)
    tail = sorted(core(e) for e in events(cli, tmp_theatre) if e["op"] != "import")
    assert tail == sorted([("remove", "m.x", 1, None), ("remove", "m.y", 2, None), ("set", "m", None, "flat")])

@pytest.mark.steps(1)
def test_history_path_filter_matches_path_and_descendants_only(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "ab: 1\na:\n  b: 2\n  c: 3\n"})
    assert sorted(e["path"] for e in events(cli, tmp_theatre, "a")) == ["a.b", "a.c"]

@pytest.mark.steps(1)
def test_failed_set_records_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md\n", ".troupe/p.md": "x\n"})
    before = events(cli, tmp_theatre)
    assert cli("set", "prompt", "5", theatre=tmp_theatre).code == 3
    assert events(cli, tmp_theatre) == before
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step1_history.py --step 1 -q`
Expected: all FAIL (`history` exits 2: invalid choice).

- [ ] **Step 3: Implement the store (persistent, SQLite under `.troupe/state/`)**

```python
# reference/src/troupe_ref/store.py
from __future__ import annotations
import os
import uuid
from pathlib import Path
from typing import Any
from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event

LOG_ID = uuid.uuid5(uuid.NAMESPACE_URL, "troupe:config-log")

class ConfigLog(Aggregate):
    @event("Created")
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    @event("Changed")
    def changed(self, op: str, path: str, old: Any, new: Any, lineage: dict) -> None:
        if op == "remove":
            self.values.pop(path, None)
        else:
            self.values[path] = new

    @classmethod
    def create_id(cls) -> uuid.UUID:
        return LOG_ID

class ConfigStore:
    def __init__(self, theatre: Path):
        state = theatre / ".troupe" / "state"
        state.mkdir(parents=True, exist_ok=True)
        self.app = Application(env={"PERSISTENCE_MODULE": "eventsourcing.sqlite",
                                    "SQLITE_DBNAME": str(state / "events.sqlite")})

    def exists(self) -> bool:
        try:
            self.app.repository.get(LOG_ID)
            return True
        except Exception:
            return False

    def _log(self) -> ConfigLog:
        if not self.exists():
            log = ConfigLog()
            self.app.save(log)
        return self.app.repository.get(LOG_ID)

    def values(self) -> dict[str, Any]:
        return dict(self._log().values)

    def record_many(self, changes: list[tuple[str, str, Any, Any]], lineage: dict) -> None:
        log = self._log()
        for op, path, old, new in changes:
            log.changed(op=op, path=path, old=old, new=new, lineage=lineage)
        self.app.save(log)   # one atomic save per command

    def history(self, path: str | None) -> list[dict]:
        out = []
        for e in list(self.app.repository.event_store.get(LOG_ID))[1:]:   # skip Created
            if path and not (e.path == path or e.path.startswith(path + ".")):
                continue
            out.append({"seq": e.originator_version - 1, "op": e.op, "path": e.path,
                        "old": e.old, "new": e.new, **e.lineage})
        return out
```

`ConfigLog.create_id` returning a fixed id makes one log per theatre database. If the installed
`eventsourcing` version rejects the classmethod form, construct with `ConfigLog._create(ConfigLog.Created, id=LOG_ID)`
— check with `uv run python -c "from troupe_ref.store import ConfigStore"` and the tests.

- [ ] **Step 4: Implement the service** (replace the copied spike `service.py` content)

```python
# reference/src/troupe_ref/service.py
from __future__ import annotations
from pathlib import Path
from typing import Any
from .loader import load
from .step import STEP
from .store import ConfigStore

_MISSING = object()

def diff(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, str, Any, Any]]:
    out = []
    for k, v in after.items():
        old = before.get(k, _MISSING)
        if old is _MISSING or old != v or type(old) is not type(v):
            out.append(("set", k, None if old is _MISSING else old, v))
    for k in sorted(before.keys() - after.keys()):
        out.append(("remove", k, before[k], None))
    return out

class Service:
    def __init__(self, theatre: Path, lineage_for_cli: dict | None = None):
        self.theatre = theatre
        self.store = ConfigStore(theatre)
        self.cli_lineage = lineage_for_cli or {}

    def ensure_imported(self) -> None:
        if not self.store.exists() or not self.store.history(None):
            flat = load(self.theatre).flat()
            self.store.record_many([("import", k, None, v) for k, v in flat.items()], self._lineage("import"))

    def reconcile(self, via: str) -> int:
        changes = diff(self.store.values(), load(self.theatre).flat())
        if changes:
            self.store.record_many(changes, self._lineage(via))
        return len(changes)

    def set(self, path: str, value: Any, **opts) -> int:
        cfg = load(self.theatre)
        cfg.set(path, value, **opts)       # raises before writing if refused
        return self.reconcile("cli")

    def _lineage(self, via: str) -> dict:
        return {}                          # Task 8 fills this in (step 4)
```

Make sure the copied `config.py`'s `Config.flat()` returns list items as `"l.0"` keys and text includes as
one string leaf (the spike's does; confirm by the first test).

- [ ] **Step 5: Wire the CLI** — every command constructs `Service`, calls `ensure_imported()`, and (only
  when `STEP >= 2`) `reconcile("file")` before its own work; `set` goes through `Service.set`; add:

```python
def cmd_history(svc, args) -> tuple[int, str]:
    rows = svc.store.history(args[0] if args else None)
    return EXIT_OK, "".join(json.dumps(r) + "\n" for r in rows)
```
Change `cmd_show`/`cmd_set` to take the `Service` and call `load(svc.theatre)` themselves, and add `history`
to the subcommand list in `build_parser()`.

- [ ] **Step 6: Run the step 1 suite**

Run: `uv run pytest tests/hidden --step 1 -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 1 history: event-sourced projection persisted per theatre"
```

---

### Task 6: Step 2 — sync with files, `watch`, loop safety

**Files:**
- Create: `tests/hidden/watcher.py` (helper), `tests/hidden/test_step2_sync.py`
- Create: `reference/src/troupe_ref/lock.py`
- Modify: `reference/src/troupe_ref/service.py`, `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `cli.spawn` (Task 1), `history.events/core` (Task 5).
- Produces: `tests/hidden/watcher.py: Watching` context manager (`with Watching(cli, theatre) as w:` starts
  `watch`, waits for the readiness line, and on exit sends SIGTERM and records the exit code in `w.code`);
  `wait_for(predicate, timeout: float) -> bool` (polls every 0.1 s); reference `lock.theatre_lock(theatre)`.

- [ ] **Step 1: Write the helper and failing tests**

```python
# tests/hidden/watcher.py
import os, select, signal, time

def wait_for(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()

class Watching:
    def __init__(self, cli, theatre, ready_timeout: float = 20):
        self.cli, self.theatre, self.ready_timeout = cli, theatre, ready_timeout
        self.code = None

    def __enter__(self):
        self.p = self.cli.spawn("watch", theatre=self.theatre)
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            r, _, _ = select.select([self.p.stdout], [], [], 0.2)
            if r and self.p.stdout.readline().startswith("watching"):
                return self
            if self.p.poll() is not None:
                break
        self._stop()
        raise AssertionError(f"`config watch` never printed its readiness line; stderr: {self.p.stderr.read()}")

    def _stop(self):
        if self.p.poll() is None:
            os.killpg(self.p.pid, signal.SIGTERM)
            try:
                self.p.wait(timeout=10)
            except Exception:
                os.killpg(self.p.pid, signal.SIGKILL)
                self.p.wait()
        self.code = self.p.returncode

    def __exit__(self, *exc):
        self._stop()
```

```python
# tests/hidden/test_step2_sync.py
import time
import pytest
from .history import core, events
from .theatre import build
from .watcher import Watching, wait_for

CFG = ".troupe/troupe.yml"

def edit(t, rel, text):
    build(t, {rel: text})

def changes(cli, t):
    return [core(e) for e in events(cli, t) if e["op"] != "import"]

@pytest.mark.steps(2)
def test_edit_while_idle_is_picked_up_by_the_next_command(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1  # c\n"})
    events(cli, tmp_theatre)                       # import
    edit(tmp_theatre, CFG, "a: 2  # c\n")
    assert cli("show", "a", theatre=tmp_theatre).out == "2\n"
    assert changes(cli, tmp_theatre) == [("set", "a", 1, 2)]

@pytest.mark.steps(2)
def test_formatting_and_comment_only_edits_record_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb: [x, y]\n"})
    events(cli, tmp_theatre)
    edit(tmp_theatre, CFG, "# new comment\na:   1   # eol\nb:\n  - x\n  - y\n")
    cli("show", "a", theatre=tmp_theatre)
    assert changes(cli, tmp_theatre) == []

@pytest.mark.steps(2)
def test_watch_picks_up_an_edit_to_an_included_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "coder: file:coder.yaml\n", ".troupe/coder.yaml": "model: opus\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        edit(tmp_theatre, ".troupe/coder.yaml", "model: sonnet\n")
        assert wait_for(lambda: changes(cli, tmp_theatre) == [("set", "coder.model", "opus", "sonnet")], 5)

@pytest.mark.steps(2)
def test_set_while_watching_records_its_change_exactly_once(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        assert cli("set", "a", "2", theatre=tmp_theatre).code == 0
        time.sleep(3)                              # give an echo every chance to appear
        assert changes(cli, tmp_theatre) == [("set", "a", 1, 2)]

@pytest.mark.steps(2)
def test_comment_only_edit_while_watching_records_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        edit(tmp_theatre, CFG, "a: 1  # explained\n")
        time.sleep(3)
        assert changes(cli, tmp_theatre) == []

@pytest.mark.steps(2)
def test_include_added_by_hand_is_followed(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        build(tmp_theatre, {".troupe/extra.yaml": "k: v\n"})
        edit(tmp_theatre, CFG, "a: 1\nextra: file:extra.yaml\n")
        assert wait_for(lambda: ("set", "extra.k", None, "v") in changes(cli, tmp_theatre), 5)

@pytest.mark.steps(2)
def test_watch_exits_0_on_sigterm(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    with Watching(cli, tmp_theatre) as w:
        pass
    assert w.code == 0

@pytest.mark.steps(2)
def test_history_does_not_reconcile(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    edit(tmp_theatre, CFG, "a: 2\n")
    assert changes(cli, tmp_theatre) == []        # recorded only once another command runs
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step2_sync.py --step 2 -q`
Expected: FAIL (no `watch`; no reconcile-first). `test_history_does_not_reconcile` and
`test_formatting_and_comment_only_edits_record_nothing` may already pass — that is expected; Task 12's negative
check lists them as "passes at the previous step" and they are acceptable only because each is paired with a
failing positive test in the same step (see Task 12, Step 3).

- [ ] **Step 3: Serialise writers with a theatre lock**

```python
# reference/src/troupe_ref/lock.py
import contextlib, fcntl
from pathlib import Path

@contextlib.contextmanager
def theatre_lock(theatre: Path):
    state = theatre / ".troupe" / "state"
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
```

In `service.py`, wrap the bodies of `ensure_imported`, `reconcile` and `set` in `with theatre_lock(self.theatre):`
(`set` holds it across write-back *and* its reconcile, so a watcher can never record a CLI change as a file
change). Make the lock re-entrant within a process by tracking depth on the `Service` instance.

- [ ] **Step 4: Add `watch`**

```python
# reference/src/troupe_ref/cli.py — additions
import signal, threading
from watchfiles import watch as fs_watch

def cmd_watch(svc, args) -> tuple[int, str]:
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    troupe_dir = svc.theatre / ".troupe"
    print(f"watching {svc.theatre}", flush=True)
    for changes in fs_watch(troupe_dir, stop_event=stop, debounce=100, step=20, rust_timeout=200,
                            yield_on_timeout=True):
        if any("/state/" not in p and not p.endswith(".troupe-tmp") for _, p in changes):
            try:
                svc.reconcile("file")
            except Exception as e:           # a half-saved file: report and keep watching
                print(f"warning: {e}", file=sys.stderr, flush=True)
    return EXIT_OK, ""
```
Register `watch` (STEP ≥ 2 only: at STEP < 2, `watch` is an unknown subcommand → exit 2) and, in `main()`,
skip the reconcile-first call when the subcommand is `history`.

- [ ] **Step 5: Run the step 2 suite, five times** (watcher tests must not flake)

Run: `for i in 1 2 3 4 5; do uv run pytest tests/hidden --step 2 -q || break; done`
Expected: all pass, five times.

- [ ] **Step 6: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 2 hidden tests and reference: reconcile-first, watch, loop safety"
```

---

### Task 7: Step 3 — `get` for values, `show` for values or sections (the command-behaviour contradiction)

**Files:**
- Create: `tests/hidden/test_step3_get_show.py`
- Create: `reference/src/troupe_ref/render.py`
- Modify: `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `Config.merged`, `Config.provenance: dict[tuple, Provenance]` (spike), `print_scalar`, `lookup`.
- Produces: `render.render_yaml(value) -> str`; `render.render_with_sources(cfg, path: tuple, theatre: Path) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/hidden/test_step3_get_show.py
import pytest
import yaml
from .theatre import build

CFG = ".troupe/troupe.yml"
FILES = {CFG: "name: demo\nagents:\n  coder: file:agents/coder.yaml\n",
         ".troupe/agents/coder.yaml": "model: opus\ntools:\n  - bash\n  - edit\nprompt: file:p.md\n",
         ".troupe/agents/p.md": "Write tests.\nKeep it simple.\n"}
MERGED = {"name": "demo", "agents": {"coder": {"model": "opus", "tools": ["bash", "edit"],
                                               "prompt": "Write tests.\nKeep it simple.\n"}}}

@pytest.mark.steps(3)
@pytest.mark.parametrize("yaml_value, printed", [
    ("demo", "demo\n"), ("42", "42\n"), ("0.2", "0.2\n"), ("true", "true\n"), ("null", "null\n")])
def test_get_prints_scalars_as_show_used_to(cli, tmp_theatre, yaml_value, printed):
    build(tmp_theatre, {CFG: f"v: {yaml_value}\n"})
    assert cli("get", "v", theatre=tmp_theatre).out == printed

@pytest.mark.steps(3)
def test_get_follows_includes(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert cli("get", "agents.coder.tools.1", theatre=tmp_theatre).out == "edit\n"
    assert cli("get", "agents.coder.prompt", theatre=tmp_theatre).out == "Write tests.\nKeep it simple.\n"

@pytest.mark.steps(3)
def test_get_on_a_section_exits_5_and_points_at_show(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    r = cli("get", "agents.coder", theatre=tmp_theatre)
    assert (r.code, r.out) == (5, "") and "config show" in r.err

@pytest.mark.steps(3)
def test_show_on_a_scalar_still_prints_the_value(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert cli("show", "name", theatre=tmp_theatre).out == "demo\n"

@pytest.mark.steps(3)
def test_show_on_a_section_prints_merged_yaml(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    r = cli("show", "agents.coder", theatre=tmp_theatre)
    assert r.code == 0 and yaml.safe_load(r.out) == MERGED["agents"]["coder"]

@pytest.mark.steps(3)
def test_show_prints_text_includes_as_literal_blocks(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    out = cli("show", "agents.coder", theatre=tmp_theatre).out
    assert "prompt: |" in out

@pytest.mark.steps(3)
def test_show_without_a_path_prints_everything(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert yaml.safe_load(cli("show", theatre=tmp_theatre).out) == MERGED

@pytest.mark.steps(3)
def test_show_sources_names_the_file_of_every_scalar(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    r = cli("show", "--sources", theatre=tmp_theatre)
    assert r.code == 0 and yaml.safe_load(r.out) == MERGED     # comments do not change the data
    lines = r.out.splitlines()
    def line_for(prefix):
        return next(l for l in lines if l.strip().startswith(prefix))
    assert line_for("name:").endswith("# from .troupe/troupe.yml")
    assert line_for("model:").endswith("# from .troupe/agents/coder.yaml")
    assert line_for("- bash").endswith("# from .troupe/agents/coder.yaml")
    assert line_for("prompt:").endswith("# from .troupe/agents/p.md")

@pytest.mark.steps(3)
def test_show_unknown_path_exits_5(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert cli("show", "agents.nobody", theatre=tmp_theatre).code == 5
```

`--sources` is passed after the subcommand like `--theatre`; the driver puts `--theatre` first, so
the arm must accept options in any order after the subcommand (argparse does).

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step3_get_show.py --step 3 -q`
Expected: FAIL (`get` unknown; `show` on a section exits 5).

- [ ] **Step 3: Implement the renderer**

```python
# reference/src/troupe_ref/render.py
from __future__ import annotations
import io
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

def _literalise(v):
    if isinstance(v, dict):
        return {k: _literalise(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_literalise(x) for x in v]
    if isinstance(v, str) and "\n" in v:
        return LiteralScalarString(v)
    return v

def render_yaml(value) -> str:
    y = YAML()
    y.default_flow_style = False
    y.indent(mapping=2, sequence=4, offset=2)
    buf = io.StringIO()
    y.dump(_literalise(value), buf)
    return buf.getvalue()

def render_with_sources(cfg, path: tuple, theatre: Path) -> str:
    """Render line by line so each scalar's line can carry `# from <file>`."""
    def rel(p) -> str:
        return Path(cfg.provenance[p].source).resolve().relative_to(theatre.resolve()).as_posix()
    out: list[str] = []
    def scalar_text(v) -> str:
        return render_yaml(v).rstrip("\n").removesuffix("\n...").splitlines()[0]
    def emit(node, p: tuple, indent: int):
        pad = " " * indent
        items = node.items() if isinstance(node, dict) else enumerate(node)
        for k, v in items:
            head = f"{pad}{k}:" if isinstance(node, dict) else f"{pad}-"
            cp = (*p, k)
            if isinstance(v, (dict, list)):
                out.append(head)
                emit(v, cp, indent + 2)
            elif isinstance(v, str) and "\n" in v:
                out.append(f"{head} |  # from {rel(cp)}" if v.endswith("\n") else f"{head} |-  # from {rel(cp)}")
                out.extend(f"{pad}  {line}" for line in v.splitlines())
            else:
                out.append(f"{head} {scalar_text(v)}  # from {rel(cp)}")
    node = cfg.merged
    for seg in path:
        node = node[seg]
    emit(node, path, 0)
    return "\n".join(out) + "\n"
```

The `prompt: |` line carries the comment on the block header, which is still a line "that holds a scalar".

- [ ] **Step 4: Wire `get` and the new `show`**

```python
# reference/src/troupe_ref/cli.py
def cmd_get(svc, args) -> tuple[int, str]:
    value = lookup(load(svc.theatre).merged, args[0])
    if isinstance(value, (dict, list)):
        raise PathError(f"{args[0]}: is a section; use `troupe config show {args[0]}`")
    return EXIT_OK, print_scalar(value)

def cmd_show(svc, args, sources: bool = False) -> tuple[int, str]:
    cfg = load(svc.theatre)
    path = tuple(int(s) if s.isdigit() else s for s in args[0].split(".")) if args else ()
    value = lookup(cfg.merged, args[0]) if args else cfg.merged
    if STEP < 3:
        if isinstance(value, (dict, list)):
            raise PathError(f"{args[0]}: is a section, not a value")
        return EXIT_OK, print_scalar(value)
    if not isinstance(value, (dict, list)):
        return EXIT_OK, print_scalar(value)
    return EXIT_OK, render_with_sources(cfg, path, svc.theatre) if sources else render_yaml(value)
```
Add `get` (STEP ≥ 3 only), make `show`'s path argument optional, and add `--sources` to `show`'s parser.

- [ ] **Step 5: Run the suites for steps 1–3**

Run: `for s in 1 2 3; do uv run pytest tests/hidden --step $s -q || break; done`
Expected: all pass at every step.

- [ ] **Step 6: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 3 hidden tests and reference: get, show sections, --sources"
```

---

### Task 8: Step 4 — lineage on every event

**Files:**
- Create: `tests/hidden/test_step4_lineage.py`
- Modify: `reference/src/troupe_ref/service.py`, `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `history.events`, `watcher.Watching`, `watcher.wait_for`.
- Produces: `service.Service(theatre, actor: dict)`; `cli.actor_from_env() -> dict` (raises `UsageError`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/hidden/test_step4_lineage.py
import getpass, re
from datetime import datetime, timedelta, timezone
import pytest
from .history import events
from .theatre import build
from .watcher import Watching, wait_for

CFG = ".troupe/troupe.yml"
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

def last(cli, t, op="set"):
    return [e for e in events(cli, t) if e["op"] == op][-1]

@pytest.mark.steps(4)
def test_import_events_have_unknown_actor_and_via_import(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    e = events(cli, tmp_theatre)[0]
    assert (e["actor"], e["via"]) == ({"kind": "unknown", "id": None}, "import")
    assert RFC3339_Z.match(e["at"])

@pytest.mark.steps(4)
@pytest.mark.parametrize("env, actor", [
    ({"TROUPE_ACTOR": "agent:coder-7"}, {"kind": "agent", "id": "coder-7"}),
    ({"TROUPE_ACTOR": "human:martin"}, {"kind": "human", "id": "martin"}),
])
def test_cli_set_records_actor_from_env_and_via_cli(cli, tmp_theatre, env, actor):
    build(tmp_theatre, {CFG: "a: 1\n"})
    assert cli("set", "a", "2", theatre=tmp_theatre, env=env).code == 0
    e = last(cli, tmp_theatre)
    assert (e["actor"], e["via"]) == (actor, "cli")

@pytest.mark.steps(4)
def test_cli_actor_defaults_to_the_login_user(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    cli("set", "a", "2", theatre=tmp_theatre)
    assert last(cli, tmp_theatre)["actor"] == {"kind": "human", "id": getpass.getuser()}

@pytest.mark.steps(4)
@pytest.mark.parametrize("bad", ["robot:x", "agent", "agent:", ":x"])
def test_malformed_actor_is_a_usage_error_and_records_nothing(cli, tmp_theatre, bad):
    build(tmp_theatre, {CFG: "a: 1\n"})
    before = events(cli, tmp_theatre)
    r = cli("set", "a", "2", theatre=tmp_theatre, env={"TROUPE_ACTOR": bad})
    assert r.code == 2 and events(cli, tmp_theatre) == before

@pytest.mark.steps(4)
def test_timestamp_is_now_in_utc(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    cli("set", "a", "2", theatre=tmp_theatre)
    at = datetime.fromisoformat(last(cli, tmp_theatre)["at"].replace("Z", "+00:00"))
    assert abs(datetime.now(timezone.utc) - at) < timedelta(minutes=2)

@pytest.mark.steps(4)
def test_idle_edit_is_recorded_as_file_with_unknown_actor(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    build(tmp_theatre, {CFG: "a: 2\n"})
    cli("show", "a", theatre=tmp_theatre, env={"TROUPE_ACTOR": "agent:x"})
    e = last(cli, tmp_theatre)
    assert (e["actor"], e["via"]) == ({"kind": "unknown", "id": None}, "file")

@pytest.mark.steps(4)
def test_set_while_watching_is_attributed_to_the_cli_not_the_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        for i in range(2, 7):                     # repeat: a race would show up as a "file" attribution
            cli("set", "a", str(i), theatre=tmp_theatre, env={"TROUPE_ACTOR": "agent:a1"})
        sets = [e for e in events(cli, tmp_theatre) if e["op"] == "set"]
        assert [(e["new"], e["via"], e["actor"]["id"]) for e in sets] == [(i, "cli", "a1") for i in range(2, 7)]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step4_lineage.py --step 4 -q`
Expected: FAIL (`KeyError: 'actor'`).

- [ ] **Step 3: Implement lineage in the reference**

```python
# reference/src/troupe_ref/cli.py
import getpass

class UsageError(Exception):
    pass

def actor_from_env() -> dict:
    raw = os.environ.get("TROUPE_ACTOR")
    if raw is None:
        return {"kind": "human", "id": getpass.getuser()}
    kind, sep, ident = raw.partition(":")
    if kind not in ("human", "agent") or not sep or not ident:
        raise UsageError(f"TROUPE_ACTOR must be human:<id> or agent:<id>, got {raw!r}")
    return {"kind": kind, "id": ident}
# main(): when STEP >= 4, compute actor_from_env() before constructing Service (UsageError -> exit 2)
```

```python
# reference/src/troupe_ref/service.py — replace _lineage and the constructor signature
from datetime import datetime, timezone

    def __init__(self, theatre: Path, actor: dict | None = None):
        self.theatre, self.actor = theatre, actor
        self.store = ConfigStore(theatre)

    def _lineage(self, via: str) -> dict:
        if STEP < 4:
            return {}
        actor = self.actor if via == "cli" else {"kind": "unknown", "id": None}
        return {"actor": actor, "via": via,
                "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")}
```

- [ ] **Step 4: Run the suites for steps 1–4** (step 2's and 4's watcher tests five times)

Run: `for s in 1 2 3 4; do uv run pytest tests/hidden --step $s -q || break; done`
Then: `for i in 1 2 3 4 5; do uv run pytest tests/hidden -k "watch" --step 4 -q || break; done`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 4 hidden tests and reference: actor, via, at on every event"
```

---

### Task 9: Step 5 — overrides (the data-rule contradiction, two concurrent change requests)

Assumes D1 (mapping-form `$include`). If the owner chose differently, rewrite the `before`/`after` strings
below to the chosen syntax before starting.

**Files:**
- Create: `tests/hidden/test_step5_overrides.py`
- Modify: `reference/src/troupe_ref/config.py`, `reference/src/troupe_ref/surgical.py`, `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `history.events`, `theatre.build/read`.
- Produces: `Config.set(path, value, in_include: bool = False)`; loader support for mapping-form includes;
  `Provenance` of an override leaf is the including file.

- [ ] **Step 1: Write the failing tests**

```python
# tests/hidden/test_step5_overrides.py
import pytest
from .history import events
from .theatre import build, read

CFG = ".troupe/troupe.yml"
CODER = ".troupe/agents/coder.yaml"
SHARED = {CFG: "agents:\n  coder: file:agents/coder.yaml  # the coder\n",
          CODER: "model: opus  # m\nlimits:\n  max_tokens: 8000\n"}

@pytest.mark.steps(5)
def test_new_key_under_include_becomes_override_in_including_file(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "agents.coder.temperature", "0.3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == ("agents:\n  coder:  # the coder\n"
                                     "    $include: file:agents/coder.yaml\n    temperature: 0.3\n")
    assert read(tmp_theatre, CODER) == SHARED[CODER]
    assert cli("get", "agents.coder.temperature", theatre=tmp_theatre).out == "0.3\n"
    assert cli("get", "agents.coder.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(5)
def test_nested_new_key_is_a_deep_merged_override(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "agents.coder.limits.max_retries", "3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == ("agents:\n  coder:  # the coder\n    $include: file:agents/coder.yaml\n"
                                     "    limits:\n      max_retries: 3\n")
    assert cli("get", "agents.coder.limits.max_tokens", theatre=tmp_theatre).out == "8000\n"
    assert cli("get", "agents.coder.limits.max_retries", theatre=tmp_theatre).out == "3\n"

@pytest.mark.steps(5)
def test_second_override_is_added_to_existing_mapping_form(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "coder:\n  $include: file:coder.yaml\n  temperature: 0.3\n",
                        ".troupe/coder.yaml": "model: opus\n"})
    assert cli("set", "coder.top_p", "0.9", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "coder:\n  $include: file:coder.yaml\n  temperature: 0.3\n  top_p: 0.9\n"

@pytest.mark.steps(5)
def test_existing_value_not_overridden_still_changes_in_its_own_file(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "agents.coder.model", "sonnet", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CODER) == "model: sonnet  # m\nlimits:\n  max_tokens: 8000\n"
    assert read(tmp_theatre, CFG) == SHARED[CFG]

@pytest.mark.steps(5)
def test_existing_overridden_value_changes_the_override(cli, tmp_theatre):
    files = {CFG: "coder:\n  $include: file:coder.yaml\n  model: sonnet\n", ".troupe/coder.yaml": "model: opus\n"}
    build(tmp_theatre, files)
    assert cli("get", "coder.model", theatre=tmp_theatre).out == "sonnet\n"
    assert cli("set", "coder.model", "haiku", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "coder:\n  $include: file:coder.yaml\n  model: haiku\n"
    assert read(tmp_theatre, ".troupe/coder.yaml") == "model: opus\n"

@pytest.mark.steps(5)
def test_in_include_flag_writes_new_key_into_the_shared_file(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "--in-include", "agents.coder.temperature", "0.3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CODER) == "model: opus  # m\nlimits:\n  max_tokens: 8000\ntemperature: 0.3\n"
    assert read(tmp_theatre, CFG) == SHARED[CFG]

@pytest.mark.steps(5)
def test_override_lists_and_scalars_replace_mappings_merge(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "c:\n  $include: file:c.yaml\n  tools: [read]\n  limits:\n    b: 20\n",
                        ".troupe/c.yaml": "tools: [bash, edit]\nlimits:\n  a: 1\n  b: 2\n"})
    assert cli("get", "c.tools.0", theatre=tmp_theatre).out == "read\n"
    assert cli("get", "c.tools.1", theatre=tmp_theatre).code == 5
    assert cli("get", "c.limits.a", theatre=tmp_theatre).out == "1\n"
    assert cli("get", "c.limits.b", theatre=tmp_theatre).out == "20\n"

@pytest.mark.steps(5)
def test_show_sources_attributes_overrides_to_the_including_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "c:\n  $include: file:c.yaml\n  model: sonnet\n", ".troupe/c.yaml": "model: opus\nx: 1\n"})
    lines = cli("show", "c", "--sources", theatre=tmp_theatre).out.splitlines()
    assert next(l for l in lines if l.strip().startswith("model:")).endswith("# from .troupe/troupe.yml")
    assert next(l for l in lines if l.strip().startswith("x:")).endswith("# from .troupe/c.yaml")

@pytest.mark.steps(5)
def test_override_events_carry_lineage(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    cli("set", "agents.coder.temperature", "0.3", theatre=tmp_theatre, env={"TROUPE_ACTOR": "agent:po"})
    e = [e for e in events(cli, tmp_theatre) if e["op"] == "set"][-1]
    assert (e["path"], e["new"], e["via"], e["actor"]) == ("agents.coder.temperature", 0.3, "cli",
                                                           {"kind": "agent", "id": "po"})
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step5_overrides.py --step 5 -q`
Expected: FAIL.

- [ ] **Step 3: Load mapping-form includes** — in `Config._walk`, when a `CommentedMap` has key `$include`
  (and `STEP >= 5`): load the target via `_load_source` exactly as a scalar include (recording
  `include_sites[merged_path] = (source, (*inner, "$include"))`), then deep-merge the sibling keys over it
  with this function, recording each override leaf's provenance as the including file:

```python
def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            out[k] = deep_merge(base[k], v) if k in base else v
        return out
    return override
```

- [ ] **Step 4: Redirect new keys** — in `Config.plan_set`, when the path is new, `STEP >= 5`,
  `in_include` is false, and the deepest existing ancestor's provenance is a file other than the one holding
  the nearest include site: the write goes to the include site's file.
  - Scalar-form site: splice the site line from `key: file:x  # c` to `key:  # c` and insert, directly
    below it at the site's indentation + 2, `$include: file:x` followed by the override lines in block
    style. Keep the end-of-line comment's bytes, including the spaces before `#`.
  - Mapping-form site: add the override under the site mapping with the normal new-key rules (Task 4).
  - Nested overrides create intermediate mappings under the site (`limits:` then `  max_retries: 3`).
  Add `--in-include` to `set`'s parser (STEP ≥ 5); pass it as `in_include=True`, which restores the step 1 rule.

- [ ] **Step 5: Run the suites for steps 1–5**

Run: `for s in 1 2 3 4 5; do uv run pytest tests/hidden --step $s -q || break; done`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 5 hidden tests and reference: overrides in the including file, --in-include"
```

---

### Task 10: Step 6 — the alias bug (arrives as a tracker issue)

Assumes D2: aliases are out of step 1's contract, so a naive arm has the bug. The reference reproduces the
bug below step 6 (`STEP < 6`: setting through an alias writes to the anchor), so step 6's tests fail on the
step 5 reference as Task 12 requires.

**Files:**
- Create: `tests/hidden/test_step6_aliases.py`
- Modify: `reference/src/troupe_ref/config.py`, `reference/src/troupe_ref/surgical.py`, `reference/src/troupe_ref/cli.py`

**Interfaces:**
- Consumes: `theatre.build/read`, `history.events`.
- Produces: `Config.set(path, value, in_include=False, expand_alias=False)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/hidden/test_step6_aliases.py
import pytest
from .history import events
from .theatre import build, read

CFG = ".troupe/troupe.yml"
SHARED = "defaults: &d\n  model: opus\ncoder:\n  settings: *d\nreviewer:\n  settings: *d\n"

@pytest.mark.steps(6)
def test_setting_the_anchor_changes_every_alias(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    assert cli("set", "defaults.model", "sonnet", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == SHARED.replace("model: opus", "model: sonnet")
    assert cli("get", "reviewer.settings.model", theatre=tmp_theatre).out == "sonnet\n"

@pytest.mark.steps(6)
def test_setting_through_an_alias_is_refused_and_suggests_expand(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    r = cli("set", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 3 and "--expand-alias" in r.err
    assert read(tmp_theatre, CFG) == SHARED
    assert cli("get", "reviewer.settings.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(6)
def test_expand_alias_makes_a_commented_local_copy_and_overrides_it(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    r = cli("set", "--expand-alias", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 0
    assert read(tmp_theatre, CFG) == ("defaults: &d\n  model: opus\n"
                                     "coder:\n  settings:  # expanded from *d by troupe\n    model: sonnet\n"
                                     "reviewer:\n  settings: *d\n")
    assert cli("get", "reviewer.settings.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(6)
def test_expanding_records_only_the_changed_leaf(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    events(cli, tmp_theatre)
    cli("set", "--expand-alias", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    changed = [(e["op"], e["path"], e["old"], e["new"]) for e in events(cli, tmp_theatre) if e["op"] != "import"]
    assert changed == [("set", "coder.settings.model", "opus", "sonnet")]

@pytest.mark.steps(6)
def test_scalar_alias_refused_and_anchor_scalar_settable(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: &x 1  # anchor\nb: *x\n"})
    assert cli("set", "b", "2", theatre=tmp_theatre).code == 3
    assert cli("set", "a", "2", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "a: &x 2  # anchor\nb: *x\n"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step6_aliases.py --step 6 -q`
Expected: the refusal and expand tests FAIL (the step-5 reference writes through the anchor, like a naive arm).

- [ ] **Step 3: Implement** — the spike's `surgical.py` already raises `AliasTargetError` for alias paths. Gate
  it: when `STEP < 6`, resolve the alias to its anchor and splice there (the bug); when `STEP >= 6`, raise
  `AliasTargetError(f"{path} is reached through alias *{name}; use --expand-alias to make a local copy")`.
  For `expand_alias=True`: render the anchored node with the Task 4 block-style rules at the alias's
  indentation + 2, splice it in place of `*name` with `  # expanded from *{name} by troupe` appended to the
  key line, then apply the `set` to the expanded copy. Add `--expand-alias` to `set` (STEP ≥ 6).

- [ ] **Step 4: Run the suites for steps 1–6**

Run: `for s in 1 2 3 4 5 6; do uv run pytest tests/hidden --step $s -q || break; done`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 6 hidden tests and reference: alias refusal and --expand-alias"
```

---

### Task 11: Step 7 — remote includes and schema (the model change)

**Files:**
- Create: `tests/hidden/remote.py` (HTTP fixture), `tests/hidden/test_step7_remote_schema.py`
- Modify: `reference/src/troupe_ref/config.py`, `reference/src/troupe_ref/cli.py`, `reference/src/troupe_ref/service.py`

**Interfaces:**
- Consumes: `theatre.build/read`.
- Produces: fixture `served(files: dict[str, str]) -> str` returning the base URL of a local HTTP server
  serving those files. Plan 2 must make this URL reachable from inside arm containers (bind on an address
  the container can reach and set `BAKEOFF_HTTP_HOST`).

- [ ] **Step 1: Write the HTTP fixture and the failing tests**

```python
# tests/hidden/remote.py
import functools, http.server, os, threading
from pathlib import Path
import pytest

@pytest.fixture
def served(tmp_path_factory):
    servers = []
    def serve(files: dict[str, str]) -> str:
        root = tmp_path_factory.mktemp("www")
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        host = os.environ.get("BAKEOFF_HTTP_HOST", "127.0.0.1")
        srv = http.server.ThreadingHTTPServer((host, 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://{host}:{srv.server_address[1]}"
    yield serve
    for s in servers:
        s.shutdown()
```

```python
# tests/hidden/test_step7_remote_schema.py
import json
import pytest
from .remote import served  # noqa: F401  (fixture)
from .theatre import build, read

CFG = ".troupe/troupe.yml"
SCHEMA = ".troupe/troupe.schema.json"
DEAD = "http://127.0.0.1:1"          # nothing listens: a fetch here fails, so success proves no fetch happened

@pytest.mark.steps(7)
def test_remote_yaml_and_text_includes_load(cli, tmp_theatre, served):
    base = served({"team.yaml": "model: opus\n", "prompt.md": "Be kind.\n"})
    build(tmp_theatre, {CFG: f"team: {base}/team.yaml\nprompt: {base}/prompt.md\n"})
    assert cli("get", "team.model", theatre=tmp_theatre).out == "opus\n"
    assert cli("get", "prompt", theatre=tmp_theatre).out == "Be kind.\n"

@pytest.mark.steps(7)
def test_failed_fetch_exits_4(cli, tmp_theatre, served):
    base = served({})
    build(tmp_theatre, {CFG: f"team: {base}/missing.yaml\n"})
    assert cli("get", "team.model", theatre=tmp_theatre).code == 4

@pytest.mark.steps(7)
def test_changing_a_remote_value_is_refused_naming_the_include(cli, tmp_theatre, served):
    base = served({"team.yaml": "model: opus\n"})
    files = {CFG: f"team: {base}/team.yaml\n"}
    build(tmp_theatre, files)
    r = cli("set", "team.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 3 and f"{base}/team.yaml" in r.err
    assert read(tmp_theatre, CFG) == files[CFG]

@pytest.mark.steps(7)
def test_new_key_under_remote_include_becomes_local_override(cli, tmp_theatre, served):
    base = served({"team.yaml": "model: opus\n"})
    build(tmp_theatre, {CFG: f"team: {base}/team.yaml\n"})
    assert cli("set", "team.temperature", "0.3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == f"team:\n  $include: {base}/team.yaml\n  temperature: 0.3\n"

@pytest.mark.steps(7)
def test_schema_format_uri_field_is_literal_and_not_fetched(cli, tmp_theatre):
    schema = {"type": "object", "properties": {"homepage": {"type": "string", "format": "uri"}}}
    build(tmp_theatre, {CFG: f"homepage: {DEAD}/site.yaml\n", SCHEMA: json.dumps(schema)})
    r = cli("get", "homepage", theatre=tmp_theatre)
    assert (r.code, r.out) == (0, f"{DEAD}/site.yaml\n")

@pytest.mark.steps(7)
def test_literal_tag_is_literal_and_kept_on_set(cli, tmp_theatre):
    build(tmp_theatre, {CFG: f'docs: !literal "{DEAD}/a.yaml"  # c\n'})
    assert cli("get", "docs", theatre=tmp_theatre).out == f"{DEAD}/a.yaml\n"
    assert cli("set", "docs", json.dumps(f"{DEAD}/b.yaml"), theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == f'docs: !literal "{DEAD}/b.yaml"  # c\n'

@pytest.mark.steps(7)
def test_url_value_set_on_untyped_field_is_written_as_literal(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "x: old\n"})
    assert cli("set", "x", f"{DEAD}/z.yaml", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == f"x: !literal {DEAD}/z.yaml\n"
    assert cli("get", "x", theatre=tmp_theatre).out == f"{DEAD}/z.yaml\n"

@pytest.mark.steps(7)
def test_include_flag_writes_a_real_include(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "x: old\n", ".troupe/extra.yaml": "k: v\n"})
    assert cli("set", "--include", "x", "file:extra.yaml", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "x: file:extra.yaml\n"
    assert cli("get", "x.k", theatre=tmp_theatre).out == "v\n"

@pytest.mark.steps(7)
def test_config_invalid_against_schema_exits_4(cli, tmp_theatre):
    schema = {"type": "object", "properties": {"budget": {"type": "integer"}}}
    build(tmp_theatre, {CFG: "budget: lots\n", SCHEMA: json.dumps(schema)})
    assert cli("get", "budget", theatre=tmp_theatre).code == 4

@pytest.mark.steps(7)
def test_set_that_would_violate_schema_is_refused(cli, tmp_theatre):
    schema = {"type": "object", "properties": {"budget": {"type": "integer"}}}
    files = {CFG: "budget: 5\n", SCHEMA: json.dumps(schema)}
    build(tmp_theatre, files)
    assert cli("set", "budget", "lots", theatre=tmp_theatre).code == 3
    assert read(tmp_theatre, CFG) == files[CFG]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/hidden/test_step7_remote_schema.py --step 7 -q`
Expected: FAIL. (The `served` fixture is imported into the test module; do not use `pytest_plugins` in
`tests/hidden/conftest.py` — pytest rejects it outside the root conftest.)

- [ ] **Step 3: Implement in the reference** — ungate the spike's remote-include, `!literal` and
  schema-literal code for `STEP >= 7` (Task 3 gated it). Then add:
  - `loader.load`: read `.troupe/troupe.schema.json` if present, pass it to `Config`, and after loading
    validate `cfg.merged` with `jsonschema.Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)`;
    failure → `LoadError`.
  - `Service.set`: apply the write to copies of the affected texts in memory, re-load and validate; only if
    valid write the files (refusal → `RejectedSet`, exit 3, nothing written).
  - `Config.set`: a string value matching `INCLUDE_RE` whose schema is not `format: uri` is written as
    `!literal <value>` unless `include=True`; add `--include` to `set` (STEP ≥ 7).
  - `ReadOnlyIncludeError` messages include the include string exactly as written in the local file.

- [ ] **Step 4: Run all seven suites**

Run: `for s in 1 2 3 4 5 6 7; do uv run pytest tests/hidden --step $s -q || break; done`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/hidden reference
git commit -m "Step 7 hidden tests and reference: remote includes, schema, !literal"
```

---

### Task 12: Validate the instrument — every suite passable, every new test able to fail

**Files:**
- Modify: `tests/hidden/conftest.py` (add `--first-step-only`)
- Create: `harness/validate_suites.py`, `harness/negative_allowlist.txt`
- Create: `results/instrument-validation.md` (generated, committed)

**Interfaces:**
- Consumes: the `steps` marker, `--step`, `TROUPE_REF_STEP`.
- Produces: `uv run python harness/validate_suites.py` → exit 0 only if every check passes; writes the report.

- [ ] **Step 1: Add first-step selection to the conftest**

```python
# tests/hidden/conftest.py — in pytest_addoption:
    parser.addoption("--first-step-only", type=int, default=None,
                     help="keep only tests whose first valid step is this one")
# in pytest_collection_modifyitems, after computing first/last:
        only = config.getoption("--first-step-only")
        if only is not None and first != only:
            drop.append(item); continue
```

- [ ] **Step 2: Write the validator**

```python
# harness/validate_suites.py
"""Positive: suite N passes on the reference at step N. Negative: tests first valid at step N fail on the
reference at step N-1 (else they may be vacuous). Flake: watcher suites pass 5 times in a row."""
from __future__ import annotations
import os, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALLOW = {l.split("#")[0].strip() for l in (REPO / "harness/negative_allowlist.txt").read_text().splitlines()
         if l.split("#")[0].strip()}

def run(step: int, ref_step: int, extra: list[str], xml: Path) -> dict[str, str]:
    env = {**os.environ, "TROUPE_REF_STEP": str(ref_step)}
    subprocess.run(["uv", "run", "pytest", "tests/hidden", "--step", str(step), "-q", "-p", "no:cacheprovider",
                    f"--junitxml={xml}", *extra], cwd=REPO, env=env)
    out = {}
    for tc in ET.parse(xml).iter("testcase"):
        outcome = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
                  "skipped" if tc.find("skipped") is not None else "passed"
        out[f"{tc.get('classname')}::{tc.get('name')}"] = outcome
    return out

def main() -> int:
    tmp = REPO / "results/tmp"; tmp.mkdir(parents=True, exist_ok=True)
    lines, ok = ["# Instrument validation", ""], True
    for n in range(1, 8):
        res = run(n, n, [], tmp / f"pos{n}.xml")
        bad = [t for t, o in res.items() if o != "passed"]
        ok &= not bad and bool(res)
        lines.append(f"- step {n} positive: {len(res)} tests, {len(bad)} not passing {bad or ''}")
    for n in range(2, 8):
        res = run(n, n - 1, ["--first-step-only", str(n)], tmp / f"neg{n}.xml")
        passing = [t for t, o in res.items() if o == "passed"]
        unexplained = [t for t in passing if t.split("::")[-1] not in ALLOW]
        ok &= not unexplained
        lines.append(f"- step {n} negative: {len(res)} new tests, {len(passing)} pass at step {n-1} "
                     f"(allowlisted: {len(passing) - len(unexplained)}; unexplained: {unexplained or 'none'})")
    for i in range(5):
        res = run(4, 4, ["-k", "watch or edit"], tmp / f"flake{i}.xml")
        bad = [t for t, o in res.items() if o != "passed"]
        ok &= not bad
        lines.append(f"- watcher run {i + 1}/5: {len(bad)} not passing {bad or ''}")
    lines += ["", f"**Result: {'PASS' if ok else 'FAIL'}**", ""]
    (REPO / "results/instrument-validation.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
```

```text
# harness/negative_allowlist.txt — tests allowed to pass on the previous step's reference.
# Each entry must name the failing test in the same step that pins the behaviour.
test_formatting_and_comment_only_edits_record_nothing   # paired with test_edit_while_idle_is_picked_up_by_the_next_command
test_history_does_not_reconcile                         # paired with test_watch_picks_up_an_edit_to_an_included_file
test_show_on_a_scalar_still_prints_the_value            # paired with test_show_on_a_section_prints_merged_yaml
test_existing_value_not_overridden_still_changes_in_its_own_file  # paired with test_new_key_under_include_becomes_override_in_including_file
test_show_unknown_path_exits_5                          # paired with test_get_on_a_section_exits_5_and_points_at_show
test_second_override_is_added_to_existing_mapping_form  # paired with test_new_key_under_include_becomes_override_in_including_file
test_existing_overridden_value_changes_the_override     # paired with test_override_lists_and_scalars_replace_mappings_merge
test_show_sources_attributes_overrides_to_the_including_file  # paired with test_nested_new_key_is_a_deep_merged_override
test_setting_the_anchor_changes_every_alias             # paired with test_setting_through_an_alias_is_refused_and_suggests_expand
test_scalar_alias_refused_and_anchor_scalar_settable    # must FAIL at step 5 (refusal part); remove this line if it does
```

Before running, delete the last allowlist line if that test fails at step 5 as intended (it should — its
first assertion is the refusal). The step 5 entries pass at step 4 only because a step 4 implementation
happens to read `$include:` as an ordinary key holding a `file:` include; each is paired with a step 5 test
that does fail. Every entry must be justified by its comment. If the validator finds further passing tests,
add them only with a pairing comment, and list them for the owner in the Task 12 commit message.

- [ ] **Step 3: Run the validator**

Run: `uv run python harness/validate_suites.py`
Expected: `**Result: PASS**`. If a negative check lists an unexplained passing test, the test is too weak:
strengthen it (or, if it genuinely pins unchanged behaviour, move it to the earlier step's range) — do not
allowlist it.

- [ ] **Step 4: Run each suite against the Task 1 skeleton** (an arm that did nothing must score zero)

Run: `git worktree add ../bakeoff-skeleton $(git rev-list -n1 --grep "reference skeleton" HEAD) && for s in 1 2 3 4 5 6 7; do uv run pytest tests/hidden --step $s --impl ../bakeoff-skeleton/reference -q | tail -1; done; git worktree remove ../bakeoff-skeleton`
Expected: every line reports 0 passed.

- [ ] **Step 5: Commit the report**

```bash
git add tests/hidden/conftest.py harness results/instrument-validation.md
git commit -m "Instrument validation: positive, negative and flake checks all pass"
git push
```
