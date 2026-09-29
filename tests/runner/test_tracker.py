"""Task 17: the step-6 bug in each arm's tracker, tracker snapshots, round-trip facts. No docker, no network:
`gh` is a scripted fake (real GitHub belongs to the canary, Task 26) and `bd` calls go through a fake `_bd`."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from runner import config, handoff, tracker
from runner.paths import Paths

TITLE = "Setting one agent's model changed another agent's model"


# --- pure helpers (plan text) -------------------------------------------------------------------------------

def test_github_issue_argv_is_a_bug_with_the_fixed_title_and_a_body_file(tmp_path):
    a = tracker.gh_create_argv("troupe-run/bakeoff-specs-openspec-pass1", tmp_path / "body.md")
    assert a[:4] == ["gh", "issue", "create", "--repo"]
    assert a[a.index("--title") + 1] == TITLE
    assert a[a.index("--type") + 1] == "Bug" and "--body-file" in a


def test_issue_url_becomes_a_ref():
    ref = tracker.parse_gh_url("https://github.com/troupe-run/bakeoff-specs-openspec-pass1/issues/1\n")
    assert ref.ref == "troupe-run/bakeoff-specs-openspec-pass1#1" and ref.id == "1"


def test_beads_create_json_becomes_a_ref():
    assert tracker.parse_bd('{"id": "bd-a3f8", "title": "x"}').ref == "beads bd-a3f8"


def test_commit_references_are_found_by_number_or_beads_id():
    log = "abc\x1fFix alias write-through (#1)\n\x1e\ndef\x1ftidy\nadd #12 later\n\x1e\nfed\x1fClose bd-a3f8\n\x1e"
    assert tracker.commits_referencing(log, "1") == ["abc"]            # "#12" is not "#1"
    assert tracker.commits_referencing(log, "bd-a3f8") == ["fed"]


def test_issue_links_a_commit_when_body_or_comments_name_its_sha():
    issue = {"body": "x", "comments": [{"body": "Fixed in abc1234def"}]}
    assert tracker.issue_links_commit(issue, ["abc1234def5678"]) is True
    assert tracker.issue_links_commit(issue, ["0000000"]) is False


def test_round_trip_facts_are_raw_facts(monkeypatch, tmp_path):
    monkeypatch.setattr(tracker.gitops, "commits_between", lambda p, a, b: "abc1234\x1fFix alias (#1)\n\x1e")
    monkeypatch.setattr(tracker.gitops, "numstat", lambda p, a, b: [(3, 1, "src/cli.py"), (5, 0, "specs/aliases.md")])
    ctx = type("C", (), {"paths": None, "arm": type("A", (), {"tracker": "github"})()})()
    issue = tracker.IssueRef("github", "o/r#1", "https://x", "1")
    snap = {"issues": [{"number": 1, "state": "CLOSED", "comments": [{"body": "done in abc1234"}], "body": ""}]}
    f = tracker.round_trip_facts(ctx, issue, "s0", "s1", snap)
    assert f == {"issue": "o/r#1", "state": "CLOSED", "comments": 1, "commits_referencing": ["abc1234"],
                 "issue_links_commit": True, "non_py_files_changed": ["specs/aliases.md"]}


# --- pure helpers (edges) -----------------------------------------------------------------------------------

def test_github_references_by_slug_or_issue_url_count_but_a_longer_number_or_beads_prefix_does_not():
    log = ("a1\x1fFixes o/r#7\x1e" "a2\x1fsee https://github.com/o/r/issues/7\x1e" "a3\x1fbump #70\x1e"
           "a4\x1fx-#7 is not a ref\x1e" "a5\x1fissue 7\x1e" "a6\x1fFixes troupe-run/bakeoff-specs-openspec-pass1#7\x1e"
           "a7\x1f#7: at the start\x1e")
    assert tracker.commits_referencing(log, "7") == ["a1", "a2", "a6", "a7"]


def test_beads_id_must_stand_alone():
    log = "b1\x1fClose r-fac.\x1e" "b2\x1fr-fac0 unrelated\x1e" "b3\x1fchild r-fac.1 done\x1e" "b4\x1fxr-fac\x1e"
    assert tracker.commits_referencing(log, "r-fac") == ["b1"]


def test_a_beads_issue_links_a_commit_through_its_close_reason_or_comment_text():
    assert tracker.issue_links_commit({"close_reason": "fixed in abc1234"}, ["abc1234ffff"]) is True
    assert tracker.issue_links_commit({"comments": [{"text": "see abc1234"}]}, ["abc1234ffff"]) is True
    assert tracker.issue_links_commit({"description": "nothing"}, ["abc1234ffff"]) is False


def test_parse_bd_takes_a_list_and_ignores_leading_noise():
    assert tracker.parse_bd('warning: x\n[{"id": "r-1"}]').id == "r-1"


def test_parse_gh_url_refuses_text_without_an_issue_url():
    with pytest.raises(ValueError):
        tracker.parse_gh_url("error: could not create issue\n")


def test_close_argv_says_superseded_by_a_harness_re_run_and_names_the_new_issue():
    a = tracker.gh_close_argv("o/r", "3", new_ref="o/r#4")
    assert a[:4] == ["gh", "issue", "close", "3"] and a[a.index("--repo") + 1] == "o/r"
    c = a[a.index("--comment") + 1]
    assert c.startswith("Superseded by a harness re-run") and "o/r#4" in c


def test_list_argv_reads_every_issue_with_comments_and_bodies():
    a = tracker.gh_list_argv("o/r")
    assert a[a.index("--state") + 1] == "all"
    assert {"number", "state", "comments", "body"} <= set(a[a.index("--json") + 1].split(","))


# --- effectful paths with fakes -----------------------------------------------------------------------------

class Owner:
    def __init__(self, yes=True):
        self.yes, self.asked = yes, []

    def confirm(self, text):
        self.asked.append(text)
        return self.yes


def _ctx(tmp_path, arm="openspec", pass_="pass1"):
    out = tmp_path / "out" / "06"
    out.mkdir(parents=True)
    return SimpleNamespace(pass_=pass_, arm=config.load_arm(arm), step=6, paths=Paths(pass_, arm), out=out)


class FakeGh:
    def __init__(self, stdout="https://github.com/troupe-run/bakeoff-specs-openspec-pass1/issues/3\n"):
        self.calls, self.stdout = [], stdout

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        if "--body-file" in argv:
            self.body = open(argv[argv.index("--body-file") + 1]).read()
        return subprocess.CompletedProcess(argv, 0, self.stdout, "")


def test_github_bug_is_created_from_the_host_after_the_owner_confirms(tmp_state, monkeypatch):
    gh = FakeGh(); monkeypatch.setattr(tracker.subprocess, "run", gh)
    ctx, owner = _ctx(tmp_state), Owner()
    ref = tracker.create_bug(ctx, owner)
    assert owner.asked and "troupe-run/bakeoff-specs-openspec-pass1" in owner.asked[0]
    assert ref == tracker.IssueRef("github", "troupe-run/bakeoff-specs-openspec-pass1#3",
                                   "https://github.com/troupe-run/bakeoff-specs-openspec-pass1/issues/3", "3")
    argv = gh.calls[0]
    assert argv[argv.index("--title") + 1] == TITLE
    brief = tracker.BRIEF.read_text()
    assert gh.body == handoff.issue_body(brief) and "Contract sections" not in gh.body
    assert "troupe config set coder.settings.model sonnet" in gh.body
    rec = json.loads((ctx.out / "issue.json").read_text())
    assert rec["ref"] == ref.ref and rec["title"] == TITLE and rec["source"] == "planted"


def test_owner_declining_the_github_issue_stops_step_6_and_calls_nothing(tmp_state, monkeypatch):
    gh = FakeGh(); monkeypatch.setattr(tracker.subprocess, "run", gh)
    with pytest.raises(RuntimeError, match="declined"):
        tracker.create_bug(_ctx(tmp_state), Owner(yes=False))
    assert gh.calls == []


def test_a_github_arm_on_a_pass_without_a_repo_is_refused(tmp_state, monkeypatch):
    gh = FakeGh(); monkeypatch.setattr(tracker.subprocess, "run", gh)
    with pytest.raises(RuntimeError, match="no GitHub repo"):
        tracker.create_bug(_ctx(tmp_state, pass_="dry9"), Owner())
    assert gh.calls == []


def test_a_substitute_bug_goes_through_the_same_path_with_its_own_title_and_body(tmp_state, monkeypatch):
    """Preflight B5 / ledger B5a-B5b: a substitute (title, body) is filed exactly like the planted one."""
    gh = FakeGh(); monkeypatch.setattr(tracker.subprocess, "run", gh)
    ctx = _ctx(tmp_state)
    tracker.create_bug(ctx, Owner(), title="Import drops comments", body="Steps:\n1. import\n")
    argv = gh.calls[0]
    assert argv[argv.index("--title") + 1] == "Import drops comments" and gh.body == "Steps:\n1. import\n"
    rec = json.loads((ctx.out / "issue.json").read_text())
    assert rec["source"] == "substitute" and rec["title"] == "Import drops comments"


@pytest.mark.parametrize("kw", [{"title": "only a title"}, {"body": "only a body"}, {"title": " ", "body": "b"},
                                {"title": "t", "body": "\n"}])
def test_a_substitute_needs_both_a_title_and_a_body(tmp_state, monkeypatch, kw):
    monkeypatch.setattr(tracker.subprocess, "run", FakeGh())
    with pytest.raises(ValueError):
        tracker.create_bug(_ctx(tmp_state), Owner(), **kw)


def test_a_failed_gh_create_raises_with_its_stderr(tmp_state, monkeypatch):
    def boom(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, "", "HTTP 404: Not Found")
    monkeypatch.setattr(tracker.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="404"):
        tracker.create_bug(_ctx(tmp_state), Owner())


def test_dry_backend_numbers_issues_and_snapshots_them(tmp_state):
    ctx = _ctx(tmp_state, arm="dryrun", pass_="dry9")
    ref = tracker.create_bug(ctx, Owner())
    f = ctx.paths.base / "tracker" / "issue-1.md"
    assert ref == tracker.IssueRef("dry", "dry#1", None, "1")
    assert f.read_text().startswith(f"# {TITLE}\n\n") and "anchor" in f.read_text()
    assert tracker.create_bug(ctx, Owner()).ref == "dry#2"
    snap = tracker.snapshot(ctx)
    assert [i["ref"] for i in snap["issues"]] == ["dry#1", "dry#2"]
    assert json.loads((ctx.out / "tracker.json").read_text()) == snap


class FakeBd:
    """Records bd argv; keeps a tiny issue table so list/show/close behave like bd 1.3.0 (probed)."""
    def __init__(self, issues=None):
        self.calls, self.issues, self.mounts = [], {i["id"]: i for i in (issues or [])}, []

    def __call__(self, ctx, *cmd, extra=None, check=True):
        self.calls.append(list(cmd)); self.mounts.append(extra or [])
        if cmd[:2] == ("bd", "create"):
            i = {"id": "r-new", "title": cmd[cmd.index("--title") + 1], "status": "open"}
            self.issues[i["id"]] = i
            return subprocess.CompletedProcess(cmd, 0, json.dumps(i), "")
        if cmd[:2] == ("bd", "list"):
            return subprocess.CompletedProcess(cmd, 0, json.dumps([{k: v for k, v in i.items() if k != "comments"}
                                                                  for i in self.issues.values()]), "")
        if cmd[:2] == ("bd", "show"):
            return subprocess.CompletedProcess(cmd, 0, json.dumps([self.issues[x] for x in cmd[2:]
                                                                  if x in self.issues]), "")
        if cmd[:2] == ("bd", "close"):
            if cmd[2] not in self.issues:
                if check:
                    raise RuntimeError("bd failed: no issue found")
                return subprocess.CompletedProcess(cmd, 1, "", "no issue found")
            self.issues[cmd[2]]["status"] = "closed"
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(cmd)


def test_beads_bug_is_created_in_the_container_with_the_body_as_a_file(tmp_state, monkeypatch):
    bd = FakeBd(); monkeypatch.setattr(tracker, "_bd", bd)
    ctx = _ctx(tmp_state, arm="speckitty", pass_="pass1")
    ref = tracker.create_bug(ctx, Owner())
    assert ref == tracker.IssueRef("beads", "beads r-new", None, "r-new")
    c = bd.calls[0]
    assert c[:2] == ["bd", "create"] and c[c.index("--type") + 1] == "bug" and "--json" in c
    assert c[c.index("--title") + 1] == TITLE and c[c.index("--body-file") + 1] == "/setup/issue.md"
    (m,) = bd.mounts[0]
    assert m.ctr == "/setup/issue.md" and m.ro and m.host.read_text() == handoff.issue_body(tracker.BRIEF.read_text())


def test_beads_snapshot_carries_comments_from_show(tmp_state, monkeypatch):
    bd = FakeBd([{"id": "r-1", "status": "closed", "comments": [{"text": "fixed in abc1234"}]}])
    monkeypatch.setattr(tracker, "_bd", bd)
    snap = tracker.snapshot(_ctx(tmp_state, arm="speckitty"))
    assert snap["backend"] == "beads" and snap["issues"][0]["comments"] == [{"text": "fixed in abc1234"}]


def test_beads_snapshot_of_an_empty_tracker_runs_no_show(tmp_state, monkeypatch):
    bd = FakeBd(); monkeypatch.setattr(tracker, "_bd", bd)
    assert tracker.snapshot(_ctx(tmp_state, arm="speckitty"))["issues"] == []
    assert [c[:2] for c in bd.calls] == [["bd", "list"]]


def test_github_snapshot_lists_every_issue(tmp_state, monkeypatch):
    gh = FakeGh(stdout=json.dumps([{"number": 3, "state": "OPEN", "comments": [], "body": "b"}]))
    monkeypatch.setattr(tracker.subprocess, "run", gh)
    ctx = _ctx(tmp_state)
    snap = tracker.snapshot(ctx)
    assert gh.calls[0][:3] == ["gh", "issue", "list"] and snap["issues"][0]["number"] == 3
    assert snap["survives_restore"] is True


def test_round_trip_facts_for_beads_match_by_id_and_read_status_and_comments(monkeypatch):
    monkeypatch.setattr(tracker.gitops, "commits_between", lambda p, a, b: "fed9876\x1fClose r-1\x1e")
    monkeypatch.setattr(tracker.gitops, "numstat", lambda p, a, b: [])
    snap = {"issues": [{"id": "r-1", "status": "closed", "close_reason": "fed9876", "comment_count": 2}]}
    f = tracker.round_trip_facts(None, tracker.IssueRef("beads", "beads r-1", None, "r-1"), "a", "b", snap)
    assert (f["state"], f["comments"], f["commits_referencing"], f["issue_links_commit"]) == \
        ("closed", 2, ["fed9876"], True)


def test_round_trip_facts_when_the_issue_is_missing_from_the_snapshot(monkeypatch):
    monkeypatch.setattr(tracker.gitops, "commits_between", lambda p, a, b: "")
    monkeypatch.setattr(tracker.gitops, "numstat", lambda p, a, b: [])
    f = tracker.round_trip_facts(None, tracker.IssueRef("github", "o/r#9", None, "9"), "a", "b", {"issues": []})
    assert f["state"] is None and f["comments"] == 0 and f["issue_links_commit"] is False


# --- supersede (a harness re-run of step 6) -----------------------------------------------------------------

def _superseded(ctx):
    return [json.loads(l) for l in (ctx.out / "tracker-superseded.jsonl").read_text().splitlines()]


def test_github_supersede_closes_the_old_issue_after_the_owner_confirms_and_names_both(tmp_state, monkeypatch):
    gh = FakeGh(); monkeypatch.setattr(tracker.subprocess, "run", gh)
    ctx, owner = _ctx(tmp_state), Owner()
    old, new = tracker.IssueRef("github", "o/r#1", None, "1"), tracker.IssueRef("github", "o/r#2", None, "2")
    rec = tracker.supersede(ctx, old, owner, new=new)
    assert owner.asked and "o/r#1" in owner.asked[0]
    assert gh.calls == [tracker.gh_close_argv("o/r", "1", new_ref="o/r#2")]
    assert rec["action"] == "closed" and rec["old"] == "o/r#1" and rec["new"] == "o/r#2"
    assert _superseded(ctx) == [rec]


def test_github_supersede_declined_closes_nothing_and_says_so(tmp_state, monkeypatch):
    gh = FakeGh(); monkeypatch.setattr(tracker.subprocess, "run", gh)
    ctx = _ctx(tmp_state)
    rec = tracker.supersede(ctx, tracker.IssueRef("github", "o/r#1", None, "1"), Owner(yes=False))
    assert gh.calls == [] and rec["action"] == "declined" and _superseded(ctx) == [rec]


def test_beads_supersede_of_an_issue_a_restore_removed_does_not_crash(tmp_state, monkeypatch):
    """Preflight M9: the restore took the step-6 issue away with the work tree; `bd close` would raise."""
    bd = FakeBd(); monkeypatch.setattr(tracker, "_bd", bd)
    ctx = _ctx(tmp_state, arm="speckitty")
    rec = tracker.supersede(ctx, tracker.IssueRef("beads", "beads r-gone", None, "r-gone"), Owner())
    assert rec["action"] == "absent" and not any(c[:2] == ["bd", "close"] for c in bd.calls)
    assert rec["survives_restore"] is False


def test_beads_supersede_closes_an_issue_that_is_still_there(tmp_state, monkeypatch):
    bd = FakeBd([{"id": "r-1", "status": "open"}]); monkeypatch.setattr(tracker, "_bd", bd)
    ctx = _ctx(tmp_state, arm="speckitty")
    rec = tracker.supersede(ctx, tracker.IssueRef("beads", "beads r-1", None, "r-1"), Owner(),
                            new=tracker.IssueRef("beads", "beads r-2", None, "r-2"))
    close = next(c for c in bd.calls if c[:2] == ["bd", "close"])
    assert close[2] == "r-1" and close[close.index("--reason") + 1].startswith("Superseded by a harness re-run")
    assert "beads r-2" in close[close.index("--reason") + 1]
    assert rec["action"] == "closed" and bd.issues["r-1"]["status"] == "closed"


def test_beads_supersede_of_an_already_closed_issue_leaves_it(tmp_state, monkeypatch):
    bd = FakeBd([{"id": "r-1", "status": "closed"}]); monkeypatch.setattr(tracker, "_bd", bd)
    rec = tracker.supersede(_ctx(tmp_state, arm="speckitty"), tracker.IssueRef("beads", "beads r-1", None, "r-1"),
                            Owner())
    assert rec["action"] == "already-closed" and not any(c[:2] == ["bd", "close"] for c in bd.calls)


def test_dry_supersede_marks_the_old_file_and_tolerates_a_missing_one(tmp_state):
    ctx = _ctx(tmp_state, arm="dryrun", pass_="dry9")
    old = tracker.create_bug(ctx, Owner())
    new = tracker.create_bug(ctx, Owner())
    assert tracker.supersede(ctx, old, Owner(), new=new)["action"] == "closed"
    assert "Superseded by a harness re-run" in (ctx.paths.base / "tracker" / "issue-1.md").read_text()
    gone = tracker.IssueRef("dry", "dry#9", None, "9")
    assert tracker.supersede(ctx, gone, Owner())["action"] == "absent"


def test_which_backends_survive_a_harness_restore_is_recorded():
    """Preflight M9: only GitHub state lives outside the arm's snapshotted trees (dry lives in the arm base,
    beside the snapshots, so it survives too); beads lives in the work tree."""
    assert tracker.SURVIVES_RESTORE == {"github": True, "dry": True, "beads": False}
