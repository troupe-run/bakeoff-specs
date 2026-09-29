# tests/runner/test_commands_docker.py — the listing runs in the container and sees vendored plugins
import json
import pytest
from runner import commands, config, docker, repo
from runner.paths import Paths

pytestmark = pytest.mark.docker


@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    assert not docker.running("bakeoff.run=dry9/dryrun")


def test_listing_sees_project_commands_skills_and_frontmatter_models(tmp_state):
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    (p.repo / ".claude/commands/opsx").mkdir(parents=True); (p.repo / ".claude/commands/opsx/propose.md").write_text("x")
    (p.repo / ".claude/skills/speckit-plan").mkdir(parents=True)
    (p.repo / ".claude/skills/speckit-plan/SKILL.md").write_text("---\nname: speckit-plan\nmodel: haiku\n---\nbody")
    l = commands.listing(p, config.load_arm("dryrun"))
    assert {"opsx:propose", "speckit-plan"} <= l.names
    assert {"file": ".claude/skills/speckit-plan/SKILL.md", "model": "haiku"} in l.models


def _plugin(root, name, skill, agent_model=None):
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}))
    (root / "skills" / skill).mkdir(parents=True)
    (root / "skills" / skill / "SKILL.md").write_text(f"---\nname: {skill}\n---\n")
    if agent_model:
        (root / "agents").mkdir()
        (root / "agents" / "reviewer.md").write_text(f"---\nmodel: {agent_model}\n---\n")


def test_listing_sees_only_installed_route_a_plugins_and_their_model_settings(tmp_state):   # FR1 item 6
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    plugins = p.config_dir / "plugins"
    _plugin(plugins / "cache" / "mkt" / "sp" / "1.0", "sp", "brainstorming", "claude-sonnet-4-5-20250929")
    _plugin(plugins / "cache" / "mkt" / "sp" / "0.9", "sp", "stale-skill", "claude-haiku-3")   # stale cache
    _plugin(plugins / "marketplaces" / "mkt" / "other", "other", "not-installed")             # catalogue only
    (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
        "sp@mkt": [{"scope": "user", "installPath": "/home/actor/.claude/plugins/cache/mkt/sp/1.0", "version": "1.0"}]}}))
    l = commands.listing(p, config.load_arm("dryrun"))
    assert {"sp:brainstorming", "brainstorming"} <= l.names
    assert not {"stale-skill", "sp:stale-skill", "not-installed", "other:not-installed"} & l.names
    assert [m["model"] for m in l.models] == ["claude-sonnet-4-5-20250929"]


def test_a_plugin_disabled_in_user_settings_is_not_listed(tmp_state):
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    plugins = p.config_dir / "plugins"
    _plugin(plugins / "cache" / "mkt" / "sp" / "1.0", "sp", "brainstorming")
    (plugins / "installed_plugins.json").write_text(json.dumps({"version": 1, "plugins": {
        "sp@mkt": {"installPath": "/home/actor/.claude/plugins/cache/mkt/sp/1.0"}}}))
    (p.config_dir / "settings.json").write_text(json.dumps({"enabledPlugins": {"sp@mkt": False}}))
    assert "brainstorming" not in commands.listing(p, config.load_arm("dryrun")).names


def test_listing_reports_user_scope_and_settings_model_choices(tmp_state):                  # FR1 item 5
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    (p.config_dir / "agents").mkdir()
    (p.config_dir / "agents" / "helper.md").write_text("---\nmodel: claude-sonnet-4-5-20250929\n---\n")
    (p.config_dir / "commands").mkdir()
    (p.config_dir / "commands" / "go.md").write_text("---\nmodel: opus\n---\n")
    (p.config_dir / "settings.json").write_text(json.dumps(
        {"model": "claude-3-7-sonnet", "env": {"ANTHROPIC_MODEL": "claude-x", "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-y",
                                              "UNRELATED": "claude-z"}}))
    (p.repo / ".claude").mkdir()
    (p.repo / ".claude" / "settings.local.json").write_text(json.dumps({"env": {"CLAUDE_CODE_SUBAGENT_MODEL": "haiku"}}))
    l = commands.listing(p, config.load_arm("dryrun"))
    got = {(m["file"], m["model"]) for m in l.models}
    assert {("~/.claude/agents/helper.md", "claude-sonnet-4-5-20250929"), ("~/.claude/commands/go.md", "opus"),
            ("~/.claude/settings.json#model", "claude-3-7-sonnet"),
            ("~/.claude/settings.json#env.ANTHROPIC_MODEL", "claude-x"),
            ("~/.claude/settings.json#env.ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-y"),
            (".claude/settings.local.json#env.CLAUDE_CODE_SUBAGENT_MODEL", "haiku")} <= got
    assert not any("UNRELATED" in f for f, _ in got) and "go" in l.names
