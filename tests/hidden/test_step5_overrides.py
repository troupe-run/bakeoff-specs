# tests/hidden/test_step5_overrides.py
import pytest
from .history import events
from .theatre import build, read

CFG = ".troupe/troupe.yml"
CODER = ".troupe/agents/coder.yaml"
SHARED = {CFG: "agents:\n  coder: file:agents/coder.yaml  # the coder\n",
          CODER: "model: opus  # m\nlimits:\n  max_tokens: 8000\n"}

@pytest.mark.steps(5)
def test_new_key_under_include_becomes_override_in_including_file(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "agents.coder.temperature", "0.3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == ("agents:\n  coder:  # the coder\n"
                                     "    $include: file:agents/coder.yaml\n    temperature: 0.3\n")
    assert read(tmp_theatre, CODER) == SHARED[CODER]
    assert cli("get", "agents.coder.temperature", theatre=tmp_theatre).out == "0.3\n"
    assert cli("get", "agents.coder.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(5)
def test_nested_new_key_is_a_deep_merged_override(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "agents.coder.limits.max_retries", "3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == ("agents:\n  coder:  # the coder\n    $include: file:agents/coder.yaml\n"
                                     "    limits:\n      max_retries: 3\n")
    assert cli("get", "agents.coder.limits.max_tokens", theatre=tmp_theatre).out == "8000\n"
    assert cli("get", "agents.coder.limits.max_retries", theatre=tmp_theatre).out == "3\n"

@pytest.mark.steps(5)
def test_second_override_is_added_to_existing_mapping_form(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "coder:\n  $include: file:coder.yaml\n  temperature: 0.3\n",
                        ".troupe/coder.yaml": "model: opus\n"})
    assert cli("set", "coder.top_p", "0.9", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "coder:\n  $include: file:coder.yaml\n  temperature: 0.3\n  top_p: 0.9\n"
    assert cli("get", "coder.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(5)
def test_existing_value_not_overridden_still_changes_in_its_own_file(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "agents.coder.model", "sonnet", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CODER) == "model: sonnet # m\nlimits:\n  max_tokens: 8000\n"
    assert read(tmp_theatre, CFG) == SHARED[CFG]

@pytest.mark.steps(5)
def test_existing_overridden_value_changes_the_override(cli, tmp_theatre):
    files = {CFG: "coder:\n  $include: file:coder.yaml\n  model: sonnet\n",
             ".troupe/coder.yaml": "model: opus\neffort: high\n"}
    build(tmp_theatre, files)
    assert cli("get", "coder.model", theatre=tmp_theatre).out == "sonnet\n"
    assert cli("get", "coder.effort", theatre=tmp_theatre).out == "high\n"
    assert cli("set", "coder.model", "haiku", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "coder:\n  $include: file:coder.yaml\n  model: haiku\n"
    assert read(tmp_theatre, ".troupe/coder.yaml") == "model: opus\neffort: high\n"
    assert cli("get", "coder.effort", theatre=tmp_theatre).out == "high\n"

@pytest.mark.steps(5)
def test_in_include_flag_writes_new_key_into_the_shared_file(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    assert cli("set", "--in-include", "agents.coder.temperature", "0.3", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CODER) == "model: opus  # m\nlimits:\n  max_tokens: 8000\ntemperature: 0.3\n"
    assert read(tmp_theatre, CFG) == SHARED[CFG]

@pytest.mark.steps(5)
def test_override_lists_and_scalars_replace_mappings_merge(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "c:\n  $include: file:c.yaml\n  tools: [read]\n  limits:\n    b: 20\n",
                        ".troupe/c.yaml": "tools: [bash, edit]\nlimits:\n  a: 1\n  b: 2\n"})
    assert cli("get", "c.tools.0", theatre=tmp_theatre).out == "read\n"
    assert cli("get", "c.tools.1", theatre=tmp_theatre).code == 5
    assert cli("get", "c.limits.a", theatre=tmp_theatre).out == "1\n"
    assert cli("get", "c.limits.b", theatre=tmp_theatre).out == "20\n"

@pytest.mark.steps(5)
def test_show_sources_attributes_overrides_to_the_including_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "c:\n  $include: file:c.yaml\n  model: sonnet\n", ".troupe/c.yaml": "model: opus\nx: 1\n"})
    lines = cli("show", "c", "--sources", theatre=tmp_theatre).out.splitlines()
    assert next(l for l in lines if l.strip().startswith("model:")).endswith("# from .troupe/troupe.yml")
    assert next(l for l in lines if l.strip().startswith("x:")).endswith("# from .troupe/c.yaml")

@pytest.mark.steps(5)
def test_override_events_carry_lineage(cli, tmp_theatre):
    build(tmp_theatre, SHARED)
    cli("set", "agents.coder.temperature", "0.3", theatre=tmp_theatre, env={"TROUPE_ACTOR": "agent:po"})
    e = [e for e in events(cli, tmp_theatre) if e["op"] == "set"][-1]
    assert (e["path"], e["new"], e["via"], e["actor"]) == ("agents.coder.temperature", 0.3, "cli",
                                                           {"kind": "agent", "id": "po"})
    assert read(tmp_theatre, CFG) == ("agents:\n  coder:  # the coder\n"
                                     "    $include: file:agents/coder.yaml\n    temperature: 0.3\n")
    assert read(tmp_theatre, CODER) == SHARED[CODER]

@pytest.mark.steps(5)
def test_appending_to_an_included_list_is_not_an_override(cli, tmp_theatre):
    files = {CFG: "c: file:c.yaml\n", ".troupe/c.yaml": "tools: [a, b]\n"}
    build(tmp_theatre, files)
    assert cli("set", "c.tools.2", "z", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/c.yaml") == "tools: [a, b, z]\n"
    assert read(tmp_theatre, CFG) == files[CFG]
    assert cli("get", "c.tools.0", theatre=tmp_theatre).out == "a\n"

@pytest.mark.steps(5)
def test_overrides_on_a_text_include_cannot_be_loaded(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "c:\n  $include: file:c.txt\n  x: 1\n", ".troupe/c.txt": "hello\n"})
    assert cli("get", "c.x", theatre=tmp_theatre).code == 4

@pytest.mark.steps(5)
def test_new_key_inside_an_included_list_item_is_written_in_the_file_holding_the_list(cli, tmp_theatre):
    files = {CFG: "c: file:c.yaml\n", ".troupe/c.yaml": "tools:\n  - model: a\n  - model: b\n"}
    build(tmp_theatre, files)
    assert cli("set", "c.tools.0.name", "val", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, ".troupe/c.yaml") == "tools:\n  - model: a\n    name: val\n  - model: b\n"
    assert read(tmp_theatre, CFG) == files[CFG]
    assert cli("get", "c.tools.1.model", theatre=tmp_theatre).out == "b\n"
