"""The supervisor's own branches, driven by a local process standing in for the docker CLI (no Docker)."""
import sys
from runner import credentials, docker, session
from runner.session import Turn, run_turn

def test_a_cli_that_never_exits_after_its_stdout_closes_is_stopped(tmp_path, monkeypatch):   # fix round 1, item 2
    # Normal-exit path: stdout reaches EOF but the process (and so maybe the container) stays alive and stderr
    # stays open. The post-drain timeout must stop the container by name, not only kill the local CLI.
    stops: list[str] = []
    child = [sys.executable, "-c",
             "import os, sys, time, json; print(json.dumps({'type':'system','subtype':'init','session_id':'s'}),"
             " flush=True); os.close(1); time.sleep(60)"]
    monkeypatch.setattr(docker, "run_argv", lambda spec: child)
    monkeypatch.setattr(docker, "stop", lambda name: stops.append(name))
    monkeypatch.setattr(session, "POST_STOP_DRAIN_S", 1)
    t = Turn("t", "dryrun", 1, 1, 1, "img", "m", {}, [], "none", False, "/w", tmp_path / "inbox", "arm", True, None)
    r = run_turn(t, credentials.dummy(), tmp_path / "out", 30)
    assert stops == [session.container_name(t)]
    assert r.outcome == "no_result" and r.session_id == "s" and r.wall_seconds < 20
