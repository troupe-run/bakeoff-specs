import subprocess
import pytest
from runner import config

pytestmark = pytest.mark.docker


def run(image, *cmd, user="1000:1000"):
    return subprocess.run(["docker", "run", "--rm", "--user", user, "--network", "none", image, *cmd],
                          capture_output=True, text=True, timeout=120)


def all_arm_images():
    from runner import images
    return sorted({config.load_arm(a).image for a in images._existing(config.all_arms())})


def test_base_image_has_the_pinned_claude_code():
    assert run(config.load_pins().images["base"], "claude", "--version").stdout.strip() == "2.1.281 (Claude Code)"


@pytest.mark.parametrize("image", all_arm_images())                            # review Q-11: really every arm image
@pytest.mark.parametrize("cmd,expect", [
    (["uv", "--version"], "uv 0.12.19"), (["python3", "--version"], "Python 3.12."), (["node", "--version"], "v22."),
    (["gh", "--version"], "gh version 2.101.0"), (["git", "--version"], "git version"),
    (["claude", "--version"], "2.1.281 (Claude Code)"),
])
def test_every_arm_image_has_the_identical_base_toolchain(image, cmd, expect):
    assert run(image, *cmd).stdout.startswith(expect)


def test_base_image_bakes_the_isolation_env():
    out = run(config.load_pins().images["base"], "env").stdout.splitlines()
    for line in ["CLAUDE_CODE_DISABLE_AUTO_MEMORY=1", "DISABLE_AUTOUPDATER=1",
                 "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1", "OPENSPEC_TELEMETRY=0",
                 "CLAUDE_CONFIG_DIR=/home/actor/.claude", "UV_PYTHON_DOWNLOADS=never"]:
        assert line in out


def test_claude_binary_matches_the_pinned_sha256():
    r = run(config.load_pins().images["base"], "sha256sum", "/usr/local/bin/claude")
    assert r.stdout.split()[0] == config.load_pins().binary_sha256


def test_tester_image_has_harness_venv_quality_tools_and_the_reference():
    img = config.load_pins().images["tester"]
    for tool in ["pytest", "mypy", "ruff"]:
        assert run(img, f"/opt/harness/bin/{tool}", "--version").returncode == 0
    assert run(img, "/opt/harness/bin/python", "-c", "import ruamel.yaml, yaml").returncode == 0
    assert run(img, "/opt/reference/.venv/bin/troupe", "--help").returncode == 0   # reference for flake checks (C-2, m24)


def test_proxy_image_runs_tinyproxy_pinned_by_apk_version():                      # review m1
    r = subprocess.run(["docker", "run", "--rm", config.load_pins().images["proxy"],
                        "tinyproxy", "-v"], capture_output=True, text=True, timeout=30)
    assert (r.stdout + r.stderr).strip()
