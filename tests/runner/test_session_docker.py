"""One supervised turn against the real Docker daemon with the fake claude (bakeoff-arm-dryrun) and the dummy
credential — no model calls, no quota. Opt in with --run-docker (preflight M1)."""
import gzip, pytest
from runner import config, credentials, docker
from runner import session
from runner.session import Turn, run_turn
from runner.docker import Mount

pytestmark = pytest.mark.docker

def turn(tmp_path, message, n=1, role="arm"):
    home = tmp_path / "home"; (home / ".claude").mkdir(parents=True, exist_ok=True)
    work = tmp_path / "work" / "bakeoff-specs-dryrun"; work.mkdir(parents=True, exist_ok=True)
    env = credentials.session_env(config.load_pins(), config.load_arm("dryrun"), role="arm", isolated=False,
                                  pass_="t")               # controller ruling: arm sessions always pass pass_
    return Turn("t", "dryrun", 1, 1, n, config.load_pins().images["dryrun"], message, env,
                [Mount(home, "/home/actor", False), Mount(tmp_path / "work", "/work", False)],
                "none", False, "/work/bakeoff-specs-dryrun", tmp_path / "inbox" / role, role, True, home / ".claude")

@pytest.fixture(autouse=True)
def no_leftovers(tmp_state):             # tmp_state: each turn's live feed (runner watch) is written under STATE
    yield
    assert not docker.running("bakeoff.run=t/dryrun")

def test_ok_turn_records_stream_and_session(tmp_path):
    r = run_turn(turn(tmp_path, "hello\nFAKE:reply=done"), credentials.dummy(), tmp_path / "out", 60)
    assert r.outcome == "ok" and r.final_text == "done" and r.session_id
    assert r.result["token_seen"] is True                      # fd 3 hand-off works
    assert "dry-run-dummy-token" not in gzip.open(r.stream_path, "rt").read()
    assert (tmp_path / "out" / "turns" / "arm-a1-001.prompt.md").read_text() == "hello\nFAKE:reply=done"
    (feed,) = (tmp_path / "state" / "t" / "dryrun" / "live").glob("01-*-arm-a1-001-*.log")   # runner watch's feed
    text = feed.read_text()
    assert "text: done" in text and "turn end: ok" in text.splitlines()[-1] and "dry-run-dummy-token" not in text

def test_the_pinned_model_is_passed_explicitly(tmp_path):     # controller ruling: never rely on the default
    r = run_turn(turn(tmp_path, "FAKE:reply=ok"), credentials.dummy(), tmp_path / "out", 60)
    assert r.init["model"] == config.load_pins().model and r.result["model_arg"] == config.load_pins().model

def test_timeout_stops_the_container(tmp_path):
    r = run_turn(turn(tmp_path, "FAKE:sleep=120"), credentials.dummy(), tmp_path / "out", 5)
    assert r.outcome == "timeout" and not docker.running("bakeoff.run=t/dryrun")

def test_auth_failure_aborts_without_waiting_for_retries(tmp_path):
    r = run_turn(turn(tmp_path, "FAKE:auth_fail"), credentials.dummy(), tmp_path / "out", 600)
    assert r.outcome == "auth_failed" and r.wall_seconds < 60

def test_a_200k_stream_line_passes_through_the_pipe(tmp_path):                 # review Q-11 (the real 64 KiB limit)
    r = run_turn(turn(tmp_path, "FAKE:bigline=200000\nFAKE:reply=ok"), credentials.dummy(), tmp_path / "out", 60)
    assert r.outcome == "ok"

def test_a_chatty_stderr_does_not_block_the_turn(tmp_path, monkeypatch):       # review C-9
    # asyncio's subprocess transport buffers each pipe itself up to 2 x the reader limit before pausing, so with
    # the production 64 MiB limit a 500 KB stderr passes even with no drain at all. Shrinking the limit (the
    # stream lines here are small) makes this test fail if stderr is not drained concurrently.
    monkeypatch.setattr(session, "STREAM_LINE_LIMIT", 64 * 1024)
    r = run_turn(turn(tmp_path, "FAKE:stderr=500000\nFAKE:reply=ok"), credentials.dummy(), tmp_path / "out", 60)
    assert r.outcome == "ok" and r.wall_seconds < 30 and len(gzip.open(r.stderr_path).read()) == 500000

def test_only_the_current_message_is_visible_in_the_container(tmp_path):      # review C-12
    (tmp_path / "inbox" / "teammate").mkdir(parents=True)
    (tmp_path / "inbox" / "teammate" / "secret.md").write_text("teammate prompt")
    run_turn(turn(tmp_path, "first", n=1), credentials.dummy(), tmp_path / "out", 60)
    r = run_turn(turn(tmp_path, "FAKE:ls_inbox", n=2), credentials.dummy(), tmp_path / "out", 60)
    assert r.final_text == "msg.md"            # not the earlier message, not another role's inbox

def test_a_persisted_credential_file_is_reported(tmp_path):                    # review S-3
    r = run_turn(turn(tmp_path, "FAKE:persist_token\nFAKE:reply=ok"), credentials.dummy(), tmp_path / "out", 60)
    assert r.credential_files == [".credentials.json"]

def test_a_clean_turn_reports_no_credential_files(tmp_path):                   # S-3, the negative half
    r = run_turn(turn(tmp_path, "FAKE:reply=ok"), credentials.dummy(), tmp_path / "out", 60)
    assert r.credential_files == []

def test_the_real_credential_is_refused_for_a_dry_arm(tmp_path):              # review C-14
    with pytest.raises(PermissionError):
        run_turn(turn(tmp_path, "x"), credentials.Credential("real"), tmp_path / "out", 60)


def test_a_not_logged_in_result_is_an_auth_failure(tmp_path):                  # fix round 1, item 1
    r = run_turn(turn(tmp_path, "FAKE:not_logged_in"), credentials.dummy(), tmp_path / "out", 60)
    assert r.outcome == "auth_failed" and r.result["is_error"] is True and r.retries == []

def test_an_oversize_stream_line_is_marked_and_the_turn_ends_normally(tmp_path, monkeypatch):   # fix round 1, item 3
    monkeypatch.setattr(session, "STREAM_LINE_LIMIT", 64 * 1024)
    r = run_turn(turn(tmp_path, "FAKE:bigline=200000\nFAKE:reply=ok"), credentials.dummy(), tmp_path / "out", 60)
    assert r.outcome == "ok" and r.final_text == "ok"
    assert '"type": "bk_oversize_line"' in gzip.open(r.stream_path, "rt").read()
