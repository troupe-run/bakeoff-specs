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
    {"commands": []}, {"commands": [{"args": ["config", "show", "x"]}] * 9},
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
    monkeypatch.setattr(cx, "run", lambda pass_, j, rn, retry_failed=False, only=None: seen.append(only) or {})
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
