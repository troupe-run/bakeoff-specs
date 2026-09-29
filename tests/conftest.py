from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

def pytest_addoption(parser):
    parser.addoption("--impl", default=str(REPO / "reference"), help="arm repo root (uv project)")
    parser.addoption("--step", type=int, default=7, help="scenario step whose suite to run (1-7)")
    parser.addoption("--cmd-prefix", default=None, help='overrides the command, e.g. "docker exec arm uv run troupe"')
    parser.addoption("--first-step-only", type=int, default=None,
                     help="keep only tests whose first valid step is this one")
    parser.addoption("--run-live", action="store_true", help="allow tests that spend real model quota")
    parser.addoption("--run-docker", action="store_true", help="allow tests that need a running Docker daemon and built images")
    parser.addoption("--run-network", action="store_true", help="allow tests that need internet (real arm setup)")
    parser.addoption("--run-host-exec", action="store_true",
                     help="allow negative controls that run arm-planted commands on the host (tmp-dir markers only)")

def pytest_configure(config):
    config.addinivalue_line("markers", "steps(first, last=7): scenario steps this test is valid for")
    config.addinivalue_line("markers", "docker: needs a running Docker daemon and built images")
    config.addinivalue_line("markers", "network: needs internet (real arm setup)")
    config.addinivalue_line("markers", "live: spends real model quota; only with --run-live")
    config.addinivalue_line("markers", "host_exec: runs arm-planted commands on the host; only with --run-host-exec")

def pytest_collection_modifyitems(config, items):
    # M1 (preflight ruling): docker/network/live are opt-in, so `pytest tests/runner -q`
    # stays fast and offline unless the matching --run-* flag is given.
    skips = {
        "live": (config.getoption("--run-live"), "live test: pass --run-live"),
        "docker": (config.getoption("--run-docker"), "docker test: pass --run-docker"),
        "network": (config.getoption("--run-network"), "network test: pass --run-network"),
        "host_exec": (config.getoption("--run-host-exec"), "host-exec negative control: pass --run-host-exec"),
    }
    for item in items:
        for marker, (enabled, reason) in skips.items():
            if marker in item.keywords and not enabled:
                item.add_marker(pytest.mark.skip(reason=reason))
