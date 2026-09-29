# tests/runner/test_setup_network.py — real shell setup with the setup egress allowlist, no model turns (no quota).
# test_verify_docker runs the same steps offline (empty allowlist); this is the as-configured run.
import pytest
from runner import checklist, docker

pytestmark = [pytest.mark.docker, pytest.mark.network]


@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    assert not docker.running("bakeoff.run=dry9/openspec")
    assert not docker.sweep("bakeoff.run=dry9/openspec")["networks"]


def test_openspec_shell_setup_passes_its_machine_checks(tmp_state):
    got = {c.id: c for c in checklist.run_shell_only("dry9", "openspec")}
    for cid in ["openspec.version", "openspec.skills", "openspec.commands", "openspec.tree",
                "openspec.telemetry-off", "openspec.context"]:
        assert got[cid].ok, got[cid]
