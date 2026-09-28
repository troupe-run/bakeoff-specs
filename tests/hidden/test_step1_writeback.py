import json
import pytest
from .theatre import build, read
from .writeback_corpus import CASES

CFG = ".troupe/troupe.yml"

def arg(value) -> str:
    # JSON is valid YAML flow syntax, so this passes exact values (types, newlines) through the contract's parser.
    # ensure_ascii=False: YAML 1.2 has no surrogate-pair rule, so an astral character (e.g. an emoji) must be
    # passed literally, not as JSON's "🎭" escape pair (a YAML parser reads that as two lone surrogates).
    return json.dumps(value, ensure_ascii=False)

@pytest.mark.steps(1)
@pytest.mark.parametrize("c", CASES, ids=[c.name for c in CASES])
def test_writeback_is_byte_surgical(cli, tmp_theatre, c):
    build(tmp_theatre, {CFG: c.before})
    codes = [cli("set", path, arg(value), theatre=tmp_theatre).code for path, value in c.ops]
    expected_code = {"error": 3, "path": 5}.get(c.expect, 0)
    assert codes == [0] * (len(codes) - 1) + [expected_code], codes
    assert read(tmp_theatre, CFG) == c.after

@pytest.mark.steps(1)
def test_text_include_set_replaces_target_text_exactly(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md  # c\n", ".troupe/p.md": "one\ntwo\n"})
    assert cli("set", "prompt", arg("one\n2\nthree\n"), theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/p.md") == "one\n2\nthree\n"
    assert read(tmp_theatre, CFG) == "prompt: file:p.md  # c\n"

@pytest.mark.steps(1)
def test_text_include_set_keeps_the_target_files_crlf_line_endings(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md\n", ".troupe/p.md": "one\r\ntwo\r\n"})
    assert cli("set", "prompt", arg("one\n2\n"), theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/p.md") == "one\r\n2\r\n"
    assert read(tmp_theatre, CFG) == "prompt: file:p.md\n"

@pytest.mark.steps(1)
def test_text_include_rejects_non_string(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md\n", ".troupe/p.md": "x\n"})
    r = cli("set", "prompt", "5", theatre=tmp_theatre)
    assert r.code == 3 and read(tmp_theatre, ".troupe/p.md") == "x\n"

@pytest.mark.steps(1)
def test_value_in_nested_include_is_written_to_that_file_only(cli, tmp_theatre):
    files = {CFG: "agents:\n  coder: file:agents/coder.yaml  # the coder\n",
             ".troupe/agents/coder.yaml": "model: 'opus'  # quoted\nlimits: file:limits.yaml\n",
             ".troupe/agents/limits.yaml": "max_tokens: 8000  # cap\n"}
    build(tmp_theatre, files)
    assert cli("set", "agents.coder.limits.max_tokens", "16000", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/agents/limits.yaml") == "max_tokens: 16000 # cap\n"
    for rel in (CFG, ".troupe/agents/coder.yaml"):
        assert read(tmp_theatre, rel) == files[rel]

@pytest.mark.steps(1, 4)   # step 5 changes where new keys go
def test_new_key_goes_to_file_of_deepest_existing_ancestor(cli, tmp_theatre):
    files = {CFG: "agents:\n  coder: file:agents/coder.yaml\n", ".troupe/agents/coder.yaml": "model: opus\n"}
    build(tmp_theatre, files)
    assert cli("set", "agents.coder.budget.daily_usd", "5", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/agents/coder.yaml") == "model: opus\nbudget:\n  daily_usd: 5\n"
    assert read(tmp_theatre, CFG) == files[CFG]

@pytest.mark.steps(1)
def test_replacing_a_whole_include_is_refused(cli, tmp_theatre):
    files = {CFG: "coder: file:coder.yaml\n", ".troupe/coder.yaml": "model: opus\n"}
    build(tmp_theatre, files)
    r = cli("set", "coder", "flat", theatre=tmp_theatre)
    assert r.code == 3 and read(tmp_theatre, CFG) == files[CFG]

@pytest.mark.steps(1)
def test_set_persists_and_show_reflects_it(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    cli("set", "a", "2", theatre=tmp_theatre)
    assert cli("show", "a", theatre=tmp_theatre).out == "2\n"
