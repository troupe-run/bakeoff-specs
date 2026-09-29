# tests/runner/test_commands_docker.py — the listing runs in the container and sees vendored plugins
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


def test_listing_sees_route_a_plugins_in_the_config_dir_and_their_model_settings(tmp_state):
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    root = p.config_dir / "plugins" / "cache" / "mkt" / "sp" / "1.0"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text('{"name": "sp"}')
    (root / "skills" / "brainstorming").mkdir(parents=True)
    (root / "skills" / "brainstorming" / "SKILL.md").write_text("---\nname: brainstorming\n---\n")
    (root / "agents").mkdir()
    (root / "agents" / "reviewer.md").write_text("---\nmodel: claude-sonnet-4-5-20250929\n---\n")
    l = commands.listing(p, config.load_arm("dryrun"))
    assert {"sp:brainstorming", "brainstorming"} <= l.names
    assert any(m["model"] == "claude-sonnet-4-5-20250929" and m["file"].endswith("agents/reviewer.md") for m in l.models)
