import dataclasses, hashlib, subprocess
from pathlib import Path
import pytest
from runner import config, credentials, docker

FAKE_REAL = "sk-ant-oat01-FAKE-test-token-never-real-0123456789"   # fake only; never the keychain item


def env(arm="control", **kw):
    kw.setdefault("role", "arm"); kw.setdefault("isolated", False)
    if kw["role"] == "arm":
        kw.setdefault("pass_", "pass1")
    return credentials.session_env(config.load_pins(), config.load_arm(arm), **kw)


def test_session_env_pins_model_and_remaps_every_alias_to_it():            # OD2
    e = env()
    for k in ["BK_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
              "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"]:
        assert e[k] == "claude-opus-5-5"


def test_session_env_carries_isolation_and_retry_settings():
    e = env("openspec")
    assert e["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1" and e["CLAUDE_CODE_MAX_RETRIES"] == "4"
    assert e["CLAUDE_CONFIG_DIR"] == "/home/actor/.claude" and e["OPENSPEC_TELEMETRY"] == "0"
    assert e["BK_DISALLOWED"] == "WebSearch,WebFetch,AskUserQuestion"


def test_isolated_sessions_request_empty_setting_sources():                # renamed (review Q-11); P7 probes behaviour
    e = env(role="po", isolated=True, tools="Read,Glob,Grep")
    assert e["BK_ISOLATED"] == "1" and e["BK_TOOLS"] == "Read,Glob,Grep"


def test_plugin_dirs_only_for_arm_sessions_under_route_b():                 # OD9
    assert env("superpowers")["BK_PLUGIN_DIRS"] == "/opt/plugins/superpowers"
    assert "BK_PLUGIN_DIRS" not in env("superpowers", role="po", isolated=True)
    pins_a = dataclasses.replace(config.load_pins(), plugin_route="marketplace")
    e = credentials.session_env(pins_a, config.load_arm("superpowers"), role="arm", isolated=False,
                                pass_="pass1")
    assert "BK_PLUGIN_DIRS" not in e


def test_session_env_never_contains_the_credential_text():                 # renamed (review Q-11); Task 24 checks every spec
    token = credentials.dummy().payload().decode().strip()
    assert all(token not in v for v in env(resume="abc").values())
    c = credentials.dummy()
    assert token not in repr(c) and token not in str(c) and token not in f"{c}"


def test_dummy_is_refused_for_real_arms_and_real_is_refused_for_dry_arms():   # review C-14
    with pytest.raises(PermissionError):
        credentials.dummy().check_turn(dry=False)
    with pytest.raises(PermissionError):
        credentials.Credential("real-token").check_turn(dry=True)
    credentials.dummy().check_turn(dry=True)
    credentials.Credential("real-token").check_turn(dry=False)


def test_keychain_error_never_contains_stdout(monkeypatch):                  # review S-6
    monkeypatch.setattr(credentials.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 44, stdout="SECRET-ish", stderr="x"))
    with pytest.raises(RuntimeError) as e:
        credentials.from_keychain("svc")
    assert "SECRET-ish" not in str(e.value)


def test_keychain_success_reads_the_named_service_and_strips(monkeypatch):
    seen = {}

    def fake_run(argv, **k):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout=FAKE_REAL + "\n", stderr="")
    monkeypatch.setattr(credentials.subprocess, "run", fake_run)
    c = credentials.from_keychain("svc")
    assert seen["argv"] == ["security", "find-generic-password", "-s", "svc", "-w"]
    assert c.payload() == (FAKE_REAL + "\n").encode()
    assert c.fingerprint() == hashlib.sha256(FAKE_REAL.encode()).hexdigest()
    assert c.raw_for_scanner() == FAKE_REAL
    c.check_turn(dry=False)                                    # a keychain credential is a real one
    assert FAKE_REAL not in repr(c) and FAKE_REAL not in f"{c!r:>80}" and FAKE_REAL not in "%s" % c


def test_keychain_empty_output_is_refused(monkeypatch):
    monkeypatch.setattr(credentials.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="  \n", stderr=""))
    with pytest.raises(RuntimeError):
        credentials.from_keychain("svc")


def test_credential_is_opaque_to_attribute_introspection():
    c = credentials.Credential(FAKE_REAL)
    assert not hasattr(c, "__dict__")                          # __slots__: no vars()/__dict__ dump
    with pytest.raises(AttributeError):
        c.token = "x"                                          # no stray attributes


# --- M4 (preflight ruling): GH_REPO for github-tracker arms, only when a slug exists ------------------

def test_github_slug_per_pass():
    assert config.github_slug("pass2", "openspec") == "troupe-run/bakeoff-specs-openspec"
    assert config.github_slug("pass1", "openspec") == "troupe-run/bakeoff-specs-openspec-pass1"
    assert config.github_slug("canary", "control") == "troupe-run/bakeoff-specs-control-canary"
    assert config.github_slug("dry1", "dryrun") is None
    assert config.github_slug("probe", "control") is None


def test_gh_repo_present_for_github_arms_with_a_slug():
    assert env("control", pass_="pass1")["GH_REPO"] == "troupe-run/bakeoff-specs-control-pass1"
    assert env("openspec", pass_="pass2")["GH_REPO"] == "troupe-run/bakeoff-specs-openspec"


def test_gh_repo_absent_for_beads_dry_slugless_and_non_arm_sessions():
    assert "GH_REPO" not in env("speckitty", pass_="pass1")                  # beads tracker
    dry_arm = dataclasses.replace(config.load_arm("control"), name="dryrun", tracker="dry", dry=True)
    e = credentials.session_env(config.load_pins(), dry_arm, role="arm", isolated=False, pass_="dry1")
    assert "GH_REPO" not in e                                                # dry arm, dry pass
    e = credentials.session_env(config.load_pins(), dry_arm, role="arm", isolated=False, pass_="pass1")
    assert "GH_REPO" not in e                                                # dry tracker even on a real pass name
    assert "GH_REPO" not in env("control", pass_="dry1")                     # no slug on dry/probe passes
    assert "GH_REPO" not in env("control", role="po", isolated=True)        # non-arm role, no pass given
    assert "GH_REPO" not in env("control", role="po", isolated=True, pass_="pass1")


# --- Secret-leak guards: the built argv / env / spec recording never carry the token ----------------

def _all_envs():
    pins = config.load_pins()
    for name in config.all_arms():
        arm = config.load_arm(name)
        for role, isolated in (("arm", False), ("arm", True), ("po", True), ("teammate", True)):
            for pass_ in ("", "pass1", "pass2", "canary", "dry1"):
                if role == "arm" and not pass_:
                    continue                                     # refused: pass_ is required for arm sessions
                yield credentials.session_env(pins, arm, role=role, isolated=isolated, tools="Read",
                                              resume="sess-1", mcp=True, pass_=pass_)


def test_no_session_env_for_any_arm_or_role_carries_the_token():
    c = credentials.Credential(FAKE_REAL)
    token = c.raw_for_scanner()
    for e in _all_envs():
        blob = repr(e)
        assert token not in blob and c.fingerprint() not in blob
        assert not any("TOKEN" in k or "OAUTH" in k or "API_KEY" in k for k in e)


def test_built_argv_and_recorded_spec_never_carry_the_token(tmp_path: Path):
    pins = config.load_pins()
    c = credentials.Credential(FAKE_REAL)
    token = c.raw_for_scanner()
    for name in config.all_arms():
        arm = config.load_arm(name)
        spec = docker.RunSpec(
            name=f"bk-{name}", image=f"bakeoff-{name}:test", label="bakeoff.run", network="none",
            mounts=[docker.Mount(tmp_path, "/home/actor", False)],
            env=credentials.session_env(pins, arm, role="arm", isolated=False, resume="s", pass_="pass1"),
            workdir="/work", cmd=["bk-turn"], stdin=True, limits=pins.limits, proxy=True)
        with docker.recording() as got:
            argv = docker.run_argv(spec)
        assert all(token not in a for a in argv)
        assert got and all(token not in repr(s) for s in got)
        assert "-i" in argv                                  # the token's only route is stdin (→ fd 3)
    assert c.payload() == (FAKE_REAL + "\n").encode()


def test_credential_refuses_pickling_but_survives_copy():
    import copy, pickle
    c = credentials.Credential(FAKE_REAL)
    with pytest.raises(TypeError):
        pickle.dumps(c)
    assert copy.deepcopy({"c": c})["c"] is c and copy.copy(c) is c


def test_arm_sessions_require_a_pass():                                     # controller ruling on concern 1
    pins, arm = config.load_pins(), config.load_arm("control")
    with pytest.raises(ValueError):
        credentials.session_env(pins, arm, role="arm", isolated=False)
    with pytest.raises(ValueError):
        credentials.session_env(pins, arm, role="arm", isolated=False, pass_="")
    for role in ("po", "teammate"):
        credentials.session_env(pins, arm, role=role, isolated=True)           # optional for other roles
