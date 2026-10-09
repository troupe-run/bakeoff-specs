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
    {"show": ["../../etc/passwd"]}])
def test_a_plan_that_could_escape_its_theatre_or_hang_is_refused(bad):
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
    assert r[0]["files"][".troupe/troupe.yml"] == "note: fine value\n# with spaces & ünïcode\n"
    assert r[0]["files"]["missing.yml"] is None                                  # absent, not empty
    assert r[1]["rc"] == 2 and "expected one argument" in r[1]["stderr"] and "actor=human:o" in r[1]["stdout"]


def test_the_starting_files_are_written_byte_for_byte(fake_tools):
    body = "a: 'quoted'  # comment\n\tb: \"$HOME\" `x`\n"
    plan = cx.parse_plan(json.dumps({**PLAN, "files": {".troupe/troupe.yml": body},
                                     "commands": [{"args": ["config", "show", "a"]}]}))
    assert _run(plan, fake_tools)[0]["files"][".troupe/troupe.yml"] == body


def test_output_cannot_forge_a_record(fake_tools, tmp_path):
    (tmp_path / "bin" / "uv").write_text('#!/bin/bash\necho "R 1 0 Zm9yZ2Vk"\necho "F 1 eA== Zm9yZ2Vk"\nexit 3\n')
    plan = cx.parse_plan(json.dumps({**PLAN, "commands": [{"args": ["config", "show", "a"]}], "show": []}))
    r = _run(plan, fake_tools)[0]
    assert r["rc"] == 3 and "R 1 0" in r["stdout"] and r["files"] == {}


def test_a_command_stopped_by_the_time_limit_says_so():
    plan = cx.parse_plan(json.dumps({**PLAN, "commands": [{"args": ["config", "show", "a"]}], "show": []}))
    r = cx.parse_output("R 1 124  ", plan)[0]
    assert r["rc"] == 124 and f"stopped after {cx.CMD_SECONDS} s" in r["stderr"]


def test_a_command_with_no_record_has_no_exit_code():
    assert cx.parse_output("", cx.parse_plan(json.dumps(PLAN)))[0]["rc"] is None


# ---- grouping by route: never an arm ---------------------------------------------------------------------------------

def test_arms_on_one_route_with_identical_results_are_merged_and_counted_never_named():
    t = {"routes": [{"route_no": 1, "route": "r", "labels": ["Arm A", "Arm B", "Arm C"]},
                    {"route_no": 2, "route": "not considered", "labels": ["Arm D"]}]}
    same, other = [{"rc": 0}], [{"rc": 2}]
    got = cx.by_route(t, {"Arm A": same, "Arm B": same, "Arm C": other, "Arm D": "could not run: RuntimeError"})
    assert got[0]["outcomes"] == [{"arms": 2, "results": same}, {"arms": 1, "results": other}]
    assert got[1]["outcomes"] == [{"arms": 1, "error": "could not run: RuntimeError"}]
    assert "Arm" not in json.dumps(got)


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
    def __init__(self, by_label=None, fail=()):
        self.calls, self.by_label, self.fail = [], by_label or {}, fail

    def run(self, label, plan):
        self.calls.append(label)
        if label in self.fail:
            raise RuntimeError("install failed for alpha")
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
    assert sorted(rn.calls) == ["Arm A", "Arm B"]                    # route 1 and "not considered"
    item = cx.item_dir("p", "dash")
    assert j.files == [["topic.json", "contract.md", "steps.md"], ["topic.json", "results.json"]]
    assert "Arm" not in (item / "topic.json").read_text()
    results = (item / "results.json").read_text()
    assert "Arm" not in results and "alpha" not in results and "ok /work/project" in results
    rec = json.loads(cx.out_path("p", "dash").read_text())
    assert rec["status"] == "ok" and rec["routes"] == ["positional", "not considered"]
    assert rec["context"]["examples"][0]["results"]["2"] == "error, exit 2"


def test_the_stage_resumes_and_redoes_a_topic_whose_routes_changed(aligned):
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner())
    j = judge.FakeJudge([])
    assert cx.run("p", j, FakeRunner())["skipped"] == 1 and j.prompts == []
    assert cx.estimate("p") == {"calls": 0, "topics": 0}
    rec = json.loads(cx.out_path("p", "dash").read_text())
    cx.out_path("p", "dash").write_text(json.dumps({**rec, "routes": ["something else"]}))
    assert cx.estimate("p") == {"calls": 2, "topics": 1}


def test_a_topic_with_nothing_to_run_runs_nothing_and_is_written_from_the_routes(aligned):
    j, rn = judge.FakeJudge(['{"runnable": false, "why": "process"}',
                             json.dumps({**WRITTEN, "examples": [], "in_practice": "Plain words."})]), FakeRunner()
    cx.run("p", j, rn)
    assert rn.calls == [] and j.files[1] == ["topic.json"] and "Nothing could be run" in j.prompts[1]
    assert json.loads(cx.out_path("p", "dash").read_text())["runnable"] is False


def test_an_arm_that_cannot_run_is_recorded_and_the_topic_still_written(aligned):
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner(fail=("Arm B",)))
    res = json.loads((cx.item_dir("p", "dash") / "results.json").read_text())
    assert res["routes"][1]["outcomes"] == [{"arms": 1, "error": "could not run: RuntimeError"}]
    assert "alpha" not in json.dumps(res)                            # the exception text is never kept


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
