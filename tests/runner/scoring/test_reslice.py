"""Decision reslice (owner, 2026-10-10): per-arm behaviour groups for topics whose route ratings are placeholders."""
import copy, json
import pytest
from runner import paths
from runner.scoring import context as cx, decisions as dz, inputs, judge, reslice as rs
from tests.runner.scoring.test_context import PLAN, WRITTEN, FakeRunner
from tests.runner.scoring.test_decisions import D1, _extracted, anon_fixture

# three arms: Arm A and Arm B on one route, Arm C on "not considered"
ONE_ROUTE = json.dumps({"topics": [
    {"id": "quoting", "question": "How is quoting kept?", "not_considered": {"proposed": "3", "why": "w"},
     "routes": [{"route": "copy the last entry's quoting", "labels": ["Arm A", "Arm B"], "reason_given": "r",
                 "outcome": "kept", "proposed": "4", "proposed_why": "p"}]}]})

SPEC = {"T1": {"questions": [
    {"id": "Q1", "text": "quoting when a section replace drops the last entry",
     "groups": [{"id": "A", "rating": 4, "description": "copies the quoting of the last REMAINING entry"},
                {"id": "B", "rating": 2.5, "description": "copies the quoting of an entry this command deleted"},
                {"id": "C", "rating": None, "description": "section rewritten as given"}]},
    {"id": "Q2", "text": "other entries",
     "groups": [{"id": "KEEP", "rating": 5, "description": "other entries untouched"},
                {"id": "LOSE", "rating": 1, "description": "other entries lose their quotes"}]}]}}


def _res(out):
    return [{"args": ["config"], "env": {}, "rc": 0, "stdout": out, "stderr": "", "files": {}}]


# Arm A and Arm C behave alike; Arm B differently. Output names an arm's repo, which must be scrubbed.
BY_LABEL = {"Arm A": _res("kept 'x' /work/bakeoff-specs-alpha"), "Arm B": _res("kept \"x\""),
            "Arm C": _res("kept 'x' /work/bakeoff-specs-gamma")}


def _reply(per):
    return json.dumps({"outcomes": per})


GOOD = _reply({"1": {"Q1": {"group": "A", "why": "single quotes kept"}, "Q2": {"group": "KEEP"}},
               "2": {"Q1": {"group": "B", "why": "double quotes"}, "Q2": {"group": "LOSE", "why": "lost"}}})


@pytest.fixture
def ctx(tmp_state):
    anon_fixture(arms=("alpha", "beta", "gamma"), steps=("01",))
    for lab in ("Arm A", "Arm B", "Arm C"):
        _extracted(lab, "01", D1 if lab != "Arm C" else "[]")
    dz.align("p", judge.FakeJudge([ONE_ROUTE]))
    cx.run("p", judge.FakeJudge([json.dumps(PLAN), json.dumps(WRITTEN)]), FakeRunner())
    _spec(SPEC)
    return paths.scoring_out("p")


def _spec(spec):
    f = rs.spec_path("p")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(spec))


def _run(j=None, rn=None, **kw):
    return rs.run("p", j or judge.FakeJudge([GOOD]), rn or FakeRunner(by_label=BY_LABEL), **kw)


# ---- reslice.json ----------------------------------------------------------------------------------------------------

def test_a_well_formed_reslice_is_accepted_with_null_and_half_step_ratings():
    assert rs.parse_spec(copy.deepcopy(SPEC)) == SPEC


def _bad(**change):
    s = copy.deepcopy(SPEC)
    q = s["T1"]["questions"][0]
    for k, v in change.items():
        if k == "topic":
            s = {v: s["T1"]}
        elif k == "group":
            q["groups"][0] = v
        else:
            q[k] = v
    return s


@pytest.mark.parametrize("bad, match", [
    (_bad(topic="dash"), "not a sheet topic id"),
    ({"T1": {"questions": []}}, "at least one question"),
    ({"T1": {"questions": SPEC["T1"]["questions"], "note": "x"}}, "no other key"),
    (_bad(id="Q2"), "unique"),
    (_bad(text=" "), '"text"'),
    (_bad(groups=[]), "at least one group"),
    (_bad(group={"id": "B", "rating": 4, "description": "dup"}), "unique"),
    (_bad(group={"id": "none", "rating": 4, "description": "x"}), "never 'none'"),
    (_bad(group={"id": "A", "rating": 3.2, "description": "x"}), "half steps"),
    (_bad(group={"id": "A", "rating": 0, "description": "x"}), "half steps"),
    (_bad(group={"id": "A", "rating": 5.5, "description": "x"}), "half steps"),
    (_bad(group={"id": "A", "rating": True, "description": "x"}), "half steps"),
    (_bad(group={"id": "A", "rating": "4", "description": "x"}), "half steps"),
    (_bad(group={"id": "A", "rating": 4, "description": ""}), '"description"'),
    (_bad(group={"id": "A", "rating": 4}), "exactly"),
    ([], "non-empty JSON object")])
def test_a_malformed_reslice_is_refused_naming_the_problem(bad, match):
    with pytest.raises(inputs.InputError, match=match):
        rs.parse_spec(bad)


def test_a_reslice_naming_a_topic_not_on_the_sheet_is_refused(ctx):
    _spec({**SPEC, "T9": SPEC["T1"]})
    with pytest.raises(inputs.InputError, match="not on the sheet: T9"):
        _run()


# ---- rating ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("groups, want", [
    ({"Q1": "A", "Q2": "KEEP"}, 4.5), ({"Q1": "B", "Q2": "LOSE"}, 1.75),
    ({"Q1": "C", "Q2": "KEEP"}, 5),                                  # C is n/a: left out of the mean
    ({"Q1": "A", "Q2": "none"}, None), ({"Q1": "A"}, None)])
def test_the_rating_is_the_mean_of_the_groups_ratings_without_the_n_a_ones(groups, want):
    assert rs.rating(SPEC["T1"], groups) == want


def test_every_group_n_a_rates_n_a():
    s = {"questions": [{"id": "Q1", "text": "t", "groups": [{"id": "U", "rating": None, "description": "d"}]}]}
    assert rs.rating(s, {"Q1": "U"}) is None


# ---- the judge's reply -----------------------------------------------------------------------------------------------

def _parse(text, outs=("1", "2")):
    return rs.parse_classified(text, list(outs), SPEC["T1"], ["Arm A", "Arm B", "Arm C"], ["alpha"])


def test_a_good_reply_is_parsed_per_outcome_and_question():
    got = _parse(GOOD)
    assert got["1"]["Q1"] == {"group": "A", "why": "single quotes kept"} and got["2"]["Q2"]["group"] == "LOSE"


@pytest.mark.parametrize("bad, match", [
    (_reply({"1": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "exactly the outcomes"),
    (_reply({"1": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}, "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}},
             "3": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "exactly the outcomes"),
    (_reply({"1": {"Q1": {"group": "A"}}, "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "exactly the questions"),
    (_reply({"1": {"Q1": {"group": "D"}, "Q2": {"group": "KEEP"}}, "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}),
     "not one of"),
    (_reply({"1": {"Q1": {"group": "KEEP"}, "Q2": {"group": "KEEP"}}, "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}),
     "not one of"),
    (_reply({"1": {"Q1": {"group": "none"}, "Q2": {"group": "KEEP"}}, "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}),
     "needs a \"why\""),
    (_reply({"1": {"Q1": "A", "Q2": {"group": "KEEP"}}, "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "must be"),
    (_reply({"1": {"Q1": {"group": "A", "rating": 5}, "Q2": {"group": "KEEP"}},
             "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "must be"),
    (_reply({"1": {"Q1": {"group": "A", "why": "Arm B also copies"}, "Q2": {"group": "KEEP"}},
             "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "names an arm"),
    (_reply({"1": {"Q1": {"group": "A", "why": "as alpha does"}, "Q2": {"group": "KEEP"}},
             "2": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}}}), "method or tool"),
    ('{"outcomes": {}, "extra": 1}', "needs one JSON object"), ("no json", "JSON")])
def test_a_malformed_reply_is_a_bad_reply(bad, match):
    with pytest.raises(judge.BadReply, match=match):
        _parse(bad)


# ---- the stage -------------------------------------------------------------------------------------------------------

def test_every_label_is_run_separately_and_classified_per_label(ctx):
    j, rn = judge.FakeJudge([GOOD]), FakeRunner(by_label=BY_LABEL)
    assert _run(j, rn) == {"written": 1, "failed": 0, "skipped": 0}
    assert sorted(rn.calls) == ["Arm A", "Arm B", "Arm C"] and rn.readied == [["Arm A", "Arm B", "Arm C"]]
    assert j.files == [["questions.json", "results.json"]] and j.inputs == [rs.item_dir("p", "quoting")]
    got = json.loads(rs.ratings_path("p").read_text())
    assert got == {"T1": {"Arm A": {"groups": {"Q1": "A", "Q2": "KEEP"}, "rating": 4.5},
                          "Arm B": {"groups": {"Q1": "B", "Q2": "LOSE"}, "rating": 1.75},
                          "Arm C": {"groups": {"Q1": "A", "Q2": "KEEP"}, "rating": 4.5}}}
    rec = json.loads(rs.out_path("p", "quoting").read_text())
    assert rec["status"] == "ok" and rec["plan_source"] == "context record"
    assert rec["labels"] == {"Arm A": "1", "Arm B": "2", "Arm C": "1"}          # A and C merged: identical once scrubbed


def test_the_judge_sees_neither_labels_arm_names_nor_the_owners_ratings(ctx):
    j = judge.FakeJudge([GOOD])
    _run(j)
    item = rs.item_dir("p", "quoting")
    for f in item.iterdir():
        text = f.read_text()
        assert "Arm" not in text and "alpha" not in text and "gamma" not in text and '"rating"' not in text, f.name
    res = json.loads((item / "results.json").read_text())
    assert res["plan"] == {k: cx.parse_plan(json.dumps(PLAN))[k] for k in ("files", "commands", "show", "passwd")}
    assert [o["outcome"] for o in res["outcomes"]] == ["1", "2"] and "/work/project" in json.dumps(res)
    assert "Arm" not in j.prompts[0] and "rating" not in j.prompts[0]


def test_the_summary_counts_groups_per_question_and_route_without_naming_an_arm(ctx):
    _run()
    s = rs.summary_path("p").read_text()
    assert "- T1 Q1 (quoting when a section replace drops the last entry): A 2, B 1, C 0" in s
    assert "  - Route 1: A 1, B 1\n  - Route 2: A 1" in s
    assert "- T1 Q2 (other entries): KEEP 2, LOSE 1" in s
    for word in ("Arm", "alpha", "beta", "gamma"):
        assert word not in s and word not in rs.ratings_path("p").read_text().replace("Arm A", "").replace(
            "Arm B", "").replace("Arm C", "")


def test_none_of_these_carries_its_reason_and_no_rating(ctx):
    _run(judge.FakeJudge([_reply({"1": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}},
                                  "2": {"Q1": {"group": "none", "why": "the command failed first"},
                                        "Q2": {"group": "KEEP"}}})]))
    b = json.loads(rs.ratings_path("p").read_text())["T1"]["Arm B"]
    assert b == {"groups": {"Q1": "none", "Q2": "KEEP"}, "rating": None,
                 "none_of_these": {"Q1": "the command failed first"}}
    s = rs.summary_path("p").read_text()
    assert "A 2, B 0, C 0, none 1" in s and "none of these: the command failed first" in s


def test_the_stage_resumes_and_a_rating_change_needs_no_new_call(ctx):
    _run()
    j = judge.FakeJudge([])
    spec = copy.deepcopy(SPEC)
    spec["T1"]["questions"][1]["groups"][0]["rating"] = 3
    _spec(spec)
    assert _run(j) == {"written": 0, "failed": 0, "skipped": 1} and j.prompts == []
    assert json.loads(rs.ratings_path("p").read_text())["T1"]["Arm A"]["rating"] == 3.5
    assert rs.estimate("p") == {"calls": 0, "topics": 0}


def test_a_changed_group_description_classifies_the_topic_again(ctx):
    _run()
    spec = copy.deepcopy(SPEC)
    spec["T1"]["questions"][0]["groups"][0]["description"] = "something else"
    _spec(spec)
    assert rs.estimate("p") == {"calls": 1, "topics": 1}
    assert _run()["written"] == 1
    assert json.loads((rs.out_dir("p") / "quoting.1.json").read_text())["status"] == "ok"


def test_only_and_redo(ctx):
    assert _run(judge.FakeJudge([]), only=["T9"]) == {"written": 0, "failed": 0, "skipped": 0}
    with pytest.raises(inputs.InputError, match="--redo needs --only"):
        _run(redo=True)
    _run()
    assert rs.estimate("p", only=["T1"], redo=True) == {"calls": 1, "topics": 1}
    assert _run(only=["quoting"], redo=True)["written"] == 1


def test_a_pin_violation_leaves_every_earlier_output_intact(ctx):
    _run()
    before = {f: f.read_text() for f in (rs.ratings_path("p"), rs.summary_path("p"), rs.out_path("p", "quoting"))}

    class PinJudge:
        def ask(self, prompt, inputs, files=()):
            raise judge.PinViolation("model pin not verified")
    with pytest.raises(judge.PinViolation):
        _run(PinJudge(), only=["T1"], redo=True)
    assert {f: f.read_text() for f in before} == before
    assert sorted(x.name for x in rs.out_dir("p").iterdir()) == ["quoting.json"]


def test_a_sandbox_failure_on_a_redo_keeps_the_earlier_classification(ctx):
    _run()
    before = rs.ratings_path("p").read_text()
    assert _run(rn=FakeRunner(by_label=BY_LABEL, fail=("Arm B",)), only=["T1"], redo=True)["failed"] == 1
    assert rs.ratings_path("p").read_text() == before
    assert json.loads(cx.failed_path(rs.out_path("p", "quoting")).read_text())["why"].startswith("run: Arm B")
    s = rs.summary_path("p").read_text()
    assert "A later attempt failed" in s and "Arm B" not in s


def test_two_bad_replies_fail_the_topic_and_retry_failed_redoes_it(ctx):
    assert _run(judge.FakeJudge(["nope", "still nope"]))["failed"] == 1
    assert json.loads(rs.out_path("p", "quoting").read_text())["status"] == "reslice_failed"
    assert json.loads(rs.ratings_path("p").read_text()) == {}
    assert "_Not classified: classify:" in rs.summary_path("p").read_text()
    assert rs.estimate("p") == {"calls": 0, "topics": 0} and rs.estimate("p", retry_failed=True)["calls"] == 1
    assert _run(retry_failed=True)["written"] == 1


def test_the_container_judges_mount_check_accepts_a_reslice_item(ctx):
    _run()
    judge.check_mounts(judge.mounts(paths.judge_home("p") / "call", rs.item_dir("p", "quoting"),
                                    ["questions.json", "results.json"]), "p")


# ---- the plan --------------------------------------------------------------------------------------------------------

def _drop_plan():
    f = cx.out_path("p", "quoting")
    rec = json.loads(f.read_text())
    del rec["plan"]
    f.write_text(json.dumps(rec))


def _reply_file(name, text):
    d = rs._calls_dir("p", "quoting") / name
    d.mkdir(parents=True)
    (d / "reply.md").write_text(text)


def test_an_older_context_records_plan_is_recovered_from_its_plan_call_reply(ctx):
    _drop_plan()
    _reply_file("aaa-1", "not a plan")
    _reply_file("bbb-1", json.dumps(WRITTEN))                                           # the write call's reply
    _reply_file("ccc-1", json.dumps({**PLAN, "why": "another attempt", "show": []}))   # another plan, other why
    _reply_file("ddd-1", "```json\n" + json.dumps(PLAN) + "\n```")
    t = rs._topics_by_sheet("p")["T1"]
    assert rs.plan_for("p", t) == (cx.parse_plan(json.dumps(PLAN)), "plan-call reply")
    assert _run()["written"] == 1
    assert json.loads(rs.out_path("p", "quoting").read_text())["plan_source"] == "plan-call reply"


def test_two_plans_with_the_same_why_are_told_apart_by_the_contexts_results_or_reported(ctx):
    _drop_plan()
    other = {**PLAN, "show": []}
    _reply_file("aaa-1", json.dumps(other))
    _reply_file("bbb-1", json.dumps(PLAN))
    t = rs._topics_by_sheet("p")["T1"]
    assert rs.plan_for("p", t)[0] == cx.parse_plan(json.dumps(PLAN))          # results.json kept PLAN's run
    (cx.item_dir("p", "quoting") / "results.json").unlink()
    plan, why = rs.plan_for("p", t)
    assert plan is None and "2 different plan-call replies" in why


def test_an_older_results_file_without_passwd_still_tells_two_plans_apart(ctx):
    _drop_plan()
    _reply_file("aaa-1", json.dumps({**PLAN, "show": []}))
    _reply_file("bbb-1", json.dumps(PLAN))
    f = cx.item_dir("p", "quoting") / "results.json"
    res = json.loads(f.read_text())
    del res["plan"]["passwd"]                                    # written before plans could set "passwd"
    f.write_text(json.dumps(res))
    assert rs.plan_for("p", rs._topics_by_sheet("p")["T1"])[0] == cx.parse_plan(json.dumps(PLAN))


def test_a_topic_without_a_recoverable_plan_is_reported_never_guessed(ctx):
    _drop_plan()
    assert _run(judge.FakeJudge([]))["failed"] == 1
    rec = json.loads(rs.out_path("p", "quoting").read_text())
    assert rec["status"] == "reslice_failed" and "not recoverable" in rec["why"]


def test_a_stale_or_unrunnable_context_gives_no_plan(ctx):
    t = rs._topics_by_sheet("p")["T1"]
    f = cx.out_path("p", "quoting")
    rec = json.loads(f.read_text())
    f.write_text(json.dumps({**rec, "runnable": False}))
    assert rs.plan_for("p", t) == (None, "its decision context had nothing to run")
    f.write_text(json.dumps({**rec, "routes": [["x", []]]}))
    assert "other routes" in rs.plan_for("p", t)[1]


# ---- import ----------------------------------------------------------------------------------------------------------

def _rated_sheet(ratings=("3", "2")):
    md = dz.sheet("p")
    text = md.read_text()
    for r in ratings:
        text = text.replace("rating:\n", f"rating: {r}\n", 1)
    md.write_text(text)


def test_import_rates_a_resliced_topic_per_arm(ctx):
    _run()
    _rated_sheet()
    routes = json.loads(dz.import_ratings("p").read_text())["topics"][0]["routes"]
    got = sorted((r["route"], r["arms"], r["rating"]) for r in routes)
    assert got == [("copy the last entry's quoting", ["alpha"], "4.5"),
                   ("copy the last entry's quoting", ["beta"], "1.75"),
                   ("not considered", ["gamma"], "4.5")]
    a = next(r for r in routes if r["arms"] == ["alpha"])
    assert a["groups"] == {"Q1": "A", "Q2": "KEEP"} and a["route_rating"] == "3"
    assert "behaviour group A" in a["reason"]
    from runner.scoring import aggregate, scales
    assert aggregate._choice("p", "beta", {})["score"] == scales.rating("1.75")


def test_import_keeps_the_route_rating_for_none_of_these_and_warns(ctx):
    _run(judge.FakeJudge([_reply({"1": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}},
                                  "2": {"Q1": {"group": "none", "why": "failed first"}, "Q2": {"group": "KEEP"}}})]))
    _rated_sheet()
    out = json.loads(dz.import_ratings("p").read_text())
    b = next(r for r in out["topics"][0]["routes"] if r["arms"] == ["beta"])
    assert b["rating"] == "3" and "warning" in b
    assert out["warnings"] == [{"topic": "T1", "route_no": 1, "arm": "beta",
                                "why": "kept the route's rating (none of these: Q1: failed first)"}]


def test_import_keeps_the_route_rating_for_an_unclassified_label_and_warns(ctx):
    _run()
    f = rs.ratings_path("p")
    got = json.loads(f.read_text())
    del got["T1"]["Arm B"]
    f.write_text(json.dumps(got))
    _rated_sheet()
    out = json.loads(dz.import_ratings("p").read_text())
    assert out["warnings"][0]["why"] == "kept the route's rating (not classified)"


def test_import_rates_n_a_when_every_chosen_group_is_n_a(ctx):
    spec = copy.deepcopy(SPEC)
    spec["T1"]["questions"][1]["groups"][0]["rating"] = None
    _spec(spec)
    _run(judge.FakeJudge([_reply({"1": {"Q1": {"group": "C"}, "Q2": {"group": "KEEP"}},
                                  "2": {"Q1": {"group": "C"}, "Q2": {"group": "KEEP"}}})]))
    _rated_sheet()
    routes = json.loads(dz.import_ratings("p").read_text())["topics"][0]["routes"]
    assert {r["rating"] for r in routes} == {"n/a"}


def test_import_refuses_an_unclassified_or_stale_reslice(ctx):
    _rated_sheet()
    with pytest.raises(inputs.InputError, match="decisions-reslice stage first"):
        dz.import_ratings("p")
    rs.write_outputs("p", SPEC, rs._topics_by_sheet("p"))           # nothing classified yet
    with pytest.raises(inputs.InputError, match="T1: not classified"):
        dz.import_ratings("p")
    _run()
    spec = copy.deepcopy(SPEC)
    spec["T1"]["questions"][1]["groups"][0]["rating"] = 2
    _spec(spec)
    with pytest.raises(inputs.InputError, match="differ from reslice.json"):
        dz.import_ratings("p")


def test_import_without_a_reslice_is_unchanged(ctx):
    rs.spec_path("p").unlink()
    _rated_sheet()
    routes = json.loads(dz.import_ratings("p").read_text())["topics"][0]["routes"]
    assert [(r["arms"], r["rating"]) for r in routes] == [(["alpha", "beta"], "3"), (["gamma"], "2")]


# ---- the CLI ---------------------------------------------------------------------------------------------------------

def test_the_stage_runs_between_context_and_import_and_needs_approval_for_its_calls(ctx, monkeypatch):
    from runner import cli
    from runner.scoring import cli as scli
    order = list(scli.STAGES)
    assert order.index("decisions-context") < order.index("decisions-reslice") < order.index("decisions-import")
    monkeypatch.setattr(judge, "items", lambda pass_, parts=None: [])
    monkeypatch.setattr(judge, "ContainerJudge", lambda pass_: judge.FakeJudge([GOOD]))
    monkeypatch.setattr(cx, "ArmRunner", lambda pass_: FakeRunner(by_label=BY_LABEL))
    (ctx / "judge-approved").write_text("approved 2026-10-10 1\n")           # 1 align + 1 reslice = 2
    assert cli.main(["score", "p", "--stage", "decisions-reslice"]) == 1 and not rs.ratings_path("p").exists()
    (ctx / "judge-approved").write_text("approved 2026-10-10 2\n")
    assert cli.main(["score", "p", "--stage", "decisions-reslice"]) == 0 and rs.ratings_path("p").exists()
    assert cli.main(["score", "p", "--stage", "decisions-reslice", "--ask", "x"]) == 1


def test_the_import_stage_prints_warnings_without_naming_the_arm(ctx, capsys):
    from runner import cli
    _run(judge.FakeJudge([_reply({"1": {"Q1": {"group": "A"}, "Q2": {"group": "KEEP"}},
                                  "2": {"Q1": {"group": "none", "why": "failed first"}, "Q2": {"group": "KEEP"}}})]))
    _rated_sheet()
    assert cli.main(["score", "p", "--stage", "decisions-import"]) == 0
    out = capsys.readouterr().out
    assert "warning: T1 route 1: one arm kept the route's rating (none of these: Q1: failed first)" in out
    assert "beta" not in out
