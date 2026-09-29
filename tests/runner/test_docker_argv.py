from pathlib import Path
from runner import config, docker
from runner.docker import RunSpec, Mount, run_argv, stop_argv

def spec(**kw):
    base = dict(name="bk-pass1-control-01-arm-a1-001", image="img", label="bakeoff.run=pass1/control",
                network="bk-net-pass1-control-run", mounts=[Mount(Path("/h/home"), "/home/actor", False)],
                env={"BK_MODEL": "claude-opus-5-5"}, workdir="/work/bakeoff-specs-control",
                cmd=["bk-claude-turn", "/inbox/msg.md"], stdin=True, limits=config.load_pins().limits, proxy=True)
    base.update(kw)
    return RunSpec(**base)

def test_stage_baseline_flags_are_always_present():
    a = run_argv(spec())
    for flag in ["--rm", "--init", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                 "--user", "1000:1000", "--pids-limit", "2048", "--cpus", "4", "--memory", "8g", "-i"]:
        assert flag in a
    assert a[a.index("--name") + 1] == "bk-pass1-control-01-arm-a1-001"
    assert a[a.index("--label") + 1] == "bakeoff.run=pass1/control"

def test_proxy_env_is_set_only_when_the_stage_has_a_proxy():
    assert "HTTPS_PROXY=http://egress:3128" in run_argv(spec())
    assert not any(x.startswith("HTTPS_PROXY") for x in run_argv(spec(proxy=False, network="none")))

def test_env_is_passed_by_name_and_value_never_by_passthrough():
    a = run_argv(spec(env={"A": "1"}))
    assert "A=1" in a and "--env-file" not in a and "-e" in a
    assert not any(x in ("SSH_AUTH_SOCK", "ANTHROPIC_API_KEY") for x in a)

def test_mounts_are_explicit_and_readonly_flagged():
    assert "/h/in/msg.md:/inbox/msg.md:ro" in run_argv(spec(mounts=[Mount(Path("/h/in/msg.md"), "/inbox/msg.md", True)]))

def test_tmp_is_exec_tmpfs_because_arms_build_and_run_code():
    assert "/tmp:rw,exec,nosuid,nodev,size=4g" in run_argv(spec())

def test_stop_targets_the_container_not_the_cli():
    assert stop_argv("x") == ["docker", "stop", "-t", "30", "x"]

def test_recording_collects_every_spec_built():
    with docker.recording() as got:
        run_argv(spec()); run_argv(spec(name="b"))
    assert [s.name for s in got] == ["bk-pass1-control-01-arm-a1-001", "b"]
    run_argv(spec(name="c"))
    assert len(got) == 2

def test_sweep_removes_labelled_networks_too(monkeypatch):                    # review C-13
    calls = []
    def fake_run(argv, **kw):
        calls.append(argv)
        out = "n1\n" if argv[:3] == ["docker", "network", "ls"] else ("c1\n" if argv[:2] == ["docker", "ps"] else "")
        return type("R", (), {"stdout": out, "returncode": 0})()
    monkeypatch.setattr(docker.subprocess, "run", fake_run)
    assert docker.sweep() == {"containers": ["c1"], "networks": ["n1"]}
    assert ["docker", "network", "rm", "n1"] in calls
