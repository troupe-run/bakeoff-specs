"""`Watching` must deliver exactly one SIGTERM to the candidate when the candidate runs behind a signal-
forwarding wrapper (`uv run`, as the hidden suite's default `cli` fixture does). A process-group-wide
SIGTERM reaches the candidate twice — once directly, once forwarded by uv — and a correct candidate can
then exit 143."""
import os, shutil, sys
from pathlib import Path
import pytest
from tests.hidden.driver import Cli
from tests.hidden.watcher import Watching

FAKE = Path(__file__).with_name("fake_watch.py")

@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv to reproduce the `uv run` wrapper path")
def test_watching_stops_a_uv_wrapped_candidate_with_exactly_one_sigterm(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "fake-watch"\nversion = "0"\nrequires-python = ">=3.8"\ndependencies = []\n')
    count_file = tmp_path / "sigterms"
    monkeypatch.setenv("FAKE_SIGTERM_COUNT", str(count_file))
    theatre = tmp_path / "theatre"
    theatre.mkdir()
    cli = Cli(["uv", "run", "--quiet", "--project", str(project), "python", str(FAKE)])
    with Watching(cli, theatre, ready_timeout=60) as w:
        pass
    assert count_file.read_text() == "1"
    assert w.code == 0

def test_watching_drains_a_chatty_candidate(tmp_path):
    # Writes far more than a pipe buffer to both streams after readiness; without continuous draining it
    # blocks on write and never reaches its SIGTERM handler's exit in time.
    script = tmp_path / "chatty.py"
    script.write_text(
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))\n"
        "print('watching', flush=True)\n"
        "for _ in range(2000):\n"
        "    sys.stdout.write('x' * 1000 + '\\n'); sys.stderr.write('y' * 1000 + '\\n')\n"
        "sys.stdout.flush(); sys.stderr.flush()\n"
        "open(sys.argv[-1] + '.done', 'w').close()\n"
        "while True: time.sleep(0.05)\n")
    theatre = tmp_path / "theatre"
    theatre.mkdir()
    cli = Cli([sys.executable, str(script)])
    with Watching(cli, theatre) as w:
        from tests.hidden.watcher import wait_for
        assert wait_for(lambda: Path(str(theatre) + ".done").exists(), 10)
    assert w.code == 0
    assert len(w.out) == 2001 and len(w.err) == 2000
