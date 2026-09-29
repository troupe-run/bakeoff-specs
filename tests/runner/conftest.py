import pytest
from runner import paths


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Point STATE/RESULTS (and derived constants) at tmp_path for tests that write evidence."""
    monkeypatch.setattr(paths, "STATE", tmp_path / "state")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "FAULTS", tmp_path / "results" / "faults.jsonl")
    monkeypatch.setattr(paths, "HALTED", tmp_path / "results" / "HALTED")
    monkeypatch.setattr(paths, "LOCK", tmp_path / "state" / "runner.lock")
    monkeypatch.setattr(paths, "IMAGES_SAVE", tmp_path / "state" / "images")
    return tmp_path


# ---- Task 15 test helpers (review Q-9: test helpers live here, never in production modules) --------------------
import dataclasses, shutil


class StubOwner:
    """A plain owner stand-in for drive tests: answers everything, never parks (tests that need a park use a
    subclass). It is neither `owner.Owner` nor `owner.ScriptedOwner`."""
    escalation_answer = "Print floats exactly as written in the file."

    def __init__(self):
        self.gates, self.escalations = [], []

    def escalation(self, q, ctx):
        self.escalations.append(q)
        return self.escalation_answer, 1.0

    def gate(self, msg, dec, diff):
        self.gates.append(msg)
        return dec.reply, "accept", 2.0

    def confirm(self, text): return True
    def reclassify(self, what, detail): return "arm"
    def step_review(self, md): return "continue", 0.0


def make_test_ctx(tmp_path, arm="openspec", step=1, **limits):
    from runner import config, credentials, drive      # lazily: drive must not be imported by every test module
    from runner.paths import Paths, REPO_ROOT
    pins = config.load_pins()
    if limits:
        pins = dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, **limits))
    brief = tmp_path / "po-brief.md"; shutil.copy(REPO_ROOT / "scenario" / "po-brief.md", brief)
    out = tmp_path / "out"; out.mkdir(parents=True, exist_ok=True)
    return drive.StepCtx("dry9", config.load_arm(arm), step, Paths("dry9", arm), pins, out, "## General\n",
                         "# Step 1", brief, credentials.dummy(), StubOwner(), "sha0", [], lambda s: None)
