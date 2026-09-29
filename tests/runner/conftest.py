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


# ---- Task 22 test helpers: the `fake_step` fixture (drive/hidden/quality/evidence faked) ------------------------
import pytest as _pytest


class FakeStep:
    def __init__(self, ctx):
        from runner import handoff
        self.ctx, self.messages, self.restored, self.parked = ctx, [], [], []
        self.progress, self.raise_on, self.pin_violation_on, self.breach_on = [], {}, {}, {}
        self.harness_flaky_first, self.hidden_runs, self.prepares, self.calls = [], 0, 0, 0
        self.no_progress = handoff.MESSAGES["no_progress"]
        self.outcome_on: dict = {}              # attempt call -> drive outcome other than "done"
        self.park_on: dict = {}                 # attempt call -> owner.Park carried by a "parked" outcome
        self.attribution_on: dict = {}          # hidden run -> (attribution, resource_evidence)
        self.run_attempt_kw: list[dict] = []    # the keyword arguments of every drive.run_attempt call
        self.verify_calls: list[dict] = []      # every verify_pin call: files, streams and keywords
        self.later_sent_at_call: list[int] = []
        self.finalised: list[dict] = []
        self.quality_runs = 0


@_pytest.fixture
def fake_step(tmp_path, monkeypatch, tmp_state):
    from runner import stepflow
    from runner.drive import AttemptResult
    from runner.faults import HarnessFault
    from runner.session import TurnResult
    from runner.transcripts import PinReport
    ctx = make_test_ctx(tmp_path, arm="control", step=2)
    fs = FakeStep(ctx)

    def turn(n):
        return TurnResult("s1", "ok", "x", {}, {}, 0.0, {}, {}, 1.0, [], tmp_path / f"arm-a{n}.stream.jsonl", None)

    def run_attempt(c, attempt, message, resume=None, **kw):
        fs.messages.append(message); fs.calls += 1; fs.run_attempt_kw.append(kw)
        fs.later_sent_at_call.append(c.later_sent)
        c.later_sent += 1                                   # as drive does when it sends a later message
        if fs.calls in fs.raise_on:
            f = HarnessFault(*fs.raise_on[fs.calls])
            f.attempt_result = AttemptResult("stalled", "s1", turns=[turn(fs.calls)])
            raise f
        outcome = fs.outcome_on.get(fs.calls, "done")
        return AttemptResult(outcome, "s1", turns=[turn(fs.calls)], breach=fs.breach_on.get(fs.calls),
                             park=fs.park_on.get(fs.calls))

    def verify_pin(files, streams, pins, **k):
        fs.verify_calls.append({"files": files, "streams": list(streams), **k})
        bad = fs.pin_violation_on.get(fs.calls)
        return PinReport(not bad, 1, 1, 0, 0, ["2.1.281"], False,
                         [{"file": "f", "line": 1, "where": "assistant", "model": bad}] if bad else [])

    def hidden_run(p, copy, step, out, install_failed=False):
        fs.hidden_runs += 1
        flaky = fs.harness_flaky_first if fs.hidden_runs == 1 else []
        n = fs.progress[min(fs.calls, len(fs.progress)) - 1] if fs.progress else 0
        attribution, ev = fs.attribution_on.get(fs.hidden_runs, (None, []))
        if attribution and attribution.startswith("harness-fault"):
            return stepflow.hidden.summarise(step, {}, ["m::t"], [], [], -1, collected=["m::t"],
                                             attribution=attribution, resource_evidence=ev)
        tests = {"m::t": "passed" if n and not attribution else "failed", **{t: "failed" for t in flaky}}
        return stepflow.hidden.summarise(step, tests, ["m::t"], flaky, [], 0, attribution=attribution,
                                         resource_evidence=ev)

    def quality_run_all(*a, **k):
        fs.quality_runs += 1
        return {"mutation": {}}

    def finalise(*a, **k):
        fs.finalised.append(k)
        return ctx.out / "summary.md"

    monkeypatch.setattr(stepflow.drive, "run_attempt", run_attempt)
    monkeypatch.setattr(stepflow.transcripts, "verify_pin", verify_pin)
    monkeypatch.setattr(stepflow.transcripts, "snapshot", lambda d: {})
    monkeypatch.setattr(stepflow.transcripts, "collect", lambda d, b, dest, **k: [])
    monkeypatch.setattr(stepflow.gitops, "main_sha", lambda p: "main-sha")
    monkeypatch.setattr(stepflow.hidden, "prepare", lambda *a, **k: (setattr(fs, "prepares", fs.prepares + 1) or
                        stepflow.hidden.Prepared(tmp_path, tmp_path, {"hidden": {"ok": True}, "quality": {"ok": True}})))
    monkeypatch.setattr(stepflow.hidden, "run", hidden_run)
    monkeypatch.setattr(stepflow.quality, "run_all", quality_run_all)
    monkeypatch.setattr(stepflow.evidence, "finalise", finalise)
    monkeypatch.setattr(stepflow.repo, "restore", lambda p, s: fs.restored.append(s))
    monkeypatch.setattr(stepflow, "park", lambda out, k, label: fs.parked.append((k, label)))
    monkeypatch.setattr(stepflow, "wait_idle", lambda ctx: None)
    return fs
