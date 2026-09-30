"""The supervisor's own branches, driven by a local process standing in for the docker CLI (no Docker).
Every test that really runs `run_turn` uses `tmp_state`: the turn's live feed is written under STATE."""
import sys
from runner import credentials, docker, session
from runner.session import Turn, run_turn

def test_a_cli_that_never_exits_after_its_stdout_closes_is_stopped(tmp_state, tmp_path, monkeypatch):   # fix round 1, item 2
    # Normal-exit path: stdout reaches EOF but the process (and so maybe the container) stays alive and stderr
    # stays open. The post-drain timeout must stop the container by name, not only kill the local CLI.
    stops: list[str] = []
    child = [sys.executable, "-c",
             "import os, sys, time, json; print(json.dumps({'type':'system','subtype':'init','session_id':'s'}),"
             " flush=True); os.close(1); time.sleep(60)"]
    monkeypatch.setattr(docker, "run_argv", lambda spec: child)
    monkeypatch.setattr(docker, "stop", lambda name: stops.append(name))
    monkeypatch.setattr(docker, "exit_state", lambda name: (False, None))
    monkeypatch.setattr(docker, "remove", lambda name: None)
    monkeypatch.setattr(session, "POST_STOP_DRAIN_S", 1)
    t = Turn("t", "dryrun", 1, 1, 1, "img", "m", {}, [], "none", False, "/w", tmp_path / "inbox", "arm", True, None)
    r = run_turn(t, credentials.dummy(), tmp_path / "out", 30)
    assert stops == [session.container_name(t)]
    assert r.outcome == "no_result" and r.session_id == "s" and r.wall_seconds < 20


# ---- final fix batch A5: an arm session container killed for memory is detected ----------------------------------

def _exiting(tmp_path, monkeypatch, code: int, state):
    child = [sys.executable, "-c",
             f"import json, sys; print(json.dumps({{'type':'system','subtype':'init','session_id':'s'}}), flush=True); "
             f"sys.exit({code})"]
    removed = []
    monkeypatch.setattr(docker, "run_argv", lambda spec: child)
    monkeypatch.setattr(docker, "stop", lambda name: None)
    monkeypatch.setattr(docker, "exit_state", lambda name: state)
    monkeypatch.setattr(docker, "remove", lambda name: removed.append(name))
    t = Turn("t", "dryrun", 1, 1, 1, "img", "m", {}, [], "none", False, "/w", tmp_path / "inbox", "arm", True, None)
    return run_turn(t, credentials.dummy(), tmp_path / "out", 30), removed, t


def test_an_oom_killed_session_container_is_reported(tmp_state, tmp_path, monkeypatch):
    r, removed, t = _exiting(tmp_path, monkeypatch, 137, (True, 137))
    assert r.oom_killed and r.exit_code == 137 and r.outcome == "no_result"
    assert removed == [session.container_name(t)]                       # inspected, then removed


def test_exit_137_alone_counts_as_killed_for_memory(tmp_state, tmp_path, monkeypatch):
    r, _, _ = _exiting(tmp_path, monkeypatch, 137, (False, None))        # inspect failed: docker run's own exit
    assert r.oom_killed and r.exit_code == 137


def test_a_normal_exit_is_not_oom(tmp_state, tmp_path, monkeypatch):
    r, removed, t = _exiting(tmp_path, monkeypatch, 0, (False, 0))
    assert not r.oom_killed and r.exit_code == 0 and removed == [session.container_name(t)]


def test_the_session_container_is_kept_until_it_is_inspected():
    from runner.config import load_pins
    s = session._spec(Turn("t", "dryrun", 1, 1, 1, "img", "m", {}, [], "none", False, "/w", __import__("pathlib").Path("/tmp"),
                           "arm", True, None))
    assert s.remove is False
    import runner.docker as d
    argv = d.run_argv(__import__("dataclasses").replace(s, mounts=[]))
    assert "--rm" not in argv and "--rm" in d.run_argv(__import__("dataclasses").replace(s, mounts=[], remove=True))


# ---- follow-up 1: a session OOM is a turn that did NOT complete ---------------------------------------------------

def test_a_child_oom_kill_in_a_turn_that_returned_a_result_is_not_a_session_oom(tmp_state, tmp_path, monkeypatch):
    child = [sys.executable, "-c",
             "import json; print(json.dumps({'type':'system','subtype':'init','session_id':'s'})); "
             "print(json.dumps({'type':'result','subtype':'success','is_error':False,'result':'done'}), flush=True)"]
    monkeypatch.setattr(docker, "run_argv", lambda spec: child)
    monkeypatch.setattr(docker, "stop", lambda name: None)
    monkeypatch.setattr(docker, "exit_state", lambda name: (True, 0))     # cgroup v2: a child was OOM-killed
    monkeypatch.setattr(docker, "remove", lambda name: None)
    t = Turn("t", "dryrun", 1, 1, 1, "img", "m", {}, [], "none", False, "/w", tmp_path / "inbox", "arm", True, None)
    r = run_turn(t, credentials.dummy(), tmp_path / "out", 30)
    assert r.outcome == "ok" and not r.oom_killed and r.exit_code == 0
