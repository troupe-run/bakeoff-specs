"""Port of spike B demos/q3_egress.sh: an --internal network can reach only allowlisted hosts through the
tinyproxy sidecar. Needs both a Docker daemon and real internet egress to exercise the allow/refuse split
(api.anthropic.com / example.com), so this is marked docker *and* network (not docker alone, unlike the
brief's literal marker line) — --run-docker without --run-network would otherwise try to hit the internet
with no way to skip cleanly."""
import subprocess, pytest
from pathlib import Path
from runner import config, egress

pytestmark = [pytest.mark.docker, pytest.mark.network]

def curl(net, *args):
    return subprocess.run(["docker", "run", "--rm", "--network", net, "-e", "HTTPS_PROXY=http://egress:3128",
                           config.load_pins().images["base"], "curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                           "--max-time", "20", *args], capture_output=True, text=True)

def test_stage_allows_listed_host_and_refuses_others(tmp_path):
    log = tmp_path / "egress.log"
    with egress.Stage("t", "probe", "run", [r"^api\.anthropic\.com$"], log) as st:
        assert curl(st.net, "https://api.anthropic.com/").stdout.strip() not in ("", "000")
        assert curl(st.net, "https://example.com/").returncode != 0
        assert curl(st.net, "--noproxy", "*", "https://1.1.1.1/").returncode != 0
    assert egress.decisions(log.read_text()) == [("api.anthropic.com", "allowed"), ("example.com", "refused")]
    assert subprocess.run(["docker", "network", "inspect", st.net], capture_output=True).returncode != 0
