from __future__ import annotations
import os
import shlex
from pathlib import Path
import pytest

REFERENCE = Path(__file__).resolve().parents[2] / "reference"
from .driver import Cli, forwarded
from .theatre import share_with_arm

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
        only = config.getoption("--first-step-only")
        if only is not None and first != only:
            drop.append(item)
            continue
        (keep if first <= step <= last else drop).append(item)
    config.hook.pytest_deselected(items=drop)
    items[:] = keep

@pytest.fixture(scope="session")
def cli(request) -> Cli:
    # `--step` only selects which tests run (pytest_collection_modifyitems above); it does not by
    # itself change how the arm behaves. For the reference implementation, behaviour is gated by
    # the TROUPE_REF_STEP env var (troupe_ref.step.STEP, default 7). Default it from --step here so
    # `uv run pytest tests/hidden --step N -q` exercises the arm as step N, not step 7 — but only a
    # default: setdefault, not assignment, so an explicitly-set TROUPE_REF_STEP always wins (e.g.
    # Task 12's validator runs `TROUPE_REF_STEP=N-1 pytest --step N` to prove step N's new tests
    # fail on step N-1's reference; an unconditional overwrite would silently defeat that check).
    os.environ.setdefault("TROUPE_REF_STEP", str(request.config.getoption("--step")))
    prefix = request.config.getoption("--cmd-prefix")
    impl = request.config.getoption("--impl")
    fwd = forwarded(impl, prefix, request.config.getoption("--forward-ref-step"), REFERENCE)
    if prefix:
        return Cli(shlex.split(prefix), fwd)
    return Cli(["uv", "run", "--quiet", "--project", impl, "troupe"], fwd)

@pytest.fixture
def tmp_theatre(tmp_path, tmp_path_factory):
    # In the runner's tester (BAKEOFF_SHARE_THEATRE_WITH_ARM=1) the arm CLI runs under a different uid from
    # pytest: open this theatre to it, and create files world-writable (umask 0) while the test runs so the
    # arm can edit what the test builds. Elsewhere (Plan 1, host runs) nothing changes.
    if os.environ.get("BAKEOFF_SHARE_THEATRE_WITH_ARM") != "1":
        yield tmp_path
        return
    share_with_arm(tmp_path, tmp_path_factory.getbasetemp().parent)
    old = os.umask(0)
    try:
        yield tmp_path
    finally:
        os.umask(old)
