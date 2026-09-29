# tests/runner/test_setup_network.py — real shell setup with the setup egress allowlist, no model turns (no quota).
# test_verify_docker runs the same steps offline (empty allowlist); this is the as-configured run.
import pytest
from runner import checklist, docker

pytestmark = [pytest.mark.docker, pytest.mark.network]

ARMS = ["openspec", "speckit", "speckitty", "ccsdd"]


@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    for arm in ARMS:
        assert not docker.running(f"bakeoff.run=dry9/{arm}"), arm
        assert not docker.sweep(f"bakeoff.run=dry9/{arm}")["networks"], arm


def test_openspec_shell_setup_passes_its_machine_checks(tmp_state):
    got = {c.id: c for c in checklist.run_shell_only("dry9", "openspec")}
    for cid in ["openspec.version", "openspec.skills", "openspec.commands", "openspec.tree",
                "openspec.telemetry-off", "openspec.context"]:
        assert got[cid].ok, got[cid]


# The constitution / charter / steering checks need the agent turn: covered by the owner's setup, not here.
@pytest.mark.parametrize("arm,ids", [
    ("speckit", ["speckit.version", "speckit.skills", "speckit.bug-skills"]),
    ("speckitty", ["speckitty.version", "speckitty.verify-setup", "speckitty.commands", "speckitty.session-hook",
                   "speckitty.tracker-binding", "speckitty.tracker-egress",
                   "beads.version", "beads.init", "beads.claude-hook", "beads.metrics-off"]),
    ("ccsdd", ["ccsdd.version", "ccsdd.skills", "ccsdd.settings", "ccsdd.project-memory", "ccsdd.no-legacy"]),
])
def test_shell_setup_passes_its_machine_checks(arm, ids, tmp_state):
    got = {c.id: c for c in checklist.run_shell_only("dry9", arm)}
    for cid in ids:
        assert got[cid].ok, got[cid]
