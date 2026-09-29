"""Live proofs against real Docker for behaviour that a monkeypatched unit test can't fully vouch for:
label-scoping of `docker.sweep()` (fix round 1, item 1 — this used to be a hand-run, uncommitted script;
it must be a committed test), the timeout->stop path of `docker.run()`, and `docker.running()` (item 4).
"""
import subprocess
import pytest
from runner import config, docker
from runner.docker import RunSpec

pytestmark = pytest.mark.docker


def _image() -> str:
    return config.load_pins().images["base"]


def _run_detached(name: str, label: str | None, cmd=("sleep", "30")) -> None:
    argv = ["docker", "run", "-d", "--name", name]
    if label:
        argv += ["--label", label]
    argv += [_image(), *cmd]
    subprocess.run(argv, check=True, capture_output=True)


def _container_names(name_filter: str) -> list[str]:
    return subprocess.run(["docker", "ps", "-a", "--filter", f"name={name_filter}", "--format", "{{.Names}}"],
                          capture_output=True, text=True).stdout.split()


def _network_names(name_filter: str) -> list[str]:
    return subprocess.run(["docker", "network", "ls", "--filter", f"name={name_filter}", "--format", "{{.Name}}"],
                          capture_output=True, text=True).stdout.split()


def test_sweep_removes_only_bakeoff_run_labelled_containers_and_networks():
    labelled = "bk-sweep-proof-labelled"
    unlabelled = "bk-sweep-proof-unlabelled"
    similar_key = "bk-sweep-proof-similar-key"
    net = "bk-sweep-proof-net"
    try:
        _run_detached(labelled, "bakeoff.run=t/sweep-proof")
        _run_detached(unlabelled, None)
        # A label KEY that only starts the same as "bakeoff.run" — must not be swept (real docker label
        # filtering is exact-key, not prefix; this proves it rather than assuming it).
        _run_detached(similar_key, "bakeoff.run-other=t/sweep-proof")
        subprocess.run(["docker", "network", "create", "--label", "bakeoff.run=t/sweep-proof", net],
                       check=True, capture_output=True)

        result = docker.sweep()

        assert _container_names(f"^{labelled}$") == []
        assert _network_names(f"^{net}$") == []
        assert _container_names(f"^{unlabelled}$") == [unlabelled]
        assert _container_names(f"^{similar_key}$") == [similar_key]
        assert result["containers"] and result["networks"]
    finally:
        subprocess.run(["docker", "rm", "-f", unlabelled, similar_key], capture_output=True)
        subprocess.run(["docker", "rm", "-f", labelled], capture_output=True)     # no-op if sweep got it
        subprocess.run(["docker", "network", "rm", net], capture_output=True)     # no-op if sweep got it


def test_run_timeout_stops_and_removes_the_container_leaving_no_orphan():
    name = "bk-run-timeout-proof"
    spec = RunSpec(name=name, image=_image(), label="bakeoff.run=t/timeout-proof", network="none",
                   mounts=[], env={}, workdir="/", cmd=["sleep", "30"], stdin=False,
                   limits=config.load_pins().limits, proxy=False)
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            docker.run(spec, timeout=1)
        assert _container_names(f"^{name}$") == []
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def test_running_lists_only_containers_carrying_the_label():
    name = "bk-running-proof"
    label = "bakeoff.run=t/running-proof"
    try:
        _run_detached(name, label)
        ids = docker.running(label)
        assert len(ids) == 1
        actual_name = subprocess.run(["docker", "inspect", "--format", "{{.Name}}", ids[0]],
                                     capture_output=True, text=True).stdout.strip().lstrip("/")
        assert actual_name == name
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
