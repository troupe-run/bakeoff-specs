"""Mutation testing an arm whose tests shell out to its own CLI via `uv run <script>` (the contract prescribes the
CLI, so arms do this). mutmut 3 copies pyproject.toml/uv.lock into `mutants/` and runs the arm's tests from there;
`uv run` from `mutants/` then treats it as its own project and, offline with UV_NO_SYNC=1, builds an empty venv
and fails to spawn the script -- the stats phase fails and the whole run used to crash (canary control/01).

The fixture is written per test (not checked in as a tree: its `test_*.py` files must not be collected by this
suite): a src-layout project with a console script, one in-process test that kills mutants of `add`, and one test
that reaches `shout` ONLY through `uv run mfx` from the repo root computed from `__file__`."""
import dataclasses

import pytest

from runner import config, hidden, quality
from runner.paths import Paths

pytestmark = pytest.mark.docker

FIXTURE = {
    "pyproject.toml": """\
[project]
name = "mfx"
version = "0"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
mfx = "mfx.cli:main"

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"

[dependency-groups]
dev = ["pytest>=8.3"]
""",
    "src/mfx/__init__.py": "",
    "src/mfx/core.py": """\
def add(a: int, b: int) -> int:
    return a + b
""",
    "src/mfx/cli.py": """\
import sys


def shout(s: str) -> str:
    return s.upper() + "!"


def main() -> None:
    print(shout(sys.argv[1]))
""",
    "tests/test_core.py": """\
from mfx.core import add


def test_add():
    assert add(2, 3) == 5
""",
    "tests/test_cli.py": """\
import subprocess
from pathlib import Path


def test_entry_point():
    r = subprocess.run(["uv", "run", "mfx", "hi"], cwd=Path(__file__).parent.parent,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout == "HI!\\n"
""",
}


def _write(root):
    for rel, text in FIXTURE.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    p = Paths("dryquality", "dryrun")
    base = tmp_path_factory.mktemp("qsub")
    a, b = base / "a" / "bakeoff-specs-dryrun", base / "b" / "bakeoff-specs-dryrun"
    for d in (a, b):
        _write(d)
    prep = hidden.prepare_copy(p, a, base, "mfx", quality_copy=b)
    assert prep.prep["quality"]["ok"], prep.prep["quality"]
    return p, prep


def test_subprocess_only_cli_mutants_are_no_tests_and_core_mutants_are_killed_without_a_crash(prepared, tmp_path):
    p, prep = prepared
    pins = config.load_pins()
    pins = dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, mutation_seconds=600))
    m = quality._mutation(p, prep.quality_copy, quality.targets(prep.quality_copy), tmp_path, pins)
    log = (tmp_path / "quality" / "mutmut.log").read_text()
    assert m["baseline_rc"] == 0, log                      # the subprocess test passes outside mutmut
    assert m["crashed"] is False, log
    assert m["score"] is not None and m["unmeasured"] is None, m
    # per-mutant statuses, from the results container's section of the log (the only place they are parsed)
    results = log[log.index("mutmut results --all true  (fresh container)"):]
    statuses = {}
    for line in results.splitlines():
        name, sep, status = line.strip().partition(": ")
        if sep and "__mutmut_" in name:
            statuses[name] = status
    cli = {n: s for n, s in statuses.items() if n.startswith("mfx.cli.")}
    core = {n: s for n, s in statuses.items() if n.startswith("mfx.core.")}
    assert cli and set(cli.values()) == {"no tests"}, statuses     # reached only through `uv run mfx`
    assert core and set(core.values()) == {"killed"}, statuses     # test_add, in-process
    assert not (prep.quality_copy / "mutants" / ".venv").exists()   # uv did not build a venv of its own there
