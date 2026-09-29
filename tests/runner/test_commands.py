# tests/runner/test_commands.py
from runner import commands

INSTALLED = {"opsx:propose", "opsx:apply", "speckit-plan", "superpowers:brainstorming", "brainstorming",
             "bmad-create-architecture", "bmad-method:bmad-create-architecture"}

def test_leading_command_is_the_first_token_only():
    assert commands.leading("/speckit-plan now please") == "/speckit-plan"
    assert commands.leading("please run /x") is None

def test_invocation_accepts_slash_commands_and_bare_skill_names():            # review F-2
    assert commands.invocation("/opsx:apply", "", INSTALLED) == "/opsx:apply"
    assert commands.invocation("opsx:apply", "change-1", INSTALLED) == "/opsx:apply change-1"
    assert commands.invocation("bmad-create-architecture", "", INSTALLED) == "/bmad-create-architecture"
    assert commands.invocation("superpowers:brainstorming", "", INSTALLED) == "/superpowers:brainstorming"

def test_invocation_of_something_not_installed_is_none():
    assert commands.invocation("/opsx:frobnicate", "", INSTALLED) is None

def test_listing_output_is_parsed():
    l = commands.parse_listing('{"names": ["a", "b"], "models": [{"file": "agents/x.md", "model": "haiku"}]}')
    assert l.names == {"a", "b"} and l.models == [{"file": "agents/x.md", "model": "haiku"}]


# --- beyond the plan text ------------------------------------------------------------------------------
def test_listing_runs_in_a_network_less_container_with_read_only_mounts(tmp_state, monkeypatch):
    """The host never walks arm-controlled trees (review F-6): the listing is a container, mounts read-only."""
    import subprocess
    from runner import config, docker
    from runner.paths import Paths
    p = Paths("dry9", "dryrun"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)
    got = []
    monkeypatch.setattr(docker, "run", lambda s, **k: got.append(s) or subprocess.CompletedProcess(
        s.cmd, 0, b'{"names": ["x"], "models": []}', b""))
    assert commands.listing(p, config.load_arm("dryrun")).names == {"x"}
    s = got[0]
    assert s.network == "none" and not s.proxy and all(m.ro for m in s.mounts)
    assert s.cmd[:2] == ["python3", "-c"] and s.cmd[3] == p.container_repo


def test_listing_container_names_are_unique(tmp_state, monkeypatch):           # preflight m13
    import subprocess
    from runner import config, docker
    from runner.paths import Paths
    p = Paths("dry9", "dryrun"); p.config_dir.mkdir(parents=True); p.repo.mkdir(parents=True)
    names = []
    monkeypatch.setattr(docker, "run", lambda s, **k: names.append(s.name) or subprocess.CompletedProcess(
        s.cmd, 0, b'{"names": [], "models": []}', b""))
    commands.listing(p, config.load_arm("dryrun")); commands.listing(p, config.load_arm("dryrun"))
    assert len(set(names)) == 2
