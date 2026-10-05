# tests/runner/scoring/test_decisions.py
"""Plan 3 Task 18: decision review (spec §8). Offline only: `FakeJudge` stands in for the model."""
import json

import pytest
from runner import paths
from runner.scoring import decisions as dz
from runner.scoring import judge, report
from tests.runner.scoring.test_judge import anon_fixture

T = {"id": "actor-check-order", "question": "Check TROUPE_ACTOR before loading?",
     "routes": [{"route": "check first, exit 2", "labels": ["Arm A"], "reason_given": "r", "outcome": "o"}]}


def test_labels_without_a_route_are_added_as_not_considered():
    t = dz.fill_not_considered(T, ["Arm A", "Arm B", "Arm C"])
    nc = [r for r in t["routes"] if r["route"] == "not considered"]
    assert nc and nc[0]["labels"] == ["Arm B", "Arm C"]


def test_a_route_only_one_arm_took_is_a_one_off():
    assert dz.kind(dz.fill_not_considered(T, ["Arm A", "Arm B"]), 2) == "one-off"


def test_the_rating_sheet_shows_no_labels_or_arm_names(tmp_state):
    sheet = dz.render_sheet([dz.fill_not_considered(T, ["Arm A", "Arm B"])], arms=["speckit", "control"])
    assert "Arm A" not in sheet and "speckit" not in sheet and "control" not in sheet
    assert sheet.index("one-off") < len(sheet) and "rating:" in sheet


def test_import_refuses_a_route_without_a_reason(tmp_state):
    with pytest.raises(ValueError, match="reason"):
        dz.parse_sheet("## actor-check-order\n### Route 1\nrating: good\nreason:\n")


# ---- classification ------------------------------------------------------------------------------------------------

def _t(*routes):
    return {"id": "t", "question": "q?", "routes": [{"route": r, "labels": ls} for r, ls in routes]}


def test_two_labels_on_different_routes_is_divergent():
    assert dz.kind(_t(("x", ["Arm A"]), ("y", ["Arm B"])), 2) == "divergent"


def test_one_route_holding_every_label_is_unanimous():
    assert dz.kind(_t(("x", ["Arm A", "Arm B", "Arm C"])), 3) == "unanimous"


def test_two_labels_on_one_route_with_the_rest_not_considered_is_divergent():
    assert dz.kind(_t(("x", ["Arm A", "Arm B"]), ("not considered", ["Arm C"])), 3) == "divergent"


def test_kind_reads_real_arm_names_in_ratings_json_as_well_as_labels():
    t = {"id": "t", "routes": [{"route": "x", "arms": ["alpha"]}, {"route": "not considered", "arms": ["beta"]}]}
    assert dz.kind(t, 2) == "one-off"


def test_report_classifies_topics_with_decisions_kind(tmp_state, monkeypatch):
    seen = []
    monkeypatch.setattr(dz, "kind", lambda t, n: (seen.append((t["id"], n)), "divergent")[1])
    d = paths.scoring_out("p") / "decisions"
    d.mkdir(parents=True)
    (d / "ratings.json").write_text(json.dumps({"topics": [
        {"id": "t1", "routes": [{"route": "A", "arms": ["alpha"], "rating": "good", "reason": "r"},
                                {"route": "not considered", "arms": ["beta"], "rating": "poor", "reason": "r"}]}]}))
    assert "### Divergent (1)" in "\n".join(report._decisions("p")) and seen == [("t1", 2)]


def test_not_considered_keeps_the_aligners_proposed_rating_for_that_route():
    t = dict(T, not_considered={"proposed": "poor", "why": "it mattered"})
    nc = dz.fill_not_considered(t, ["Arm A", "Arm B"])["routes"][-1]
    assert nc["route"] == "not considered" and nc["proposed"] == "poor" and nc["proposed_why"] == "it mattered"


def test_fill_not_considered_does_not_change_its_input():
    before = json.dumps(T, sort_keys=True)
    dz.fill_not_considered(T, ["Arm A", "Arm B"])
    assert json.dumps(T, sort_keys=True) == before


# ---- the sheet -----------------------------------------------------------------------------------------------------

def _topic(id_, *routes, nc=None):
    t = {"id": id_, "question": f"{id_}?", "routes": [
        {"route": r, "labels": ls, "reason_given": f"why {r}", "outcome": f"then {r}", "proposed": "acceptable",
         "proposed_why": f"note {r}"} for r, ls in routes]}
    if nc:
        t["not_considered"] = {"proposed": nc, "why": "nc note"}
    return dz.fill_not_considered(t, ["Arm A", "Arm B", "Arm C"])


TOPICS = [_topic("zz-unanimous", ("same", ["Arm A", "Arm B", "Arm C"])),
          _topic("mm-divergent", ("left", ["Arm A"]), ("right", ["Arm B", "Arm C"])),
          _topic("aa-one-off", ("only me", ["Arm C"]), nc="poor")]


def test_the_sheet_orders_one_offs_then_divergent_then_unanimous():
    s = dz.render_sheet(TOPICS, arms=[])
    assert s.index("## aa-one-off") < s.index("## mm-divergent") < s.index("## zz-unanimous")


def test_each_route_shows_its_text_reasoning_outcome_and_proposed_rating_with_blank_owner_fields():
    s = dz.render_sheet(TOPICS, arms=[])
    one = s[s.index("## aa-one-off"):s.index("## mm-divergent")]
    assert "only me" in one and "why only me" in one and "then only me" in one and "proposed: acceptable" in one
    assert "not considered" in one and "proposed: poor" in one
    assert one.count("\nrating:\n") == 2 and one.count("\nreason:\n") == 2


def test_judge_text_naming_a_label_or_an_arm_is_scrubbed_on_the_sheet():
    t = _topic("x", ("like Arm B did, the speckit way", ["Arm A"]))
    s = dz.render_sheet([t], arms=["speckit"])
    assert "Arm B" not in s and "speckit" not in s.lower()


def test_judge_text_cannot_inject_a_heading_or_a_rating_line():
    t = _topic("x", ("a\n## other-topic\nrating: good", ["Arm A"]))
    s = dz.render_sheet([t], arms=[])
    assert "\n## other-topic" not in s and "\nrating: good" not in s


def test_a_filled_sheet_round_trips_through_parse_sheet():
    s = dz.render_sheet(TOPICS, arms=[])
    filled = s.replace("rating:\nreason:\n", "rating: good\nreason: fine\n")
    got = dz.parse_sheet(filled)
    assert sorted(got) == ["aa-one-off", "mm-divergent", "zz-unanimous"]
    assert got["mm-divergent"] == [{"route_no": 1, "rating": "good", "reason": "fine"},
                                   {"route_no": 2, "rating": "good", "reason": "fine"}]
    assert [r["route_no"] for r in got["aa-one-off"]] == [1, 2]


def test_out_of_scope_may_be_written_with_spaces():
    got = dz.parse_sheet("## t\n### Route 1\nrating: Out of scope\nreason: does not matter\n")
    assert got["t"][0]["rating"] == "out_of_scope"


def test_parse_sheet_names_the_topic_and_route_of_every_problem():
    md = ("## t1\n### Route 1\nrating: great\nreason: x\n### Route 2\nreason: y\n"
          "## t2\n### Route 1\nrating: poor\nreason: z\n### Route 1\nrating: good\nreason: again\n")
    with pytest.raises(ValueError) as e:
        dz.parse_sheet(md)
    msg = str(e.value)
    assert "t1 route 1: rating 'great'" in msg and "t1 route 2: no rating" in msg and "t2 route 1: rated twice" in msg


# ---- extract -------------------------------------------------------------------------------------------------------

D1 = json.dumps([{"decision": "fail when TROUPE_ACTOR is unset", "options": ["fail", "record null"],
                  "reason": "owner prefers failing", "recorded_at": "gates.md:3"}])


def test_extract_asks_once_per_label_and_step_and_writes_each_list(tmp_state):
    out, lab = anon_fixture()
    j = judge.FakeJudge([D1] * 4)
    d = dz.extract("p", j)
    assert d == out / "decisions" / "extracted"
    got = json.loads((d / "Arm A" / "01.json").read_text())
    assert got[0]["decision"] == "fail when TROUPE_ACTOR is unset" and got[0]["recorded_at"] == "gates.md:3"
    assert sorted(str(p.relative_to(d)) for p in d.rglob("*.json")) == [
        "Arm A/01.json", "Arm A/03.json", "Arm B/01.json", "Arm B/03.json"]
    assert [i.relative_to(out / "anon").as_posix() for i in j.inputs] == ["Arm A/01", "Arm A/03", "Arm B/01", "Arm B/03"]
    assert j.files[0] == ["diff.patch", "gates.md", "questions.md", "repo/", "transcript.md"]


def test_the_extract_prompt_names_neither_label_nor_arm_and_asks_for_silent_choices(tmp_state):
    anon_fixture()
    j = judge.FakeJudge([D1] * 4)
    dz.extract("p", j)
    assert not any(w in p for p in j.prompts for w in ("Arm A", "Arm B", "alpha", "beta"))
    assert "unrecorded" in j.prompts[0] and "/judge/gates.md" in j.prompts[0]


def test_extract_mounts_only_the_inputs_present(tmp_state):
    out, lab = anon_fixture(arms=("alpha",), steps=("01",))
    d = out / "anon" / "Arm A" / "01"
    (d / "transcript.md").unlink()
    (d / "MISSING.json").write_text(json.dumps([{"files": ["transcript.md"], "why": "no arm turn streams"}]))
    j = judge.FakeJudge([D1])
    dz.extract("p", j)
    assert j.files == [["diff.patch", "gates.md", "questions.md", "repo/"]]


def test_two_unusable_extraction_replies_are_recorded_as_failed_never_as_an_empty_list(tmp_state):
    anon_fixture(arms=("alpha",), steps=("01",))
    j = judge.FakeJudge(["no json here", '[{"decision": ""}]'])
    d = dz.extract("p", j)
    got = json.loads((d / "Arm A" / "01.json").read_text())
    assert got["status"] == "extract_failed" and got["raw"] == '[{"decision": ""}]' and "decision" in got["why"]
    assert "could not be used" in j.prompts[1]


def test_an_empty_list_is_a_valid_extraction(tmp_state):
    anon_fixture(arms=("alpha",), steps=("01",))
    d = dz.extract("p", judge.FakeJudge(["[]"]))
    assert json.loads((d / "Arm A" / "01.json").read_text()) == []


def test_a_step_with_no_inputs_is_recorded_input_missing_without_asking(tmp_state):
    out, _ = anon_fixture(arms=("alpha",), steps=("01",))
    d = out / "anon" / "Arm A" / "01"
    for f in ("diff.patch", "gates.md", "questions.md", "transcript.md"):
        (d / f).unlink()
    (d / "repo" / "README.md").unlink(); (d / "repo").rmdir()
    got = json.loads((dz.extract("p", judge.FakeJudge([])) / "Arm A" / "01.json").read_text())
    assert got["status"] == "input_missing"


def test_extract_resumes_and_retries_failed_only_when_asked(tmp_state):
    anon_fixture(arms=("alpha",), steps=("01", "03"))
    d = paths.scoring_out("p") / "decisions" / "extracted" / "Arm A"
    d.mkdir(parents=True)
    (d / "01.json").write_text(D1)
    (d / "03.json").write_text(json.dumps({"status": "extract_failed", "why": "x", "raw": ""}))
    j = judge.FakeJudge([])
    dz.extract("p", j)
    assert j.prompts == []
    j = judge.FakeJudge([D1])
    dz.extract("p", j, retry_failed=True)
    assert len(j.prompts) == 1 and json.loads((d / "03.json").read_text())[0]["recorded_at"] == "gates.md:3"


def test_extract_ignores_anon_entries_that_are_not_labelled_arms(tmp_state):
    out, _ = anon_fixture(arms=("alpha",), steps=("01",))
    (out / "anon" / dz.ALIGN_ITEM / "x").mkdir(parents=True)
    j = judge.FakeJudge([D1])
    dz.extract("p", j)
    assert len(j.prompts) == 1


# ---- align ---------------------------------------------------------------------------------------------------------

ALIGNED = json.dumps({"topics": [
    {"id": "actor-unset", "question": "What if TROUPE_ACTOR is unset?", "not_considered": {"proposed": "poor", "why": "w"},
     "routes": [{"route": "fail", "labels": ["Arm A"], "reason_given": "owner", "outcome": "kept",
                 "proposed": "good", "proposed_why": "matches the owner's note"}]}]})


def _extracted(lab, nn, body):
    f = paths.scoring_out("p") / "decisions" / "extracted" / lab / f"{nn}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body)


def test_align_writes_topics_with_every_other_label_not_considered(tmp_state):
    anon_fixture(arms=("alpha", "beta"), steps=("01",))
    _extracted("Arm A", "01", D1); _extracted("Arm B", "01", "[]")
    j = judge.FakeJudge([ALIGNED])
    f = dz.align("p", j)
    t = json.loads(f.read_text())["topics"][0]
    assert f == paths.scoring_out("p") / "decisions" / "topics.json"
    assert [(r["route"], r["labels"]) for r in t["routes"]] == [("fail", ["Arm A"]), ("not considered", ["Arm B"])]
    assert t["routes"][1]["proposed"] == "poor"


def test_align_reads_one_scrubbed_input_and_never_an_arm_name(tmp_state):
    anon_fixture(arms=("alpha", "beta"), steps=("01",))
    _extracted("Arm A", "01", json.dumps([{"decision": "like speckit does", "options": [], "reason": "",
                                           "recorded_at": "unrecorded"}]))
    _extracted("Arm B", "01", "[]")
    j = judge.FakeJudge([ALIGNED])
    dz.align("p", j)
    assert j.files == [["extracted.json"]] and j.inputs[0] == paths.scoring_out("p") / "anon" / dz.ALIGN_ITEM
    text = (j.inputs[0] / "extracted.json").read_text()
    assert "Arm A" in text and "speckit" not in text.lower()
    assert not any(w in j.prompts[0] for w in ("alpha", "beta"))


def test_align_refuses_while_an_extraction_has_not_run(tmp_state):
    from runner.scoring import inputs
    anon_fixture(arms=("alpha", "beta"), steps=("01",))
    _extracted("Arm A", "01", D1)
    with pytest.raises(inputs.InputError, match="Arm B/01"):
        dz.align("p", judge.FakeJudge([]))


@pytest.mark.parametrize("bad", [
    '{"topics": [{"id": "x", "question": "q", "not_considered": {"proposed": "poor", "why": "w"}, '
    '"routes": [{"route": "r", "labels": ["Arm Z"], "reason_given": "", "outcome": "", "proposed": "good", "proposed_why": ""}]}]}',
    '{"topics": [{"id": "x", "question": "q", "not_considered": {"proposed": "poor", "why": "w"}, '
    '"routes": [{"route": "not considered", "labels": ["Arm A"], "reason_given": "", "outcome": "", "proposed": "good", "proposed_why": ""}]}]}',
    '{"topics": [{"id": "x", "question": "q", "not_considered": {"proposed": "poor", "why": "w"}, '
    '"routes": [{"route": "r", "labels": ["Arm A"], "reason_given": "", "outcome": "", "proposed": "great", "proposed_why": ""}]}]}',
    '{"topics": [{"id": "x", "question": "q", "not_considered": {"proposed": "poor", "why": "w"}, '
    '"routes": [{"route": "r", "labels": ["Arm A"], "reason_given": "", "outcome": "", "proposed": "good", "proposed_why": ""}, '
    '{"route": "s", "labels": ["Arm A"], "reason_given": "", "outcome": "", "proposed": "good", "proposed_why": ""}]}]}',
    '{"topics": [{"id": "Has Spaces", "question": "q", "not_considered": {"proposed": "poor", "why": "w"}, '
    '"routes": [{"route": "r", "labels": ["Arm A"], "reason_given": "", "outcome": "", "proposed": "good", "proposed_why": ""}]}]}'])
def test_unusable_alignments_are_refused(bad):
    with pytest.raises(judge.BadReply):
        dz.parse_topics(bad, ["Arm A", "Arm B"])


def test_two_unusable_alignments_are_recorded_and_stop_the_stage(tmp_state):
    from runner.scoring import inputs
    anon_fixture(arms=("alpha",), steps=("01",))
    _extracted("Arm A", "01", D1)
    with pytest.raises(inputs.InputError, match="align-failed.json"):
        dz.align("p", judge.FakeJudge(["nope", "nope again"]))
    got = json.loads((paths.scoring_out("p") / "decisions" / "align-failed.json").read_text())
    assert got["raw"] == "nope again" and not (paths.scoring_out("p") / "decisions" / "topics.json").exists()


# ---- sheet and import ----------------------------------------------------------------------------------------------

def _aligned_pass(failed=False):
    anon_fixture(arms=("alpha", "beta"), steps=("01",))
    _extracted("Arm A", "01", D1)
    _extracted("Arm B", "01", json.dumps({"status": "extract_failed", "why": "x", "raw": ""}) if failed else "[]")
    dz.align("p", judge.FakeJudge([ALIGNED]))


def test_sheet_writes_markdown_and_json_and_lists_failed_extractions_in_the_header(tmp_state):
    _aligned_pass(failed=True)
    md = dz.sheet("p")
    text = md.read_text()
    header = text[:text.index("\n## ")]
    assert "1 extraction failed" in header and "step 01" in header and "Arm B" not in text
    js = json.loads((md.parent / "rating-sheet.json").read_text())
    assert [(r["route_no"], r["route"], r["labels"]) for r in js["topics"][0]["routes"]] == [
        (1, "fail", ["Arm A"]), (2, "not considered", ["Arm B"])]
    assert js["failed"] == [{"label": "Arm B", "status": "extract_failed", "step": "01", "why": "x"}]


def test_import_writes_ratings_under_real_arm_names(tmp_state):
    _aligned_pass()
    md = dz.sheet("p")
    md.write_text(md.read_text().replace("rating:\nreason:\n", "rating: good\nreason: sensible\n", 1)
                  .replace("rating:\nreason:\n", "rating: poor\nreason: it mattered\n", 1))
    f = dz.import_ratings("p")
    assert f == paths.scoring_out("p") / "decisions" / "ratings.json"
    assert json.loads(f.read_text()) == {"topics": [{"id": "actor-unset", "routes": [
        {"route": "fail", "arms": ["alpha"], "rating": "good", "reason": "sensible"},
        {"route": "not considered", "arms": ["beta"], "rating": "poor", "reason": "it mattered"}]}]}


def test_import_refuses_a_sheet_with_a_route_left_unrated(tmp_state):
    _aligned_pass()
    md = dz.sheet("p")
    md.write_text(md.read_text().replace("rating:\nreason:\n", "rating: good\nreason: sensible\n", 1))
    with pytest.raises(ValueError, match="actor-unset route 2: no rating"):
        dz.import_ratings("p")
    assert not (paths.scoring_out("p") / "decisions" / "ratings.json").exists()


def test_import_refuses_a_topic_or_route_the_sheet_never_had(tmp_state):
    _aligned_pass()
    md = dz.sheet("p")
    md.write_text(md.read_text().replace("rating:\nreason:\n", "rating: good\nreason: s\n")
                  + "### Route 3\nrating: good\nreason: s\n## made-up\n### Route 1\nrating: good\nreason: s\n")
    with pytest.raises(ValueError) as e:
        dz.import_ratings("p")
    assert "actor-unset route 3: not on the sheet" in str(e.value) and "made-up: not on the sheet" in str(e.value)


# ---- estimate and the CLI gate -------------------------------------------------------------------------------------

def test_the_estimate_counts_unfinished_extractions_and_one_alignment(tmp_state):
    anon_fixture()
    assert dz.estimate("p")["calls"] == 5
    for lab in ("Arm A", "Arm B"):
        for nn in ("01", "03"):
            _extracted(lab, nn, "[]")
    assert dz.estimate("p")["calls"] == 1
    (paths.scoring_out("p") / "decisions" / "topics.json").write_text('{"topics": []}')
    assert dz.estimate("p")["calls"] == 0


def test_judge_estimate_prints_decision_calls_in_the_total(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a")])
    assert cli.main(["score", "p", "--stage", "judge-estimate"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert (got["judge_calls"], got["decision_calls"], got["calls"]) == (1, 5, 6)


@pytest.mark.parametrize("stage", ["decisions-extract", "decisions-align"])
def test_decision_stages_that_ask_a_model_refuse_without_approval(tmp_state, monkeypatch, capsys, stage):
    from runner import cli
    anon_fixture()
    monkeypatch.setattr(judge, "items", lambda pass_: [])
    monkeypatch.setattr(judge, "ContainerJudge", lambda *a, **k: pytest.fail("no judge without approval"))
    assert cli.main(["score", "p", "--stage", stage]) == 1
    assert "judge-approved is missing" in capsys.readouterr().out


def test_decisions_extract_runs_once_the_total_is_approved(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    monkeypatch.setattr(judge, "items", lambda pass_: [])
    (paths.scoring_out("p") / "judge-approved").write_text("approved 2026-10-06 5\n")
    monkeypatch.setattr(judge, "ContainerJudge", lambda pass_: judge.FakeJudge([D1] * 4))
    assert cli.main(["score", "p", "--stage", "decisions-extract"]) == 0
    assert len(list((paths.scoring_out("p") / "decisions" / "extracted").rglob("*.json"))) == 4


def test_decisions_sheet_and_import_stages_need_no_approval(tmp_state, capsys):
    from runner import cli
    _aligned_pass()
    assert cli.main(["score", "p", "--stage", "decisions-sheet"]) == 0
    md = paths.scoring_out("p") / "decisions" / "rating-sheet.md"
    md.write_text(md.read_text().replace("rating:\nreason:\n", "rating: good\nreason: s\n"))
    assert cli.main(["score", "p", "--stage", "decisions-import"]) == 0
    assert (paths.scoring_out("p") / "decisions" / "ratings.json").exists()


def test_decisions_import_prints_the_sheets_problems_and_exits_1(tmp_state, capsys):
    from runner import cli
    _aligned_pass()
    assert cli.main(["score", "p", "--stage", "decisions-sheet"]) == 0
    capsys.readouterr()
    assert cli.main(["score", "p", "--stage", "decisions-import"]) == 1
    assert "actor-unset route 1: no rating" in capsys.readouterr().out


def test_sheet_refuses_to_overwrite_a_sheet_the_owner_has_started(tmp_state):
    from runner.scoring import inputs
    _aligned_pass()
    md = dz.sheet("p")
    assert dz.sheet("p") == md                              # a blank sheet may be rewritten
    md.write_text(md.read_text().replace("rating:\nreason:\n", "rating: good\nreason:\n", 1))
    with pytest.raises(inputs.InputError, match="already holds ratings"):
        dz.sheet("p")
    assert "rating: good" in md.read_text()


def test_the_container_judges_mount_check_accepts_the_alignment_and_extraction_inputs(tmp_state):
    out, _ = anon_fixture(arms=("alpha",), steps=("01",))
    _extracted("Arm A", "01", D1)
    dz.align("p", judge.FakeJudge([ALIGNED]))
    home = paths.judge_home("p") / "call"
    judge.check_mounts(judge.mounts(home, out / "anon" / dz.ALIGN_ITEM, ["extracted.json"]), "p")
    d = out / "anon" / "Arm A" / "01"
    judge.check_mounts(judge.mounts(home, d, dz._present(d)), "p")
