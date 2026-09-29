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
    assert parse_stream([INIT, j(type="result", subtype="success", is_error=True, result="API Error: 401")]).outcome == "is_error"

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
