import pytest
from runner import config


def test_pins_pin_claude_code_and_the_model():
    p = config.load_pins()
    assert p.claude_version == "2.1.281"
    assert p.model == "claude-opus-5-5"
    assert p.accepted_models == ["claude-opus-5-5"]


def test_web_tools_and_ask_user_question_are_disallowed_for_every_session():
    assert set(config.load_pins().disallowed_tools) >= {"WebSearch", "WebFetch", "AskUserQuestion"}


def test_beads_native_binary_is_pinned_by_a_real_sha256():                 # review fix-round-1 item 1
    assert len(config.load_pins().bd_sha256) == 64


def test_od_parameters_have_their_recommended_defaults():
    p = config.load_pins()
    assert p.pass2_order == "reverse"                      # OD13 B
    assert p.plugin_route == "plugin-dir"                  # OD9 B
    assert (p.limits.turn_seconds, p.limits.exchanges_per_attempt) == (28800, 250)   # OD14 B
    assert p.limits.owner_reclassifies_first_breach is True
    assert p.limits.mutation_sample == 200                 # OD15 B


def test_control_arm_loads_with_plain_entry():
    a = config.load_arm("control")
    assert a.entry == "{handoff}" and a.tracker == "github" and a.must_run == [] and a.smoke is None


def test_unknown_key_in_arm_file_is_rejected(tmp_path, monkeypatch):
    (tmp_path / "x.toml").write_text('name="x"\nsurprise=1\n')
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)
    with pytest.raises(config.ConfigError, match="surprise"):
        config.load_arm("x")


def test_smoke_table_is_accepted_from_the_start(tmp_path, monkeypatch):     # review Q-5
    text = (config.ARMS_DIR / "control.toml").read_text().replace(
        '[setup]\n', '[setup]\nsmoke = { prompt = "p", expect_skill = "s" }\n', 1)
    (tmp_path / "control.toml").write_text(text)
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)
    assert config.load_arm("control").smoke == config.Smoke("p", "s")


def test_arm_cannot_widen_the_run_allowlist_with_an_unanchored_pattern(tmp_path, monkeypatch):
    text = (config.ARMS_DIR / "control.toml").read_text().replace(
        "run = ['^api\\.github\\.com$']", "run = ['api.github.com']")
    assert "run = ['api.github.com']" in text
    (tmp_path / "control.toml").write_text(text)
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)
    with pytest.raises(config.ConfigError, match="anchored"):
        config.load_arm("control")


def test_must_run_needs_a_citation(tmp_path, monkeypatch):                  # review F-5
    text = (config.ARMS_DIR / "control.toml").read_text().replace('must_run = []', 'must_run = ["/x"]').replace(
        'must_run_source = "no methodology: no closing command"', 'must_run_source = ""')
    (tmp_path / "control.toml").write_text(text)
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)
    with pytest.raises(config.ConfigError, match="must_run_source"):
        config.load_arm("control")


# ---- Task 22 ruling 6: per-arm spec paths (the N.a discovery stop) ------------------------------------------------

@pytest.mark.parametrize("name", list(config.REAL_ARMS) + ["dryrun"])
def test_every_arm_names_its_spec_paths_each_with_a_reason(name):
    a = config.load_arm(name)
    assert a.spec_paths and all(s.path and s.why.strip() for s in a.spec_paths)


def test_the_method_arms_spec_paths_are_their_own_artefact_folders():
    got = {n: {s.path for s in config.load_arm(n).spec_paths} for n in config.REAL_ARMS}
    assert "openspec/" in got["openspec"] and "specs/" in got["speckit"] and ".kiro/" in got["ccsdd"]
    assert "kitty-specs/" in got["speckitty"] and "_bmad-output/" in got["bmad"]
    assert "docs/superpowers/" in got["superpowers"]


def test_a_spec_path_without_a_reason_is_refused(tmp_path, monkeypatch):
    import re
    src = (config.ARMS_DIR / "control.toml").read_text()
    (tmp_path / "control.toml").write_text(re.sub(r'why = "[^"]*"', 'why = " "', src))
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)
    with pytest.raises(config.ConfigError, match="why"):
        config.load_arm("control")


def test_the_common_docs_paths_are_pinned_once_each_with_a_reason():
    ps = config.load_pins().discovery_paths
    assert {"docs/", "*.md"} <= {s.path for s in ps} and all(s.why.strip() for s in ps)


# ---- Task 23: parked arms (owner: bmad stays parked until BMAD 6.13) -------------------------------------------

def test_bmad_is_parked_and_every_other_real_arm_is_active():
    assert config.load_arm("bmad").parked is True
    assert config.active_arms() == [a for a in config.all_arms() if a != "bmad"]
    assert "bmad" in config.all_arms()                        # the full set stays for checklists


def test_parked_is_a_boolean_and_defaults_to_false(tmp_path, monkeypatch):
    assert config.load_arm("control").parked is False
    (tmp_path / "control.toml").write_text(
        (config.ARMS_DIR / "control.toml").read_text().replace('env = {}', 'parked = "yes"\nenv = {}', 1))
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)
    with pytest.raises(config.ConfigError, match="parked"):
        config.load_arm("control")
