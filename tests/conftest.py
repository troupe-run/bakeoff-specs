from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def pytest_addoption(parser):
    parser.addoption("--impl", default=str(REPO / "reference"), help="arm repo root (uv project)")
    parser.addoption("--step", type=int, default=7, help="scenario step whose suite to run (1-7)")
    parser.addoption("--cmd-prefix", default=None, help='overrides the command, e.g. "docker exec arm uv run troupe"')

def pytest_configure(config):
    config.addinivalue_line("markers", "steps(first, last=7): scenario steps this test is valid for")
