"""Orchestration (plan Task 23; design §5, §6, §9; owner run structure 2026-09-29). The only module that knows the
step order.

**Step-major runs (owner, 2026-09-29, replaces pass 1 / pass 2).** For each step N in 1..7:

1. **N.a (discovery)**: every live arm, one at a time, in the recorded order, runs `stepflow.run_step(run="a")`: it
   stops at the arm's first approval request or first code edit outside its spec paths, is recorded under
   `results/<pass>/<arm>/NN/a/`, unscored, and stepflow restores the pre-step snapshot.
2. **Consistency check**: every brief answer escalated at step N and not yet confirmed is shown to the owner, grouped
   by question, with conflicting answers to the same question and overlapping questions flagged; the owner confirms
   each group or edits `po-brief.md` and the check runs again. Recorded in `results/<pass>/consistency/step-NN.json`.
   Parked if the owner is away.
3. **N.b (scored)**: every live arm, one at a time, runs `run_step(run="b")` to completion, from the same snapshot and
   `sha_before` as N.a. N.b carries forward to N+1.

The real run is ONE namespace, `pass1` (Paths, keychain `bakeoff-gh-pass1-<arm>`, private repo `…-pass1`), with runs
a and b inside each step; `pass2` is retired (`order("pass2")` refuses), and setup runs once per arm. `canary` and
`dry*` passes stay separate. `run_pass` runs the recorded order step-major; `run_arm` runs one arm the same way and
is for the canary and dry passes only (on the real pass one arm alone would break the lockstep of N.a, the check
and N.b).

**Before an arm's step starts** (once; never again for a started step, review I-2): step 2 sets the arm's leftovers
aside so `main` is clean, then `stepflow.hand_edit` (which takes `snapshot(2)`, post-edit, so 2.a's reset keeps the
edit; `sha_before` is the teammate commit); step 6 prechecks the planted bug on the step-5 commit (the owner may
substitute a bug whose acceptance test is first proved to FAIL there), files the issue, then snapshots (so a restore
keeps the issue for beads); every other step snapshots. The step's snapshot and `sha_before` are then fixed.

**Resume** (`state/<pass>/<arm>/progress.json`): a run that ended `parked`, `paused`, `halted`, `interrupted` or was
still `running` (a crash) has left the tree mid-step: the EXISTING pre-step snapshot is restored and that run's
evidence moved aside (`NN/a-interrupted-<k>/`, `NN/b-interrupted-<k>/`) before it runs again — except a scored run stopped in its tests phase (stepflow's `NN/tests-pending.json`, final fix
batch A1): the arm's attempt is kept, nothing is restored, and stepflow resumes at the tests on the same commit. A
tracker or precheck fault here (the step-6 issue, the tracker snapshot) is recorded in the ledger (`infra-tracker`,
`infra-hidden`) and stops the run for the owner; a repeat halts. A completed run is
never run again; its remaining post actions (secret scan, detection, tracker snapshot, end snapshot, the owner's
review) are. Every `owner.*` answer is checked for `owner.Park`: a park parks that arm (recorded in
`results/<pass>/run-log.jsonl`) and the run moves on to the next arm; the phase barrier then stops the run until the
parked item is done. A step-6 issue the arm touched (comments, state) is superseded and a fresh one filed before the
next run of step 6 and on a harness restore inside it (`ctx.on_restore`).

**Faults** (design §9): stepflow records its own. Here: `setup-drift:<check id>` (the step-mode verify script before
each run), `secret-in-evidence` (`secrets.scan_step` after each run; the run is not repeated, the scan is), the
`secret-in-publish` of `repo.publish`, a setup's harness fault (step 0), and `suite-resource:<step>` — after each
arm's N.b, the arms with ANY N.b resource-exhaustion record at that step since the last resolution are counted (N.a's
records are evidence only, follow-up 8); at
`limits.suite_resource_arms` the bake-off halts for owner review (`faults.halt`), and after `faults resume` the arms
scored all-failed there ("repeat") re-run that step's N.b. Owner-declared faults: `--scope rerun-step` supersedes the
step and every later one (`NN-superseded-<k>/`) and re-runs them from the step's existing snapshot (the hand edit and
the issue are kept); `--scope retest` re-runs the hidden tests and quality on the step's recorded `sha_after`.

**Records and locking (fix round 1)**: every progress, consistency, suite-resource and evidence record is written
atomically (`fsutil`: temp file, fsync, `os.replace`). `preflight.lock()` is taken before every pre-check and any
setup. A run still marked `running` whose stepflow completion record exists (`NN/a/discovery.json`; `NN/run.json`,
plus `arm-result.json` when stopped) is adopted, not run again. Owner parks on the setup path end setup as parked
(`checklist.SetupParked`, `00-setup/parked.json`); the next `run-pass` redoes the setup.

**The end of an arm**: `repo.bundle` → `results/<pass>/<arm>/repo.bundle`; `arm-result.json` (`{"completed": true}`;
a stopped arm's is stepflow's and is never rewritten); `repo.publish` to the arm's PRIVATE repo when the pass has one
(scan of the tip tree and history first; the owner's confirmation, where a park is never a yes).
"""
from __future__ import annotations
import dataclasses, hashlib, json, random, re, shutil
from datetime import datetime, timezone
from pathlib import Path

from runner import (checklist, config, docker, drive, faults, fsutil, gitops, handedit, handoff, hidden, owner as owner_mod,
                    paths, po, preflight, quality, repo, secrets, stepflow, tracker)
from runner.faults import HarnessFault
from runner.paths import Paths, REAL_PASSES, REPO_ROOT

NotReady = checklist.NotReady
CONTRACT = REPO_ROOT / "scenario" / "contract.md"
BRIEFS = sorted((REPO_ROOT / "scenario" / "steps").glob("0*.md"))
STEPS = range(1, 8)
RUNS = ("a", "b")
REAL = "pass1"                    # the real run's one namespace (Task 23 ruling)
DONE = {"a": ("discovered",), "b": ("done", "stopped")}
INTERRUPTED = ("running", "parked", "paused", "halted", "interrupted")
KEEP_ON_B_ASIDE = ("a", "hand-edit", "precheck", "substitute", "issue.json", "issue-body.md", "tracker-superseded.jsonl")


class _OwnerParked(Exception):
    """An owner prompt inside another module (tracker, publish) returned a Park: never a yes."""

    def __init__(self, park):
        super().__init__(f"owner parked: {getattr(park, 'context', '')}")
        self.park = park


class _Stop(Exception):
    """The owner declined (not parked): the run stops here."""


class _Guard:
    """An owner for modules that treat `confirm()` as a bool (tracker, repo.publish): a `Park` raises instead of
    reading as truthy."""

    def __init__(self, owner):
        self._o = owner

    def confirm(self, text: str) -> bool:
        got = self._o.confirm(text)
        if isinstance(got, owner_mod.Park):
            raise _OwnerParked(got)
        return got is True

    def __getattr__(self, name):
        return getattr(self._o, name)


def _log_line(pass_: str, rec: dict) -> None:
    """Append one record to `results/<pass>/run-log.jsonl`. A crash can leave a partial last line: the next record
    starts on a new line, so it is never glued onto it."""
    f = paths.RESULTS / pass_ / "run-log.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "ab+") as fh:
        fh.seek(0, 2)
        lead = b""
        if fh.tell():
            fh.seek(-1, 2)
            lead = b"" if fh.read(1) == b"\n" else b"\n"
        fh.write(lead + (json.dumps(rec, default=str) + "\n").encode())


def read_log(pass_: str) -> tuple[list[dict], list[dict]]:
    """(entries, skipped): the run log's records; a line that is not a whole JSON object (a partial line left by a
    crash) is skipped and recorded as {"line", "bytes"}, never fatal."""
    f = paths.RESULTS / pass_ / "run-log.jsonl"
    entries, skipped = [], []
    if not f.is_file():
        return entries, skipped
    for i, line in enumerate(f.read_bytes().split(b"\n"), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            rec = None
        if isinstance(rec, dict):
            entries.append(rec)
        else:
            skipped.append({"line": i, "bytes": len(line)})
    return entries, skipped


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _jw(f: Path, obj) -> None:
    fsutil.write_json(f, obj)                     # atomic: temp + fsync + os.replace (fix round 1)


def _jr(f: Path, default=None):
    return json.loads(f.read_text()) if f.is_file() else default


# ---- the order (OD13; owner: bmad parked; one real pass) ------------------------------------------------------------

def order(pass_: str, seed: int | None = None) -> list[str]:
    """`pass1`: a `random.Random(seed)` shuffle of the ACTIVE arms, control swapped out of first place (OD13); a
    missing seed is drawn and recorded, so the order can always be reproduced. `canary`: control alone. Written to
    `results/<pass>/order.json`. The same order serves every step's N.a and N.b."""
    if pass_ == "pass2":
        raise NotReady("pass2 is retired (owner, 2026-09-29): the real run is pass1, with N.a and N.b inside each step")
    if pass_ == REAL:
        seed = seed if seed is not None else random.SystemRandom().randrange(2 ** 32)
        arms = config.active_arms()
        random.Random(seed).shuffle(arms)
        if arms[0] == "control":
            arms[0], arms[1] = arms[1], arms[0]
        rec = {"seed": seed, "rule": "shuffle of the active arms; control not first (OD13)", "order": arms}
    elif pass_ == "canary":
        arms = ["control"]
        rec = {"seed": None, "rule": "canary: control alone (OD25)", "order": arms}
    else:
        raise NotReady(f"{pass_}: no recorded order rule (dry passes run one arm with `run-arm`)")
    _jw(paths.RESULTS / pass_ / "order.json", rec)
    return list(arms)


# ---- progress --------------------------------------------------------------------------------------------------

def _load(p: Paths) -> dict:
    prog = _jr(p.progress, {}) or {}
    prog.setdefault("steps", {})
    prog.setdefault("stopped_at", None)
    prog.setdefault("finished", {"bundle": False, "arm_result": False, "published": None})
    prog.setdefault("rerun", None)
    prog.setdefault("retests_done", [])
    prog.setdefault("teammate_turns", [])
    return prog


def _save(p: Paths, prog: dict) -> None:
    _jw(p.progress, prog)


def _turns_out(turns) -> list[dict]:
    return [{"session_id": t.session_id, "outcome": t.outcome, "cost_usd": t.cost_usd, "usage": t.usage,
             "model_usage": t.model_usage, "wall_seconds": t.wall_seconds} for t in turns or []]


def _turns_in(recs: list[dict]) -> list:
    from runner.session import TurnResult
    return [TurnResult(r.get("session_id"), r.get("outcome", "ok"), "", {}, None, float(r.get("cost_usd") or 0.0),
                       r.get("usage") or {}, r.get("model_usage") or {}, float(r.get("wall_seconds") or 0.0), [], None)
            for r in recs]


def _complete(e: dict, run: str) -> bool:
    r = e.get(run) or {}
    return r.get("status") in DONE[run] and all(r.get("post", {}).get(k) for k in r.get("post_needed", [])) and \
        (run == "a" or e.get("review") in ("continue", "pause"))


# ---- the run ---------------------------------------------------------------------------------------------------------

class _Run:
    def __init__(self, pass_: str, arms: list[str], cred, owner, pins: config.Pins, lits: list[str]):
        self.pass_, self.arms, self.cred, self.owner, self.pins, self.lits = pass_, arms, cred, owner, pins, lits
        self.guard = _Guard(owner)
        self.contract = CONTRACT.read_text()
        self.parked: list[dict] = []
        self.keychain = False                            # whether this run may read the keychain (set by _run)

    # -- records ------------------------------------------------------------------------------------------------
    def log(self, event: str, **kw) -> None:
        _log_line(self.pass_, {"at": _now(), "event": event, **kw})

    def park(self, arm: str | None, step: int | None, run: str | None, what: str, park=None) -> str:
        item = {"arm": arm, "step": step, "run": run, "what": what}
        self.parked.append(item)
        self.log("parked", **item, park=dataclasses.asdict(park) if park is not None else None)
        return "parked"

    def fault(self, f: HarnessFault, arm: str, step: int, run: str | None, why: str):
        """Record a fault found here; the second identical one halts (design §9), otherwise stop for the owner."""
        if faults.record(f, self.pass_, arm, step, 0, run=run) == "halt":
            raise stepflow.Halt(faults.halted(self.pass_)) from f
        raise NotReady(f"harness fault {f.kind}:{f.signature} ({arm}, step {step}): {why}") from f

    def infra(self, kind: str, arm: str, step: int, run: str | None, what: str, fn):
        """`fn()`, with a harness fault or a container/git/subprocess error recorded in the ledger as `kind` (final
        fix batch A1: tracker and precheck faults here never escape unrecorded). An owner park passes through."""
        try:
            return fn()
        except HarnessFault as f:
            self.fault(f, arm, step, run, f"{what} failed; fix it, then run again")
        except stepflow.INFRA_ERRORS as e:
            self.fault(HarnessFault(kind, stepflow._sig(str(e)), repr(e)[:500]), arm, step, run,
                       f"{what} failed; fix it, then run again")

    # -- the step context ----------------------------------------------------------------------------------------
    def ctx(self, arm_name: str, step: int, out: Path, e: dict, run: str = "b") -> drive.StepCtx:
        arm, p = config.load_arm(arm_name), Paths(self.pass_, arm_name)
        return drive.StepCtx(pass_=self.pass_, arm=arm, step=step, paths=p, pins=self.pins, out=out,
                             contract_in_force=handoff.in_force(step, self.contract),
                             step_brief=BRIEFS[step - 1].read_text(), brief_path=paths.brief_path(self.pass_),
                             cred=self.cred, owner=self.owner, sha_before=e.get("sha_before") or "",
                             snapshot=e.get("snapshot"), contract=self.contract, run=run)

    # -- before a step starts (once) ----------------------------------------------------------------------------
    def begin(self, arm_name: str, step: int, prog: dict) -> str | None:
        p = Paths(self.pass_, arm_name)
        e = prog["steps"].setdefault(str(step), {})
        out = p.step(step); out.mkdir(parents=True, exist_ok=True)
        if step == 2:
            if self._hand_edit(arm_name, p, prog, e, out) == "parked":
                return "parked"
        elif step == 6:
            if self._close_stale(arm_name, prog) == "parked":        # never two bug reports in front of the arm
                return "parked"
            if not e.get("issue"):
                got = self._file_issue(arm_name, p, prog, e, out)
                if got == "parked":
                    return "parked"
            repo.snapshot(p, 6)
            e["sha_before"] = gitops.main_sha(p) or gitops.head(p)
        else:
            repo.snapshot(p, step)
            e["sha_before"] = gitops.main_sha(p) or gitops.head(p)
        e.update(snapshot=step, started=True, restore_needed=False, started_at=_now())
        _save(p, prog)
        self.log("step-started", arm=arm_name, step=step, sha_before=e["sha_before"])
        return None

    def _hand_edit(self, arm_name, p, prog, e, out) -> str | None:
        pre = p.snapshots / f"step-{handedit.PRE_EDIT}.tar"
        if e.get("hand_edit") in ("started", "paused", "halted") and pre.is_file():
            repo.restore(p, handedit.PRE_EDIT)               # a retry starts from the pre-edit state
        else:
            rec = gitops.set_aside_to_main(p, "bakeoff: the arm's leftovers at the end of step 1, set aside before "
                                              "the step-2 hand edit")
            _jw(out / "hand-edit" / "pre-edit-state.json", rec)
        e["hand_edit"] = "started"; _save(p, prog)
        step1 = (_jr(p.step(1) / "hidden" / "summary.json", {}) or {}).get("tests", {})
        ctx = self.ctx(arm_name, 2, out, {"sha_before": gitops.main_sha(p) or "", "snapshot": 2})
        try:
            edit = stepflow.hand_edit(ctx, step1)
        except (stepflow.Paused, stepflow.Halt) as x:
            cause = x.__cause__ or x.__context__
            prog["teammate_turns"] += _turns_out(getattr(cause, "hand_edit_turns", None))
            e["hand_edit"] = "halted" if isinstance(x, stepflow.Halt) else "paused"
            _save(p, prog)
            if isinstance(x, stepflow.Paused) and x.park is not None:
                return self.park(arm_name, 2, None, "hand-edit", x.park)
            if isinstance(x, stepflow.Paused):
                raise _Stop(f"{arm_name}: {x}") from x
            raise
        prog["teammate_turns"] += _turns_out(edit.turns)
        e.update(hand_edit="done", sha_before=edit.sha,
                 edit={"sha": edit.sha, "files": edit.files, "tries": edit.tries})
        return None

    # -- step 6: precheck, substitute, issue --------------------------------------------------------------------
    def _file_issue(self, arm_name, p, prog, e, out) -> str | None:
        arm = config.load_arm(arm_name)
        pc_dir = out / "precheck"
        if e.get("precheck") is None:
            def precheck():
                try:
                    prep = hidden.prepare(p, hidden.MAIN, "06-precheck", pc_dir)
                except hidden.NoMain:                # nothing committed: the planted bug cannot already pass
                    return hidden.summarise(6, {}, [], [], [], -1, attribution=hidden.NO_MAIN)
                return hidden.run(p, prep.hidden_copy, 6, pc_dir,
                                  install_failed=not prep.prep.get("hidden", {}).get("ok"))
            s = self.infra("infra-hidden", arm_name, 6, None, "the step-6 precheck", precheck)
            rec = {"scoreable": s.scoreable, "attribution": s.attribution, "new_at_step": s.new_at_step,
                   "new_passed": s.new_passed, "sha": gitops.main_sha(p), "tests": s.tests}
            if not s.scoreable:                      # m-3: never deliver the planted bug on an unread precheck
                _jw(pc_dir / "precheck-unscoreable.json", {**rec, "at": _now()})
                return self.park(arm_name, 6, None, "precheck-unscoreable")
            passes = bool(s.new_at_step and all(s.tests.get(t) == "passed" for t in s.new_at_step))
            e["precheck"] = {"planted_already_passes": passes, **rec}
            _jw(pc_dir / "precheck.json", e["precheck"])
            _save(p, prog)
        title = body = None
        if e["precheck"]["planted_already_passes"] and not e.get("substitute"):
            got = self._substitute(arm, p, e, out)
            if got == "parked":
                return "parked"
            _save(p, prog)
        if (e.get("substitute") or {}).get("choice") == "substitute":
            title, body = e["substitute"]["title"], e["substitute"]["body"]
        ctx = self.ctx(arm_name, 6, out, e)
        try:
            ref = self.infra("infra-tracker", arm_name, 6, None, "filing the step-6 issue",
                             lambda: tracker.create_bug(ctx, self.guard, title=title, body=body))
        except _OwnerParked as x:
            return self.park(arm_name, 6, None, "issue", x.park)
        e["issue"] = dataclasses.asdict(ref)
        e["issue_fp"] = self.infra("infra-tracker", arm_name, 6, None, "reading the step-6 issue",
                                   lambda: self._issue_fp(ctx, ref))
        _save(p, prog)
        return None

    def _substitute(self, arm, p, e, out) -> str | None:
        pc = e["precheck"]
        summary = (f"The planted alias bug's step-6 tests already pass on {arm.name}'s step-5 commit "
                   f"{pc.get('sha')}: {pc.get('new_passed')}/{len(pc.get('new_at_step') or [])} new tests pass "
                   f"(see {out / 'precheck'}).")
        d = out / "substitute"
        while True:
            got = self.owner.substitute_bug(arm, summary)
            if isinstance(got, owner_mod.Park):
                return self.park(arm.name, 6, None, "substitute-bug", got)
            choice, title, body, why, test_body, secs = got
            if choice != "substitute":
                e["substitute"] = {"choice": "planted", "owner_seconds": secs}
                _jw(d / "decision.json", e["substitute"])
                return None
            d.mkdir(parents=True, exist_ok=True)
            (d / "test_substitute.py").write_text(test_body)
            (d / "why.md").write_text(f"# Why this substitute\n\n{why}\n")
            prep = self.infra("infra-hidden", arm.name, 6, None, "installing the step-5 commit for the substitute",
                              lambda: hidden.prepare(p, hidden.MAIN, "06-substitute", d))
            if not prep.prep.get("hidden", {}).get("ok"):          # m-3: an install failure is not "the test fails"
                r = {"outcome": "not-run", "detail": "the step-5 commit does not install (see prep-06-substitute.json)"}
                _jw(d / "acceptance.json", r)
                summary += (f"\n\nREJECTED: {title!r} cannot be checked: the step-5 commit does not install, so its "
                            f"acceptance test cannot genuinely fail. Keep the planted bug, or fix the harness first.")
                continue
            r = self.infra("infra-hidden", arm.name, 6, None, "the substitute's acceptance test",
                           lambda: hidden.run_acceptance(p, prep.hidden_copy, 6, test_body))
            _jw(d / "acceptance.json", r)
            if r.get("outcome") == "failed" and not r.get("attribution"):     # a genuine failure, not a death
                e["substitute"] = {"choice": "substitute", "title": title, "body": body, "why": why,
                                   "test": str(d / "test_substitute.py"), "acceptance": r, "owner_seconds": secs}
                _jw(d / "decision.json", e["substitute"])
                return None
            if r.get("attribution"):                  # it "failed" only because the run died (round 2, item 5)
                summary += (f"\n\nREJECTED: the acceptance run for {title!r} died ({r['attribution']}) on the "
                            f"step-5 commit instead of reaching the test's own assertion, so it proves nothing "
                            f"about the bug. A substitute must be a bug this commit really has.")
            else:
                summary += (f"\n\nREJECTED: the acceptance test for {title!r} passed or did not run on the step-5 "
                            f"commit (outcome {r.get('outcome')}: {str(r.get('detail') or r.get('tests'))[:400]}), "
                            f"so the bug is not there. A substitute must be a bug this commit really has.")

    def _issue_fp(self, ctx, ref) -> str:
        probe = dataclasses.replace(ctx, out=ctx.paths.scratch / "tracker-probe")
        snap = tracker.snapshot(probe)
        match = next((i for i in snap.get("issues", []) if str(i.get("number", i.get("id", ""))) == ref.id
                      or i.get("ref") == ref.ref), None)
        return hashlib.sha256(json.dumps(match, sort_keys=True, default=str).encode()).hexdigest() if match else "absent"

    @staticmethod
    def _bug(e: dict) -> tuple[str | None, str | None]:
        sub = e.get("substitute") or {}
        return (sub["title"], sub["body"]) if sub.get("choice") == "substitute" else (None, None)

    def _fresh_issue(self, ctx, e: dict, prog: dict, key: str = "issue") -> str | None:
        """Before any run of step 6 and on a harness restore inside it: an issue the arm touched (or that is gone) is
        superseded and a new one filed (GitHub issues cannot be rolled back). Returns the new bug message, or None.
        `key` "issue_a": the copy in a GitHub arm's N.a discovery repo (A3), recorded under `06/a/`."""
        ref = tracker.IssueRef(**e[key])
        if self._issue_fp(ctx, ref) == e.get(f"{key}_fp"):
            return None
        title, body = self._bug(e)
        out = ctx.paths.step(6) / "a" if key == "issue_a" else ctx.paths.step(6)
        new = tracker.create_bug(dataclasses.replace(ctx, out=out), self.guard, title=title, body=body)
        tracker.supersede(dataclasses.replace(ctx, out=out), ref, self.guard, new)
        e[key], e[f"{key}_fp"] = dataclasses.asdict(new), self._issue_fp(ctx, new)
        e.setdefault("superseded_issues", []).append(ref.ref)
        _save(ctx.paths, prog)
        self.log("issue-superseded", arm=ctx.arm.name, old=ref.ref, new=new.ref)
        return handoff.entry_message(ctx.arm, 6, handoff.bug_message(new.ref, self.contract))

    def _issue_for_run(self, ctx, e: dict, prog: dict, run: str) -> str:
        """The key of the step-6 issue this run sees. A GitHub arm's N.a gets the same bug filed in its discovery
        repo (A3: its PAT reaches only that repo); every other run and backend shares the one issue."""
        if run != "a" or not config.github_disc_slug(self.pass_, ctx.arm.name):
            self.infra("infra-tracker", ctx.arm.name, 6, run, "checking the step-6 issue",
                       lambda: self._fresh_issue(ctx, e, prog))
            return "issue"
        if not e.get("issue_a"):
            title, body = self._bug(e)
            ref = self.infra("infra-tracker", ctx.arm.name, 6, run, "filing the N.a step-6 issue",
                             lambda: tracker.create_bug(ctx, self.guard, title=title, body=body))
            e["issue_a"] = dataclasses.asdict(ref)
            e["issue_a_fp"] = self.infra("infra-tracker", ctx.arm.name, 6, run, "reading the N.a step-6 issue",
                                         lambda: self._issue_fp(ctx, ref))
            _save(ctx.paths, prog)
        else:
            self.infra("infra-tracker", ctx.arm.name, 6, run, "checking the N.a step-6 issue",
                       lambda: self._fresh_issue(ctx, e, prog, "issue_a"))
        return "issue_a"

    def _close_stale(self, arm_name: str, prog: dict) -> str | None:
        """Step-6 issues left behind by `faults declare … --scope rerun-step` of an earlier step (A3): closed with
        "Superseded by a harness re-run" before step 6 files a new one. A park keeps them for the next run."""
        p = Paths(self.pass_, arm_name)
        left = list(prog.get("stale_issues") or [])
        while left:
            item = left[0]
            ctx = self.ctx(arm_name, 6, p.results / "06-stale-issues", {}, item.get("run", "b"))
            try:
                rec = self.infra("infra-tracker", arm_name, 6, None, "closing a stale step-6 issue",
                                 lambda: tracker.supersede(ctx, tracker.IssueRef(**item["ref"]), self.guard, None))
            except _OwnerParked as x:
                prog["stale_issues"] = left; _save(p, prog)
                return self.park(arm_name, 6, None, "close-stale-issue", x.park)
            self.log("stale-issue", arm=arm_name, ref=item["ref"]["ref"], action=rec.get("action"))
            left.pop(0)
            prog["stale_issues"] = left; _save(p, prog)
        return None

    # -- one run of one step for one arm ---------------------------------------------------------------------------
    def run_one(self, arm_name: str, step: int, run: str) -> str:
        """"complete" | "parked" | "pause"."""
        p = Paths(self.pass_, arm_name)
        prog = _load(p)
        e = prog["steps"].setdefault(str(step), {})
        r = e.get(run) or {}
        if r.get("status") in DONE[run]:
            return self.post(arm_name, step, run, prog)
        if r.get("status") in ("running", "interrupted") and (done := self._stepflow_finished(p, step, run)):
            return self._adopt(arm_name, step, run, prog, done)            # never spend another arm session
        if not e.get("started"):
            if self.begin(arm_name, step, prog) == "parked":
                return "parked"
        tests_pending = run == "b" and (p.step(step) / stepflow.PENDING).is_file()
        if tests_pending:                        # A1: the attempt ran; its tests resume on the same commit
            e["restore_needed"] = False
            _save(p, prog)
            self.log("tests-resumed", arm=arm_name, step=step, run=run, status=r.get("status"))
        elif e.get("restore_needed") or r.get("status") in INTERRUPTED:
            repo.restore(p, e["snapshot"])                                   # the EXISTING snapshot (I-2)
            if r.get("status") in INTERRUPTED:
                self._aside(p, step, run, "interrupted")
            e["restore_needed"] = False
            _save(p, prog)
        self._verify(arm_name, step, run, e, prog, restorable=not tests_pending, arm_drift=not tests_pending)
        out = p.step(step) / "a" if run == "a" else p.step(step)
        out.mkdir(parents=True, exist_ok=True)
        ctx = self.ctx(arm_name, step, out, e, run)
        try:
            if step == 6:
                key = self._issue_for_run(ctx, e, prog, run)
                issue = tracker.IssueRef(**e[key])
                messages = [handoff.bug_message(issue.ref, self.contract)]

                def on_restore(ctx=ctx, e=e, prog=prog, key=key):
                    return self._fresh_issue(ctx, e, prog, key)
                ctx.on_restore = on_restore
            elif step == 5:
                messages = handoff.step5(ctx.step_brief, self.contract)
            else:
                messages = [handoff.compose(step, ctx.step_brief, self.contract)]
        except _OwnerParked as x:
            return self.park(arm_name, step, run, "issue", x.park)
        sub = e.get("substitute") or {}
        if step == 6 and run == "b" and sub.get("choice") == "substitute":             # A4: scored by its test
            ctx.acceptance = {"body": Path(sub["test"]).read_text(),
                              "baseline": (e.get("precheck") or {}).get("tests") or {}}
        ctx.later_messages = messages[1:]
        ctx.shas = {"po_brief_at_handoff": _sha(ctx.brief_path), "contract": _sha(CONTRACT),
                    "step_brief": _sha(BRIEFS[step - 1])}
        (out / "handoff.md").write_text("\n\n===== next message =====\n\n".join(messages))
        _jw(out / "handoff-shas.json", ctx.shas)
        extra = {"teammate": _turns_in(prog["teammate_turns"])} if (step == 2 and run == "b") else {}
        e[run] = {"status": "running", "started_at": _now(), "interrupted": r.get("interrupted", 0)}
        _save(p, prog)

        def mark(status: str, park=None) -> None:
            e[run] = {**e[run], "status": status, "park": dataclasses.asdict(park) if park is not None else None}
            e["restore_needed"] = True
            _save(p, prog)
        try:
            outcome = stepflow.run_step(ctx, handoff.entry_message(ctx.arm, step, messages[0]), extra, run=run)
        except stepflow.Halt:
            mark("halted"); raise
        except stepflow.Paused as x:
            mark("paused", x.park)
            if x.park is not None:
                return self.park(arm_name, step, run, "run", x.park)
            self.log("declined", arm=arm_name, step=step, run=run, why=str(x))
            raise _Stop(f"{arm_name} step {step}{run}: {x}") from x
        except _OwnerParked as x:
            mark("parked", x.park)
            return self.park(arm_name, step, run, "run", x.park)
        except BaseException:
            mark("interrupted"); raise
        if outcome.status == "parked":
            mark("parked", outcome.park)
            return self.park(arm_name, step, run, "run", outcome.park)
        needed = self._post_needed(step, run)
        e[run] = {**e[run], "status": outcome.status, "ended_at": _now(), "post": {}, "post_needed": needed}
        if outcome.status == "stopped":
            prog["stopped_at"] = step                   # stepflow wrote arm-result.json: never rewritten here
        _save(p, prog)
        self.log("run-ended", arm=arm_name, step=step, run=run, status=outcome.status)
        return self.post(arm_name, step, run, prog)

    def _violation(self, p: Paths, rec: dict) -> None:
        """An arm violation found here (final fix batch A5): `results/<pass>/<arm>/arm-violations.jsonl`, never
        the harness ledger."""
        p.results.mkdir(parents=True, exist_ok=True)
        with open(p.results / stepflow.VIOLATIONS, "a") as fh:
            fh.write(json.dumps({"at": _now(), **rec}) + "\n")
        self.log("arm-violation", arm=p.arm, **{k: v for k, v in rec.items() if k != "files"})

    def _verify(self, arm_name: str, step: int, run: str, e: dict, prog: dict, restorable: bool,
                arm_drift: bool = True) -> None:
        """The step-mode verify before a run. A failing check the ARM can cause (stepflow.ARM_DRIFT) is an arm
        violation (A5): the step's existing snapshot is restored to repair it and the verify runs again; if that
        cannot repair it, the run stops for the owner — never a ledger entry. Any other failure is `setup-drift`."""
        p, arm = Paths(self.pass_, arm_name), config.load_arm(arm_name)
        for again in (False, True):
            fails = [c for c in checklist.verify(p, arm, "step") if c.status == "fail"]
            other = [c for c in fails if c.id not in stepflow.ARM_DRIFT]
            if other:
                c = other[0]
                self.fault(HarnessFault("setup-drift", c.id, c.detail), arm_name, step, run,
                           "the arm's setup drifted (checklists/verify, step mode); the owner fixes it")
            # follow-up 7: resuming a tests phase, stepflow's pending record already judged the attempt's drift
            drift = [c for c in fails if c.id in stepflow.ARM_DRIFT] if arm_drift else []
            if not drift:
                return
            for c in drift:
                self._violation(p, {"step": step, "run": run, "kind": "setup-drift", "check": c.id,
                                    "detail": c.detail[:300], "before_run": True, "after_restore": again})
            if again or not restorable or not e.get("started") or e.get("snapshot") is None:
                raise NotReady(f"{arm_name} step {step}{run}: the arm's own setup drift "
                               f"({', '.join(c.id for c in drift)}) is still there"
                               f"{' after restoring the step snapshot' if again else ''}; an arm violation, not a "
                               f"harness fault — repair it (`runner shell`), then run again")
            repo.restore(p, e["snapshot"])

    def _stepflow_finished(self, p: Paths, step: int, run: str) -> str | None:
        """The crash window between `stepflow.run_step` returning and progress being saved (fix round 1): stepflow's
        own completion record says the run finished. N.a: `NN/a/discovery.json`. N.b: `NN/run.json` (written by
        `evidence.finalise` once the step is decided) — "stopped" only with stepflow's `arm-result.json` too."""
        if run == "a":
            return "discovered" if (p.step(step) / "a" / "discovery.json").is_file() else None
        rec = _jr(p.step(step) / "run.json", {}) or {}
        if rec.get("outcome") == "done":
            return "done"
        if rec.get("outcome") == "stopped" and (p.results / "arm-result.json").is_file():
            return "stopped"
        return None

    def _adopt(self, arm_name: str, step: int, run: str, prog: dict, status: str) -> str:
        p = Paths(self.pass_, arm_name)
        e = prog["steps"][str(step)]
        if run == "a":
            repo.restore(p, e["snapshot"])               # stepflow may have died before its own reset
        e["restore_needed"] = False
        e[run] = {**e[run], "status": status, "adopted": True, "ended_at": _now(), "post": {},
                  "post_needed": self._post_needed(step, run)}
        if status == "stopped":
            prog["stopped_at"] = step
        _save(p, prog)
        self.log("run-adopted", arm=arm_name, step=step, run=run, status=status)
        return self.post(arm_name, step, run, prog)

    @staticmethod
    def _post_needed(step: int, run: str) -> list[str]:
        needed = (["mentions"] if step == 2 and run == "a" else []) + ["scan"]
        if run == "b":
            needed = (["detect"] if step == 2 else []) + ["tracker"] + needed + ["end_snapshot"]
        return needed

    def post(self, arm_name: str, step: int, run: str, prog: dict) -> str:
        p = Paths(self.pass_, arm_name)
        e = prog["steps"][str(step)]
        r = e[run]
        done = r.setdefault("post", {})
        out = p.step(step) / "a" if run == "a" else p.step(step)
        ctx = self.ctx(arm_name, step, out, e, run)
        for k in r.get("post_needed", []):
            if done.get(k):
                continue
            if k == "mentions":                          # 2.a: did the arm notice the hand edit? recorded, not scored
                files = sorted((out / "turns").glob("arm-*.stream.jsonl.gz")) + sorted((out / "transcripts").rglob("*.jsonl.gz"))
                qa = [json.loads(l) for l in (out / "questions.jsonl").read_text().splitlines() if l.strip()] \
                    if (out / "questions.jsonl").exists() else []
                _jw(p.step(2) / "hand-edit" / "detection-a.json",
                    {"run": "a", "session_mentions": handedit.mentions(files, handedit.NEEDLE),
                     "raised_with_po": sum(str(q.get("arm_message") or "").count(handedit.NEEDLE) for q in qa)})
            elif k == "detect":                          # stepflow's own layout: this run's arm streams + transcripts
                ed = e.get("edit") or {}
                edit = handedit.HandEdit(ed.get("sha", ""), ed.get("files", []), [], {}, ed.get("tries", 1), {})
                files = sorted((out / "turns").glob("arm-*.stream.jsonl.gz")) + sorted((out / "transcripts").rglob("*.jsonl.gz"))
                handedit.detect(ctx, edit, gitops.main_sha(p) or "", arm_files=files)
            elif k == "tracker":
                def track():
                    snap = tracker.snapshot(ctx)
                    if step == 6 and e.get("issue"):
                        _jw(out / "tracker-round-trip.json", tracker.round_trip_facts(
                            ctx, tracker.IssueRef(**e["issue"]), e["sha_before"], gitops.main_sha(p) or "", snap))
                self.infra("infra-tracker", arm_name, step, run, "the tracker snapshot", track)
            elif k == "scan":                            # review S-2: before the step counts as done
                own = secrets.own_pat_values(p, ctx.arm, self.cred, keychain=self.keychain)                         # A5: the arm's own token
                if (files := secrets.redact([p.step(step)], own)):
                    self._violation(p, {"step": step, "run": run, "kind": "own-token-in-evidence", "files": files[:50]})
                if (found := secrets.scan_step(p, step, self.lits)):
                    self.fault(secrets.SecretFound("secret-in-evidence", found), arm_name, step, run,
                               f"secret in {p.step(step)} ({secrets.describe(found)}); scrub it, then run again")
            elif k == "end_snapshot":
                repo.snapshot(p, f"{step:02d}-end")
            done[k] = True
            _save(p, prog)
        if run == "a":
            return "complete"
        if e.get("review") in ("continue", "pause"):
            return "complete"
        md = (out / "summary.md").read_text() if (out / "summary.md").exists() else \
            f"# Step {step} summary — {arm_name} ({self.pass_})\n\n(no summary.md)\n"
        got = self.owner.step_review(md)
        if isinstance(got, owner_mod.Park):
            e["review"] = "parked"; _save(p, prog)
            return self.park(arm_name, step, "b", "review", got)
        decision, secs = got
        e["review"], e["review_seconds"] = ("pause" if decision == "pause" else "continue"), secs
        _save(p, prog)
        return "pause" if decision == "pause" else "complete"

    def _aside(self, p: Paths, step: int, run: str, why: str) -> Path | None:
        """Move a run's evidence out of the way: `NN/a-<why>-<k>/`, or everything of the step dir that belongs to
        run b into `NN/b-<why>-<k>/` (N.a's `a/`, the hand edit, the precheck and the issue records stay)."""
        d = p.step(step)
        k = 1
        while (d / f"{run}-{why}-{k}").exists():
            k += 1
        dest = d / f"{run}-{why}-{k}"
        if run == "a":
            if not (d / "a").exists():
                return None
            shutil.move(str(d / "a"), str(dest))
            return dest
        moving = [x for x in d.iterdir() if x.name not in KEEP_ON_B_ASIDE and not re.match(r"[ab]-\w+-\d+$", x.name)] \
            if d.is_dir() else []
        if not moving:
            return None
        dest.mkdir(parents=True)
        for x in moving:
            shutil.move(str(x), str(dest / x.name))
        return dest

    # -- the consistency check -----------------------------------------------------------------------------------
    def consistency(self, step: int) -> str | None:
        """None when confirmed (or nothing new); "parked" or raises _Stop otherwise."""
        f = paths.RESULTS / self.pass_ / "consistency" / f"step-{step:02d}.json"
        rec = _jr(f) or {"pass": self.pass_, "step": step, "rounds": [], "confirmed": [], "status": None}
        brief = paths.brief_path(self.pass_)
        new = self._unconfirmed(_escalations(brief.read_text()), step, rec)
        if not new:
            if rec["status"] is None:
                rec["status"] = "nothing-new"; _jw(f, rec)
            return None
        sha0 = _sha(brief)
        rec.setdefault("brief_sha_before", sha0)
        while True:
            entries = _escalations(brief.read_text())
            new = self._unconfirmed(entries, step, rec)
            prior = [x for x in entries if x not in new]
            groups = _groups(new, prior)
            items = [(g["id"], _group_text(g)) for g in groups]
            got = self.owner.items(items)
            rnd = {"at": _now(), "groups": groups}
            if isinstance(got, owner_mod.Park):
                rnd["owner"] = {"park": dataclasses.asdict(got)}
                rec["rounds"].append(rnd); rec["status"] = "parked"; _jw(f, rec); _md(f, rec)
                return self.park(None, step, None, "consistency", got)
            rnd["owner"] = {k: {"ok": v[0], "note": v[1], "seconds": v[2]} for k, v in got.items()}
            rec["rounds"].append(rnd)
            if all(v[0] for v in got.values()):
                edited = _sha(brief) != rec["brief_sha_before"]
                # m-9: committed BEFORE the check is recorded, so a crash re-runs it; only when the brief really
                # differs from HEAD (follow-up 5: a crash just after the commit resumes without an empty commit)
                if edited and self.pass_ in REAL_PASSES and gitops.harness_differs_from_head(brief):
                    po.commit_brief(brief, self.pass_, "consistency-check", step)
                rec["confirmed"] += [x["text"] for x in new]
                rec.update(status="confirmed", brief_sha_after=_sha(brief), edited=edited, committed=edited)
                _jw(f, rec); _md(f, rec)     # atomic (fsutil)
                self.log("consistency-confirmed", step=step, groups=len(groups), edited=rec["edited"])
                return None
            rec["status"] = "editing"; _jw(f, rec); _md(f, rec)
            bad = ", ".join(k for k, v in got.items() if not v[0])
            ok = self.owner.confirm(f"Edit {brief} so the answers in {bad} are consistent (same question → same "
                                    f"answer), save it, then confirm to re-check")
            if isinstance(ok, owner_mod.Park):
                rec["status"] = "parked"; _jw(f, rec)
                return self.park(None, step, None, "consistency", ok)
            if not ok:
                rec["status"] = "declined"; _jw(f, rec)
                raise _Stop(f"consistency check of step {step} not confirmed")

    def _unconfirmed(self, entries: list[dict], step: int, rec: dict) -> list[dict]:
        """Answers escalated at step N, and at step N-1 (its N.b ran after N-1's check, fix round 1), that no check
        has confirmed yet."""
        prev = _jr(paths.RESULTS / self.pass_ / "consistency" / f"step-{step - 1:02d}.json", {}) or {}
        done = set(rec["confirmed"]) | set(prev.get("confirmed", []))
        return [x for x in entries if x["pass"] == self.pass_ and x["step"] in (step - 1, step) and x["text"] not in done]

    # -- suite resource exhaustion (design §9) ---------------------------------------------------------------------
    def suite_resource(self, step: int) -> None:
        f = paths.RESULTS / self.pass_ / "suite-resource" / f"step-{step:02d}.json"
        st = _jr(f, {}) or {}
        if st.get("open"):
            return
        since = st.get("resolved_at")
        recs = [r for r in faults.resource_records(self.pass_, step) if (since is None or r.get("at", "") > since)
                and r.get("run") == "b"]                  # follow-up 8: only the scored run counts (and re-runs)
        arms = sorted({r["arm"] for r in recs})
        if len(arms) < self.pins.limits.suite_resource_arms:
            return
        hf = HarnessFault("suite-resource", str(step), f"arms {arms} exhausted resources at step {step}")
        rerun = sorted({r["arm"] for r in recs if r.get("exhausted") == "repeat"})
        _jw(f, {"open": True, "arms": arms, "rerun_arms": rerun, "at": _now(), "resolved_at": since})
        action = faults.record(hf, self.pass_, "+".join(arms), step, 0, run="b")
        if not faults.halted(self.pass_):
            faults.halt(self.pass_, f"suite-resource:{step}: {len(arms)} arms exhausted resources at step {step} "
                                    f"(design §9: the suite, not the framework)",
                        {"kind": "suite-resource", "signature": str(step), "arms": arms, "rerun_after_fix": rerun,
                         "ledger_action": action})
        self.log("suite-resource", step=step, arms=arms, rerun=rerun)
        raise stepflow.Halt(faults.halted(self.pass_))

    # -- pending owner decisions: declared faults, suite-resource re-runs ---------------------------------------------
    def pending(self) -> None:
        for step in STEPS:
            f = paths.RESULTS / self.pass_ / "suite-resource" / f"step-{step:02d}.json"
            st = _jr(f, {}) or {}
            if st.get("open"):
                for a in st.get("rerun_arms", []):
                    if a in self.arms:
                        self._rerun_b(a, step)
                _jw(f, {**st, "open": False, "resolved_at": _now()})
        for a in self.arms:
            p = Paths(self.pass_, a)
            prog = _load(p)
            if prog.get("rerun"):
                self._rerun_step(a, int(prog["rerun"]))
            prog = _load(p)
            if prog.get("stale_issues"):
                self._close_stale(a, prog)
            prog = _load(p)
            for d in faults.entries(self.pass_):                  # `--scope retest` lives in the ledger
                key = f"{d.get('at')}|{d.get('signature')}|{d.get('step')}"
                if d.get("scope") == "retest" and d.get("arm") == a and d.get("pass") == self.pass_ \
                        and key not in prog["retests_done"]:
                    self._retest(a, int(d["step"]), d, key)

    def _rerun_b(self, arm_name: str, step: int) -> None:
        p = Paths(self.pass_, arm_name)
        prog = _load(p)
        e = prog["steps"].get(str(step)) or {}
        if not e.get("started"):
            return
        dest = self._aside(p, step, "b", "superseded")
        if prog.get("stopped_at") == step and (p.results / "arm-result.json").exists():
            shutil.move(str(p.results / "arm-result.json"), str((dest or p.step(step)) / "arm-result.json"))
            prog["stopped_at"] = None
        e.pop("b", None); e.pop("review", None)
        e["restore_needed"] = True
        prog["finished"] = {"bundle": False, "arm_result": False, "published": None}
        _save(p, prog)
        self.log("rerun-b", arm=arm_name, step=step, reason="suite-resource")

    def _rerun_step(self, arm_name: str, step: int) -> None:
        """`faults declare … --scope rerun-step`: this step and every later one are superseded and run again; the
        step's snapshot, sha_before, hand edit and issue are kept (never re-snapshotted, I-2)."""
        p = Paths(self.pass_, arm_name)
        prog = _load(p)
        for n in [n for n in STEPS if n >= step]:
            d = p.step(n)
            if d.exists():
                k = 1
                while (p.results / f"{n:02d}-superseded-{k}").exists():
                    k += 1
                sup = p.results / f"{n:02d}-superseded-{k}"
                shutil.move(str(d), str(sup))
                if n == step:
                    d.mkdir(parents=True)
                    for keep in ("hand-edit", "precheck", "substitute", "issue.json", "issue-body.md"):
                        if (sup / keep).is_dir():
                            shutil.copytree(sup / keep, d / keep)
                        elif (sup / keep).is_file():
                            shutil.copy2(sup / keep, d / keep)
                if n == step and (p.results / "arm-result.json").exists():
                    shutil.move(str(p.results / "arm-result.json"), str(sup / "arm-result.json"))
        e = prog["steps"].get(str(step)) or {}
        if step < 6:                                     # A3: step 6's issues are dropped here; close them later
            e6 = prog["steps"].get("6") or {}
            prog.setdefault("stale_issues", [])
            prog["stale_issues"] += [{"ref": e6[k], "run": "a" if k == "issue_a" else "b"}
                                     for k in ("issue", "issue_a") if e6.get(k)]
        keep = {k: e[k] for k in ("started", "snapshot", "sha_before", "hand_edit", "edit", "issue", "issue_fp",
                                  "issue_a", "issue_a_fp", "precheck", "substitute", "started_at") if k in e}
        prog["steps"] = {k: v for k, v in prog["steps"].items() if int(k) < step}
        if step < 2:                                     # step 2's entry (and its hand edit) is gone: so is its cost
            prog["teammate_turns"] = []
        if keep.get("started"):
            prog["steps"][str(step)] = {**keep, "restore_needed": True}
        if prog.get("stopped_at") and prog["stopped_at"] >= step:
            prog["stopped_at"] = None
        prog["finished"] = {"bundle": False, "arm_result": False, "published": None}
        prog["rerun"] = None
        _save(p, prog)
        self.log("rerun-step", arm=arm_name, step=step)

    def _retest(self, arm_name: str, step: int, declared: dict, key: str) -> None:
        """`faults declare … --scope retest`: hidden tests and quality again on the step's recorded `sha_after`,
        with no new arm session. The superseded results stay beside the new ones."""
        p = Paths(self.pass_, arm_name)
        prog = _load(p)
        d = p.step(step)
        sha = (_jr(d / "git.json", {}) or {}).get("sha_after")
        if not sha:                                      # refused once, recorded, never a permanent block
            f = p.results / "retest-refused.json"
            why = (f"step {step} has no recorded sha_after ({d / 'git.json'}): nothing to re-test. The declaration "
                   f"is refused and will not be retried; once the step has run, declare it again "
                   f"(`runner faults declare {self.pass_} {arm_name} {step} <slug> --scope retest`).")
            _jw(f, (_jr(f, []) or []) + [{"at": _now(), "step": step, "declared": declared, "why": why}])
            prog["retests_done"].append(key)
            _save(p, prog)
            self.log("retest-refused", arm=arm_name, step=step, why=why)
            print(f"retest refused ({arm_name}): {why}")
            return
        k = 1
        while (d / f"retest-{k}.json").exists():
            k += 1
        for name in ("hidden", "quality"):
            if (d / name).exists():
                shutil.move(str(d / name), str(d / f"{name}-superseded-{k}"))
        def retest():
            prep = hidden.prepare(p, sha, f"{step:02d}-retest{k}", d, with_quality=True, require_main=False)
            return prep, hidden.run(p, prep.hidden_copy, step, d,
                                    install_failed=not prep.prep.get("hidden", {}).get("ok"),
                                    install=hidden.install_record(prep.prep.get("hidden")))
        prep, s = self.infra("infra-hidden", arm_name, step, "b", "the declared re-test", retest)
        q = self.infra("infra-quality", arm_name, step, "b", "the declared re-test's quality",
                       lambda: quality.run_all(p, prep, d, self.pins))
        _jw(d / f"retest-{k}.json", {"sha": sha, "at": _now(), "passed": s.passed, "total": s.total,
                                    "attribution": s.attribution, "quality": q, "declared": declared})
        prog["retests_done"].append(key)
        _save(p, prog)
        self.log("retest", arm=arm_name, step=step, sha=sha)

    # -- the end of an arm -------------------------------------------------------------------------------------
    def finish(self, arm_name: str) -> None:
        p = Paths(self.pass_, arm_name)
        prog = _load(p)
        fin = prog["finished"]
        if not fin.get("bundle"):
            repo.bundle(p, p.results / "repo.bundle")
            fin["bundle"] = True; _save(p, prog)
        if not fin.get("arm_result"):
            if prog.get("stopped_at") is None:
                _jw(p.results / "arm-result.json", {"completed": True, "last_step": 7, "at": _now()})
            fin["arm_result"] = True; _save(p, prog)
        arm = config.load_arm(arm_name)
        if fin.get("published") is None and config.github_slug(self.pass_, arm_name) and not arm.dry:
            lits = secrets.literals(self.cred, require_oauth=True)
            try:
                ok = repo.publish(p, self.pass_, self.guard.confirm,
                                  lambda tree, history: secrets.scan_publish(tree, history, lits))
            except _OwnerParked as x:
                self.park(arm_name, None, None, "publish", x.park)
                return
            except secrets.SecretFound as f:
                self.fault(f, arm_name, 7, None, "secret in what publish would push; nothing was pushed")
            fin["published"] = bool(ok)
            _save(p, prog)
            self.log("published" if ok else "publish-declined", arm=arm_name)

    # -- state -----------------------------------------------------------------------------------------------
    def stopped_before(self, arm_name: str, step: int) -> bool:
        s = _load(Paths(self.pass_, arm_name)).get("stopped_at")
        return s is not None and s < step

    def is_complete(self, arm_name: str, step: int, run: str) -> bool:
        e = _load(Paths(self.pass_, arm_name))["steps"].get(str(step)) or {}
        return _complete(e, run)

    def finished(self, arm_name: str) -> bool:
        prog = _load(Paths(self.pass_, arm_name))
        fin = prog["finished"]
        needs_publish = config.github_slug(self.pass_, arm_name) and not config.load_arm(arm_name).dry
        return fin.get("bundle") and fin.get("arm_result") and (fin.get("published") is not None or not needs_publish)


def _result(R: _Run, arms: list[str], **kw) -> dict:
    out: dict = {**kw}
    if R.parked:
        out["parked"] = R.parked
    out["arms"] = {}
    for a in arms:
        prog = _load(Paths(R.pass_, a))
        out["arms"][a] = {"stopped_at": prog.get("stopped_at"), "finished": prog["finished"]}
    return out


def _run(pass_: str, arms: list[str], cred, owner, *, limits_override: dict | None = None,
         stop_after: int | None = None) -> dict:
    """The step-major run. The caller holds `preflight.lock()` (fix round 1: the lock comes before every
    pre-check and before any setup)."""
    if faults.halted(pass_):
        raise NotReady(f"bake-off halted (design §9): {faults.halt_reason(pass_)}")
    pins = config.load_pins()
    if limits_override:
        if not all(config.load_arm(a).dry for a in arms):
            raise PermissionError("limits_override is for dry-run arms only")
        pins = dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, **limits_override))
    if not paths.brief_path(pass_).is_file():
        raise NotReady(f"no PO brief at {paths.brief_path(pass_)}")
    for a in arms:
        p = Paths(pass_, a)
        checklist.require_clean_green(p)                  # design §6: no step before a clean, green setup
        preflight.check_images(a, p)                      # design §2: the locked images, the baked reference
        if config.github_disc_slug(pass_, a):             # follow-up 6: N.a's PAT, before any step starts
            checklist.require_disc_pat(pass_, config.load_arm(a))
    docker.sweep()
    # A dry pass never touches the keychain (Task 24): its only credential is the dummy, so the dummy token (and any
    # arm-home PAT value) is what its scans look for; a real pass adds every keychain value.
    dry = all(config.load_arm(a).dry for a in arms)
    lits = secrets.literals(cred, keychain=not dry)
    for a in arms:
        _scan_setup(pass_, a, lits, cred)                 # m-7: no step before a clean setup scan
    R = _Run(pass_, arms, cred, owner, pins, lits)
    R.keychain = not dry                                  # a dry pass never touches the keychain (Task 24)
    try:
        R.pending()
        for step in range(1, (stop_after or 7) + 1):
            live = [a for a in arms if not R.stopped_before(a, step)]
            if not live:
                break
            for run in RUNS:
                pending_b = run == "b" and not all(R.is_complete(a, step, "b") for a in live)
                if pending_b and R.consistency(step) == "parked":     # only before a scored run is due
                    return _result(R, arms)
                for a in live:
                    got = R.run_one(a, step, run)
                    if got == "pause":
                        return _result(R, arms, paused_after={"arm": a, "step": step})
                    if run == "b" and got == "complete":
                        R.suite_resource(step)
                if not all(R.is_complete(a, step, run) for a in live):
                    return _result(R, arms)              # the phase barrier: parked items first
        if stop_after:
            return _result(R, arms, stopped_after=stop_after)
        for a in arms:
            R.finish(a)
        return _result(R, arms, completed=all(R.finished(a) for a in arms))
    except _Stop as s:
        return _result(R, arms, declined=str(s))


def _single(res: dict, arm: str) -> dict:
    """run_arm's shape (Task 24): {"completed": True} | {"stopped_at": n} | {"paused_after": n} | {"stopped_after": n}
    | {"parked": [...]} | {"declined": why}. An arm that stopped (design §9) is reported as `stopped_at`, also when a
    canary's `stop_after` would otherwise end the run (fix round 1)."""
    if "declined" in res:
        return {"declined": res["declined"]}
    if "paused_after" in res:
        return {"paused_after": res["paused_after"]["step"]}
    if "parked" in res:
        return {"parked": res["parked"]}
    a = res["arms"][arm]
    if a["stopped_at"] is not None and (res.get("completed") or "stopped_after" in res):
        return {"stopped_at": a["stopped_at"]}
    if "stopped_after" in res:
        return {"stopped_after": res["stopped_after"]}
    return {"completed": True} if res.get("completed") else {"incomplete": res}


def run_arm(pass_: str, arm: str, cred, owner, limits_override: dict | None = None,
            stop_after: int | None = None) -> dict:
    """One arm, step-major, resumable. For the canary (`stop_after`, Task 26) and dry passes (`limits_override`, dry
    arms only, Task 24); refused on the real pass, where `run_pass` keeps every arm in step (N.a, check, N.b)."""
    if pass_ in REAL_PASSES:
        raise NotReady(f"{pass_} is step-major across every arm: use `runner run-pass {pass_}`")
    brief = paths.brief_path(pass_)
    if pass_ == "canary" and not brief.exists():           # m-8: the canary's own copy (Task 26), made once
        brief.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / "scenario" / "po-brief.md", brief)
    with preflight.lock():
        return _single(_run(pass_, [arm], cred, owner, limits_override=limits_override, stop_after=stop_after), arm)


def run_pass(pass_: str, cred, owner) -> dict:
    """Every arm in `results/<pass>/order.json`, step-major. An arm with no state, or whose setup was parked, is set
    up first once the owner confirms (setup runs once per arm). The lock is taken before anything else."""
    rec = _jr(paths.RESULTS / pass_ / "order.json")
    if not rec:
        raise NotReady(f"no results/{pass_}/order.json: run `runner order {pass_} [--seed N]` first")
    arms = list(rec["order"])
    with preflight.lock():
        for a in arms:
            p = Paths(pass_, a)
            parked_setup = (p.setup_results / "parked.json").is_file()
            if p.base.exists() and not parked_setup:
                continue
            got = owner.confirm(f"Set up {a} for {pass_} now (owner present)?")
            if isinstance(got, owner_mod.Park):
                return {"parked": [{"arm": a, "step": 0, "run": None, "what": "setup"}]}
            if not got:
                return {"declined": f"setup of {a}"}
            try:
                r = _setup(pass_, a, cred, owner, again=parked_setup)
            except checklist.SetupParked:
                return {"parked": [{"arm": a, "step": 0, "run": None, "what": "setup"}]}
            if not r.green:
                raise NotReady(f"{a}: setup is not green — see results/{pass_}/{a}/00-setup")
        return _run(pass_, arms, cred, owner)


# ---- setup once per arm -----------------------------------------------------------------------------------------

def setup(pass_: str, arm: str, cred, owner, again: bool = False):
    """`checklist.run_setup`, once per arm, under the runner lock. `again` (after a setup harness fault or a parked
    setup): the arm's state is moved aside first (`repo.init` refuses an existing base), and its `00-setup` evidence
    kept as `00-setup-superseded-<k>`; refused once any step has started. A harness fault during setup is recorded
    (step 0); an owner park ends setup as parked (`checklist.SetupParked`, recorded in `00-setup/parked.json`)."""
    with preflight.lock():
        return _setup(pass_, arm, cred, owner, again)


def _scan_setup(pass_: str, arm: str, lits, cred=None) -> None:
    """m-7: `00-setup` (shell logs, setup transcripts, shell history) is secret-scanned when setup ends, not only
    at close-out; recorded in `00-setup/secret-scan.json`. The arm's own PAT is redacted first (A5); anything left
    is `secret-in-evidence` at step 0 (the owner scrubs it; a repeat halts). A clean record is not scanned again."""
    p = Paths(pass_, arm)
    f = p.setup_results / "secret-scan.json"
    if (_jr(f) or {}).get("clean") is True or not p.setup_results.is_dir():
        return
    lits = lits() if callable(lits) else lits        # the setup path computes them only when there is evidence
    redacted = secrets.redact([p.setup_results], secrets.own_pat_values(p, config.load_arm(arm), cred))
    found = secrets.scan_tree(p.setup_results, lits) + secrets.scan_files(secrets.ledger_files(pass_), lits)
    _jw(f, {"at": _now(), "clean": not found, "findings": [f"{x.path}:{x.line} {x.kind}" for x in found[:50]],
            "redacted_own_token": redacted[:50]})
    if found:
        sf = secrets.SecretFound("secret-in-evidence", found)
        if faults.record(sf, pass_, arm, 0, 0) == "halt":
            raise stepflow.Halt(faults.halted(pass_)) from sf
        raise NotReady(f"harness fault secret-in-evidence:{sf.signature} in {p.setup_results} "
                       f"({secrets.describe(found)}); scrub it, then run again")


def _setup(pass_: str, arm: str, cred, owner, again: bool = False):
    p = Paths(pass_, arm)
    if p.base.exists():
        if not again:
            raise NotReady(f"{p.base} exists: setup runs once per arm (`runner setup {pass_} {arm} --again` moves "
                           f"it aside after a setup fault or park)")
        if any(e.get("started") for e in _load(p)["steps"].values()):
            raise NotReady(f"{arm}: a step has started; its state is evidence and is never moved aside")
        p.base.rename(p.base.with_name(f"{arm}.aside-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"))
        if p.setup_results.exists():
            k = 1
            while (p.results / f"00-setup-superseded-{k}").exists():
                k += 1
            shutil.move(str(p.setup_results), str(p.results / f"00-setup-superseded-{k}"))
    try:
        r = checklist.run_setup(pass_, arm, cred, owner)
        _scan_setup(pass_, arm, lambda: secrets.literals(cred, keychain=not config.load_arm(arm).dry), cred)   # m-7
        return r
    except checklist.SetupParked as x:
        rec = {"at": _now(), "park": dataclasses.asdict(x.park) if dataclasses.is_dataclass(x.park) else str(x.park)}
        _jw(p.setup_results / "parked.json", rec)
        _log_line(pass_, {"at": _now(), "event": "parked", "arm": arm, "step": 0, "run": None, "what": "setup",
                          "park": rec["park"]})
        raise
    except HarnessFault as f:
        action = faults.record(f, pass_, arm, 0, 0)
        if action == "halt":
            raise stepflow.Halt(faults.halted(pass_)) from f
        raise NotReady(f"harness fault {f.kind}:{f.signature} during setup of {arm}; fix it, then "
                       f"`runner setup {pass_} {arm} --again`") from f


# ---- the brief's escalated answers (the consistency check) --------------------------------------------------------

_ENTRY = re.compile(r"^- \*\*Q:\*\* (?P<q>.*?) \*\*A:\*\* (?P<a>.*?)(?: _\((?P<meta>[^()]*)\)_)?\s*$", re.S)
_META = re.compile(r"(?P<date>[^;]*); (?P<pass>[^;]*); first raised by (?P<arm>\S+) at step (?P<step>\d+);")
_WORD = re.compile(r"[a-z0-9]+")


def _escalations(text: str) -> list[dict]:
    span = po._section_span(text)
    if span is None:
        return []
    groups: list[list[str]] = []
    for line in text[span[0]:span[1]].splitlines():
        if line.startswith("  ") and groups:
            groups[-1].append(line)
        elif line.startswith("- **Q:**"):
            groups.append([line])
    out = []
    for g in groups:
        t = "\n".join(g)
        m = _ENTRY.match(t)
        if not m:
            continue
        meta = _META.search(m.group("meta") or "")
        out.append({"text": t, "question": m.group("q").strip(), "answer": m.group("a").strip(),
                    "arm": meta.group("arm") if meta else None, "step": int(meta.group("step")) if meta else None,
                    "pass": meta.group("pass").strip() if meta else None})
    return out


def _norm(s: str) -> str:
    return " ".join(_WORD.findall(s.lower()))


def _overlap(a: str, b: str) -> float:
    x, y = set(_WORD.findall(a.lower())), set(_WORD.findall(b.lower()))
    return len(x & y) / len(x | y) if x | y else 0.0


OVERLAP = 0.5


def _groups(new: list[dict], prior: list[dict]) -> list[dict]:
    by: dict[str, dict] = {}
    for x in new:
        g = by.setdefault(_norm(x["question"]), {"question": x["question"], "answers": []})
        g["answers"].append({"arm": x["arm"], "answer": x["answer"], "step": x["step"]})
    groups = list(by.values())
    for i, g in enumerate(groups, 1):
        g["id"] = f"Q{i}"
        g["conflict"] = len({_norm(a["answer"]) for a in g["answers"]}) > 1
    for g in groups:
        g["overlaps"] = [h["id"] for h in groups if h is not g and _overlap(g["question"], h["question"]) >= OVERLAP]
        g["earlier"] = [{"question": x["question"], "answer": x["answer"], "arm": x["arm"], "step": x["step"]}
                        for x in prior if _overlap(g["question"], x["question"]) >= OVERLAP]
    return groups


def _group_text(g: dict) -> str:
    lines = [f"Question: {g['question']}"]
    lines += [f"  {a['arm']} (step {a.get('step')}): {a['answer']}" for a in g["answers"]]
    if g["conflict"]:
        lines.append("  CONFLICT: different answers to the same question")
    if g["overlaps"]:
        lines.append(f"  OVERLAPS {', '.join(g['overlaps'])} (a similar question this step)")
    for x in g["earlier"]:
        lines.append(f"  OVERLAPS an earlier answer (step {x['step']}, {x['arm']}): {x['question']} → {x['answer']}")
    lines.append("  Consistent with each other? Consistency with the brief's own text (its standing answers in "
                 "scenario/po-brief.md) is your call: this check compares escalated answers only.")
    return "\n".join(lines)


def _md(f: Path, rec: dict) -> None:
    lines = [f"# Consistency check — {rec['pass']} step {rec['step']}: {rec['status']}", ""]
    for i, rnd in enumerate(rec["rounds"], 1):
        lines += [f"## Round {i} ({rnd['at']})", ""]
        for g in rnd["groups"]:
            lines += [f"### {g['id']}", "", _group_text(g), ""]
        lines += [f"Owner: {json.dumps(rnd.get('owner'))}", ""]
    fsutil.write_text(f.with_suffix(".md"), "\n".join(lines))


# ---- close-out and status -----------------------------------------------------------------------------------------

def close_out(pass_: str, owner) -> Path:
    """The end of a run (review S-2): every arm finished, a secret scan of `results/<pass>` and the ledger clean, every
    bundle present, publishing finished, and every run PAT revoked (the owner confirms each — a park or a "no" is not
    a confirmation). Written to `results/<pass>/close-out.md`; `NotReady` unless every item holds."""
    rec = _jr(paths.RESULTS / pass_ / "order.json") or {}
    arms = rec.get("order") or (sorted(x.name for x in (paths.STATE / pass_).iterdir()
                                       if (x / "progress.json").exists()) if (paths.STATE / pass_).is_dir() else [])
    missing = [a for a in arms if not (Paths(pass_, a).results / "arm-result.json").exists()]
    if missing:
        raise NotReady(f"{pass_}: not finished: {missing}")
    lits = secrets.literals()
    found = secrets.scan_tree(paths.RESULTS / pass_, lits) + secrets.scan_files(secrets.ledger_files(pass_), lits)
    no_bundle = [a for a in arms if not (Paths(pass_, a).results / "repo.bundle").is_file()]
    pats = [(f"pat-{a}", f"The fine-grained PAT bakeoff-gh-{pass_}-{a} is revoked (GitHub → Settings → Developer "
                         f"settings → Fine-grained tokens)")
            for a in arms if config.load_arm(a).tracker == "github" and config.github_slug(pass_, a)
            and not config.load_arm(a).dry]
    pats += [(f"pat-disc-{a}", f"The fine-grained PAT bakeoff-gh-{pass_}-disc-{a} (the N.a discovery repo) is revoked")
             for a in arms if config.github_disc_slug(pass_, a)]
    unpublished = [a for a in arms if config.github_slug(pass_, a) and not config.load_arm(a).dry
                   and (_load(Paths(pass_, a))["finished"].get("published") is not True)]
    esc7 = []                                        # no later consistency check covers step 7's N.b answers
    for a in arms:
        qa = [json.loads(l) for l in (Paths(pass_, a).step(7) / "questions.jsonl").read_text().splitlines()
              if l.strip()] if (Paths(pass_, a).step(7) / "questions.jsonl").is_file() else []
        esc7 += [(f"esc7-{a}-{k}", f"{a}: step 7 N.b escalation (no later consistency check covers it): "
                                   f"{', '.join(q['escalated'])} → {q.get('reply')}. Consistent with the brief and "
                                   f"the earlier answers?")
                 for k, q in enumerate([q for q in qa if q.get("escalated")], 1)]
    asks = pats + esc7
    got = owner.items(asks) if asks else {}
    lines = [f"# Close-out — {pass_} (review S-2)", "", f"- secret scan: {'clean' if not found else 'FINDINGS'}"]
    lines += [f"  - {f.path}:{f.line} {f.kind}" for f in found[:50]]
    lines.append(f"- bundles: {'all present' if not no_bundle else 'MISSING ' + ', '.join(no_bundle)}")
    lines.append(f"- publish: {'finished' if not unpublished else 'NOT FINISHED ' + ', '.join(unpublished)}")
    not_revoked: list[str] = []
    not_confirmed: list[str] = []
    if isinstance(got, owner_mod.Park):
        lines.append("- PAT revocation and step-7 escalations: PARKED — run `runner close-out` again with the owner "
                     "present")
        not_revoked = [i for i, _ in pats]
        not_confirmed = [i for i, _ in esc7]
    else:
        for iid, text in asks:
            ok, note, _ = got.get(iid, (False, "", 0.0))
            if ok is not True:
                (not_revoked if iid.startswith("pat-") else not_confirmed).append(iid)
            lines.append(f"- [{'x' if ok is True else ' '}] {iid}: {text}{' — ' + note if note else ''}")
    if not esc7:
        lines.append("- step 7 N.b escalations: none")
    lines.append(f"- brief at close: sha256 {_sha(paths.brief_path(pass_))}")
    problems = ([f"secret scan: {len(found)} finding(s)"] if found else []) + \
        ([f"bundle missing: {no_bundle}"] if no_bundle else []) + \
        ([f"publish not finished: {unpublished}"] if unpublished else []) + \
        ([f"PAT revocation not confirmed: {not_revoked}"] if not_revoked else []) + \
        ([f"step-7 escalations not confirmed: {not_confirmed}"] if not_confirmed else [])
    if not problems and pass_ in REAL_PASSES:            # OWNER: the arm's history to its final PRIVATE repo
        problems += _publish_final(pass_, arms, owner, lines)
    lines.append(f"\n**Result: {'CLOSED' if not problems else 'NOT CLOSED — ' + '; '.join(problems)}**")
    f = paths.RESULTS / pass_ / "close-out.md"
    fsutil.write_text(f, "\n".join(lines) + "\n")
    if problems:                                     # fix round 1: a close-out is all or nothing
        raise NotReady(f"{pass_} close-out refused: {'; '.join(problems)} (see {f})")
    return f


def _publish_final(pass_: str, arms: list[str], owner, lines: list[str]) -> list[str]:
    """OWNER (2026-09-30): each real arm's history goes to `troupe-run/bakeoff-specs-<arm>`, created PRIVATE via the
    owner's `gh` if absent (the owner changes visibility later). A repo that exists and is not private is never
    published to, and never changed. Recorded in progress (`finished.final`), so each arm is published once."""
    problems, guard = [], _Guard(owner)
    lits = None
    for a in arms:
        arm, p = config.load_arm(a), Paths(pass_, a)
        if arm.dry:
            continue
        prog = _load(p)
        slug = config.github_final_slug(a)
        if (prog["finished"].get("final") or {}).get("published"):
            lines.append(f"- {slug}: published earlier")
            continue
        state = repo.ensure_private_repo(slug, f"bakeoff-specs arm: {arm.tool} {arm.version} (the bake-off's result)")
        if state not in ("created", "exists"):
            problems.append(f"{slug} is {state.removeprefix('exists-')} (public or unknown): not published")
            lines.append(f"- {slug}: {state} — NOT published (the runner never publishes to a non-private repo)")
            continue
        lits = lits if lits is not None else secrets.literals(require_oauth=True)
        try:
            ok = repo.publish(p, pass_, guard.confirm, lambda tree, history: secrets.scan_publish(tree, history, lits),
                              slug=slug)
        except _OwnerParked:
            ok = False
        prog["finished"]["final"] = {"slug": slug, "repo": state, "published": bool(ok), "at": _now()}
        _save(p, prog)
        lines.append(f"- {slug}: {'created private' if state == 'created' else 'exists (private)'}, "
                     f"{'published' if ok else 'NOT published (declined or parked)'}")
        if not ok:
            problems.append(f"{slug}: not published")
    return problems


def status() -> str:
    rows = []
    if not paths.STATE.is_dir():
        return ""
    for pass_dir in sorted(x for x in paths.STATE.iterdir() if x.is_dir()):
        h = faults.halted(pass_dir.name) if faults.valid_name(pass_dir.name) else None
        if h:
            rows.append(f"{pass_dir.name}: HALTED")
        for arm_dir in sorted(x for x in pass_dir.iterdir() if (x / "progress.json").is_file()):
            prog = _load(Paths(pass_dir.name, arm_dir.name))
            cells = []
            for n in STEPS:
                e = prog["steps"].get(str(n))
                if not e:
                    continue
                runs = [f"{r}={e[r]['status']}" for r in RUNS if e.get(r)]
                if e.get("review") == "parked":
                    runs.append("review=parked")
                cells.append(f"{n}:{','.join(runs) or 'started'}")
            end = f" stopped_at={prog['stopped_at']}" if prog.get("stopped_at") else ""
            rows.append(f"{pass_dir.name:8} {arm_dir.name:12} {' '.join(cells)}{end} finished={prog['finished']}")
    return "\n".join(rows)


# ---- the dry run (Task 24) ------------------------------------------------------------------------------------------
# The whole runner end to end with the fake claude as arm, PO and teammate (no model, no GitHub), the dummy credential
# and the scripted owner. Each pass is the step-major structure of the real run for one arm: N.a (discovery, reset),
# the consistency check, N.b. `limits_override` is for dry arms only: a 1 s transient backoff, a smaller mutation
# budget (quality.run_all's "cheaper mutation budget"), and dry4's 20 s turn limit (the fake hangs for 120 s).
DRY_TOKEN = "dry-run-dummy-token"
_DRY_LIMITS = {"transient_backoff": [1, 1, 1], "mutation_sample": 20, "mutation_seconds": 600}
DRY = [("dry1", "dryrun", "dryrun-owner.toml", dict(_DRY_LIMITS)),
       ("dry2", "dryrun-broken", "dryrun-owner.toml", dict(_DRY_LIMITS)),
       ("dry3", "dryrun-pinfault", "dryrun-owner.toml", dict(_DRY_LIMITS)),
       ("dry4", "dryrun-edge", "dryrun-owner-dry4.toml", {**_DRY_LIMITS, "turn_seconds": 20})]
# Task 18's PLAN-2 NOTE: hidden tests whose harness plumbing only a full run exercises; dry1 must pass them.
PLAN2_NOTE = {2: "tests/hidden/test_step2_sync.py::test_watch_picks_up_an_edit_to_an_included_file",
              4: "tests/hidden/test_step4_lineage.py::test_cli_actor_defaults_to_the_login_user",
              7: "tests/hidden/test_step7_remote_schema.py::test_remote_yaml_and_text_includes_load"}


def dry_run() -> dict:
    """The four dry passes (plan Task 24), each from nothing: state and results removed, a fresh copy of the PO brief,
    setup (once, under the runner lock), then `run_arm`; dry4 pauses after step 1 and is resumed. Every container
    spec built is recorded, and those carrying the dummy token are counted (`results/dryrun-specs.json`)."""
    from runner import credentials
    cred, res = credentials.dummy(), {}
    with docker.recording() as specs:
        for pass_, arm_name, script, limits in DRY:
            shutil.rmtree(paths.STATE / pass_, ignore_errors=True)
            shutil.rmtree(paths.RESULTS / pass_, ignore_errors=True)
            (paths.STATE / pass_).mkdir(parents=True)
            shutil.copy(REPO_ROOT / "scenario" / "po-brief.md", paths.brief_path(pass_))
            o = owner_mod.ScriptedOwner(config.CONFIG_DIR / script).bind(config.load_arm(arm_name))
            try:
                s = setup(pass_, arm_name, cred, o)                 # a Halt here is this pass's result too
                if not s.green:
                    res[pass_] = {"setup_not_green": [c.id for c in s.checks if c.status != "ok"]}
                    continue
                r = run_arm(pass_, arm_name, cred, o, limits)
                if "paused_after" in r or "paused_at" in r:     # dry4: paused by the owner, then resumed
                    _jw(Paths(pass_, arm_name).results / "resume.json", r)
                    r = run_arm(pass_, arm_name, cred, o, limits)
                res[pass_] = r
            except stepflow.Halt as h:
                res[pass_] = {"halted": str(h)[:500]}
    bad = sum(1 for s in specs if DRY_TOKEN in json.dumps(s.env) or any(DRY_TOKEN in x for x in s.cmd))
    _jw(paths.RESULTS / "dryrun-specs.json", {"specs": len(specs), "specs_containing_token": bad})
    return res


def _dry_facts() -> list[str]:
    """What dry1 shows about the run structure and the hidden tests (read from its evidence; absent → says so)."""
    p = Paths("dry1", "dryrun")
    lines = ["", "## dry1: N.a → reset → consistency check → N.b, per step", ""]
    for n in STEPS:
        d = _jr(p.step(n) / "a" / "discovery.json", {}) or {}
        why = (d.get("discovery") or {}).get("why") or d.get("outcome") or "no N.a record"
        s = _jr(p.step(n) / "hidden" / "summary.json", {}) or {}
        c = (_jr(paths.RESULTS / "dry1" / "consistency" / f"step-{n:02d}.json", {}) or {}).get("status")
        lines.append(f"- step {n}: N.a stopped at {why}; consistency check {c or 'no record'}; N.b hidden "
                     f"{s.get('passed', '?')}/{s.get('total', '?')} passed, {s.get('failed', '?')} failed")
    lines += ["", "## Task 18 PLAN-2 NOTE tests in dry1", ""]
    for n, t in PLAN2_NOTE.items():
        tests = (_jr(p.step(n) / "hidden" / "summary.json", {}) or {}).get("tests", {})
        got = next((o for k, o in tests.items() if k.endswith(t.split("::")[-1])), "not run")
        lines.append(f"- step {n}: `{t}`: {got}")
    return lines


def dry_results() -> dict:
    """The four passes' results read back from their evidence (to regenerate the report without re-running):
    `arm-result.json` (completed / stopped_at), `HALTED` (halted), dry4's `resume.json` counting only when the arm
    then completed."""
    out: dict = {}
    for pass_, arm_name, _, _ in DRY:
        p = Paths(pass_, arm_name)
        halted = paths.RESULTS / pass_ / "HALTED"
        ar = _jr(p.results / "arm-result.json", {}) or {}
        if halted.is_file():
            out[pass_] = {"halted": halted.read_text()[:500]}
        elif ar.get("completed") is True:
            out[pass_] = {"completed": True}
        elif ar.get("stopped_at") is not None:
            out[pass_] = {"stopped_at": ar["stopped_at"]}
        else:
            out[pass_] = {"incomplete": True}
    return out


def _gate_dry1() -> list[tuple[str, bool, str]]:
    p = Paths("dry1", "dryrun")
    want = {1: 101, 2: 109, 3: 121, 4: 135, 5: 146, 6: 151, 7: 161}
    counts, shas, pins = [], [], []
    for n in STEPS:
        s = _jr(p.step(n) / "hidden" / "summary.json", {}) or {}
        counts.append((n, s.get("total"), s.get("passed"), s.get("failed"), s.get("flaky"), s.get("flaky_arm")))
        a = (_jr(p.step(n) / "a" / "discovery.json", {}) or {}).get("sha_before")
        b = (_jr(p.step(n) / "git.json", {}) or {}).get("sha_before")
        shas.append((n, a, b))
        for run, f in (("a", p.step(n) / "a" / "model-pin.json"), ("b", p.step(n) / "model-pin.json")):
            pin = _jr(f, {}) or {}
            if not (pin.get("ok") is True and not pin.get("violations")):
                pins.append(f"{n}.{run}")
    probe = _jr(p.step(2) / "hand-edit" / "probe.json", {}) or {}
    return [("dry1 hidden counts", all((t, ps, fl, fk, fa) == (want[n], want[n], 0, 0, 0)
                                       for n, t, ps, fl, fk, fa in counts),
             "; ".join(f"{n}: {ps}/{t} passed, {fl} failed (want {want[n]})" for n, t, ps, fl, fk, fa in counts)),
            ("dry1 N.a/N.b sha_before", all(a and a == b for _, a, b in shas),
             "; ".join(f"{n}: {str(a)[:10]} {'=' if a and a == b else '!='} {str(b)[:10]}" for n, a, b in shas)),
            ("dry1 hand-edit probe", bool(probe) and all(v is True for v in probe.values()), json.dumps(probe)),
            ("dry1 model pin", not pins, f"violations or not ok at: {pins}" if pins else "ok for every N.a and N.b")]


def _gate_dry2() -> list[tuple[str, bool, str]]:
    ar = _jr(Paths("dry2", "dryrun-broken").results / "arm-result.json", {}) or {}
    ok = ar.get("stopped_at") == 2 and ar.get("reason") == "no progress in 3 attempts"
    return [("dry2 stop rule", ok, f"stopped_at {ar.get('stopped_at')}; reason {ar.get('reason')!r}")]


def _gate_dry3() -> list[tuple[str, bool, str]]:
    f = paths.RESULTS / "dry3" / "faults.jsonl"
    led = [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.is_file() else []
    got = [(e.get("kind"), e.get("signature"), e.get("action")) for e in led]
    want = [("model-pin", "claude-haiku-4-5", "rerun"), ("model-pin", "claude-haiku-4-5", "halt")]
    ok = got == want and (paths.RESULTS / "dry3" / "HALTED").is_file()
    return [("dry3 halt rule", ok, f"ledger {got}; HALTED {'present' if (paths.RESULTS / 'dry3' / 'HALTED').is_file() else 'absent'}")]


def _gate_dry4() -> list[tuple[str, bool, str]]:
    p = Paths("dry4", "dryrun-edge")
    iv = (_jr(p.step(1) / "run.json", {}) or {}).get("interventions") or []
    br = _jr(p.results / "breaches.json", []) or []
    rs = _jr(p.results / "resume.json", {}) or {}
    review = ((_jr(p.progress, {}) or {}).get("steps", {}).get("1") or {}).get("review")
    log, skipped = read_log("dry4")
    ended = [(e.get("step"), e.get("run")) for e in log if e.get("event") == "run-ended"]
    one_b = ended.count((1, "b"))
    paused = rs.get("paused_after", rs.get("paused_at"))
    last = ended[-1] if ended else None
    pr = review == "pause" and one_b == 1 and paused == 1 and last == (7, "b")      # the run ended at 7.b
    return [("dry4 transient retry", any(str(i).startswith("transient-retry:") for i in iv), f"1.b interventions {iv}"),
            ("dry4 timeout owned by the arm", any(b.get("breach") == "turn_seconds" and b.get("owner") == "arm" for b in br),
             f"breaches {br}"),
            ("dry4 pause and resume", pr, f"progress step 1 review {review!r}; resume.json {rs}; run-ended 1.b x{one_b}; "
                                          f"last run-ended {last}; run-log lines skipped: {len(skipped)}")]


def _trim(text: str) -> str:
    """Host paths out of the committed report: the repo root becomes relative."""
    return text.replace(str(REPO_ROOT) + "/", "").replace(str(REPO_ROOT), ".")


def dry_report(res: dict) -> Path:
    """`results/dryrun-validation.md`, ending `**Result: PASS**` only when dry1 and dry4 completed, dry2 stopped at
    step 2, dry3 halted, every gate of what a pass proves holds (read from its evidence and listed with its facts:
    dry1 exact hidden counts, N.a/N.b sha_before, hand-edit probe, model pins; dry2 the no-progress stop at step 2;
    dry3 the same model-pin fault twice ending in halt; dry4 the transient retry, the arm-owned turn_seconds breach,
    the pause at step 1's review and the resume), no container spec carried the token, no token is anywhere in the four passes' evidence or
    state (.gz decompressed, tars opened), and no `bakeoff.run` container is left."""
    findings = [f for i in range(1, 5) for root in (paths.RESULTS / f"dry{i}", paths.STATE / f"dry{i}")
                for f in secrets.scan_tree(root, [DRY_TOKEN])]
    left = docker.running("bakeoff.run")
    spec = _jr(paths.RESULTS / "dryrun-specs.json", {}) or {"specs": 0, "specs_containing_token": None}
    gates = _gate_dry1() + _gate_dry2() + _gate_dry3() + _gate_dry4()
    ok = (not findings and not left and spec["specs_containing_token"] == 0 and "halted" in res.get("dry3", {})
          and res.get("dry2", {}).get("stopped_at") == 2 and res.get("dry1", {}).get("completed") is True
          and res.get("dry4", {}).get("completed") is True and all(g[1] for g in gates))
    lines = ["# Dry-run validation", "", f"- results: {json.dumps(res)[:2000]}",
             f"- secret findings (evidence + state, .gz decompressed): {len(findings)}",
             *[f"  - {f.path}:{f.line} {f.kind}" for f in findings[:20]],
             f"- container specs built: {spec['specs']}; containing the token: {spec['specs_containing_token']}",
             f"- leftover containers: {len(left)}", "", "## What each pass proves (every gate must hold)", "",
             *[f"- {'ok' if g else 'FAIL'}: {name} — {facts}" for name, g, facts in gates],
             *_dry_facts(), "", f"**Result: {'PASS' if ok else 'FAIL'}**", ""]
    out = paths.RESULTS / "dryrun-validation.md"
    fsutil.write_text(out, _trim("\n".join(lines)))
    return out
