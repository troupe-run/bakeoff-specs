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
import dataclasses, json, shutil, subprocess


class StubOwner:
    """A plain owner stand-in for drive tests: answers everything, never parks (tests that need a park use a
    subclass). It is neither `owner.Owner` nor `owner.ScriptedOwner`."""
    escalation_answer = "Print floats exactly as written in the file."

    def __init__(self):
        self.gates, self.escalations, self.informed = [], [], []

    def escalation(self, q, ctx):
        self.escalations.append(q)
        return self.escalation_answer, 1.0

    def gate(self, msg, dec, diff):
        self.gates.append(msg)
        return dec.reply, "accept", 2.0

    def confirm(self, text): return True
    def inform(self, text): self.informed.append(text)
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
        self.drift_on: dict = {}                # attempt call -> failing step-mode check ids after it (A5)
        self.leak_on: set = set()               # attempt calls whose evidence carries the arm's own token (A5)
        self.oom_on: dict = {}                  # attempt call -> number of OOM-killed turns in it (A5)
        self.all_failed: list[str] = []         # hidden.all_failed attributions


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
        ooms = fs.oom_on.get(fs.calls, 0)
        return AttemptResult("arm-resource" if ooms >= 2 else outcome, "s1", turns=[turn(fs.calls)],
                             breach=fs.breach_on.get(fs.calls), park=fs.park_on.get(fs.calls),
                             resource_events=[{"turn": 1, "exit": 137}] * ooms)

    def verify_pin(files, streams, pins, **k):
        fs.verify_calls.append({"files": files, "streams": list(streams), **k})
        bad = fs.pin_violation_on.get(fs.calls)
        return PinReport(not bad, 1, 1, 0, 0, ["2.1.281"], False,
                         [{"file": "f", "line": 1, "where": "assistant", "model": bad}] if bad else [])

    def hidden_run(p, copy, step, out, install_failed=False, **k):
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
    from runner.checklist import Check
    monkeypatch.setattr(stepflow.checklist, "verify", lambda p, arm, mode: [
        Check(i, False, f"{i} changed") for i in fs.drift_on.get(fs.calls, [])])
    monkeypatch.setattr(stepflow.secrets, "own_pat_values", lambda p, arm, cred=None, **k: ["github_pat_" + "Q" * 60])
    monkeypatch.setattr(stepflow.secrets, "redact", lambda roots, values: [str(ctx.out / "questions.jsonl")]
                        if fs.calls in fs.leak_on else [])

    def all_failed(p, step, out, why):
        fs.all_failed.append(why)
        return stepflow.hidden.summarise(step, {"m::t": "failed"}, ["m::t"], [], [], -1, attribution=why)
    monkeypatch.setattr(stepflow.hidden, "all_failed", all_failed)
    return fs


# ---- Task 23 test helpers: the `fake_orch` fixture (stepflow, git, snapshots, tracker, scans faked) ----------------
class OrchOwner(StubOwner):
    """StubOwner plus the prompts orchestration uses; every answer is scripted by the test."""

    def __init__(self):
        super().__init__()
        self.reviews, self.confirms, self.item_calls, self.substitutes = [], [], [], []
        self.review_answer = lambda md: ("continue", 0.0)
        self.confirm_answer = lambda text: True
        self.items_answer = lambda items: {i: (True, "", 0.0) for i, _ in items}
        self.substitute_answers: list = []

    def step_review(self, md):
        self.reviews.append(md)
        return self.review_answer(md)

    def confirm(self, text):
        self.confirms.append(text)
        return self.confirm_answer(text)

    def items(self, items):
        self.item_calls.append(items)
        return self.items_answer(items)

    def substitute_bug(self, arm, summary):
        self.substitutes.append(summary)
        return self.substitute_answers.pop(0)


class FakeOrch:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.calls: list = []                 # ("run_step", arm, step, run) and other effect markers, in order
        self.ctxs: dict = {}                  # (arm, step, run) -> the last StepCtx passed to run_step
        self.firsts: dict = {}
        self.extras: dict = {}
        self.outcome: dict = {}               # (arm, step, run) -> list of behaviours, consumed in order
        self.escalate: dict = {}              # (arm, step) -> (question, answer) appended to the brief in N.a
        self.escalate_b: dict = {}            # (arm, step) -> (question, answer) appended to the brief in N.b, as
        #                                       runs before the N.b fallback (owner, 2026-10-01) could
        self.fallback_b: dict = {}            # (arm, step) -> [question]: N.b escalations drive answered with the
        #                                       fallback (its questions.jsonl shape; never the brief)
        self.crash_after: set = set()         # (arm, step, run): stepflow finished, then the runner died
        self.resource: dict = {}              # (arm, step) -> "once" | "repeat" recorded during N.b
        self.state = {"branch": "main", "dirty": False}
        self.main = {}                        # arm -> current main sha
        self.findings: dict = {}              # (arm, step) -> remaining scans that find a secret
        self.touched: set = set()             # issue numbers the arm has touched (comments, state)
        self.precheck_passes = False
        self.acceptance: list = []            # run_acceptance outcomes, consumed in order
        self.owner = OrchOwner()
        self.issues = 0
        self.turns_written: dict = {}
        self.verify_now: list = []            # failing step-mode check ids the next verify reports (A5)
        self.bug_runs: list = []              # (arm, step, ctx.run, issue number) for every create_bug


@_pytest.fixture
def fake_orch(tmp_state, tmp_path, monkeypatch):
    import json as J
    from runner import (checklist, config, credentials, docker, faults, gitops, handedit, hidden, images, orchestrate,
                        paths, po, preflight, quality, repo, secrets, stepflow, tracker)
    from runner.paths import Paths
    from runner.session import TurnResult
    env = FakeOrch(tmp_path)
    env.cred = credentials.dummy()
    brief = tmp_path / "po-brief.md"
    shutil.copy(paths.REPO_ROOT / "scenario" / "po-brief.md", brief)
    env.brief = brief
    monkeypatch.setattr(paths, "brief_path", lambda pass_: brief)
    monkeypatch.setattr(gitops, "commit_harness_file", lambda path, msg: env.calls.append(("commit-brief", msg)))
    monkeypatch.setattr(gitops, "harness_differs_from_head", lambda path: True, raising=False)
    monkeypatch.setattr(checklist, "require_clean_green", lambda p: None)
    from runner.checklist import Check

    def verify(p, arm, mode):
        return [Check(i, False, f"{i} drifted") for i in (env.verify_now or [])]
    monkeypatch.setattr(checklist, "verify", verify)
    monkeypatch.setattr(preflight, "check_images", lambda arm, p: None)
    monkeypatch.setattr(docker, "sweep", lambda *a, **k: env.calls.append(("sweep",)) or {})
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: ["dry-run-dummy-token"])
    monkeypatch.setattr(credentials, "github_disc_pat", lambda pass_, arm: "github_pat_" + "D" * 50)   # never the keychain
    env.own = []                                # the arm's own token values (A5); never the keychain in tests
    monkeypatch.setattr(secrets, "own_pat_values", lambda p, arm, cred=None, **k: list(env.own))

    def scan_step(p, n, lits=()):
        left = env.findings.get((p.arm, n), 0)
        env.calls.append(("scan", p.arm, n))
        if left:
            env.findings[(p.arm, n)] = left - 1
            return [secrets.Finding(f"{n:02d}/turns/x.gz", "github-pat", 3)]
        return []
    monkeypatch.setattr(secrets, "scan_step", scan_step)
    monkeypatch.setattr(gitops, "main_sha", lambda p: env.main.get(p.arm, "sha-0"))
    monkeypatch.setattr(gitops, "state", lambda p: gitops.RepoState(env.state["branch"], env.state["dirty"],
                                                                  env.main.get(p.arm, "sha-0"),
                                                                  env.main.get(p.arm, "sha-0"), True))

    def set_aside(p, message):                  # as gitops.set_aside_to_main: a clean main is left alone
        rec = {"branch": env.state["branch"], "dirty": env.state["dirty"], "stashed": env.state["dirty"],
               "checked_out_main": env.state["branch"] != "main"}
        if rec["stashed"] or rec["checked_out_main"]:
            env.calls.append(("set_aside", p.arm))
        env.state.update(branch="main", dirty=False)
        return rec
    monkeypatch.setattr(gitops, "set_aside_to_main", set_aside)
    monkeypatch.setattr(repo, "snapshot", lambda p, s: env.calls.append(("snapshot", p.arm, s)))
    monkeypatch.setattr(repo, "restore", lambda p, s: env.calls.append(("restore", p.arm, s)))
    monkeypatch.setattr(repo, "bundle", lambda p, d: env.calls.append(("bundle", p.arm)) or d)
    monkeypatch.setattr(repo, "publish", lambda p, pass_, ask, scan, slug=None: env.calls.append(
        ("publish", p.arm) if slug is None else ("publish", p.arm, slug)) or ask(f"Push main of {p.arm}? ") is True)
    env.gh_repos: dict = {}                     # slug -> visibility: the fake gh's repos (close-out, OWNER)

    def gh(argv, **k):                          # a fake `gh` (never GitHub): repo view / repo create only
        env.calls.append(("gh", *argv[1:4]))
        slug = argv[3]
        if argv[1:3] == ["repo", "view"]:
            if slug in env.gh_repos:
                return subprocess.CompletedProcess(argv, 0, json.dumps({"visibility": env.gh_repos[slug]}), "")
            return subprocess.CompletedProcess(argv, 1, "", "GraphQL: Could not resolve to a Repository")
        if argv[1:3] == ["repo", "create"]:
            assert "--private" in argv and "--public" not in argv
            env.gh_repos[slug] = "PRIVATE"
            return subprocess.CompletedProcess(argv, 0, f"https://github.com/{slug}\n", "")
        raise AssertionError(f"unexpected gh call {argv}")
    monkeypatch.setattr(repo, "_gh", gh)

    def turn(cost):
        return TurnResult("t", "ok", "", {}, None, cost, {"input_tokens": 1}, {}, 1.0, [], None)

    def hand_edit(ctx, step1_tests):
        env.calls.append(("hand_edit", ctx.arm.name, ctx.step))
        env.main[ctx.arm.name] = "edit-sha"
        return handedit.HandEdit("edit-sha", ["src/cli.py"], [], {}, 1, {}, [turn(0.25)])
    monkeypatch.setattr(stepflow, "hand_edit", hand_edit)

    def detect(ctx, edit, end_sha, arm_files=None):
        env.calls.append(("detect", ctx.arm.name, end_sha, tuple(sorted(str(f.relative_to(ctx.out)) for f in arm_files))))
        return {}
    monkeypatch.setattr(handedit, "detect", detect)

    def create_bug(ctx, owner, *, title=None, body=None):
        if not owner.confirm(f"Create the step-6 issue for {ctx.arm.name}?"):
            raise RuntimeError("declined")
        env.issues += 1
        env.calls.append(("create_bug", ctx.arm.name, title))
        env.bug_runs.append((ctx.arm.name, ctx.step, getattr(ctx, "run", "b"), env.issues))
        return tracker.IssueRef("github", f"troupe-run/x#{env.issues}", None, str(env.issues))
    monkeypatch.setattr(tracker, "create_bug", create_bug)

    def supersede(ctx, old, owner, new=None):
        if not owner.confirm(f"Close {old.ref}?"):
            return {"action": "declined"}
        env.calls.append(("supersede", ctx.arm.name, old.ref))
        return {"action": "closed"}
    monkeypatch.setattr(tracker, "supersede", supersede)

    def tsnap(ctx):
        env.calls.append(("tracker.snapshot", ctx.arm.name, ctx.step))
        snap = {"issues": [{"number": i, "state": "commented" if i in env.touched else "open"}
                           for i in range(1, env.issues + 1)]}
        ctx.out.mkdir(parents=True, exist_ok=True)
        (ctx.out / "tracker.json").write_text(J.dumps(snap))
        return snap
    monkeypatch.setattr(tracker, "snapshot", tsnap)
    monkeypatch.setattr(tracker, "round_trip_facts",
                        lambda ctx, issue, a, b, snap: env.calls.append(("round_trip", ctx.arm.name, issue.ref, a, b))
                        or {"issue": issue.ref})

    def prepare(p, sha, label, out_dir, with_quality=False, require_main=True):
        env.calls.append(("prepare", p.arm, label, sha))
        return hidden.Prepared(tmp_path / "copy", None, {"hidden": {"ok": True}})
    monkeypatch.setattr(hidden, "prepare", prepare)

    def hrun(p, copy, step, out_dir, install_failed=False, **k):
        env.calls.append(("hidden.run", p.arm, step))
        ok = env.precheck_passes
        return hidden.summarise(step, {"m::new": "passed" if ok else "failed", "m::old": "passed"}, ["m::new"], [],
                                [], 0 if ok else 1)
    monkeypatch.setattr(hidden, "run", hrun)
    monkeypatch.setattr(hidden, "run_acceptance", lambda p, copy, step, body: env.calls.append(("acceptance", body))
                        or env.acceptance.pop(0))
    monkeypatch.setattr(quality, "run_all", lambda p, prep, out, pins=None: env.calls.append(("quality", p.arm)) or {})

    def run_step(ctx, first, extra=None, run="b"):
        a, n = ctx.arm.name, ctx.step
        env.calls.append(("run_step", a, n, run))
        env.ctxs[(a, n, run)] = ctx
        env.firsts[(a, n, run)] = first
        env.extras[(a, n, run)] = extra
        behaviour = (env.outcome.get((a, n, run)) or ["ok"]).pop(0) if env.outcome.get((a, n, run)) else "ok"
        ctx.out.mkdir(parents=True, exist_ok=True)
        if behaviour.startswith("touch"):                      # the arm comments on the step-6 issue
            env.touched.add(env.issues)
            behaviour = behaviour.removeprefix("touch").lstrip("-") or "ok"
        if behaviour == "harness-rerun":                      # stepflow's harness restore inside the step
            env.restore_message = ctx.on_restore() if ctx.on_restore is not None else None
            behaviour = "ok"
        if run == "a" and (a, n) in env.escalate:
            q, ans = env.escalate[(a, n)]
            po.append_escalation(ctx.brief_path, q, ans, ctx.pass_, a, n, source="scripted")
        if run == "b" and (a, n) in env.fallback_b:            # drive._reply's N.b fallback entry
            from runner import handoff
            qs = env.fallback_b[(a, n)]
            with open(ctx.out / "questions.jsonl", "a") as fh:
                fh.write(J.dumps({"kind": "question", "escalated": qs, "fallback": qs, "answered_by": "fallback",
                                  "reply": handoff.MESSAGES["escalation_fallback"]}) + "\n")
        if run == "b" and (a, n) in env.escalate_b:
            q, ans = env.escalate_b[(a, n)]
            po.append_escalation(ctx.brief_path, q, ans, ctx.pass_, a, n, source="scripted")
        if behaviour.startswith("tests-"):              # the attempt ran; the tests phase parked or crashed (A1)
            (ctx.out / stepflow.PENDING).write_text(J.dumps({"attempt": 1}))
            behaviour = behaviour.removeprefix("tests-")
        if behaviour == "halt":
            raise stepflow.Halt("HALTED")
        if behaviour == "paused":
            raise stepflow.Paused("the owner declined")
        if behaviour == "paused-park":
            from runner.owner import Park
            raise stepflow.Paused("parked", park=Park("confirm", "x", "unattended", 0.0, 0.0))
        if behaviour == "boom":
            raise RuntimeError("crash mid-step")
        if behaviour == "parked":
            from runner.owner import Park
            (ctx.out / "parked.json").write_text("{}")
            return stepflow.StepOutcome("parked", 0, park=Park("gate", "x", "unattended", 0.0, 0.0), run=run)
        (ctx.out / "turns").mkdir(exist_ok=True)
        (ctx.out / "turns" / "arm-a1-001.stream.jsonl.gz").write_bytes(b"")
        (ctx.out / "transcripts" / "a1" / "projects").mkdir(parents=True, exist_ok=True)
        (ctx.out / "transcripts" / "a1" / "projects" / "s.jsonl.gz").write_bytes(b"")
        if run == "a":
            (ctx.out / "discovery.json").write_text("{}")
            if (a, n, run) in env.crash_after:
                env.crash_after.discard((a, n, run))
                raise KeyboardInterrupt("killed after stepflow returned")
            return stepflow.StepOutcome("discovered", 1, run="a")
        env.main[a] = f"sha-{n}"
        (ctx.out / stepflow.PENDING).unlink(missing_ok=True)          # as stepflow does once the step is decided
        if (a, n) in env.resource:
            faults.record_resource(ctx.pass_, a, n, 1, env.resource[(a, n)], [["oom"]], run="b")
        (ctx.out / "summary.md").write_text(f"# Step {n} summary — {a} ({ctx.pass_})\n")
        (ctx.out / "run.json").write_text(J.dumps({"outcome": "stopped" if behaviour == "stopped" else "done"}))
        s = hidden.summarise(n, {"m::t": "passed"}, ["m::t"], [], [], 0)
        s.write(ctx.out)
        if behaviour == "stopped":
            ctx.paths.results.mkdir(parents=True, exist_ok=True)
            (ctx.paths.results / "arm-result.json").write_text(J.dumps({"stopped_at": n, "by": "stepflow"}))
        if (a, n, run) in env.crash_after:
            env.crash_after.discard((a, n, run))
            raise KeyboardInterrupt("killed after stepflow returned")
        if behaviour == "stopped":
            return stepflow.StepOutcome("stopped", 3, s, {}, run="b")
        return stepflow.StepOutcome("done", 1, s, {}, run="b")
    monkeypatch.setattr(stepflow, "run_step", run_step)

    def setup_arm(pass_, arm, cred, owner):
        p = Paths(pass_, arm)
        p.base.mkdir(parents=True)
        env.calls.append(("setup", arm))
        return checklist.SetupResult([], {}, True, 0.0)
    monkeypatch.setattr(checklist, "run_setup", setup_arm)

    def arms(*names, pass_="dry7"):
        for a in names:
            Paths(pass_, a).base.mkdir(parents=True, exist_ok=True)
    env.make = arms
    env.runs = lambda: [c[1:] for c in env.calls if c[0] == "run_step"]
    return env


# ---- no test ever reads the real keychain (follow-up round 2, item 1) -------------------------------------------------
class KeychainBlocked(AssertionError):
    """Raised when a test reaches the real `/usr/bin/security`. An AssertionError, never a RuntimeError, so no reader
    can mistake it for an absent item: the test fails loudly, and no keychain value is ever read or printed."""


class _GuardedSubprocess:
    """`credentials.subprocess` for tests: every call delegates to the real module except `run` of the keychain
    binary, which raises. A test that fakes `credentials.subprocess.run` overrides it explicitly."""

    def __init__(self, real, security: str):
        self._real, self._security = real, security

    def run(self, argv, *a, **k):
        if argv and str(argv[0]).endswith("security"):
            raise KeychainBlocked("a test reached the real keychain; fake credentials.* or secrets.keychain_* instead")
        return self._real.run(argv, *a, **k)

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture(autouse=True)
def _no_real_keychain(monkeypatch):
    import subprocess as _sp
    from runner import credentials, secrets
    monkeypatch.setattr(credentials, "subprocess", _GuardedSubprocess(_sp, credentials.SECURITY))
    secrets.clear_keychain_cache()                      # nothing cached from an earlier test (or a real read)
    yield
    secrets.clear_keychain_cache()
