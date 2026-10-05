# tests/runner/scoring/test_judge.py
"""Plan 3 Task 17: judges. Offline only: `FakeJudge` stands in for a model; `ContainerJudge` is exercised with
`session.run_turn` and `egress.Stage` replaced by in-process fakes (no Docker, no model calls)."""
import gzip
import json
from pathlib import Path

import pytest
from runner import config, credentials, paths, session
from runner.docker import Mount

from runner.scoring import aggregate, inputs, judge
from runner.session import TurnResult

OK = '{"score": 3, "evidence": ["spec/003/spec.md:12"], "notes": "one doc stale"}'
NA = '{"score": null, "status": "not_applicable", "evidence": ["questions.md: (none)"], "notes": "no questions"}'
REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("bad", ['not json', '{"score": 5, "evidence": ["x"], "notes": ""}',
                                 '{"score": 2, "evidence": [], "notes": ""}', '{"score": "3", "evidence": ["x"]}'])
def test_unusable_replies_are_refused(bad):
    with pytest.raises(judge.BadReply):
        judge.parse(bad)


def test_a_reply_wrapped_in_prose_is_accepted_when_it_holds_one_object():
    assert judge.parse("Here you go:\n" + OK).score == 3


def test_two_bad_replies_are_recorded_as_judge_failed_not_a_score(tmp_path):
    j = judge.FakeJudge(["nope", "still nope"])
    v = judge.ask_with_retry(j, "prompt", tmp_path)
    assert v.status == "judge_failed" and v.score is None and v.raw == "still nope"


def test_the_stage_resumes_without_repeating_finished_items(tmp_state, monkeypatch):
    items = [("req_test_code", "alpha", "01", "auditor"), ("req_test_code", "alpha", "01", "maintainer")]
    monkeypatch.setattr(judge, "items", lambda pass_: items)
    monkeypatch.setattr(judge, "inputs_for", lambda pass_, part, arm, key: (tmp_state, ["repo/x"]))
    (tmp_state / "repo").mkdir(); (tmp_state / "repo" / "x").write_text("x")   # R24(d): inputs must exist
    first = judge.FakeJudge([OK])
    with pytest.raises(IndexError):                     # the fake runs out after one reply: a crash mid-stage
        judge.run("p", first)
    second = judge.FakeJudge([OK])
    assert judge.run("p", second)["asked"] == 1         # only the unfinished item is asked again


# ---- R5: "not applicable" ------------------------------------------------------------------------------------------

def test_a_not_applicable_reply_parses_to_no_score_where_allowed():
    v = judge.parse(NA, na_allowed=True)
    assert v.status == "not_applicable" and v.score is None and v.evidence == ["questions.md: (none)"]


@pytest.mark.parametrize("bad", [
    '{"score": null, "status": "not_applicable", "evidence": [], "notes": ""}',        # still needs evidence
    '{"score": 2, "status": "not_applicable", "evidence": ["x"], "notes": ""}',        # n/a carries no score
    '{"score": null, "status": "judge_failed", "evidence": ["x"], "notes": ""}',       # a judge cannot claim this
    '{"score": null, "evidence": ["x"], "notes": ""}'])
def test_malformed_not_applicable_replies_are_refused(bad):
    with pytest.raises(judge.BadReply):
        judge.parse(bad, na_allowed=True)


def test_not_applicable_is_refused_by_default_and_where_the_rubric_does_not_offer_it():
    for kw in ({}, {"na_allowed": False}):
        with pytest.raises(judge.BadReply):
            judge.parse(NA, **kw)


def test_a_second_not_applicable_by_default_is_judge_failed(tmp_path):
    assert judge.ask_with_retry(judge.FakeJudge([NA, NA]), "p", tmp_path).status == "judge_failed"


def test_not_applicable_is_offered_only_by_rubrics_with_the_explicit_key():
    r = inputs.load_rubrics()
    assert r["research_first"].not_applicable is True and judge.na_allowed(r["research_first"])
    assert [p for p, x in r.items() if x.not_applicable] == ["research_first"]
    assert not judge.na_allowed(r["req_test_code"])


RUBRIC = """dimension = "interaction"
unit = "{unit}"
evidence = ["questions"]
{extra}
[levels]
0 = "a"
1 = "b"
2 = "c"
3 = "d"
4 = "e"
""" + "".join(f'[[lens]]\nname = "l{i}"\nperspective = "not applicable when nothing to judge"\n' for i in range(3))


def test_rubric_text_mentioning_not_applicable_without_the_key_does_not_offer_it(tmp_path):
    (tmp_path / "x.toml").write_text(RUBRIC.format(unit="step", extra=""))
    r = inputs.load_rubrics(tmp_path)["x"]
    assert r.not_applicable is False and not judge.na_allowed(r)


@pytest.mark.parametrize("unit,extra", [("arm", "not_applicable = true"), ("step", 'not_applicable = "yes"')])
def test_the_not_applicable_key_is_refused_on_arm_units_and_when_not_a_boolean(tmp_path, unit, extra):
    (tmp_path / "x.toml").write_text(RUBRIC.format(unit=unit, extra=extra))
    with pytest.raises(inputs.InputError):
        inputs.load_rubrics(tmp_path)


def test_the_prompt_mentions_not_applicable_only_when_it_is_allowed():
    r = inputs.load_rubrics()
    lens = r["research_first"].lenses[0]
    p = judge.prompt(r["research_first"], lens, "03", ["questions.md", "transcript.md"])
    assert '"status": "not_applicable"' in p
    p2 = judge.prompt(r["req_test_code"], r["req_test_code"].lenses[0], "03", ["repo/"])
    assert "not_applicable" not in p2


def test_a_second_not_applicable_where_it_is_not_allowed_is_judge_failed(tmp_path):
    v = judge.ask_with_retry(judge.FakeJudge([NA, NA]), "p", tmp_path, na_allowed=False)
    assert v.status == "judge_failed" and v.score is None


# ---- the prompt ----------------------------------------------------------------------------------------------------

def test_the_prompt_carries_the_rubric_levels_lens_files_shape_and_blindness_instruction():
    r = inputs.load_rubrics()["req_test_code"]
    lens = r.lenses[1]
    p = judge.prompt(r, lens, "03", ["repo/"])
    assert all(r.levels[n] in p for n in range(5))
    assert lens["perspective"] in p and "/judge/repo/" in p
    assert '"score"' in p and '"evidence"' in p and '"notes"' in p
    assert "Cite at least one file path with line, commit, or transcript line for your score." in p
    assert "You are judging Arm X at step 3; you do not know which method it used and must not guess." in p


# ---- items, inputs_for, run on an anonymised fixture -------------------------------------------------------------

STEP_FILES = ("diff.patch", "transcript.md", "questions.md", "gates.md", "others-questions.md")


def anon_fixture(pass_="p", arms=("alpha", "beta"), steps=("01", "03")):
    """The layout anonymise writes (stale-list.toml beside each step that has a stale list)."""
    out = paths.scoring_out(pass_)
    labels = {a: f"Arm {chr(65 + i)}" for i, a in enumerate(sorted(arms))}
    for arm, lab in labels.items():
        for nn in steps:
            d = out / "anon" / lab / nn
            (d / "repo").mkdir(parents=True)
            (d / "repo" / "README.md").write_text("readme " * 100)
            for f in STEP_FILES:
                (d / f).write_text(f"{f} of {lab}\n")
            if nn != "01":
                (d / "stale-list.toml").write_text(f"stale list {nn}\n")
        (out / "anon" / lab / "setup").mkdir(parents=True)
        (out / "anon" / lab / "setup" / "checklist.json").write_text("{}")
    (out / "anon-key.json").write_text(json.dumps({lab: arm for arm, lab in labels.items()}))
    return out, labels


def test_items_cover_every_judged_part_arm_applicable_step_and_lens(tmp_state):
    anon_fixture()
    its = judge.items("p")
    assert its == sorted(its)
    r = inputs.load_rubrics()
    assert {(p, a, k, l) for p, a, k, l in its if p == "req_test_code"} == {
        ("req_test_code", arm, nn, l["name"]) for arm in ("alpha", "beta") for nn in ("01", "03")
        for l in r["req_test_code"].lenses}
    assert {k for p, a, k, l in its if p == "stale_updated"} == {"03"}       # steps 3, 5, 7 only; 5 and 7 absent
    assert {k for p, a, k, l in its if p == "hand_edit"} == set()            # step 2 only; absent
    assert {k for p, a, k, l in its if r[p].unit == "arm"} == {"arm"}
    assert {p for p, *_ in its} == set(r) - {"hand_edit", "step6_spec_trace"}
    assert {a for _, a, *_ in its} == {"alpha", "beta"}                        # real arm names, never labels


def test_items_refuse_without_the_anonymisation_key(tmp_state):
    with pytest.raises(inputs.InputError):
        judge.items("p")


def test_inputs_for_selects_the_files_each_rubric_evidence_kind_names(tmp_state):
    out, lab = anon_fixture()
    d, files = judge.inputs_for("p", "req_test_code", "beta", "03")
    assert d == out / "anon" / lab["beta"] / "03" and files == ["repo/"]
    assert judge.inputs_for("p", "gates", "beta", "03")[1] == ["gates.md", "transcript.md"]
    assert judge.inputs_for("p", "change_reason", "beta", "03")[1] == ["diff.patch", "repo/"]


def test_question_value_also_reads_the_other_arms_questions(tmp_state):
    anon_fixture()
    assert judge.inputs_for("p", "question_value", "alpha", "01")[1] == [
        "others-questions.md", "questions.md", "transcript.md"]
    assert "others-questions.md" not in judge.inputs_for("p", "research_first", "alpha", "01")[1]


def test_inputs_for_selects_the_anonymised_stale_list_and_writes_nothing(tmp_state):
    out, lab = anon_fixture()
    before = sorted((p, p.stat().st_mtime_ns) for p in out.rglob("*"))
    d, files = judge.inputs_for("p", "stale_updated", "alpha", "03")
    assert files == ["diff.patch", "repo/", "stale-list.toml"]
    assert sorted((p, p.stat().st_mtime_ns) for p in out.rglob("*")) == before


def test_arm_unit_parts_read_the_anonymised_setup_record(tmp_state):
    out, lab = anon_fixture()
    d, files = judge.inputs_for("p", "fit", "alpha", "arm")
    assert d == out / "anon" / lab["alpha"] / "setup" and files == ["checklist.json"]


def test_run_writes_each_verdict_under_the_real_arm_and_never_names_it_to_the_judge(tmp_state, monkeypatch):
    anon_fixture()
    its = [("req_test_code", "alpha", "01", "auditor"), ("fit", "beta", "arm", "claude-code-user")]
    monkeypatch.setattr(judge, "items", lambda pass_: its)
    j = judge.FakeJudge([OK, OK])
    assert judge.run("p", j) == {"asked": 2, "skipped": 0, "input_missing": 0}
    v = json.loads(judge.out_path("p", "req_test_code", "alpha", "01", "auditor").read_text())
    assert v["score"] == 3 and v["status"] == "ok" and v["evidence"] == ["spec/003/spec.md:12"]
    assert judge.out_path("p", "fit", "beta", "arm", "claude-code-user").exists()
    assert not any("alpha" in p or "beta" in p for p in j.prompts)
    assert [i.name for i in j.inputs] == ["01", "setup"]
    assert j.files == [["repo/"], ["checklist.json"]]


# ---- R24(d): missing inputs are not asked --------------------------------------------------------------------------

def missing_json(d, *entries):
    (d / "MISSING.json").write_text(json.dumps([{"files": f, "why": w} for f, w in entries]))


def test_an_item_whose_input_is_named_in_missing_json_is_recorded_input_missing_without_asking(tmp_state, monkeypatch):
    out, lab = anon_fixture()
    d = out / "anon" / lab["alpha"] / "01"
    (d / "transcript.md").unlink()
    missing_json(d, (["transcript.md"], "no arm turn streams"))
    monkeypatch.setattr(judge, "items", lambda pass_: [("gates", "alpha", "01", "auditor"),
                                                       ("req_test_code", "alpha", "01", "auditor")])
    j = judge.FakeJudge([OK])
    assert judge.run("p", j) == {"asked": 1, "skipped": 0, "input_missing": 1}
    v = json.loads(judge.out_path("p", "gates", "alpha", "01", "auditor").read_text())
    assert v["score"] is None and v["status"] == "input_missing" and v["evidence"] == []
    assert "transcript.md: no arm turn streams" in v["notes"]
    assert len(j.prompts) == 1                                          # only req_test_code (repo/ present) asked


def test_missing_json_is_authoritative_even_for_a_file_on_disk(tmp_state, monkeypatch):
    out, lab = anon_fixture()
    missing_json(out / "anon" / lab["alpha"] / "01", (["repo/", "diff.patch"], "export failed"))
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "x")])
    judge.run("p", judge.FakeJudge([]))
    v = json.loads(judge.out_path("p", "req_test_code", "alpha", "01", "x").read_text())
    assert v["status"] == "input_missing" and v["notes"] == "repo/: export failed"


def test_an_absent_required_file_without_missing_json_is_also_input_missing(tmp_state, monkeypatch):
    out, lab = anon_fixture()
    (out / "anon" / lab["alpha"] / "01" / "diff.patch").unlink()
    monkeypatch.setattr(judge, "items", lambda pass_: [("change_reason", "alpha", "01", "x")])
    judge.run("p", judge.FakeJudge([]))
    v = json.loads(judge.out_path("p", "change_reason", "alpha", "01", "x").read_text())
    assert v["status"] == "input_missing" and "diff.patch" in v["notes"]


def test_a_missing_setup_record_is_input_missing(tmp_state, monkeypatch):
    import shutil
    out, lab = anon_fixture()
    shutil.rmtree(out / "anon" / lab["alpha"] / "setup")
    monkeypatch.setattr(judge, "items", lambda pass_: [("fit", "alpha", "arm", "x")])
    judge.run("p", judge.FakeJudge([]))
    assert json.loads(judge.out_path("p", "fit", "alpha", "arm", "x").read_text())["status"] == "input_missing"


def test_aggregate_scores_an_input_missing_step_as_unmeasured_with_why_input_missing(tmp_state):
    d = paths.scoring_out("p") / "judged" / "gates" / "alpha" / "01"
    d.mkdir(parents=True)
    for lens in ("a", "b", "c"):
        (d / f"{lens}.json").write_text(json.dumps({"score": None, "status": "input_missing", "evidence": [],
                                                   "notes": "transcript.md: absent"}))
    got = aggregate._judged("p", "gates", "alpha", "01", {}, frozenset({"a", "b", "c"}))
    assert got["score"] is None and got["why"] == "input missing" and got["lenses"] == {}


# ---- resume: input_missing is re-checked, judge_failed only with retry_failed -----------------------------------

def _write_status(status, *key):
    f = judge.out_path("p", *key); f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"score": None, "status": status, "evidence": [], "notes": "", "raw": ""}))


def test_an_input_missing_verdict_is_asked_again_once_the_inputs_are_present(tmp_state, monkeypatch):
    anon_fixture()
    key = ("req_test_code", "alpha", "01", "a")
    monkeypatch.setattr(judge, "items", lambda pass_: [key])
    _write_status("input_missing", *key)
    assert judge.run("p", judge.FakeJudge([OK])) == {"asked": 1, "skipped": 0, "input_missing": 0}
    assert json.loads(judge.out_path("p", *key).read_text())["status"] == "ok"


def test_an_input_missing_verdict_stays_when_the_inputs_are_still_missing(tmp_state, monkeypatch):
    out, lab = anon_fixture()
    (out / "anon" / lab["alpha"] / "01" / "gates.md").unlink()
    key = ("gates", "alpha", "01", "a")
    monkeypatch.setattr(judge, "items", lambda pass_: [key])
    _write_status("input_missing", *key)
    assert judge.run("p", judge.FakeJudge([])) == {"asked": 0, "skipped": 0, "input_missing": 1}
    assert json.loads(judge.out_path("p", *key).read_text())["status"] == "input_missing"


def test_a_judge_failed_verdict_is_final_unless_retry_failed_is_asked_for(tmp_state, monkeypatch):
    anon_fixture()
    key = ("req_test_code", "alpha", "01", "a")
    monkeypatch.setattr(judge, "items", lambda pass_: [key])
    _write_status("judge_failed", *key)
    assert judge.run("p", judge.FakeJudge([])) == {"asked": 0, "skipped": 1, "input_missing": 0}
    assert judge.estimate("p")["calls"] == 0 and judge.estimate("p", retry_failed=True)["calls"] == 1
    assert judge.run("p", judge.FakeJudge([OK]), retry_failed=True)["asked"] == 1
    assert json.loads(judge.out_path("p", *key).read_text())["status"] == "ok"


def test_estimate_counts_input_missing_items_that_are_now_answerable(tmp_state, monkeypatch):
    out, lab = anon_fixture()
    (out / "anon" / lab["alpha"] / "01" / "gates.md").unlink()
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a"),
                                                       ("gates", "alpha", "01", "a")])
    _write_status("input_missing", "req_test_code", "alpha", "01", "a")   # answerable now
    _write_status("input_missing", "gates", "alpha", "01", "a")           # still missing
    assert judge.estimate("p")["calls"] == 1


# ---- estimate and the cost it implies ------------------------------------------------------------------------------

def test_estimate_counts_pending_calls_and_their_input_size(tmp_state, monkeypatch):
    out, lab = anon_fixture(arms=("alpha",), steps=("01",))
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a"),
                                                       ("req_test_code", "alpha", "01", "b"),
                                                       ("gates", "alpha", "01", "a")])
    judge.out_path("p", "req_test_code", "alpha", "01", "b").parent.mkdir(parents=True)
    judge.out_path("p", "req_test_code", "alpha", "01", "b").write_text("{}")       # already done: not a call
    e = judge.estimate("p")
    size = len("readme " * 100) + len("gates.md of Arm A\n") + len("transcript.md of Arm A\n")
    assert e == {"calls": 2, "input_mb": round(size / 1e6, 3)}


def test_the_implied_cost_uses_the_pos_mean_cost_per_call(tmp_state):
    for arm, usd, turns in (("alpha", 1.0, 4), ("beta", 2.0, 6)):
        d = paths.RESULTS / "p" / arm / "01"; d.mkdir(parents=True)
        (d / "cost.json").write_text(json.dumps({"po": {"usd": usd, "turns": turns}}))
    c = judge.implied_cost("p", 20)
    assert c == {"po_usd_per_call": 0.3, "implied_usd": 6.0}


def test_the_implied_cost_is_unknown_without_po_costs(tmp_state):
    (paths.RESULTS / "p").mkdir(parents=True)
    assert judge.implied_cost("p", 20) == {"po_usd_per_call": None, "implied_usd": None}


# ---- ContainerJudge (fakes for the container and the egress stage) -------------------------------------------------

class FakeStage:
    made: list = []

    def __init__(self, *a, **k):
        self.net = "bk-net-fake"
        FakeStage.made.append(a)

    def __enter__(self): return self

    def __exit__(self, *exc): return None


def fake_turns(monkeypatch, replies, model=None):
    """`session.run_turn` stand-in: each call pops (outcome, text), writes a stream and a transcript as the real
    claude would, and records the Turn it was given."""
    model = model or config.load_pins().model
    FakeStage.made = []
    monkeypatch.setattr(judge.egress, "Stage", FakeStage)
    monkeypatch.setattr(judge.time, "sleep", lambda s: None)
    seen, queue = [], list(replies)

    def run_turn(t, cred, out_dir, timeout_s):
        projects = t.config_dir / "projects"
        object.__setattr__(t, "preexisting", sorted(str(f) for f in projects.rglob("*")) if projects.exists() else [])
        seen.append(t)
        outcome, text = queue.pop(0)
        (out_dir / "turns").mkdir(parents=True, exist_ok=True)
        stream = out_dir / "turns" / f"{session.stem(t)}.stream.jsonl.gz"
        sid = f"s{len(seen)}"
        evs = [{"type": "system", "subtype": "init", "model": model, "claude_code_version": "2.1.281"},
               {"type": "assistant", "message": {"model": model, "content": [{"type": "text", "text": text}]}}]
        result = None
        if outcome in ("ok", "is_error"):
            result = {"type": "result", "is_error": outcome == "is_error", "result": text,
                      "modelUsage": {model: {}}, "total_cost_usd": 0.01}
            evs.append(result)
        with gzip.open(stream, "wt") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in evs))
        proj = t.config_dir / "projects" / "-judge"; proj.mkdir(parents=True, exist_ok=True)
        (proj / f"{sid}.jsonl").write_text(json.dumps(evs[1]) + "\n")
        return TurnResult(sid, outcome, text if result else "", evs[0], result, 0.01, {}, {}, 0.1, [], stream, None)

    monkeypatch.setattr(judge.session, "run_turn", run_turn)
    return seen


@pytest.fixture
def item(tmp_state):
    out, lab = anon_fixture()
    return out / "anon" / lab["alpha"] / "03"


FILES = ["diff.patch", "repo/"]


def test_the_container_judge_runs_with_only_a_fresh_home_its_selected_inputs_and_the_message(item, monkeypatch):
    seen = fake_turns(monkeypatch, [("ok", OK)])
    assert judge.ContainerJudge("p", credentials.dummy()).ask("judge this", item, FILES) == OK
    t = seen[0]
    spec = session._spec(t)                                     # the container's final mount set
    m = {x.ctr: x for x in spec.mounts}
    assert set(m) == {"/home/actor", "/judge/diff.patch", "/judge/repo", "/inbox/msg.md"}
    assert m["/judge/diff.patch"].host == item / "diff.patch" and m["/judge/repo"].host == item / "repo"
    assert all(m[c].ro for c in ("/judge/diff.patch", "/judge/repo", "/inbox/msg.md"))
    assert m["/inbox/msg.md"].host.parent == paths.judge_inbox("p")
    assert m["/home/actor"].ro is False and m["/home/actor"].host.parent == paths.judge_home("p")
    assert t.role == "judge" and t.workdir == "/judge" and t.message == "judge this" and t.dry is False
    assert t.image == config.load_pins().images["base"] and t.step == 3
    assert t.config_dir == m["/home/actor"].host / ".claude"
    assert FakeStage.made[0][3] == config.load_pins().egress_po


def test_a_research_first_judge_cannot_see_the_other_arms_questions(item, monkeypatch):
    seen = fake_turns(monkeypatch, [("ok", OK)])
    monkeypatch.setattr(judge, "items", lambda pass_: [("research_first", "alpha", "03", "investigator")])
    judge.run("p", judge.ContainerJudge("p", credentials.dummy()))
    ctrs = {x.ctr for x in seen[0].mounts}
    assert ctrs == {"/home/actor", "/judge/questions.md", "/judge/transcript.md"}


def test_each_call_gets_a_fresh_home_holding_no_earlier_calls_transcripts_and_it_is_removed(item, monkeypatch):
    seen = fake_turns(monkeypatch, [("ok", OK), ("ok", OK)])
    j = judge.ContainerJudge("p", credentials.dummy())
    j.ask("lens one", item, FILES)
    j.ask("lens two", item, FILES)
    assert seen[0].config_dir != seen[1].config_dir
    assert seen[1].preexisting == []                      # nothing of call 1 was in call 2's home
    assert not seen[0].config_dir.parent.exists() and not seen[1].config_dir.parent.exists()
    assert list((j.last_dir / "transcripts").rglob("*.jsonl.gz"))   # collected before the home went


def test_the_container_judge_refuses_an_empty_input_list(item, monkeypatch):
    fake_turns(monkeypatch, [("ok", OK)])
    with pytest.raises(ValueError):
        judge.ContainerJudge("p", credentials.dummy()).ask("judge this", item, [])


def test_the_container_judge_runs_isolated_with_read_only_tools_in_safe_mode(item, monkeypatch):
    seen = fake_turns(monkeypatch, [("ok", OK)])
    judge.ContainerJudge("p", credentials.dummy()).ask("judge this", item, FILES)
    env = seen[0].env
    assert env["BK_ISOLATED"] == "1" and env["BK_TOOLS"] == "Read,Glob,Grep" and env["CLAUDE_CODE_SAFE_MODE"] == "1"
    assert env["BK_MODEL"] == config.load_pins().model == "claude-opus-5-5"
    assert "GH_REPO" not in env and "BK_PLUGIN_DIRS" not in env


def test_the_container_judge_keeps_transcripts_and_a_clean_pin_report_per_call(item, monkeypatch):
    fake_turns(monkeypatch, [("ok", OK)])
    j = judge.ContainerJudge("p", credentials.dummy())
    j.ask("judge this", item, FILES)
    pin = json.loads((j.last_dir / "model-pin.json").read_text())
    assert pin["ok"] is True and list((j.last_dir / "transcripts").rglob("*.jsonl.gz"))
    assert j.last_dir.is_relative_to(paths.scoring_out("p") / "judge-calls" / "Arm A" / "03")


def test_a_reply_from_the_wrong_model_raises_and_is_never_returned(item, monkeypatch):
    fake_turns(monkeypatch, [("ok", OK)], model="claude-sonnet-4-5")
    with pytest.raises(judge.PinViolation):
        judge.ContainerJudge("p", credentials.dummy()).ask("judge this", item, FILES)


def test_a_transient_failure_is_retried_with_backoff(item, monkeypatch):
    seen = fake_turns(monkeypatch, [("no_result", ""), ("ok", OK)])
    assert judge.ContainerJudge("p", credentials.dummy()).ask("judge this", item, FILES) == OK
    assert len(seen) == 2


@pytest.mark.parametrize("outcome", ["auth_failed", "timeout"])
def test_auth_failures_and_timeouts_raise_at_once(item, monkeypatch, outcome):
    seen = fake_turns(monkeypatch, [(outcome, ""), ("ok", OK)])
    with pytest.raises(judge.SessionError):
        judge.ContainerJudge("p", credentials.dummy()).ask("judge this", item, FILES)
    assert len(seen) == 1


def _home():
    return Mount(paths.judge_home("p") / "call-1", "/home/actor", False)


@pytest.mark.parametrize("host", [
    lambda: paths.scoring_out("p") / "anon-key.json",
    lambda: paths.scoring_out("p"),                                  # would expose anon-key.json
    lambda: paths.scoring_out("p") / "anon",                         # every label at once
    lambda: paths.scoring_out("p") / "anon" / "Arm A",               # every step of one label
    lambda: paths.scoring_out("p") / "anon" / "Arm A" / "03",        # the whole item, not its selected inputs
    lambda: paths.scoring_out("p") / "collected",                    # results/ outside anon/
    lambda: paths.RESULTS / "p" / "alpha" / "01",
    lambda: REPO / "tests",
    lambda: REPO / "reference",
    lambda: REPO,                                                    # contains all of the above
    lambda: paths.STATE / "p" / "alpha" / "work",
    lambda: paths.STATE / "p",
    lambda: paths.judge_home("p"),                                   # every call's home, not one fresh one
])
def test_the_judge_mount_check_refuses_anything_but_one_fresh_home_and_one_items_selected_inputs(tmp_state, host):
    with pytest.raises(PermissionError):
        judge.check_mounts([_home(), Mount(host(), "/judge/x", True)], "p")


def test_the_judge_mount_check_refuses_inputs_from_two_items(item):
    other = item.parent.parent / "Arm B" / "03"
    with pytest.raises(PermissionError):
        judge.check_mounts([_home(), Mount(item / "diff.patch", "/judge/diff.patch", True),
                            Mount(other / "repo", "/judge/repo", True)], "p")


def test_the_judge_mount_check_refuses_writable_inputs(item):
    with pytest.raises(PermissionError):
        judge.check_mounts([Mount(item / "repo", "/judge/repo", False)], "p")


def test_the_judge_mount_check_refuses_inputs_outside_slash_judge(item):
    with pytest.raises(PermissionError):
        judge.check_mounts([Mount(item / "repo", "/work", True)], "p")


def test_the_judge_mount_check_accepts_a_fresh_home_and_one_items_selected_inputs(item):
    judge.check_mounts(judge.mounts(paths.judge_home("p") / "call-1", item, FILES), "p")


def test_judge_is_a_known_session_role():
    assert "judge" in session.ROLES


# ---- the stages ----------------------------------------------------------------------------------------------------

def test_the_judge_stage_refuses_without_the_owners_approval_and_asks_nothing(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    monkeypatch.setattr(judge, "ContainerJudge", lambda *a, **k: pytest.fail("no judge without approval"))
    assert cli.main(["score", "p", "--stage", "judge"]) == 1
    assert "judge-approved" in capsys.readouterr().out
    assert not (paths.scoring_out("p") / "judged").exists()


@pytest.mark.parametrize("line", ["approved", "approved 2026-10-06", "approved yesterday 2", "ok 2026-10-06 2",
                                  "approved 2026-10-06 two"])
def test_the_judge_stage_refuses_a_malformed_approval(tmp_state, monkeypatch, capsys, line):
    from runner import cli
    anon_fixture()
    (paths.scoring_out("p") / "judge-approved").write_text(line + "\n")
    monkeypatch.setattr(judge, "ContainerJudge", lambda *a, **k: pytest.fail("no judge on a malformed approval"))
    assert cli.main(["score", "p", "--stage", "judge"]) == 1
    assert "approved <date> <calls>" in capsys.readouterr().out


def test_the_judge_stage_refuses_when_the_estimate_has_grown_past_the_approval(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    # anon_fixture also makes 5 decision calls (4 extractions + 1 alignment): one approval covers the total (Task 18)
    (paths.scoring_out("p") / "judge-approved").write_text("approved 2026-10-06 6\n")
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a"),
                                                       ("req_test_code", "alpha", "01", "b")])
    monkeypatch.setattr(judge, "ContainerJudge", lambda *a, **k: pytest.fail("no judge past the approval"))
    assert cli.main(["score", "p", "--stage", "judge"]) == 1
    out = capsys.readouterr().out
    assert "7 calls" in out and "approved 6" in out


def test_retry_failed_counts_failed_items_against_the_approval_and_asks_them(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    key = ("req_test_code", "alpha", "01", "a")
    monkeypatch.setattr(judge, "items", lambda pass_: [key])
    _write_status("judge_failed", *key)
    # anon_fixture also makes 5 decision calls (4 extractions + 1 alignment): one approval covers the total (Task 18)
    (paths.scoring_out("p") / "judge-approved").write_text("approved 2026-10-06 6\n")
    monkeypatch.setattr(judge, "ContainerJudge", lambda pass_: judge.FakeJudge([OK]))
    assert cli.main(["score", "p", "--stage", "judge"]) == 0
    assert '"asked": 0' in capsys.readouterr().out
    assert cli.main(["score", "p", "--stage", "judge", "--retry-failed"]) == 0
    assert '"asked": 1' in capsys.readouterr().out


def test_the_judge_stage_runs_once_approved(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    # anon_fixture also makes 5 decision calls (4 extractions + 1 alignment): one approval covers the total (Task 18)
    (paths.scoring_out("p") / "judge-approved").write_text("approved 2026-10-06 7\n")
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a"),
                                                       ("req_test_code", "alpha", "01", "b")])
    monkeypatch.setattr(judge, "ContainerJudge", lambda pass_: judge.FakeJudge([OK, OK]))
    assert cli.main(["score", "p", "--stage", "judge"]) == 0
    assert '"asked": 2' in capsys.readouterr().out


def test_the_estimate_stage_needs_no_approval_and_prints_calls_size_and_implied_cost(tmp_state, monkeypatch, capsys):
    from runner import cli
    anon_fixture()
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a")])
    assert cli.main(["score", "p", "--stage", "judge-estimate"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["judge_calls"] == 1 and got["calls"] == 6 and "input_mb" in got and got["implied_usd"] is None


def test_the_estimate_shows_an_upper_bound_with_parse_retries_but_approval_still_checks_the_calls(tmp_state, monkeypatch,
                                                                                                   capsys):
    # every judge and decision call may be retried once when its reply does not parse: shown, never gated on
    from runner import cli
    anon_fixture()
    monkeypatch.setattr(judge, "items", lambda pass_: [("req_test_code", "alpha", "01", "a")])
    monkeypatch.setattr(judge, "implied_cost", lambda pass_, calls: {"po_usd_per_call": 0.5, "implied_usd": 0.5 * calls})
    assert cli.main(["score", "p", "--stage", "judge-estimate"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["calls_with_parse_retries"] == 2 * got["calls"] and got["implied_usd_with_parse_retries"] == got["calls"]
    (paths.scoring_out("p") / "judge-approved").write_text(f"approved 2026-10-06 {got['calls']}\n")
    monkeypatch.setattr(judge, "run", lambda *a, **k: {})
    monkeypatch.setattr(judge, "ContainerJudge", lambda pass_: None)
    assert cli.main(["score", "p", "--stage", "judge"]) == 0
