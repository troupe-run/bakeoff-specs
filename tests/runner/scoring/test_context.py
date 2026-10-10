"""Decision review context (plan 2026-10-09-decision-context): plan -> run in each label's code -> write."""
import json, os, stat, subprocess
import pytest
from runner import paths
from runner.scoring import context as cx, decisions as dz, judge
from tests.runner.scoring.test_decisions import D1, _extracted, anon_fixture

PLAN = {"runnable": True, "why": "dash values",
        "files": {".troupe/troupe.yml": "note: old\n"},
        "commands": [{"args": ["config", "set", "note", "-hello"]},
                     {"args": ["config", "show", "note"], "env": {"TROUPE_ACTOR": "human:o"}}],
        "show": [".troupe/troupe.yml", "missing.yml"]}
WRITTEN = {"stakes": "Values starting with '-'.", "tradeoff": "Route 1 needs nothing extra.",
           "examples": [{"input": "`config set note -hello`", "before": "note: old",
                         "results": {"1": "stores \"-hello\"", "2": "error, exit 2"}, "observed": True}]}


# ---- plan ------------------------------------------------------------------------------------------------------------

def test_a_plan_is_parsed_with_defaults():
    got = cx.parse_plan(json.dumps(PLAN))
    assert got["commands"][0] == {"args": ["config", "set", "note", "-hello"], "env": {}}
    assert got["commands"][1]["env"] == {"TROUPE_ACTOR": "human:o"} and got["show"][1] == "missing.yml"


def test_a_topic_with_nothing_to_run_says_so():
    assert cx.parse_plan('{"runnable": false, "why": "process"}') == {"runnable": False, "why": "process"}


@pytest.mark.parametrize("bad", [
    {"files": {"../x": "a"}}, {"files": {"/etc/x": "a"}}, {"files": {"a/../../x": "a"}},
    {"commands": []}, {"commands": [{"args": ["config", "show", "x"]}] * (cx.MAX_COMMANDS + 1)},
    {"commands": [{"args": ["config", "watch"]}]}, {"commands": [{"args": ["rm", "-rf", "/"]}]},
    {"commands": [{"args": ["config", "show"], "env": {"PATH": "/x"}}]},
    {"commands": [{"args": ["config", "show"], "env": {"lower": "x"}}]},
    {"commands": [{"args": ["config", "show"], "env": {"UV_INDEX_URL": "x"}}]},
    {"commands": [{"args": ["config", "show"], "env": {"PYTHONHOME": "/x"}}]},
    {"commands": [{"args": ["config", "show", "--theatre", "/work"]}]},
    {"commands": [{"args": ["config", "show", "--theatre=/work"]}]},
    {"commands": [{"args": ["config", "show", "a\x00b"]}]},
    {"files": {"-x": "a"}}, {"show": ["sub/-x"]},
    {"show": ["../../etc/passwd"]}])
def test_a_plan_with_paths_outside_the_theatre_an_option_like_path_a_harness_variable_or_watch_is_refused(bad):
    with pytest.raises(judge.BadReply):
        cx.parse_plan(json.dumps({**PLAN, **bad}))


# ---- run: the sandbox script, with stand-in `uv` and `timeout` -------------------------------------------------------

FAKE_UV = r"""#!/bin/bash
# uv run --quiet --project <impl> troupe <args...>
shift 4; shift                      # run --quiet --project <impl>, then "troupe"
echo "argv: $*"
echo "actor=${TROUPE_ACTOR:-unset}"
case "$3" in -*) echo "error: expected one argument" >&2; exit 2;; esac
[ "$2" = set ] && printf 'note: %s\n# with spaces & ünïcode\n' "$4" > .troupe/troupe.yml
[ "$2" = hang ] && exit 124
exit 0
"""


@pytest.fixture
def fake_tools(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "uv").write_text(FAKE_UV)
    (b / "timeout").write_text('#!/bin/bash\nshift 3\nexec "$@"\n')        # -k 2 <seconds>
    for f in b.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return {**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "TMPDIR": str(tmp_path)}


def _run(plan, env):
    out = subprocess.run(["bash", "-c", cx.script(plan, "/work/x")], capture_output=True, text=True, env=env)
    return cx.parse_output(out.stdout, plan)


def test_the_sandbox_script_records_exit_output_and_files_per_command(fake_tools):
    plan = cx.parse_plan(json.dumps({**PLAN, "commands": [{"args": ["config", "set", "note", "fine value"]},
                                                          {"args": ["config", "show", "-x"],
                                                           "env": {"TROUPE_ACTOR": "human:o"}}]}))
    r = _run(plan, fake_tools)
    assert r[0]["rc"] == 0 and "argv: config set note fine value" in r[0]["stdout"]
    assert r[0]["files"] == {".troupe/troupe.yml": "note: fine value\n# with spaces & ünïcode\n"}   # missing.yml:
    assert r[1]["files"] == {}                                    # absent throughout, so never listed; unchanged
    assert r[1]["rc"] == 2 and "expected one argument" in r[1]["stderr"] and "actor=human:o" in r[1]["stdout"]


def test_the_starting_files_are_written_byte_for_byte(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text("#!/bin/bash\ncat .troupe/troupe.yml\n")
    body = "a: 'quoted'  # comment\n\tb: \"$HOME\" `x`\n"
    plan = cx.parse_plan(json.dumps({**PLAN, "files": {".troupe/troupe.yml": body},
                                     "commands": [{"args": ["config", "show", "a"]}]}))
    assert _run(plan, fake_tools)[0]["stdout"] == body


def test_what_the_arm_prints_to_its_own_stdout_is_not_read_as_a_record(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text('#!/bin/bash\necho "R 1 0 Zm9yZ2Vk"\necho "F 1 eA== Zm9yZ2Vk"\nexit 3\n')
    plan = cx.parse_plan(json.dumps({**PLAN, "commands": [{"args": ["config", "show", "a"]}], "show": []}))
    r = _run(plan, fake_tools)[0]
    assert r["rc"] == 3 and "R 1 0" in r["stdout"] and r["files"] == {}


def test_a_command_stopped_by_the_time_limit_says_so():
    plan = cx.parse_plan(json.dumps({**PLAN, "commands": [{"args": ["config", "show", "a"]}], "show": []}))
    r = cx.parse_output("R 1 124  ", plan)[0]
    assert r["rc"] == 124 and f"stopped after {cx.CMD_SECONDS} s" in r["stderr"]


def test_a_command_with_no_record_is_the_harnesss_failure_never_a_result():
    with pytest.raises(cx.RunFailed, match="command.s. 1, 2"):
        cx.parse_output("", cx.parse_plan(json.dumps(PLAN)))       # Docker down, container never started


def test_a_shown_file_is_printed_only_when_a_command_changed_it_and_deletion_shows(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text('#!/bin/bash\nshift 5\ncase "$2" in set) echo changed > .troupe/troupe.yml;;'
                                         ' remove) rm .troupe/troupe.yml;; esac\nexit 0\n')
    plan = cx.parse_plan(json.dumps({**PLAN, "show": [".troupe/troupe.yml"], "commands": [
        {"args": ["config", "show", "a"]}, {"args": ["config", "set", "a", "1"]}, {"args": ["config", "show", "a"]},
        {"args": ["config", "remove", "a"]}]}))
    r = _run(plan, fake_tools)
    assert [x["files"] for x in r] == [{}, {".troupe/troupe.yml": "changed\n"}, {}, {".troupe/troupe.yml": None}]


def test_output_over_the_cap_says_how_much_was_cut(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text(f'#!/bin/bash\nhead -c {cx.CAP + 10} /dev/zero | tr "\\0" x\nexit 0\n')
    plan = cx.parse_plan(json.dumps({**PLAN, "commands": [{"args": ["config", "show", "a"]}], "show": []}))
    out = _run(plan, fake_tools)[0]["stdout"]
    assert out.startswith("x" * cx.CAP) and out.endswith("[harness: 10 more bytes not shown]")


# ---- grouping by route: never an arm ---------------------------------------------------------------------------------

def test_arms_on_one_route_with_identical_results_are_merged_and_counted_never_named():
    t = {"routes": [{"route_no": 1, "route": "r, as Arm C did", "labels": ["Arm A", "Arm B", "Arm C"]},
                    {"route_no": 2, "route": "not considered", "labels": ["Arm D"]}]}
    same, other = [{"rc": 0}], [{"rc": 2}]
    got = cx.by_route(t, {"Arm A": same, "Arm B": same, "Arm C": other, "Arm D": same}, dz._cleaner([]))
    assert got[0]["outcomes"] == [{"arms": 2, "results": same}, {"arms": 1, "results": other}]
    assert got[1]["outcomes"] == [{"arms": 1, "results": same}]
    assert "Arm" not in json.dumps(got)                               # the route text is cleaned too


def test_scrubbing_removes_the_copy_path_and_the_theatre_path():
    r = cx._scrub_results([{"args": [], "env": {}, "rc": 1, "stdout": "/work/bakeoff-specs-alpha/src/x.py",
                            "stderr": "in /tmp/tmp.AbC123/.troupe", "files": {"f": None}}], ["alpha"])[0]
    assert r["stdout"] == "/work/project/src/x.py" and r["stderr"] == "in /theatre/.troupe"


# ---- write -----------------------------------------------------------------------------------------------------------

def test_the_written_context_must_give_every_route_a_result():
    bad = {**WRITTEN, "examples": [{**WRITTEN["examples"][0], "results": {"1": "x"}}]}
    with pytest.raises(judge.BadReply, match=r"every route \['1', '2'\]"):
        cx.parse_written(json.dumps(bad), [1, 2], ["Arm A"])
    assert cx.parse_written(json.dumps(WRITTEN), [1, 2], ["Arm A"])["examples"][0]["observed"] is True


def test_a_written_context_that_names_a_method_is_refused(monkeypatch):
    from runner.scoring import leakcheck
    monkeypatch.setattr(leakcheck, "words", lambda arms: ["speckit"])
    with pytest.raises(judge.BadReply, match="names a method"):
        cx.parse_written(json.dumps({**WRITTEN, "stakes": "as speckit does"}), [1, 2], [], ["speckit"])


def test_nothing_is_observed_when_nothing_ran():
    got = cx.parse_written(json.dumps(WRITTEN), [1, 2], [], runnable=False)
    assert got["examples"][0]["observed"] is False


def test_a_written_context_that_names_an_arm_is_refused():
    bad = {**WRITTEN, "tradeoff": "C fixed it later"}
    with pytest.raises(judge.BadReply, match="names an arm"):
        cx.parse_written(json.dumps(bad), [1, 2], ["Arm A", "Arm B", "Arm C"])


def test_no_examples_needs_plain_words():
    with pytest.raises(judge.BadReply, match="in_practice"):
        cx.parse_written(json.dumps({**WRITTEN, "examples": []}), [1, 2], [])
    assert cx.parse_written(json.dumps({**WRITTEN, "examples": [], "in_practice": "x"}), [1, 2], [])


# ---- the stage -------------------------------------------------------------------------------------------------------

class FakeRunner:
    def __init__(self, by_label=None, fail=(), not_ready=()):
        self.calls, self.by_label, self.fail, self.not_ready, self.readied = [], by_label or {}, fail, not_ready, []

    def ready(self, labels):
        self.readied.append(labels)
        if bad := [lab for lab in labels if lab in self.not_ready]:
            from runner.scoring import inputs
            raise inputs.InputError(f"cannot run {bad}")

    def run(self, label, plan):
        self.calls.append(label)
        if label in self.fail:
            raise cx.RunFailed(f"{label}: the sandbox failed: TimeoutExpired")
        return self.by_label.get(label, [{"args": ["config"], "env": {}, "rc": 0, "stdout": "ok /work/bakeoff-specs-alpha",
                                          "stderr": "", "files": {}}])


TWO_ROUTES = json.dumps({"topics": [
    {"id": "dash", "question": "How are dash values parsed?", "not_considered": {"proposed": "3", "why": "w"},
     "routes": [{"route": "positional", "labels": ["Arm A"], "reason_given": "r", "outcome": "kept",
                 "proposed": "4", "proposed_why": "p"}]}]})


@pytest.fixture
def aligned(tmp_state):
    anon_fixture(arms=("alpha", "beta"), steps=("01",))
    _extracted("Arm A", "01", D1)
    _extracted("Arm B", "01", "[]")
    dz.align("p", judge.FakeJudge([TWO_ROUTES]))
    return paths.scoring_out("p")


def test_the_stage_plans_runs_every_label_and_writes_a_blind_context(aligned):
    j, rn = judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner()
    assert cx.run("p", j, rn) == {"written": 1, "failed": 0, "skipped": 0}
    assert sorted(rn.calls) == ["Arm A", "Arm B"] and rn.readied == [["Arm A", "Arm B"]]
    item = cx.item_dir("p", "dash")
    assert j.files == [["topic.json", "contract.md", "steps.md"], ["topic.json", "results.json"]]
    assert "Arm" not in (item / "topic.json").read_text()
    results = (item / "results.json").read_text()
    assert "Arm" not in results and "alpha" not in results and "ok /work/project" in results
    rec = json.loads(cx.out_path("p", "dash").read_text())
    assert rec["status"] == "ok" and rec["routes"] == [["positional", ["Arm A"]], ["not considered", ["Arm B"]]]
    assert rec["context"]["examples"][0]["results"]["2"] == "error, exit 2"


def test_the_stage_resumes_and_redoes_a_topic_whose_routes_changed(aligned):
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner())
    j = judge.FakeJudge([])
    assert cx.run("p", j, FakeRunner())["skipped"] == 1 and j.prompts == []
    assert cx.estimate("p") == {"calls": 0, "topics": 0}
    rec = json.loads(cx.out_path("p", "dash").read_text())
    moved = [["positional", ["Arm A", "Arm B"]], ["not considered", []]]      # same texts, labels moved
    cx.out_path("p", "dash").write_text(json.dumps({**rec, "routes": moved}))
    assert cx.estimate("p") == {"calls": 2, "topics": 1}


def test_a_topic_with_nothing_to_run_runs_nothing_and_is_written_from_the_routes(aligned):
    j, rn = judge.FakeJudge(['{"runnable": false, "why": "process"}',
                             json.dumps({**WRITTEN, "examples": [], "in_practice": "Plain words."})]), FakeRunner()
    cx.run("p", j, rn)
    assert rn.calls == [] and j.files[1] == ["topic.json"] and "Nothing could be run" in j.prompts[1]
    assert json.loads(cx.out_path("p", "dash").read_text())["runnable"] is False


def test_an_arm_whose_code_cannot_run_stops_the_stage_before_anything_is_spent(aligned):
    from runner.scoring import inputs
    j = judge.FakeJudge([])
    with pytest.raises(inputs.InputError, match="cannot run"):
        cx.run("p", j, FakeRunner(not_ready=("Arm B",)))
    assert j.prompts == [] and not cx.out_path("p", "dash").exists()


def test_a_sandbox_failure_mid_topic_fails_the_topic_never_becomes_a_result_and_is_retried(aligned):
    j = judge.FakeJudge([json.dumps(PLAN)])
    assert cx.run("p", j, FakeRunner(fail=("Arm B",)))["failed"] == 1
    rec = json.loads(cx.out_path("p", "dash").read_text())
    assert rec["status"] == "context_failed" and rec["why"].startswith("run: Arm B")
    assert not (cx.item_dir("p", "dash") / "results.json").exists() and len(j.prompts) == 1   # no write call
    assert cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner(),
                  retry_failed=True)["written"] == 1


def test_two_bad_replies_record_the_topic_as_failed_and_retry_failed_redoes_it(aligned):
    cx.run("p", judge.FakeJudge(["nope", "still nope"]), FakeRunner())
    rec = json.loads(cx.out_path("p", "dash").read_text())
    assert rec["status"] == "context_failed" and rec["why"].startswith("plan:")
    assert cx.estimate("p") == {"calls": 0, "topics": 0} and cx.estimate("p", retry_failed=True)["calls"] == 2
    assert cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner(),
                  retry_failed=True)["written"] == 1


def test_only_limits_the_run_to_the_named_sheet_ids(aligned):
    j = judge.FakeJudge([])
    assert cx.run("p", j, FakeRunner(), only=["T9"]) == {"written": 0, "failed": 0, "skipped": 0}


def test_the_container_judges_mount_check_accepts_a_context_item(aligned):
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner())
    home = paths.judge_home("p") / "call"
    item = cx.item_dir("p", "dash")
    judge.check_mounts(judge.mounts(home, item, ["topic.json", "contract.md", "steps.md"]), "p")
    judge.check_mounts(judge.mounts(home, item, ["topic.json", "results.json"]), "p")


def test_the_context_stage_needs_approval_for_its_two_calls_per_topic_and_passes_only(aligned, monkeypatch):
    from runner import cli
    monkeypatch.setattr(judge, "items", lambda pass_: [])
    monkeypatch.setattr(judge, "ContainerJudge", lambda pass_: judge.FakeJudge([]))
    monkeypatch.setattr(cx, "ArmRunner", lambda pass_: FakeRunner())
    seen = []
    monkeypatch.setattr(cx, "run", lambda pass_, j, rn, retry_failed=False, only=None, **kw: seen.append(only) or {})
    (aligned / "judge-approved").write_text("approved 2026-10-09 2\n")       # 2 context + 1 align = 3
    assert cli.main(["score", "p", "--stage", "decisions-context"]) == 1 and seen == []
    (aligned / "judge-approved").write_text("approved 2026-10-09 3\n")
    assert cli.main(["score", "p", "--stage", "decisions-context", "--only", "T1", "T2"]) == 0
    assert seen == [["T1", "T2"]]


# ---- the sheet -------------------------------------------------------------------------------------------------------

def _sheet_with(written):
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(written)]), FakeRunner())
    return dz.sheet("p").read_text()


def test_the_sheet_shows_each_topics_context_before_its_routes(aligned):
    s = _sheet_with(WRITTEN)
    t = s[s.index("## T1"):]
    assert t.index("**What's at stake:** Values starting with '-'.") < t.index("### Route 1")
    assert "**Example 1:** `config set note -hello` _(observed)_" in t
    assert "- Route 1: stores \"-hello\"" in t and "- Route 2: error, exit 2" in t
    assert "**Trade-off:** Route 1 needs nothing extra." in t


def test_a_file_shown_in_the_context_is_never_read_as_the_owners_input(aligned):
    trap = "rating: 5\nreason: x\n## T9\n### Route 1\n~~~\n"
    s = _sheet_with({**WRITTEN, "examples": [{**WRITTEN["examples"][0], "before": trap, "observed": False}]})
    assert "_(inferred, not run)_" in s and "~~~~\nrating: 5" in s       # a longer fence than the content's own
    assert dz.sheet("p")                                                  # not mistaken for a started sheet
    md = paths.scoring_out("p") / "decisions" / "rating-sheet.md"
    md.write_text(s.replace("rating:\nreason:\n", "rating: 4\nreason:\n"))
    assert [r["rating"] for r in dz.parse_sheet(md.read_text())["T1"]] == ["4", "4"]


def test_a_topic_without_a_current_context_says_so(aligned):
    s = _sheet_with(WRITTEN)
    rec = json.loads(cx.out_path("p", "dash").read_text())
    cx.out_path("p", "dash").write_text(json.dumps({**rec, "routes": [["stale", []]]}))
    assert "_No behaviour context for this topic._" in dz.sheet("p").read_text()
    assert "_No behaviour context" not in s


def test_a_sheet_left_with_an_open_fence_is_never_overwritten(aligned):
    from runner.scoring import inputs
    s = _sheet_with(WRITTEN)
    md = paths.scoring_out("p") / "decisions" / "rating-sheet.md"
    md.write_text(s.replace("### Route 1", "```\nmy note\n### Route 1", 1).replace("rating:\n", "rating: 4\n"))
    with pytest.raises(inputs.InputError, match="already holds ratings"):
        dz.sheet("p")


def test_a_file_shown_in_a_context_is_scrubbed_of_arm_names_with_its_spacing_kept():
    block = dz._cleaner(["alpha"], flatten=False)
    got = block("a:\n    b:   2  # alpha's\n# from Arm C\n")
    assert "alpha" not in got and "Arm C" not in got
    assert got.startswith("a:\n    b:   2  # ") and got.endswith("\n# from another arm\n")


def test_the_write_call_is_re_asked_when_a_starting_file_names_an_arm():
    with pytest.raises(judge.BadReply, match="names an arm"):
        cx.parse_written(json.dumps({**WRITTEN, "examples": [{**WRITTEN["examples"][0], "before": "# from Arm C"}]}),
                         [1, 2], ["Arm A", "Arm B", "Arm C"])


def test_a_result_holding_a_file_is_shown_with_its_lines_and_indentation_kept(aligned):
    yml = "exit 0; the file now reads:\nagent:\n  prompt: |2 # the prompt\n     indented first\n    second\n"
    s = _sheet_with({**WRITTEN, "examples": [{**WRITTEN["examples"][0], "results": {"1": yml, "2": "exit 2"}}]})
    assert ("- Route 1: exit 0; the file now reads:\n\n  ~~~\n  agent:\n    prompt: |2 # the prompt\n"
            "       indented first\n      second\n  ~~~\n") in s
    assert "- Route 2: exit 2" in s
    md = paths.scoring_out("p") / "decisions" / "rating-sheet.md"
    from runner.scoring import rate
    filled = rate.set_ratings(md.read_text(), "T1", ["4", "2"])                       # the fenced file is skipped
    assert [r["rating"] for r in dz.parse_sheet(filled)["T1"]] == ["4", "2"]


def test_redo_writes_a_topic_again_with_the_owners_ask_and_keeps_the_earlier_record(aligned):
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner())
    j = judge.FakeJudge([json.dumps(PLAN), json.dumps({**WRITTEN, "stakes": "Again."})])
    assert cx.run("p", j, FakeRunner(), only=["T1"], redo=True, ask="run a hand edit")["written"] == 1
    assert "The owner asked for this topic to be re-run with: run a hand edit" in j.prompts[0]
    assert json.loads(cx.out_path("p", "dash").read_text())["context"]["stakes"] == "Again."
    assert json.loads((cx.out_dir("p") / "dash.1.json").read_text())["context"]["stakes"] == WRITTEN["stakes"]


def test_redo_without_only_is_refused(aligned):
    from runner.scoring import inputs
    with pytest.raises(inputs.InputError, match="need --only"):
        cx.run("p", judge.FakeJudge([]), FakeRunner(), redo=True)


def test_a_hand_edit_step_rewrites_the_file_between_commands_without_running_troupe(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text("#!/bin/bash\ncat .troupe/troupe.yml\n")
    plan = cx.parse_plan(json.dumps({**PLAN, "show": [".troupe/troupe.yml"], "commands": [
        {"args": ["config", "show", "a"]},
        {"edit": {"path": ".troupe/troupe.yml", "content": "note: by hand\n"}},
        {"args": ["config", "history"]}]}))
    r = _run(plan, fake_tools)
    assert r[0]["stdout"] == "note: old\n" and r[1]["hand_edit"] == ".troupe/troupe.yml" and r[1]["rc"] == 0
    assert r[1]["files"] == {".troupe/troupe.yml": "note: by hand\n"} and r[2]["stdout"] == "note: by hand\n"


@pytest.mark.parametrize("bad", [{"edit": {"path": "../x", "content": "a"}}, {"edit": {"path": "x"}}, {"edit": "x"}])
def test_a_hand_edit_outside_the_theatre_or_without_content_is_refused(bad):
    with pytest.raises(judge.BadReply, match="edit"):
        cx.parse_plan(json.dumps({**PLAN, "commands": [bad]}))


# ---- watch, sleep, symlinks, listings, --theatre, no login name (2026-10-10) ----------------------------------------

WATCHED = {**PLAN, "show": [], "commands": [
    {"watch": "start", "args": ["config", "watch"]},
    {"edit": {"path": ".troupe/troupe.yml", "content": "note: by hand\n"}}, {"sleep": 0.3},
    {"watch": "stop", "signal": "SIGINT"}]}


def _plan(steps, **kw):
    return {**PLAN, "show": [], "commands": steps, **kw}


@pytest.mark.parametrize("ok", [
    ["--theatre", ".", "config", "get", "x"], ["config", "--theatre=sub", "show"], ["config", "show", "--theatre", "a/b"],
    ["--theatre=linked", "config", "set", "note", "--theatre-like"]])
def test_a_relative_theatre_inside_the_theatre_is_accepted_in_any_position(ok):
    assert cx.parse_plan(json.dumps(_plan([{"args": ok}])))["commands"][0]["args"] == ok


@pytest.mark.parametrize("bad", [
    ["--theatre", "/tmp", "config", "show"], ["--theatre=../x", "config", "show"], ["config", "show", "--theatre"],
    ["config", "show", "--theatre="], ["--theat", "/x", "config", "show"], ["config", "show", "--the=/x"],
    ["--theatre", ".", "show"], ["--theatre", "--theatre", "config", "show"]])
def test_an_absolute_dotdot_missing_or_abbreviated_theatre_or_no_config_is_refused(bad):
    with pytest.raises(judge.BadReply, match="theatre|config"):
        cx.parse_plan(json.dumps(_plan([{"args": bad}])))


def test_env_may_set_or_unset_the_login_variables_and_passwd_defaults_to_true():
    got = cx.parse_plan(json.dumps(_plan([{"args": ["config", "show"], "env": {"USER": None, "LOGNAME": "o"}}])))
    assert got["commands"][0]["env"] == {"USER": None, "LOGNAME": "o"} and got["passwd"] is True
    assert cx.parse_plan(json.dumps(_plan([{"args": ["config", "show"]}], passwd=False)))["passwd"] is False


@pytest.mark.parametrize("bad", [
    _plan([{"args": ["config", "show"], "env": {"HOME": None}}]), _plan([{"args": ["config", "show"]}], passwd="no"),
    _plan([{"args": ["config", "show"], "env": {"USER": 1}}])])
def test_a_harness_variable_cannot_be_unset_and_passwd_must_be_a_boolean(bad):
    with pytest.raises(judge.BadReply, match="env|passwd"):
        cx.parse_plan(json.dumps(bad))


def test_a_watch_plan_is_parsed_into_start_steps_stop():
    got = cx.parse_plan(json.dumps(WATCHED))["commands"]
    assert got[0] == {"watch": "start", "args": ["config", "watch"], "env": {}}
    assert got[2] == {"sleep": 0.3, "args": [], "env": {}}
    assert got[3] == {"watch": "stop", "signal": "SIGINT", "args": [], "env": {}}


@pytest.mark.parametrize("steps, match", [
    ([{"watch": "start", "args": ["config", "watch"]}], "ends with watch running"),
    ([{"watch": "stop", "signal": "SIGINT"}], "no watch is running"),
    ([{"watch": "start", "args": ["config", "watch"]}, {"watch": "start", "args": ["config", "watch"]}],
     "already running"),
    ([{"watch": "start", "args": ["config", "watch"]}, {"watch": "stop", "signal": "SIGKILL"}], "SIGINT or SIGTERM"),
    ([{"watch": "start", "args": ["config", "watch"]}, {"watch": "stop"}], "SIGINT or SIGTERM"),
    ([{"watch": "start", "args": ["config", "show"]}], "watch start runs `config watch`"),
    ([{"args": ["--theatre", ".", "config", "watch"]}], "runs only as"),
    ([{"watch": "pause"}], '"start" or "stop"'),
    ([{"sleep": 1, "edit": {"path": "x", "content": ""}}], "one step kind"),
    ([{"sleep": 0}], "sleep"), ([{"sleep": cx.MAX_SLEEP_SECONDS + 1}], "sleep"), ([{"sleep": True}], "sleep"),
    ([{"sleep": 6}, {"sleep": 6}], "in all"),
    ([{"symlink": {"path": "l", "target": "/etc"}}], "symlink"),
    ([{"symlink": {"path": "l", "target": "../x"}}], "symlink"),
    ([{"symlink": {"path": "/l", "target": "x"}}], "symlink"), ([{"symlink": {"path": "l"}}], "symlink"),
    ([{"list": "/"}], "list"), ([{"list": "../x"}], "list"), ([{"list": ["."]}], "list"), (["x"], "JSON object")])
def test_bad_watch_sleep_symlink_and_list_steps_are_refused(steps, match):
    with pytest.raises(judge.BadReply, match=match):
        cx.parse_plan(json.dumps(_plan(steps)))


def test_the_plan_prompt_says_what_the_sandbox_now_allows():
    p = cx.plan_prompt()
    assert "cannot be unset" not in p and '"passwd": false' in p and '{"USER": null}' in p
    assert '"watch": "start"' in p and '"signal": "SIGINT"' in p and '"symlink"' in p and '"list"' in p
    assert '["--theatre", ".", "config", "get", "x"]' in p and "applies to the whole plan" in p


def test_a_plan_at_its_limits_ends_inside_the_sandboxs_600_seconds_by_the_constants():
    assert cx.worst_seconds() < 600 and cx.WATCH_SECONDS < 600                          # hidden.run_script: 600 s
    assert cx.WATCH_READY_SECONDS <= cx.CMD_SECONDS and cx.WATCH_STOP_SECONDS + 1 <= cx.CMD_SECONDS


def test_the_generated_script_always_ends_a_watch_bounded_in_time():
    sc = cx.script(cx.parse_plan(json.dumps(WATCHED)), "/work/x")
    assert "set -m" in sc and "trap 'if [ -n \"$W\" ]; then wstop TERM; fi' EXIT" in sc
    assert 'kill -s KILL -- "-$W"' in sc and f"timeout -k 2 {cx.WATCH_SECONDS} uv run" in sc and "wstop INT" in sc


FAKE_WATCH_UV = r"""#!/bin/bash
shift 5                             # run --quiet --project <impl> troupe
case " $* " in
*" watch "*)
  echo $$ > "$TMPDIR/watch.pid"
  [ -f broken ] && { echo "config is broken" >&2; exit 4; }
  if [ -f stubborn ]; then trap '' INT TERM
  else trap 'echo "INT; file: $(cat .troupe/troupe.yml)"; exit 0' INT; trap 'echo TERM; exit 0' TERM; fi
  echo "watching $PWD"; echo "watch argv: $*" >&2
  while :; do sleep 0.1; done;;
*) echo "argv: $*"; echo "user=${USER-unset} logname=${LOGNAME-unset}"
   [ "$2" = mkstate ] && { mkdir -p .troupe/sub; printf '\0\1SQLite format 3' > .troupe/history.db; }
   exit 0;;
esac
"""


@pytest.fixture
def watch_tools(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text(FAKE_WATCH_UV)
    return fake_tools


def test_watch_runs_in_the_background_while_a_hand_edit_lands_and_sigint_stops_it(watch_tools):
    r = _run(cx.parse_plan(json.dumps(WATCHED)), watch_tools)
    assert r[0]["watch"] == "start" and r[0]["rc"] is None and r[0]["stdout"].startswith("watching ")
    assert r[0]["watch_state"] == "printed its watching line and is running" and "watch argv" in r[0]["stderr"]
    assert r[1]["hand_edit"] == ".troupe/troupe.yml" and r[2]["sleep"] == 0.3
    assert r[3]["watch"] == "stop" and r[3]["signal"] == "SIGINT" and r[3]["rc"] == 0
    assert r[3]["watch_state"] == "exited after the signal"
    assert "INT; file: note: by hand" in r[3]["stdout"] and r[3]["stdout"].startswith("watching ")


def test_sigterm_reaches_watch_and_a_command_can_run_while_it_watches(watch_tools):
    plan = cx.parse_plan(json.dumps(_plan([{"watch": "start", "args": ["--theatre", ".", "config", "watch"]},
                                           {"args": ["config", "show", "note"]},
                                           {"watch": "stop", "signal": "SIGTERM"}])))
    r = _run(plan, watch_tools)
    assert r[1]["stdout"].startswith("argv: config show note") and r[2]["stdout"].endswith("TERM\n")
    assert r[2]["rc"] == 0


def test_a_watch_that_exits_at_once_on_a_broken_config_is_reported_as_such(watch_tools):
    plan = cx.parse_plan(json.dumps(_plan([{"watch": "start", "args": ["config", "watch"]}, {"sleep": 0.2},
                                           {"watch": "stop", "signal": "SIGINT"}], files={"broken": ""})))
    r = _run(plan, watch_tools)
    assert r[0]["rc"] == 4 and r[0]["watch_state"] == "exited before printing a watching line"
    assert "config is broken" in r[0]["stderr"]
    assert r[2]["rc"] == 4 and r[2]["watch_state"] == "had already exited before the signal"


def test_a_watch_that_ignores_the_signal_is_killed(watch_tools, monkeypatch):
    monkeypatch.setattr(cx, "WATCH_STOP_SECONDS", 1)
    plan = cx.parse_plan(json.dumps(_plan([{"watch": "start", "args": ["config", "watch"]},
                                           {"watch": "stop", "signal": "SIGINT"}], files={"stubborn": ""})))
    r = _run(plan, watch_tools)
    assert r[1]["watch_state"] == "still running 1 s after the signal, so killed" and r[1]["rc"] == 128 + 9


def test_a_watch_left_running_is_killed_when_the_script_ends(watch_tools, tmp_path):
    plan = {"files": {}, "show": [], "commands": [{"watch": "start", "args": ["config", "watch"], "env": {}}]}
    assert _run(plan, watch_tools)[0]["rc"] is None                                   # parse_plan would refuse it
    with pytest.raises(ProcessLookupError):
        os.kill(int((tmp_path / "watch.pid").read_text()), 0)


def test_a_watch_still_running_at_the_lifetime_limit_says_so():
    plan = cx.parse_plan(json.dumps(_plan([{"watch": "start", "args": ["config", "watch"]},
                                           {"watch": "stop", "signal": "SIGINT"}])))
    r = cx.parse_output("R 1 -   0 0 watching\nR 2 124   0 0 exited-before-stop", plan)
    assert f"stopped after {cx.WATCH_SECONDS} s" in r[1]["stderr"] and r[1]["watch_state"].startswith("had already")


def test_a_symlink_step_links_inside_the_theatre_and_theatre_may_name_it(watch_tools):
    plan = cx.parse_plan(json.dumps(_plan([
        {"symlink": {"path": "linked", "target": "sub"}}, {"symlink": {"path": "linked", "target": "x"}},
        {"args": ["--theatre", "linked", "config", "show"]}, {"list": "."}], files={"sub/.troupe/troupe.yml": "a: 1\n"})))
    r = _run(plan, watch_tools)
    assert r[0]["rc"] == 0 and r[0]["symlink"] == {"path": "linked", "target": "sub"}
    assert r[1]["rc"] == 1 and "already exists" in r[1]["stderr"]
    assert r[2]["stdout"].startswith("argv: --theatre linked config show")
    assert "linked -> sub\n" in r[3]["stdout"] and "sub/.troupe/troupe.yml  5 bytes\n" in r[3]["stdout"]


def test_a_listing_shows_paths_and_sizes_never_a_binary_stores_bytes(watch_tools):
    plan = cx.parse_plan(json.dumps(_plan([{"list": ".troupe"}, {"args": ["config", "mkstate"]}, {"list": ".troupe"},
                                           {"list": "nowhere"}])))
    r = _run(plan, watch_tools)
    assert r[0]["stdout"] == ".troupe/troupe.yml  10 bytes\n" and r[0]["list"] == ".troupe"
    assert r[2]["stdout"] == ".troupe/history.db  17 bytes\n.troupe/sub/\n.troupe/troupe.yml  10 bytes\n"
    assert "SQLite" not in r[2]["stdout"] and r[3]["rc"] == 1 and "no directory nowhere" in r[3]["stderr"]


def test_env_null_unsets_a_login_variable_for_one_command(watch_tools):
    plan = cx.parse_plan(json.dumps(_plan([{"args": ["config", "show"], "env": {"USER": None, "LOGNAME": None}},
                                           {"args": ["config", "show"], "env": {"USER": "someone"}}])))
    r = _run(plan, {**watch_tools, "USER": "u", "LOGNAME": "l"})
    assert "user=unset logname=unset" in r[0]["stdout"] and "user=someone logname=l" in r[1]["stdout"]


def test_a_plan_without_passwd_runs_with_no_account_entry_for_the_arm_uid(monkeypatch):
    from runner import hidden
    seen = []
    monkeypatch.setattr(hidden, "run_script", lambda p, copy, sc, arm_entry=True: seen.append(arm_entry) or "R 1 0  ")
    rn = cx.ArmRunner("p")
    rn._prep["Arm A"] = (None, paths.REPO_ROOT / "copy")
    rn.run("Arm A", cx.parse_plan(json.dumps(_plan([{"args": ["config", "show"]}], passwd=False))))
    rn.run("Arm A", cx.parse_plan(json.dumps(_plan([{"args": ["config", "show"]}]))))
    assert seen == [False, True]


def test_scrubbing_keeps_what_a_step_was():
    r = cx._scrub_results([{"args": [], "env": {}, "rc": None, "stdout": "watching /tmp/tmp.AbC123", "stderr": "",
                            "files": {}, "watch": "start", "watch_state": "x"}], ["alpha"])[0]
    assert r["stdout"] == "watching /theatre" and r["watch"] == "start" and r["watch_state"] == "x"
