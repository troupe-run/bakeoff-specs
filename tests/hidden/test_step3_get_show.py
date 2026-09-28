import pytest
from . import yaml12
from .theatre import build

CFG = ".troupe/troupe.yml"
FILES = {CFG: "name: demo\nagents:\n  coder: file:agents/coder.yaml\n",
         ".troupe/agents/coder.yaml": "model: opus\ntools:\n  - bash\n  - edit\nprompt: file:p.md\n",
         ".troupe/agents/p.md": "Write tests.\nKeep it simple.\n"}
MERGED = {"name": "demo", "agents": {"coder": {"model": "opus", "tools": ["bash", "edit"],
                                               "prompt": "Write tests.\nKeep it simple.\n"}}}

@pytest.mark.steps(3)
@pytest.mark.parametrize("yaml_value, printed", [
    ("demo", "demo\n"), ("42", "42\n"), ("0.2", "0.2\n"), ("true", "true\n"), ("null", "null\n")])
def test_get_prints_scalars_as_show_used_to(cli, tmp_theatre, yaml_value, printed):
    build(tmp_theatre, {CFG: f"v: {yaml_value}\n"})
    assert cli("get", "v", theatre=tmp_theatre).out == printed

@pytest.mark.steps(3)
def test_get_follows_includes(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert cli("get", "agents.coder.tools.1", theatre=tmp_theatre).out == "edit\n"
    assert cli("get", "agents.coder.prompt", theatre=tmp_theatre).out == "Write tests.\nKeep it simple.\n"

@pytest.mark.steps(3)
def test_get_on_a_section_exits_5_and_points_at_show(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    r = cli("get", "agents.coder", theatre=tmp_theatre)
    assert (r.code, r.out) == (5, "") and "config show" in r.err

@pytest.mark.steps(3)
def test_show_on_a_scalar_still_prints_the_value(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert cli("show", "name", theatre=tmp_theatre).out == "demo\n"

@pytest.mark.steps(3)
def test_show_on_a_section_prints_merged_yaml(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    r = cli("show", "agents.coder", theatre=tmp_theatre)
    assert r.code == 0 and yaml12.load(r.out) == MERGED["agents"]["coder"]

@pytest.mark.steps(3)
def test_show_prints_text_includes_as_literal_blocks(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    out = cli("show", "agents.coder", theatre=tmp_theatre).out
    assert "prompt: |" in out

@pytest.mark.steps(3)
def test_show_without_a_path_prints_everything(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert yaml12.load(cli("show", theatre=tmp_theatre).out) == MERGED

@pytest.mark.steps(3)
def test_show_sources_names_the_file_of_every_scalar(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    r = cli("show", "--sources", theatre=tmp_theatre)
    assert r.code == 0 and yaml12.load(r.out) == MERGED     # comments do not change the data
    lines = r.out.splitlines()
    def line_for(prefix):
        return next(l for l in lines if l.strip().startswith(prefix))
    assert line_for("name:").endswith("# from .troupe/troupe.yml")
    assert line_for("model:").endswith("# from .troupe/agents/coder.yaml")
    assert line_for("- bash").endswith("# from .troupe/agents/coder.yaml")
    assert line_for("prompt:").endswith("# from .troupe/agents/p.md")

@pytest.mark.steps(3)
def test_show_unknown_path_exits_5(cli, tmp_theatre):
    build(tmp_theatre, FILES)
    assert cli("show", "agents.nobody", theatre=tmp_theatre).code == 5

# Regression fixture for fix round 1: a single-line string past ruamel's default ~80-column wrap
# width (a plain YAML scalar that long silently folds onto continuation lines unless the dumper is
# told not to wrap), an empty list, an empty mapping, and the string "yes" (a YAML 1.1 boolean but
# a plain YAML 1.2 string — the contract is 1.2, so `yaml12.load`, not `yaml.safe_load`, must be
# used to judge it).
LONG = " ".join(["word"] * 40)  # 199 chars
EDGE_FILES = {CFG: (
    f"long: {LONG}\n"
    "empty_list: []\n"
    "empty_map: {}\n"
    "flag: yes\n"
)}
EDGE_MERGED = {"long": LONG, "empty_list": [], "empty_map": {}, "flag": "yes"}

@pytest.mark.steps(3)
def test_show_handles_long_scalars_empty_collections_and_yaml12_strings(cli, tmp_theatre):
    build(tmp_theatre, EDGE_FILES)
    assert yaml12.load(cli("show", theatre=tmp_theatre).out) == EDGE_MERGED
    assert yaml12.load(cli("show", "--sources", theatre=tmp_theatre).out) == EDGE_MERGED
