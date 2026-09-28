import pytest
from .theatre import build

CFG = ".troupe/troupe.yml"

def show(cli, t, path):
    return cli("show", path, theatre=t)

@pytest.mark.steps(1)
@pytest.mark.parametrize("yaml_value, printed", [
    ("demo", "demo\n"), ('"quoted"', "quoted\n"), ("42", "42\n"), ("0.2", "0.2\n"),
    ("true", "true\n"), ("null", "null\n"), ("yes", "yes\n"),   # YAML 1.2: `yes` is a string
])
def test_show_prints_scalars_per_contract(cli, tmp_theatre, yaml_value, printed):
    build(tmp_theatre, {CFG: f"v: {yaml_value}\n"})
    r = show(cli, tmp_theatre, "v")
    assert (r.code, r.out) == (0, printed)

@pytest.mark.steps(1)
def test_show_nested_path_and_list_index(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "agents:\n  coder:\n    tools:\n      - bash\n      - edit\n"})
    assert show(cli, tmp_theatre, "agents.coder.tools.1").out == "edit\n"

@pytest.mark.steps(1)
def test_troupe_yaml_extension_is_accepted(cli, tmp_theatre):
    build(tmp_theatre, {".troupe/troupe.yaml": "v: 1\n"})
    assert show(cli, tmp_theatre, "v").out == "1\n"

@pytest.mark.steps(1)
def test_yaml_include_is_embedded_recursively_relative_to_including_file(cli, tmp_theatre):
    build(tmp_theatre, {
        CFG: "agents:\n  coder: file:agents/coder.yaml\n",
        ".troupe/agents/coder.yaml": "model: opus\nlimits: file:limits.yml\n",
        ".troupe/agents/limits.yml": "max_tokens: 8000\n",
    })
    assert show(cli, tmp_theatre, "agents.coder.model").out == "opus\n"
    assert show(cli, tmp_theatre, "agents.coder.limits.max_tokens").out == "8000\n"

@pytest.mark.steps(1)
def test_text_include_value_is_the_exact_file_text(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:prompts/p.md\n", ".troupe/prompts/p.md": "# Coder\n\nWrite tests.\n"})
    assert show(cli, tmp_theatre, "prompt").out == "# Coder\n\nWrite tests.\n"

@pytest.mark.steps(1)
def test_text_include_without_final_newline_gets_one_when_printed(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.txt\n", ".troupe/p.txt": "one line"})
    assert show(cli, tmp_theatre, "prompt").out == "one line\n"

@pytest.mark.steps(1)
@pytest.mark.parametrize("files", [
    {},                                                   # no config file
    {CFG: "a: 1\n", ".troupe/troupe.yaml": "a: 2\n"},     # both config files
    {CFG: "a: [1, 2\n"},                                  # invalid YAML
    {CFG: "a: file:missing.yaml\n"},                      # missing include
    {CFG: "a: file:x.yaml\n", ".troupe/x.yaml": "b: file:troupe.yml\n"},  # include cycle
], ids=["none", "both", "invalid", "missing-include", "cycle"])
def test_unloadable_configuration_exits_4_with_empty_stdout(cli, tmp_theatre, files):
    build(tmp_theatre, files)
    (tmp_theatre / ".troupe").mkdir(exist_ok=True)
    r = show(cli, tmp_theatre, "a")
    assert r.code == 4 and r.out == "" and r.err.strip()

@pytest.mark.steps(1)
def test_missing_include_error_names_the_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: file:missing.yaml\n"})
    assert "missing.yaml" in show(cli, tmp_theatre, "a").err

@pytest.mark.steps(1)
def test_unknown_path_exits_5_and_names_the_path(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    r = show(cli, tmp_theatre, "nope.deeper")
    assert (r.code, r.out) == (5, "") and "nope.deeper" in r.err

@pytest.mark.steps(1, 2)
def test_show_on_a_mapping_exits_5_before_step_3(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a:\n  b: 1\n"})
    r = show(cli, tmp_theatre, "a")
    assert (r.code, r.out) == (5, "")
