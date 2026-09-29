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
