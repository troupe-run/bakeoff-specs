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


# ---- Task 20 test helpers (evidence.finalise inputs) --------------------------------------------------------
# Tasks 18 (`runner/hidden.py`) and 19 (`runner/quality.py`) are not landed on this branch. `FakeHiddenSummary`
# is a test-only stand-in for Task 18's real hidden-test summary object, shaped only with what
# `evidence.finalise` and `summary.md` actually read (`.passed`, `.total`, `.new_passed`, `.new_at_step`,
# `.new_discriminating_passed`, `.flaky_arm`) plus a `.write(out)` that drops a `hidden/summary.json`, so a
# test can simulate Task 18 having already run for this step. `runner.evidence` must never import
# `runner.hidden` or `runner.quality` (Task 20 brief).
import json as _json


@dataclasses.dataclass
class FakeHiddenSummary:
    step: int
    results: dict
    new_at_step: list
    flaky_arm: list
    new_discriminating: list
    owner_seconds: float = 0.0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for v in self.results.values() if v == "passed")

    @property
    def new_passed(self) -> int:
        return sum(1 for k in self.new_at_step if self.results.get(k) == "passed")

    @property
    def new_discriminating_passed(self) -> int:
        return sum(1 for k in self.new_discriminating if self.results.get(k) == "passed")

    def write(self, out) -> None:
        d = out / "hidden"; d.mkdir(parents=True, exist_ok=True)
        (d / "summary.json").write_text(_json.dumps({
            "step": self.step, "passed": self.passed, "total": self.total, "new_passed": self.new_passed,
            "new_at_step": self.new_at_step, "new_discriminating_passed": self.new_discriminating_passed,
            "flaky_arm": self.flaky_arm}, indent=2))


def finalise_inputs(tmp_path, monkeypatch):
    """Real inputs for `evidence.finalise`; only `gitops` (containers) is faked here. `hidden` is
    `FakeHiddenSummary`, not `runner.hidden` (not landed on this branch, Task 20 brief).

    Redirects `paths.STATE`/`RESULTS` at `tmp_path` itself (same as the `tmp_state` fixture) — `ctx.paths`
    (unlike `ctx.out`) is a real `Paths("dry9", "control")` whose `.setup_results` etc. resolve against those
    module constants; a caller that later writes under `ctx.paths.setup_results` (fix round 1: the
    owner-shell-commits record) must never land in the real repo's `results/` tree."""
    from runner import gitops, paths
    from runner.transcripts import PinReport
    monkeypatch.setattr(paths, "STATE", tmp_path / "state")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    ctx = make_test_ctx(tmp_path, arm="control", step=3)
    (ctx.out / "questions.jsonl").write_text(_json.dumps({"kind": "continue", "arm_message": "Shall I proceed?",
                                                          "n": 1, "owner_seconds": 0.0, "escalated": [],
                                                          "significant": False}) + "\n")
    s = FakeHiddenSummary(3, {"m::a": "passed"}, ["m::a"], [], [])
    s.write(ctx.out)
    (ctx.out / "quality").mkdir(); (ctx.out / "quality" / "summary.json").write_text("{}")
    monkeypatch.setattr(gitops, "state", lambda p: gitops.RepoState("main", False, "main-sha", "main-sha", True))
    monkeypatch.setattr(gitops, "log", lambda p, a, b: [{"sha": "main-sha", "author": "Developer", "subject": "x"}])
    monkeypatch.setattr(gitops, "diffstat", lambda p, a, b: " a.py | 1 +")
    from runner.drive import AttemptResult
    kw = dict(attempts=[AttemptResult("done", "s1")], extra_turns={}, hidden=s, quality={"mutation": {}},
              pin=PinReport(True, 1, 1, 0, 0, ["2.1.281"], False, []), sha_before="sha0", started=1.7e9,
              ended=1.7e9 + 10, fault_entries=[],
              shas={"po_brief_at_handoff": "b", "contract": "c", "step_brief": "s"},
              tests_seconds=3.0, outcome="done")
    return ctx, kw
