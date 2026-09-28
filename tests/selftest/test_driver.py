import json, sys
from pathlib import Path
from tests.hidden.driver import Cli
from tests.hidden import theatre

FAKE = [sys.executable, str(Path(__file__).with_name("fake_troupe.py"))]

def test_theatre_goes_directly_after_subcommand(tmp_path):
    r = Cli(FAKE)("set", "a.b", "1", theatre=tmp_path)
    assert json.loads(r.out)["argv"] == ["config", "set", "--theatre", str(tmp_path), "a.b", "1"]

def test_exit_code_and_env_are_passed_through(tmp_path):
    r = Cli(FAKE)("show", "x", theatre=tmp_path, env={"FAKE_EXIT": "5", "TROUPE_ACTOR": "agent:a1"})
    assert r.code == 5
    assert json.loads(r.out)["actor"] == "agent:a1"

def test_build_writes_exact_bytes_including_crlf_and_no_final_newline(tmp_path):
    theatre.build(tmp_path, {".troupe/troupe.yml": "a: 1\r\nb: 2"})
    assert (tmp_path / ".troupe/troupe.yml").read_bytes() == b"a: 1\r\nb: 2"
    assert theatre.read(tmp_path, ".troupe/troupe.yml") == "a: 1\r\nb: 2"
