"""Task 26 (OD25): the canary's build — pre-flight, confirm, the call order, the tracker read with the arm's PAT, and
`canary_check`'s rows against a synthetic results tree laid out by the real writers. Nothing here reaches Claude, the
keychain, Docker, GitHub or the network: every one of them is faked."""
from __future__ import annotations
import dataclasses, json, shutil, subprocess
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import (checklist, config, credentials, docker, egress, faults, hidden, orchestrate, owner as owner_mod,
                    paths, repo, secrets, tracker)
from runner.paths import Paths, REPO_ROOT
from runner.transcripts import PinReport

ARM = "control"
SLUG = "troupe-run/bakeoff-specs-control-canary"
DISC = "troupe-run/bakeoff-specs-control-canary-disc"
ITEMS = {"bakeoff-claude-oauth", "bakeoff-gh-canary-control", "bakeoff-gh-canary-disc-control"}


# ---- credentials: existence only ---------------------------------------------------------------------------------

def test_keychain_item_exists_runs_security_without_w_and_discards_its_output(monkeypatch):
    seen = []

    def fake(argv, **kw):
        seen.append((argv, kw))
        return SimpleNamespace(returncode=0 if argv[-1] == "present" else 44)
    monkeypatch.setattr(credentials.subprocess, "run", fake)
    assert credentials.keychain_item_exists("present") is True
    assert credentials.keychain_item_exists("absent") is False
    for argv, kw in seen:
        assert argv[:3] == [credentials.SECURITY, "find-generic-password", "-s"] and "-w" not in argv
        assert kw["stdout"] is subprocess.DEVNULL and kw["stderr"] is subprocess.DEVNULL


def test_keychain_item_exists_reports_a_timeout_as_absent(monkeypatch):
    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 1)
    monkeypatch.setattr(credentials.subprocess, "run", slow)
    assert credentials.keychain_item_exists("x") is False


def test_pat_item_names_are_the_ones_the_pat_readers_use(monkeypatch):
    asked = []

    def fake(argv, **kw):
        asked.append(argv[argv.index("-s") + 1])
        return SimpleNamespace(returncode=0, stdout="v\n")
    monkeypatch.setattr(credentials.subprocess, "run", fake)
    credentials.github_pat("canary", ARM); credentials.github_disc_pat("canary", ARM)
    assert asked == [credentials.github_pat_item("canary", ARM), credentials.github_disc_pat_item("canary", ARM)]
    assert asked == ["bakeoff-gh-canary-control", "bakeoff-gh-canary-disc-control"]


# ---- repo gaps (the owner's gh) ----------------------------------------------------------------------------------

def _gh_fake(repos: dict, issues: dict | None = None):
    """`repo._gh` stand-in: `gh repo view <slug> --json …` answered from `repos` (slug → view dict, absent = 404);
    `gh issue list --repo <slug> …` from `issues` (slug → list of issue dicts; absent = none)."""
    calls = []

    def gh(argv):
        calls.append(argv)
        if argv[:3] == ["gh", "issue", "list"]:
            slug = argv[argv.index("--repo") + 1]
            assert "--state" in argv and argv[argv.index("--state") + 1] == "all"
            return subprocess.CompletedProcess(argv, 0, json.dumps((issues or {}).get(slug, [])), "")
        assert argv[:3] == ["gh", "repo", "view"]
        slug = argv[3]
        if slug not in repos:
            return subprocess.CompletedProcess(argv, 1, "", "GraphQL: Could not resolve to a Repository")
        return subprocess.CompletedProcess(argv, 0, json.dumps(repos[slug]), "")
    gh.calls = calls
    return gh


GOOD = {"visibility": "PRIVATE", "hasIssuesEnabled": True}


@pytest.mark.parametrize("view,want", [
    (GOOD, []),
    (None, ["not found"]),
    ({"visibility": "PUBLIC", "hasIssuesEnabled": True}, ["is PUBLIC"]),
    ({"visibility": "PRIVATE", "hasIssuesEnabled": False}, ["issues are disabled"]),
], ids=["ok", "missing", "public", "no-issues"])
def test_repo_gaps_names_each_gap(monkeypatch, view, want):
    monkeypatch.setattr(repo, "_gh", _gh_fake({} if view is None else {SLUG: view}))
    got = repo.repo_gaps(SLUG)
    assert len(got) == len(want) and all(w in g and SLUG in g for w, g in zip(want, got))


@pytest.mark.parametrize("fake,kind", [
    (lambda argv: (_ for _ in ()).throw(subprocess.TimeoutExpired(argv, 120)), "timed out"),
    (lambda argv: subprocess.CompletedProcess(argv, 0, "{not json", ""), "malformed JSON"),
    (lambda argv: subprocess.CompletedProcess(argv, 0, "[1, 2]", ""), "malformed JSON"),
    (lambda argv: subprocess.CompletedProcess(argv, 4, "", "auth required"), "exit 4"),
], ids=["timeout", "bad-json", "not-an-object", "non-zero"])
def test_repo_gaps_reports_a_gh_failure_as_a_gap_naming_the_repo_and_the_error_kind(monkeypatch, fake, kind):
    monkeypatch.setattr(repo, "_gh", fake)
    got = repo.repo_gaps(SLUG)
    assert len(got) == 1 and SLUG in got[0] and kind in got[0]


PROBE_T = tracker.PROBE_ISSUE["title"]


@pytest.mark.parametrize("issues,ok", [
    ([], True),
    ([{"number": 1, "title": PROBE_T}], True),
    ([{"number": 1, "title": PROBE_T}, {"number": 2, "title": "Alias bug"}], False),
], ids=["clean", "probe-issue-only", "one-other-issue"])
def test_issue_gaps_passes_an_empty_or_probe_only_repo_and_fails_one_with_another_issue(monkeypatch, issues, ok):
    monkeypatch.setattr(repo, "_gh", _gh_fake({SLUG: GOOD}, {SLUG: issues}))
    got = repo.issue_gaps(SLUG, ignore_title=PROBE_T)
    assert (got == []) is ok
    if not ok:
        assert len(got) == 1 and SLUG in got[0] and "1 issue(s)" in got[0]
        assert "gh issue delete" in got[0] and "recreate the repo" in got[0]


@pytest.mark.parametrize("fake,kind", [
    (lambda argv: (_ for _ in ()).throw(subprocess.TimeoutExpired(argv, 120)), "timed out"),
    (lambda argv: subprocess.CompletedProcess(argv, 0, "{}", ""), "malformed JSON"),
    (lambda argv: subprocess.CompletedProcess(argv, 1, "", "boom"), "exit 1"),
], ids=["timeout", "bad-json", "non-zero"])
def test_issue_gaps_reports_a_gh_failure_as_a_gap(monkeypatch, fake, kind):
    monkeypatch.setattr(repo, "_gh", fake)
    got = repo.issue_gaps(SLUG, ignore_title=PROBE_T)
    assert len(got) == 1 and SLUG in got[0] and kind in got[0]


# ---- the canary: fakes ------------------------------------------------------------------------------------------

class RecOwner:
    def __init__(self, answer=True):
        self.answer, self.confirms = answer, []

    def confirm(self, text):
        self.confirms.append(text)
        return self.answer


@pytest.fixture
def world(tmp_state, monkeypatch):
    """Every effect the canary has, faked and recorded in `w.events` in order."""
    w = SimpleNamespace(events=[], repos={SLUG: GOOD, DISC: GOOD}, issues={}, items=set(ITEMS), green=True,
                        read_rc=0, read_title=None, read_err=b"", stage_hosts=None, spec=None)
    monkeypatch.setattr(repo, "_gh", _gh_fake(w.repos, w.issues))
    monkeypatch.setattr(credentials, "keychain_item_exists", lambda item: item in w.items)
    monkeypatch.setattr(orchestrate.gitops, "image_for", lambda arm: "bakeoff-base:test")

    def cred_of():
        w.events.append("cred")
        return credentials.dummy()
    w.cred_of = cred_of

    def setup(pass_, arm, cred, owner, again=False):
        w.brief_at_setup = paths.brief_path(pass_).read_text() if paths.brief_path(pass_).is_file() else None
        w.order_at_setup = json.loads((paths.RESULTS / pass_ / "order.json").read_text())["order"] \
            if (paths.RESULTS / pass_ / "order.json").is_file() else None
        w.events.append(("setup", pass_, arm, again))
        return SimpleNamespace(green=w.green)
    monkeypatch.setattr(orchestrate, "setup", setup)

    w.ran = None                                      # None: the canary's normal finish, {"stopped_after": 2}

    def run_arm(pass_, arm, cred, owner, limits_override=None, stop_after=None):
        w.events.append(("run_arm", pass_, arm, stop_after))
        return w.ran if w.ran is not None else {"stopped_after": stop_after}
    monkeypatch.setattr(orchestrate, "run_arm", run_arm)

    def create_bug(ctx, owner, *, title=None, body=None):
        got = owner.confirm("Create the step-6 issue?")
        assert got is True
        ctx.out.mkdir(parents=True, exist_ok=True)
        (ctx.out / "issue.json").write_text(json.dumps({"title": "the planted title"}))
        w.events.append(("create_bug", ctx.pass_, ctx.arm.name, getattr(ctx, "run", "b")))
        return tracker.IssueRef("github", f"{SLUG}#7", f"https://github.com/{SLUG}/issues/7", "7")
    monkeypatch.setattr(tracker, "create_bug", create_bug)

    def supersede(ctx, old, owner, new=None):
        w.events.append(("supersede", old.ref))
        return {"action": "closed", "old": old.ref}
    monkeypatch.setattr(tracker, "supersede", supersede)

    class Stage:
        def __init__(self, pass_, arm, phase, hosts, log_to):
            self.net = f"bk-net-{pass_}-{arm}-{phase}"
            w.stage_hosts = hosts
            w.events.append(("stage", pass_, arm, phase))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            w.events.append("stage-exit")
    monkeypatch.setattr(egress, "Stage", Stage)

    def run(spec, input=None, timeout=None, stop_grace=30):
        w.spec = spec
        w.events.append(("docker.run", tuple(spec.cmd)))
        title = w.read_title if w.read_title is not None else "the planted title"
        out = json.dumps({"title": title}).encode() if w.read_rc == 0 else b""
        return subprocess.CompletedProcess(spec.cmd, w.read_rc, out, w.read_err)
    monkeypatch.setattr(docker, "run", run)
    return w


# ---- pre-flight -------------------------------------------------------------------------------------------------

def test_preflight_with_everything_present_finds_no_gap(world):
    assert orchestrate.canary_preflight() == []


def test_preflight_asks_for_both_repos_and_all_three_keychain_items(world, monkeypatch):
    asked = []
    monkeypatch.setattr(credentials, "keychain_item_exists", lambda item: asked.append(item) or True)
    orchestrate.canary_preflight()
    assert set(asked) == ITEMS
    assert sorted(c[3] for c in repo._gh.calls if c[1] == "repo") == sorted([SLUG, DISC])
    assert sorted(c[c.index("--repo") + 1] for c in repo._gh.calls if c[1] == "issue") == sorted([SLUG, DISC])


@pytest.mark.parametrize("where", [SLUG, DISC])
def test_preflight_names_a_repo_holding_an_earlier_runs_issue_and_spends_nothing(world, where):
    world.issues[where] = [{"number": 3, "title": PROBE_T}, {"number": 4, "title": "Alias bug"}]
    own = RecOwner()
    res = orchestrate.canary(world.cred_of, own)
    assert len(res["preflight_missing"]) == 1 and where in res["preflight_missing"][0]
    assert own.confirms == [] and world.events == []


def test_preflight_passes_repos_holding_only_the_probe_issue(world):
    world.issues[SLUG] = [{"number": 1, "title": PROBE_T}]
    world.issues[DISC] = [{"number": 1, "title": PROBE_T}]
    assert orchestrate.canary_preflight() == []


def test_preflight_lists_exactly_the_missing_items_and_spends_nothing(world):
    del world.repos[DISC]
    world.items.discard("bakeoff-gh-canary-disc-control")
    own = RecOwner()
    res = orchestrate.canary(world.cred_of, own)
    missing = res["preflight_missing"]
    assert len(missing) == 2
    assert any(DISC in m for m in missing) and any("bakeoff-gh-canary-disc-control" in m for m in missing)
    assert "github-plan canary" in res["hint"]
    assert own.confirms == [] and world.events == []            # no confirm, no credential, no setup, no run
    assert not (paths.STATE / "canary").exists() and not (paths.RESULTS / "canary").exists()


# ---- confirm ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("answer", [False, owner_mod.Park("confirm", "canary", "owner-choice", 0.0, 0.0)],
                         ids=["no", "park"])
def test_declining_or_parking_the_confirm_spends_nothing_and_keeps_the_previous_canary(world, answer):
    old = paths.STATE / "canary" / "control" / "marker"
    old.parent.mkdir(parents=True); old.write_text("evidence")
    own = RecOwner(answer)
    res = orchestrate.canary(world.cred_of, own)
    assert res.get("skipped") is True
    assert len(own.confirms) == 1 and world.events == []
    assert old.read_text() == "evidence"


def test_confirm_text_names_the_replacement_only_when_a_previous_canary_exists(world):
    own = RecOwner(False)
    orchestrate.canary(world.cred_of, own)
    assert "replace" not in own.confirms[0].lower()
    assert "GitHub issues are NOT reset" in own.confirms[0]
    (paths.RESULTS / "canary").mkdir(parents=True)
    orchestrate.canary(world.cred_of, own)
    assert "replaced" in own.confirms[1].lower() and str(paths.RESULTS / "canary") in own.confirms[1]


def test_a_confirmed_canary_replaces_the_previous_state_and_results(world):
    for d in (paths.STATE / "canary" / "control", paths.RESULTS / "canary" / "control" / "01"):
        d.mkdir(parents=True); (d / "old").write_text("x")
    orchestrate.canary(world.cred_of, RecOwner())
    assert not (paths.STATE / "canary" / "control" / "old").exists()
    assert not (paths.RESULTS / "canary" / "control" / "01" / "old").exists()


# ---- the call order -------------------------------------------------------------------------------------------

def test_the_canary_calls_in_order_and_records_the_tracker_check(world):
    own = RecOwner()
    res = orchestrate.canary(world.cred_of, own)
    ev = world.events
    assert ev[0] == "cred"
    assert ev[1] == ("setup", "canary", ARM, False)
    assert ev[2] == ("run_arm", "canary", ARM, 2)
    assert ev[3] == ("create_bug", "canary", ARM, "b")            # run "b": the canary repo, not the disc repo
    assert ev[4] == ("stage", "canary", ARM, "ghread")
    assert ev[5] == ("docker.run", ("gh", "issue", "view", "7", "--repo", SLUG, "--json", "title"))
    assert ev[6] == "stage-exit"
    assert ev[7] == ("supersede", f"{SLUG}#7")
    assert len(ev) == 8
    # the brief copy and the order exist before setup runs; the copy is the real brief's text
    assert world.brief_at_setup == (REPO_ROOT / "scenario" / "po-brief.md").read_text()
    assert paths.brief_path("canary") != REPO_ROOT / "scenario" / "po-brief.md"
    assert world.order_at_setup == [ARM]
    rec = json.loads((Paths("canary", ARM).results / "tracker-check" / "result.json").read_text())
    assert rec["issue"] == f"{SLUG}#7" and rec["arm_pat_read_ok"] is True and rec["superseded"] == "closed"
    assert res["run"] == {"stopped_after": 2} and res["tracker_check"]["arm_pat_read_ok"] is True


def test_the_read_runs_in_the_arm_image_with_its_home_behind_run_common_plus_github(world):
    orchestrate.canary(world.cred_of, RecOwner())
    s, p = world.spec, Paths("canary", ARM)
    assert world.stage_hosts == config.load_pins().egress_run_common + [r"^api\.github\.com$"]
    assert s.network == "bk-net-canary-control-ghread" and s.proxy is True
    assert any(m.host == p.home and m.ro for m in s.mounts)       # the arm's own home: its hosts.yml holds its PAT
    assert s.image == "bakeoff-base:test"


def test_a_failed_read_is_recorded_redacted_and_the_issue_is_still_closed(world):
    tok = "ghp_" + "A" * 36
    world.read_rc, world.read_err = 1, f"HTTP 401 with {tok}".encode()
    orchestrate.canary(world.cred_of, RecOwner())
    f = Paths("canary", ARM).results / "tracker-check" / "result.json"
    rec = json.loads(f.read_text())
    assert rec["arm_pat_read_ok"] is False and rec["superseded"] == "closed"
    assert tok not in f.read_text() and "401" in rec["read_detail"]


def test_a_read_of_a_different_title_is_not_ok(world):
    world.read_title = "some other issue"
    orchestrate.canary(world.cred_of, RecOwner())
    rec = json.loads((Paths("canary", ARM).results / "tracker-check" / "result.json").read_text())
    assert rec["arm_pat_read_ok"] is False


UNFINISHED = [{"parked": [{"arm": ARM, "step": 1}]}, {"paused_after": 1}, {"declined": "setup of control"},
              {"stopped_at": 1}, {"incomplete": {"arms": {}}}, {"completed": True}]
UNFINISHED_IDS = ["parked", "paused_after", "declined", "stopped_at", "incomplete", "completed"]


@pytest.mark.parametrize("ran", UNFINISHED, ids=UNFINISHED_IDS)
def test_an_unfinished_run_writes_nothing_to_github_and_reports_its_status_at_the_top(world, ran):
    world.ran = ran
    res = orchestrate.canary(world.cred_of, RecOwner())
    assert not any(isinstance(e, tuple) and e[0] in ("create_bug", "docker.run", "supersede") for e in world.events)
    assert res["not_finished"] == ran and all(res[k] == v for k, v in ran.items())
    assert str(res["tracker_check"]).startswith("not run")
    assert not (Paths("canary", ARM).results / "tracker-check").exists()


@pytest.mark.parametrize("ran", UNFINISHED, ids=UNFINISHED_IDS)
def test_cli_canary_exits_non_zero_and_says_why_when_the_run_did_not_finish(world, monkeypatch, capsys, ran):
    from runner import cli
    world.ran = ran
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: credentials.dummy())
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner())
    assert cli.main(["canary"]) == 1
    out = capsys.readouterr().out
    assert "did not finish steps 1-2" in out and "runner canary --resume" in out
    assert not any(isinstance(e, tuple) and e[0] == "create_bug" for e in world.events)


def test_a_setup_that_is_not_green_stops_before_the_run(world):
    world.green = False
    res = orchestrate.canary(world.cred_of, RecOwner())
    assert res.get("setup_green") is False
    assert [e for e in world.events if isinstance(e, tuple) and e[0] in ("run_arm", "create_bug")] == []


def test_a_parked_issue_confirm_is_recorded_and_nothing_is_read(world, monkeypatch):
    park = owner_mod.Park("confirm", "issue", "owner-choice", 0.0, 0.0)

    class ParkOnIssue(RecOwner):
        def confirm(self, text):
            self.confirms.append(text)
            return park if "step-6 issue" in text else True
    orchestrate.canary(world.cred_of, ParkOnIssue())
    rec = json.loads((Paths("canary", ARM).results / "tracker-check" / "result.json").read_text())
    assert rec["issue"] is None and rec["arm_pat_read_ok"] is False and "park" in rec["error"]
    assert not any(isinstance(e, tuple) and e[0] == "docker.run" for e in world.events)


# ---- canary_check: a synthetic tree in the real writers' layout -----------------------------------------------------

def _pin(ok=True, n=5) -> str:
    return PinReport(ok=ok, assistant_messages=n, stream_assistant_messages=n, synthetic=0, truncated_lines=0,
                     claude_code_versions=["2.1.281"], no_evidence=n == 0).to_json()


def _summary(step, total=10, passed=9):
    return hidden.Summary(step=step, total=total, passed=passed, failed=total - passed, flaky=0, flaky_arm=0,
                          tests={}, new_at_step=[], new_passed=0, new_discriminating_passed=0, exit_code=0)


def good_tree():
    p = Paths("canary", ARM)
    for n in (1, 2):
        d = p.step(n)
        (d / "a" / "po" / "a1-001").mkdir(parents=True)
        (d / "po" / "a1-001").mkdir(parents=True)
        (d / "model-pin.json").write_text(_pin())                              # evidence.finalise
        (d / "po" / "a1-001" / "model-pin.json").write_text(_pin())            # po.py: <out>/po/a<k>-NNN/
        (d / "run.json").write_text(json.dumps({"outcome": "done", "harness_faults": []}))   # evidence.finalise
        _summary(n).write(d)                                                    # hidden.Summary.write
        (d / "a" / "model-pin.json").write_text(_pin())                        # stepflow N.a
        (d / "a" / "po" / "a1-001" / "model-pin.json").write_text(_pin())
        (d / "a" / "discovery.json").write_text(json.dumps({"run": "a", "harness_faults": []}))
    he = p.step(2) / "hand-edit"
    he.mkdir()
    (he / "edit.json").write_text(json.dumps({"sha": "abc1234", "files": ["src/x.py"]}))     # handedit._land
    (he / "model-pin-t1.json").write_text(_pin())                                            # handedit teammate
    (he / "detection.json").write_text(json.dumps({"feature_present": True}))                # handedit.detect
    tc = p.results / "tracker-check"
    tc.mkdir()
    orchestrate._write_tracker_check(tc, {"issue": f"{SLUG}#7", "arm_pat_read_ok": True, "superseded": "closed"})
    (p.config_dir).mkdir(parents=True)
    return p


LIT = "canary-test-literal-QWERTY-0123456789"


@pytest.fixture
def tree(tmp_state, monkeypatch):
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: [LIT])
    return good_tree()


def _failing(rows):
    return {what for what, ok, _ in rows if not ok}


def test_a_good_tree_passes_every_row_and_the_report_says_pass(tree):
    rows = orchestrate.canary_check()
    assert _failing(rows) == set()
    md = (paths.RESULTS / "canary" / "canary.md").read_text()
    assert md.rstrip().endswith("**Result: PASS**")
    assert len(rows) == len(orchestrate.canary_row_names())


def _rw(f: Path, **kv):
    d = json.loads(f.read_text()); d.update(kv); f.write_text(json.dumps(d))


DEFECTS = {
    "step 1: arm pin verified from real transcripts (N.b)":
        lambda p: (p.step(1) / "model-pin.json").write_text(_pin(ok=False)),
    "step 2: arm pin verified from real transcripts (N.b)":
        lambda p: (p.step(2) / "model-pin.json").write_text(_pin(n=0)),
    "step 1: arm pin verified from real transcripts (N.a)":
        lambda p: (p.step(1) / "a" / "model-pin.json").unlink(),
    "step 1: every PO decision pin-verified (N.b)":
        lambda p: (p.step(1) / "po" / "a1-001" / "model-pin.json").write_text(_pin(ok=False)),
    "step 1: every PO decision pin-verified (N.a)":
        lambda p: (p.step(1) / "a" / "po" / "a1-001" / "model-pin.json").write_text(_pin(n=0)),
    "the real PO answered at least once across steps 1-2":
        lambda p: [shutil.rmtree(p.step(n) / sub) for n in (1, 2) for sub in ("po", "a/po")],
    "step 2: arm pin verified from real transcripts (N.a)":
        lambda p: (p.step(2) / "a" / "model-pin.json").write_text(_pin(ok=False)),
    "step 1: no harness fault (N.a discovery.json)":
        lambda p: (p.step(1) / "a" / "discovery.json").write_text(json.dumps({"run": "a"})),
    "step 1: evidence scan clean":
        lambda p: (p.step(1) / "leak.txt").write_text(f"oops {LIT}\n"),
    "step 2: hidden tests ran in the tester container":
        lambda p: (p.step(2) / "hidden" / "summary.json").unlink(),
    "step 2: every PO decision pin-verified (N.b)":
        lambda p: (p.step(2) / "po" / "a1-001" / "model-pin.json").write_text(_pin(ok=False)),
    "step 2: every PO decision pin-verified (N.a)":
        lambda p: (p.step(2) / "a" / "po" / "a1-001" / "model-pin.json").write_text(_pin(ok=False)),
    "step 1: no harness fault (N.b run.json)":
        lambda p: _rw(p.step(1) / "run.json", harness_faults=[{"kind": "infra-auth"}]),
    "step 2: no harness fault (N.b run.json)":
        lambda p: (p.step(2) / "run.json").write_text(json.dumps({"outcome": "done"})),   # no harness_faults key
    "step 2: no harness fault (N.a discovery.json)":
        lambda p: _rw(p.step(2) / "a" / "discovery.json", harness_faults=[{"kind": "model-pin"}]),
    "step 2: evidence scan clean":
        lambda p: (p.step(2) / "a" / "leak.txt").write_text(f"oops {LIT}\n"),
    "step 1: hidden tests ran in the tester container":
        lambda p: _summary(1, total=0, passed=0).write(p.step(1)),
    "step 2: hand edit applied (hand-edit/edit.json)":
        lambda p: (p.step(2) / "hand-edit" / "edit.json").unlink(),
    "step 2: teammate turns pin-verified":
        lambda p: (p.step(2) / "hand-edit" / "model-pin-t1.json").write_text(_pin(ok=False)),
    "step 2: hand-edit detection recorded":
        lambda p: (p.step(2) / "hand-edit" / "detection.json").unlink(),
    "GitHub issue created by the owner and read with the arm's PAT":
        lambda p: _rw(p.results / "tracker-check" / "result.json", arm_pat_read_ok=False),
    "canary issue closed again (superseded)":
        lambda p: _rw(p.results / "tracker-check" / "result.json", superseded="declined"),
    "tracker-check evidence scan clean":
        lambda p: (p.results / "tracker-check" / "issue-body.md").write_text(LIT),
    "no credential file in the arm's home":
        lambda p: ((p.home / "deep" / "x").mkdir(parents=True), (p.home / "deep" / "x" / ".credentials.json").write_text("{}")),
    "no harness fault in the canary ledger (setup included)":
        lambda p: (faults.ledger_paths("canary")[0].write_text(json.dumps({"kind": "infra-auth", "step": 0}) + "\n")),
}


def test_every_row_has_a_defect_case():
    assert set(DEFECTS) == set(orchestrate.canary_row_names())


def test_the_per_step_po_rows_pass_with_zero_decisions_and_only_the_at_least_once_row_fails(tree):
    DEFECTS["the real PO answered at least once across steps 1-2"](tree)
    rows = orchestrate.canary_check()
    assert _failing(rows) == {"the real PO answered at least once across steps 1-2"}
    assert all(ok for what, ok, _ in rows if "every PO decision" in what)


def test_the_credential_row_fails_when_the_arm_home_is_missing(tree):
    shutil.rmtree(tree.home)
    assert _failing(orchestrate.canary_check()) == {"no credential file in the arm's home"}


def test_the_ledger_row_fails_when_results_canary_is_missing(tmp_state, monkeypatch):
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: [LIT])
    assert not (paths.RESULTS / "canary").exists()
    check = dict(orchestrate._canary_rows([]))["no harness fault in the canary ledger (setup included)"]
    ok, detail = check()                     # evaluated before canary_check would create results/canary/canary.md
    assert ok is False and "no results/canary" in detail


@pytest.mark.parametrize("row", sorted(DEFECTS))
def test_each_row_fails_on_its_own_defect_alone(tree, row):
    DEFECTS[row](tree)
    rows = orchestrate.canary_check()
    assert _failing(rows) == {row}
    assert (paths.RESULTS / "canary" / "canary.md").read_text().rstrip().endswith("**Result: FAIL**")


def test_an_empty_results_tree_fails_every_row_without_crashing(tmp_state, monkeypatch):
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: [LIT])
    rows = orchestrate.canary_check()
    assert _failing(rows) == set(orchestrate.canary_row_names())      # no row passes on nothing
    assert (paths.RESULTS / "canary" / "canary.md").read_text().rstrip().endswith("**Result: FAIL**")


# ---- the CLI ------------------------------------------------------------------------------------------------------

def test_cli_canary_with_gaps_prints_each_missing_item_and_the_plan_hint_and_reads_no_credential(world, monkeypatch,
                                                                                               capsys):
    from runner import cli
    del world.repos[DISC]
    world.items.discard("bakeoff-gh-canary-disc-control")
    read = []
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: read.append(1))
    own = RecOwner()
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: own)
    assert cli.main(["canary"]) != 0
    out = capsys.readouterr().out
    assert DISC in out and "bakeoff-gh-canary-disc-control" in out
    assert "uv run python -m runner github-plan canary" in out
    assert read == [] and own.confirms == [] and world.events == []


def test_cli_canary_declined_exits_non_zero_and_spends_nothing(world, monkeypatch):
    from runner import cli
    read = []
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: read.append(1))
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner(False))
    assert cli.main(["canary"]) != 0
    assert read == [] and world.events == []


def test_cli_canary_confirmed_runs_with_the_keychain_credential(world, monkeypatch):
    from runner import cli
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: credentials.dummy())
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner())
    assert cli.main(["canary"]) == 0
    assert ("run_arm", "canary", ARM, 2) in world.events


@pytest.mark.parametrize("ok,code", [(True, 0), (False, 1)])
def test_cli_canary_check_prints_the_report_and_exits_by_its_result(tree, capsys, ok, code):
    from runner import cli
    if not ok:
        (tree.step(1) / "model-pin.json").unlink()
    assert cli.main(["canary", "--check"]) == code
    out = capsys.readouterr().out
    assert out.rstrip().endswith("**Result: PASS**" if ok else "**Result: FAIL**")


# ---- final review I-1: an interrupted canary is completable ---------------------------------------------------------

def test_a_pause_at_step_2s_review_counts_as_finished_and_the_tracker_check_runs(world):
    world.ran = {"paused_after": 2}
    res = orchestrate.canary(world.cred_of, RecOwner())
    assert "not_finished" not in res and res["tracker_check"]["arm_pat_read_ok"] is True
    assert ("create_bug", "canary", ARM, "b") in world.events


def _previous_canary():
    marker = paths.STATE / "canary" / ARM / "keep"
    marker.parent.mkdir(parents=True); marker.write_text("evidence")
    return marker


def test_resume_keeps_the_state_runs_no_setup_and_finishes_with_the_tracker_check(world):
    marker = _previous_canary()
    own = RecOwner()
    res = orchestrate.canary_resume(world.cred_of, own)
    assert marker.read_text() == "evidence"                                   # no wipe
    kinds = [e[0] if isinstance(e, tuple) else e for e in world.events]
    assert "setup" not in kinds
    assert kinds[:3] == ["cred", "run_arm", "create_bug"]
    assert ("run_arm", "canary", ARM, 2) in world.events
    assert res["tracker_check"]["superseded"] == "closed"
    assert "skipped on resume" in own.confirms[0] and len(own.confirms) == 2   # the resume confirm + the issue confirm


def test_resume_skips_the_issue_check_but_not_the_repo_and_keychain_checks(world):
    _previous_canary()
    world.issues[SLUG] = [{"number": 5, "title": "an issue the arm filed in step 1"}]
    assert orchestrate.canary_preflight(resume=True) == []
    assert orchestrate.canary_preflight() != []
    del world.repos[DISC]
    world.items.discard("bakeoff-claude-oauth")
    own = RecOwner()
    res = orchestrate.canary_resume(world.cred_of, own)
    assert len(res["preflight_missing"]) == 2 and own.confirms == [] and world.events == []


def test_resume_without_a_previous_canary_is_refused(world):
    with pytest.raises(orchestrate.NotReady, match="no canary to resume"):
        orchestrate.canary_resume(world.cred_of, RecOwner())
    assert world.events == []


@pytest.mark.parametrize("answer", [False, owner_mod.Park("confirm", "canary", "owner-choice", 0.0, 0.0)],
                         ids=["no", "park"])
def test_declining_the_resume_spends_nothing(world, answer):
    _previous_canary()
    res = orchestrate.canary_resume(world.cred_of, RecOwner(answer))
    assert res.get("skipped") is True and world.events == []


def test_a_resume_that_still_does_not_finish_writes_nothing_to_github(world):
    _previous_canary()
    world.ran = {"parked": [{"arm": ARM, "step": 2}]}
    res = orchestrate.canary_resume(world.cred_of, RecOwner())
    assert res["not_finished"] == world.ran and res["resume"].endswith("runner canary --resume")
    assert not any(isinstance(e, tuple) and e[0] == "create_bug" for e in world.events)


def test_a_resume_keeps_a_tracker_check_that_already_held_and_files_no_second_issue(world):
    _previous_canary()
    tc = Paths("canary", ARM).results / "tracker-check"; tc.mkdir(parents=True)
    orchestrate._write_tracker_check(tc, {"issue": f"{SLUG}#7", "arm_pat_read_ok": True, "superseded": "closed"})
    res = orchestrate.canary_resume(world.cred_of, RecOwner())
    assert res["tracker_check_kept"] is True
    assert not any(isinstance(e, tuple) and e[0] == "create_bug" for e in world.events)


def test_a_resume_reruns_a_tracker_check_that_failed(world):
    _previous_canary()
    tc = Paths("canary", ARM).results / "tracker-check"; tc.mkdir(parents=True)
    orchestrate._write_tracker_check(tc, {"issue": f"{SLUG}#7", "arm_pat_read_ok": False, "superseded": "closed"})
    res = orchestrate.canary_resume(world.cred_of, RecOwner())
    assert ("create_bug", "canary", ARM, "b") in world.events and res["tracker_check"]["arm_pat_read_ok"] is True


def test_cli_canary_resume_calls_the_resume_path(world, monkeypatch):
    from runner import cli
    marker = _previous_canary()
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: credentials.dummy())
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner())
    assert cli.main(["canary", "--resume"]) == 0
    assert marker.exists() and not any(isinstance(e, tuple) and e[0] == "setup" for e in world.events)


def test_cli_canary_resume_without_a_previous_canary_exits_non_zero(world, monkeypatch):
    from runner import cli
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner())
    assert cli.main(["canary", "--resume"]) == 1


def test_cli_canary_check_and_resume_are_exclusive(capsys):
    from runner import cli
    with pytest.raises(SystemExit):
        cli.main(["canary", "--check", "--resume"])
    assert "argument --resume: not allowed with argument --check" in capsys.readouterr().err


# ---- run-arm never takes the canary past step 2 ---------------------------------------------------------------------

@pytest.fixture
def run_seen(tmp_state, monkeypatch):
    seen = []
    monkeypatch.setattr(orchestrate, "_run", lambda pass_, arms, cred, owner, **kw: seen.append(kw["stop_after"]) or
                        {"stopped_after": kw["stop_after"], "arms": {a: {"stopped_at": None} for a in arms}})
    return seen


def test_run_arm_on_the_canary_defaults_to_stop_after_2(run_seen):
    orchestrate.run_arm("canary", ARM, credentials.dummy(), RecOwner())
    assert run_seen == [2]


@pytest.mark.parametrize("n", [1, 2])
def test_run_arm_on_the_canary_accepts_stop_after_up_to_2(run_seen, n):
    orchestrate.run_arm("canary", ARM, credentials.dummy(), RecOwner(), stop_after=n)
    assert run_seen == [n]


@pytest.mark.parametrize("n", [3, 7, 0, -1])
def test_run_arm_on_the_canary_refuses_stop_after_outside_1_to_2(run_seen, n):
    with pytest.raises(orchestrate.NotReady, match="steps 1-2 only"):
        orchestrate.run_arm("canary", ARM, credentials.dummy(), RecOwner(), stop_after=n)
    assert run_seen == []


def test_cli_run_arm_canary_with_stop_after_0_is_refused_and_runs_nothing(run_seen, monkeypatch, capsys):
    from runner import cli
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: (credentials.dummy(), RecOwner()))
    assert cli.main(["run-arm", "canary", ARM, "--stop-after", "0"]) == 1
    assert run_seen == [] and "steps 1-2 only" in capsys.readouterr().out


def test_canary_and_resume_pass_run_arm_a_stop_after_of_exactly_2(world):
    orchestrate.canary(world.cred_of, RecOwner())
    Paths("canary", ARM).base.mkdir(parents=True, exist_ok=True)      # what the real setup leaves (faked here)
    orchestrate.canary_resume(world.cred_of, RecOwner())
    assert [e[3] for e in world.events if isinstance(e, tuple) and e[0] == "run_arm"] == [2, 2]


def test_cli_run_arm_canary_without_stop_after_stops_after_2(run_seen, monkeypatch):
    from runner import cli
    monkeypatch.setattr(cli, "_cred_owner", lambda arm: (credentials.dummy(), RecOwner()))
    assert cli.main(["run-arm", "canary", ARM]) == 0
    assert run_seen == [2]


def test_run_arm_on_a_dry_pass_keeps_no_default_stop(run_seen):
    orchestrate.run_arm("dry1", "dryrun", credentials.dummy(), RecOwner())
    assert run_seen == [None]


# ---- final review m-1: a failed tracker check fails the command ----------------------------------------------------

@pytest.mark.parametrize("setup,what", [
    (lambda w, mp: setattr(w, "read_rc", 1), "read with the arm's PAT failed"),
    (lambda w, mp: mp.setattr(tracker, "supersede", lambda ctx, old, owner, new=None: {"action": "declined"}),
     "not closed again"),
    (lambda w, mp: mp.setattr(tracker, "create_bug", lambda ctx, owner, **k: (_ for _ in ()).throw(
        RuntimeError("owner declined the step-6 issue"))), "issue not created"),
], ids=["read", "close", "create"])
def test_cli_canary_exits_non_zero_naming_what_of_the_tracker_check_failed(world, monkeypatch, capsys, setup, what):
    from runner import cli
    setup(world, monkeypatch)
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: credentials.dummy())
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner())
    assert cli.main(["canary"]) == 1
    out = capsys.readouterr().out
    assert "tracker check failed" in out and what in out


def test_a_tracker_check_that_held_leaves_no_failure_and_the_cli_exits_zero(world, monkeypatch):
    from runner import cli
    monkeypatch.setattr(credentials, "from_keychain", lambda *a, **k: credentials.dummy())
    monkeypatch.setattr(owner_mod, "Owner", lambda *a, **k: RecOwner())
    assert "tracker_check_failed" not in orchestrate.canary(world.cred_of, RecOwner())
    assert cli.main(["canary"]) == 0
