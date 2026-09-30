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

def _gh_fake(repos: dict):
    """`repo._gh` stand-in: `gh repo view <slug> --json …` answered from `repos` (slug → view dict, absent = 404)."""
    calls = []

    def gh(argv):
        calls.append(argv)
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
    w = SimpleNamespace(events=[], repos={SLUG: GOOD, DISC: GOOD}, items=set(ITEMS), green=True,
                        read_rc=0, read_title=None, read_err=b"", stage_hosts=None, spec=None)
    monkeypatch.setattr(repo, "_gh", _gh_fake(w.repos))
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

    def run_arm(pass_, arm, cred, owner, limits_override=None, stop_after=None):
        w.events.append(("run_arm", pass_, arm, stop_after))
        return {"stopped_after": stop_after}
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
    assert sorted(c[3] for c in repo._gh.calls) == sorted([SLUG, DISC])


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
            return park if "issue" in text else True
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
        lambda p: shutil.rmtree(p.step(1) / "po"),
    "step 2: every PO decision pin-verified (N.b)":
        lambda p: (p.step(2) / "po" / "a1-001" / "model-pin.json").write_text(_pin(ok=False)),
    "step 2: every PO decision pin-verified (N.a)":
        lambda p: (p.step(2) / "a" / "po" / "a1-001" / "model-pin.json").write_text(_pin(ok=False)),
    "step 1: no harness fault (N.b run.json)":
        lambda p: _rw(p.step(1) / "run.json", harness_faults=[{"kind": "infra-auth"}]),
    "step 2: no harness fault (N.b run.json)":
        lambda p: (p.step(2) / "run.json").unlink(),
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
    assert set(DEFECTS) <= set(orchestrate.canary_row_names())
    # rows without a named defect here are the per-step twins of one that has (same code path, other step)
    assert {r.replace("step 1", "step N").replace("step 2", "step N") for r in orchestrate.canary_row_names()} == \
        {r.replace("step 1", "step N").replace("step 2", "step N") for r in DEFECTS}


@pytest.mark.parametrize("row", sorted(DEFECTS))
def test_each_row_fails_on_its_own_defect_alone(tree, row):
    DEFECTS[row](tree)
    rows = orchestrate.canary_check()
    assert _failing(rows) == {row}
    assert (paths.RESULTS / "canary" / "canary.md").read_text().rstrip().endswith("**Result: FAIL**")


def test_an_empty_results_tree_fails_every_row_without_crashing(tmp_state, monkeypatch):
    monkeypatch.setattr(secrets, "literals", lambda *a, **k: [LIT])
    rows = orchestrate.canary_check()
    # only the two absence rows (no credential file, no ledger entry) hold on nothing; every evidence row fails,
    # the scan rows included (a scan of evidence that is not there proves nothing)
    vacuous = {r for r in orchestrate.canary_row_names() if "credential file" in r or "canary ledger" in r}
    assert _failing(rows) == set(orchestrate.canary_row_names()) - vacuous
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
