from __future__ import annotations
import shlex
from pathlib import Path
import pytest
from .driver import Cli

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
