from __future__ import annotations
import os
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
    # `--step` only selects which tests run (pytest_collection_modifyitems above); it does not by
    # itself change how the arm behaves. For the reference implementation, behaviour is gated by
    # the TROUPE_REF_STEP env var (troupe_ref.step.STEP, default 7). Propagate --step into it here
    # so `uv run pytest tests/hidden --step N -q` actually exercises the arm as step N, not step 7.
    os.environ["TROUPE_REF_STEP"] = str(request.config.getoption("--step"))
    prefix = request.config.getoption("--cmd-prefix")
    if prefix:
        return Cli(shlex.split(prefix))
    return Cli(["uv", "run", "--quiet", "--project", request.config.getoption("--impl"), "troupe"])

@pytest.fixture
def tmp_theatre(tmp_path) -> Path:
    return tmp_path
