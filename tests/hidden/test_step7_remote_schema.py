import json
import pytest
from .remote import served  # noqa: F401  (fixture)
from .theatre import build, read

CFG = ".troupe/troupe.yml"
SCHEMA = ".troupe/troupe.schema.json"
DEAD = "http://127.0.0.1:1"          # nothing listens: a fetch here fails, so success proves no fetch happened

@pytest.mark.steps(7)
def test_remote_yaml_and_text_includes_load(cli, tmp_theatre, served):
    base = served({"team.yaml": "model: opus\n", "prompt.md": "Be kind.\n"})
    build(tmp_theatre, {CFG: f"team: {base}/team.yaml\nprompt: {base}/prompt.md\n"})
    assert cli("get", "team.model", theatre=tmp_theatre).out == "opus\n"
    assert cli("get", "prompt", theatre=tmp_theatre).out == "Be kind.\n"

@pytest.mark.steps(7)
def test_failed_fetch_exits_4(cli, tmp_theatre, served):
    base = served({})
    build(tmp_theatre, {CFG: f"team: {base}/missing.yaml\n"})
    assert cli("get", "team.model", theatre=tmp_theatre).code == 4

@pytest.mark.steps(7)
def test_changing_a_remote_value_is_refused_naming_the_include(cli, tmp_theatre, served):
    base = served({"team.yaml": "model: opus\n"})
    files = {CFG: f"team: {base}/team.yaml\n"}
    build(tmp_theatre, files)
    r = cli("set", "team.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 3 and f"{base}/team.yaml" in r.err
    assert read(tmp_theatre, CFG) == files[CFG]

@pytest.mark.steps(7)
def test_new_key_under_remote_include_becomes_local_override(cli, tmp_theatre, served):
    base = served({"team.yaml": "model: opus\n"})
    build(tmp_theatre, {CFG: f"team: {base}/team.yaml\n"})
    assert cli("set", "team.temperature", "0.3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == f"team:\n  $include: {base}/team.yaml\n  temperature: 0.3\n"

@pytest.mark.steps(7)
def test_schema_format_uri_field_is_literal_and_not_fetched(cli, tmp_theatre):
    schema = {"type": "object", "properties": {"homepage": {"type": "string", "format": "uri"},
                                               "docs": {"type": "string", "format": "uri"}}}
    build(tmp_theatre, {CFG: f"homepage: {DEAD}/site.yaml\ndocs: file:missing.yaml\n", SCHEMA: json.dumps(schema)})
    r = cli("get", "homepage", theatre=tmp_theatre)
    assert (r.code, r.out) == (0, f"{DEAD}/site.yaml\n")
    r = cli("get", "docs", theatre=tmp_theatre)          # before step 7 this is an include of a missing file
    assert (r.code, r.out) == (0, "file:missing.yaml\n")

@pytest.mark.steps(7)
def test_literal_tag_is_literal_and_kept_on_set(cli, tmp_theatre):
    build(tmp_theatre, {CFG: f'docs: !literal "{DEAD}/a.yaml"  # c\n'})
    assert cli("get", "docs", theatre=tmp_theatre).out == f"{DEAD}/a.yaml\n"
    assert cli("set", "docs", json.dumps(f"{DEAD}/b.yaml"), theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == f'docs: !literal "{DEAD}/b.yaml"  # c\n'

@pytest.mark.steps(7)
def test_url_value_set_on_untyped_field_is_written_as_literal(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "x: old\n"})
    assert cli("set", "x", f"{DEAD}/z.yaml", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == f"x: !literal {DEAD}/z.yaml\n"
    assert cli("get", "x", theatre=tmp_theatre).out == f"{DEAD}/z.yaml\n"

@pytest.mark.steps(7)
def test_include_flag_writes_a_real_include(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "x: old\n", ".troupe/extra.yaml": "k: v\n"})
    assert cli("set", "--include", "x", "file:extra.yaml", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "x: file:extra.yaml\n"
    assert cli("get", "x.k", theatre=tmp_theatre).out == "v\n"

@pytest.mark.steps(7)
def test_config_invalid_against_schema_exits_4(cli, tmp_theatre):
    schema = {"type": "object", "properties": {"budget": {"type": "integer"}}}
    build(tmp_theatre, {CFG: "budget: lots\n", SCHEMA: json.dumps(schema)})
    assert cli("get", "budget", theatre=tmp_theatre).code == 4

@pytest.mark.steps(7)
def test_set_that_would_violate_schema_is_refused(cli, tmp_theatre):
    schema = {"type": "object", "properties": {"budget": {"type": "integer"}}}
    files = {CFG: "budget: 5\n", SCHEMA: json.dumps(schema)}
    build(tmp_theatre, files)
    assert cli("set", "budget", "lots", theatre=tmp_theatre).code == 3
    assert read(tmp_theatre, CFG) == files[CFG]
