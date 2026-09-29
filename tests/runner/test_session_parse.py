import json
from pathlib import Path
import pytest
from runner import credentials
from runner.session import Turn, container_name, parse_stream, run_turn, stem

def j(**o): return json.dumps(o)

INIT = j(type="system", subtype="init", session_id="s1", model="claude-opus-5-5", claude_code_version="2.1.281")

def test_ok_needs_a_result_that_is_not_an_error():
    p = parse_stream([INIT, j(type="result", subtype="success", is_error=False, result="done",
                              total_cost_usd=0.5, usage={"output_tokens": 3}, modelUsage={"claude-opus-5-5": {}})])
    assert p.outcome == "ok" and p.final_text == "done" and p.session_id == "s1" and p.cost_usd == 0.5

def test_success_subtype_with_is_error_is_an_error():
    assert parse_stream([INIT, j(type="result", subtype="success", is_error=True, result="API Error: 500 internal error")]).outcome == "is_error"  # 401 is auth (fix round 1)

def test_missing_result_is_no_result():
    assert parse_stream([INIT]).outcome == "no_result"

def test_authentication_failed_retry_is_detected():
    p = parse_stream([INIT, j(type="system", subtype="api_retry", attempt=1, error="authentication_failed")])
    assert p.outcome == "auth_failed"

def test_parser_handles_a_200k_line():                              # renamed (review Q-11); the docker test covers the pipe
    big = j(type="assistant", message={"model": "claude-opus-5-5", "content": [{"type": "text", "text": "x" * 200_000}]})
    assert parse_stream([INIT, big]).outcome == "no_result"

def test_truncated_last_line_is_ignored_not_fatal():
    assert parse_stream([INIT, '{"type": "resu']).outcome == "no_result"

def test_permission_denials_are_kept_for_the_research_record():     # review F-8
    p = parse_stream([INIT, j(type="result", is_error=False, result="x",
                              permission_denials=[{"tool_name": "WebSearch"}])])
    assert p.result["permission_denials"] == [{"tool_name": "WebSearch"}]


def _turn(tmp_path: Path, role="arm", attempt=1, n=7) -> Turn:
    return Turn("t", "dryrun", 3, attempt, n, "img", "msg", {}, [], "none", False, "/work",
                tmp_path / "inbox" / role, role, True, None)

def test_stem_and_container_name_carry_role_attempt_and_turn():
    t = _turn(Path("/x"), role="po", attempt=2, n=7)
    assert stem(t) == "po-a2-007" and container_name(t) == "bk-t-dryrun-03-po-a2-007"

def test_credential_is_checked_before_anything_is_written(tmp_path):    # review C-14, no docker needed
    with pytest.raises(PermissionError):
        run_turn(_turn(tmp_path), credentials.Credential("real"), tmp_path / "out", 60)
    assert not (tmp_path / "inbox").exists() and not (tmp_path / "out").exists()


# --- Fix round 1 ------------------------------------------------------------------------------------------

import asyncio
from runner import session
from runner.session import AUTH_FAILURE_SHAPES, read_lines

@pytest.mark.parametrize("text", [
    "Not logged in · Please run /login",                                  # spike FINDINGS Evidence 2 (verbatim)
    "Failed to authenticate. API Error: 401 API key is invalid.",         # spike FINDINGS Q3 (verbatim)
    "  Not logged in · Please run /login\n",                              # surrounding whitespace is stripped
])
def test_claude_codes_own_auth_message_on_a_turn_that_did_no_work_is_auth_failed(text):   # fix rounds 1+2
    p = parse_stream([INIT, j(type="result", subtype="success", is_error=True, result=text, total_cost_usd=0)])
    assert p.outcome == "auth_failed"

def test_every_listed_prefix_is_recognised_at_the_start():
    for shape in AUTH_FAILURE_SHAPES:
        assert parse_stream([INIT, j(type="result", is_error=True, result=f"{shape} y")]).outcome == "auth_failed"

@pytest.mark.parametrize("text", [                                   # fix round 2: the reviewer's false positives
    "the mock server returned API Error: 401 because the fixture key was wrong",
    "Tests fail with authentication_error from the stubbed client",
    "I could not finish: the test config sends an invalid x-api-key",
    "Blocked: step 3 Failed to authenticate against the local fixture server",
])
def test_an_arm_failure_that_merely_mentions_auth_stays_is_error(text):
    assert parse_stream([INIT, j(type="result", is_error=True, result=text)]).outcome == "is_error"

TOOL_USE = j(type="assistant", message={"model": "claude-opus-5-5", "content": [
    {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "uv run pytest"}}]})

def test_an_auth_message_after_tool_use_work_is_the_arms_error():          # fix round 2
    p = parse_stream([INIT, TOOL_USE, j(type="result", is_error=True, result="Failed to authenticate. API Error: 401")])
    assert p.outcome == "is_error"

def test_an_auth_message_on_a_turn_that_cost_money_is_the_arms_error():   # fix round 2
    p = parse_stream([INIT, j(type="result", is_error=True, result="Not logged in · Please run /login",
                              total_cost_usd=0.12)])
    assert p.outcome == "is_error"

def test_an_ordinary_error_result_stays_is_error():
    assert parse_stream([INIT, j(type="result", is_error=True, result="API Error: 529 overloaded")]).outcome == "is_error"

def test_auth_words_in_a_successful_reply_do_not_make_it_a_fault():
    p = parse_stream([INIT, j(type="result", is_error=False, result="I fixed the 'Not logged in' message")])
    assert p.outcome == "ok"

FIXTURE = Path(__file__).parent / "fixtures" / "stream-authenticated-shape.jsonl"

def test_a_realistic_authenticated_stream_parses_to_its_result():          # fix round 1, item 6
    # Shape of the owner's authenticated run (FINDINGS addendum: init -> assistant(thinking, tool_use) ->
    # rate_limit_event -> user tool_result -> assistant -> result, $0.0298). The spike did not save that
    # stream, so the event bodies are reconstructed from Claude Code's stream-json shape, ids scrubbed.
    p = parse_stream(FIXTURE.read_text().splitlines())
    assert p.outcome == "ok" and p.final_text == "Done."
    assert p.session_id == "00000000-0000-4000-8000-000000000000"
    assert p.init["model"] == "claude-opus-5-5" and p.init["claude_code_version"] == "2.1.281"
    assert p.cost_usd == 0.0298 and p.retries == []
    assert p.result["num_turns"] == 2 and p.result["duration_ms"] == 8123 and p.result["duration_api_ms"] == 7011
    assert p.result["usage"]["output_tokens"] == 66
    assert list(p.result["modelUsage"]) == ["claude-opus-5-5"]


def _lines(data: bytes, limit: int) -> list[bytes]:
    async def go():
        r = asyncio.StreamReader(limit=limit)
        r.feed_data(data); r.feed_eof()
        return [l async for l in read_lines(r)]
    return asyncio.run(go())

def test_an_oversize_line_becomes_a_marker_and_reading_continues():       # fix round 1, item 3
    got = _lines(b'{"a":1}\n' + b"x" * 1000 + b'\n{"b":2}\n{"c":', limit=64)
    assert got[0] == b'{"a":1}\n'
    assert json.loads(got[1]) == {"type": "bk_oversize_line", "bytes": 1001}
    assert got[2:] == [b'{"b":2}\n', b'{"c":']                          # the truncated tail is still delivered

def test_an_oversize_line_at_eof_without_newline_is_a_marker():
    got = _lines(b'{"a":1}\n' + b"x" * 1000, limit=64)
    assert got[0] == b'{"a":1}\n' and json.loads(got[1]) == {"type": "bk_oversize_line", "bytes": 1000}
    assert len(got) == 2

def test_the_marker_does_not_disturb_the_outcome():
    marker = json.dumps({"type": "bk_oversize_line", "bytes": 10})
    assert parse_stream([INIT, marker, j(type="result", is_error=False, result="ok")]).outcome == "ok"
