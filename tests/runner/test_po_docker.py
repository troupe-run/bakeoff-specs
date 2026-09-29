"""The PO session against the real Docker daemon with the fake claude and the dummy credential (no model calls).
Opt in with --run-docker (preflight M1).

The fake's `/po/message.md` merge is baked into `bakeoff-arm-dryrun:1` (rebuilt by Task 24), so these tests run the
image's own `/usr/local/bin/claude`; nothing is bind-mounted over it."""
import dataclasses, json
from pathlib import Path

import pytest

from runner import config, credentials, docker, po, repo
from runner.paths import Paths

pytestmark = pytest.mark.docker



@pytest.fixture(autouse=True)
def no_leftovers():
    yield
    assert not docker.running("bakeoff.run=dry9/dryrun")
    import subprocess
    nets = subprocess.run(["docker", "network", "ls", "-q", "--filter", "label=bakeoff.run=dry9/dryrun"],
                          capture_output=True, text=True).stdout.split()
    assert nets == []


def ctx(tmp_state):
    p = Paths("dry9", "dryrun"); repo.init(p, "dryrun", "dry9")
    return po.PoContext("dry9", "dryrun", 1, 1, p, config.load_pins().images["dryrun"], True, "## General\n",
                        "# Step 1", [], tmp_state / "out")


def test_decide_returns_the_decision_and_keeps_every_input(tmp_state, tmp_path):
    b = tmp_path / "brief.md"; b.write_text("# brief\n## Escalated answers\n")
    good = json.dumps({"kind": "continue", "answers": [], "reply": "Please continue.", "approved": None,
                       "command": None, "arguments": "", "significant": False})
    r = po.decide(ctx(tmp_state), f"working\nFAKE:reply={good}", credentials.dummy(), 1, b)
    assert r.decision.kind == "continue" and r.pin.ok
    for f in ["protocol.md", "po-brief.md", "contract.md", "step.md", "qa.md", "message.md", "decision.json", "model-pin.json"]:
        assert (tmp_state / "out" / "po" / "a1-001" / f).exists()
    assert list((tmp_state / "out" / "po" / "a1-001" / "transcripts").rglob("*.jsonl.gz"))


def test_the_po_container_has_work_read_only_and_no_hidden_tests(tmp_state, tmp_path):    # OD21
    b = tmp_path / "brief.md"; b.write_text("# brief\n## Escalated answers\n")
    c = ctx(tmp_state)
    good = json.dumps({"kind": "step_done", "answers": [], "reply": None, "approved": None,
                       "command": None, "arguments": "", "significant": False})
    with docker.recording() as specs:
        po.decide(c, f"FAKE:reply={good}", credentials.dummy(), 1, b)
    (s,) = specs
    argv = docker.run_argv(s)
    vols = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    assert f"{c.paths.work}:/work:ro" in vols
    repo_root = Path(__file__).resolve().parents[2]
    for v in vols:
        host, ctr, _ = v.split(":")
        assert "hidden" not in ctr and not Path(host).resolve().is_relative_to(repo_root / "tests")
        assert not Path(host).resolve().is_relative_to(repo_root / "reference")
        assert not Path(host).resolve().is_relative_to(c.paths.scratch.resolve())
    assert s.network.startswith("bk-net-dry9-dryrun-po") and s.proxy is True


def test_unusable_reply_twice_is_a_protocol_error(tmp_state, tmp_path):
    b = tmp_path / "brief.md"; b.write_text("# brief\n## Escalated answers\n")
    with pytest.raises(po.ProtocolError):
        po.decide(ctx(tmp_state), "FAKE:reply=nonsense", credentials.dummy(), 2, b)


def test_a_failed_po_session_is_a_session_error_not_a_protocol_error(tmp_state, tmp_path, monkeypatch):   # C-5
    pins = dataclasses.replace(config.load_pins(),                        # preflight M3: capture, then patch
                               limits=dataclasses.replace(config.load_pins().limits, transient_backoff=[0]))
    monkeypatch.setattr(po.config, "load_pins", lambda: pins)
    b = tmp_path / "brief.md"; b.write_text("# brief\n## Escalated answers\n")
    with pytest.raises(po.SessionError):
        po.decide(ctx(tmp_state), "FAKE:api_error=API Error: 529 overloaded", credentials.dummy(), 3, b)
