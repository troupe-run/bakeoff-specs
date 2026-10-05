# tests/runner/scoring/test_review.py
"""Plan 3 Task 19: the owner's review queue (disputed, decisive, seeded sample), the blind sheet and the import."""
import copy
import json
import math
from datetime import date

import pytest
from runner import paths
from runner.scoring import aggregate, inputs, review
from runner.scoring import cli as scli
from tests.runner.scoring.test_confidence import W, arm
from tests.runner.scoring.test_judge import anon_fixture


def _scores(arms):
    return {"weights": {"dimensions": W, "parts": {}}, "arms": arms}


def _judged_arm(fa, fb, lenses):
    """An arm whose dimension-a step 1 is judged (carries lenses) but not disputed."""
    a = arm(fa, fb)
    a["dimensions"]["a"]["parts"]["a"]["steps"]["1"] = {"score": sorted(lenses.values())[1] / 4, "disputed": False,
                                                        "lenses": lenses}
    return a


def test_disputed_items_are_always_queued():
    q = review.queue(_scores({"p": arm(0.9, 0.9, lenses={"x": 0, "y": 2, "z": 4}), "q": arm(0.1, 0.1)}), "s", 0.0)
    assert [(i["arm"], i["reason"]) for i in q] == [("p", "disputed")]


def _many(fa, n):
    """An arm whose dimension-a part has n judged, non-disputed steps (and a measured dimension b)."""
    a = arm(fa, fa)
    a["dimensions"]["a"]["parts"]["a"]["steps"] = {str(i): {"score": 0.5, "disputed": False,
                                                           "lenses": {"x": 2, "y": 2, "z": 2}}
                                                   for i in range(1, n + 1)}
    return a


def _pool():
    return _scores({"p": _many(0.9, 10), "q": _many(0.1, 10)})        # 20 judged steps; none swings the order


def test_sampling_is_seeded_and_sized_by_the_pool():
    s = _pool()
    q1 = review.queue(s, "seed-1", 0.3)
    assert len(q1) == math.ceil(0.3 * 20) and {i["reason"] for i in q1} == {"sample"}
    assert q1 == review.queue(s, "seed-1", 0.3)
    assert q1 != review.queue(s, "seed-2", 0.3)


def test_the_sample_does_not_depend_on_dict_insertion_order():
    s = _pool()
    flipped = copy.deepcopy(s)
    flipped["arms"] = dict(reversed(list(flipped["arms"].items())))
    for a in flipped["arms"].values():
        part = a["dimensions"]["a"]["parts"]["a"]
        part["steps"] = dict(reversed(list(part["steps"].items())))
    assert review.queue(s, "seed-1", 0.3) == review.queue(flipped, "seed-1", 0.3)


def test_a_step_whose_highest_lens_would_swing_the_top_two_is_queued_though_its_lowest_would_not():
    s = _scores({"p": _judged_arm(0.5, 0.5, {"x": 1, "y": 2, "z": 3}), "q": arm(0.55, 0.5)})
    assert [(i["arm"], i["reason"]) for i in review.queue(s, "s", 0.0)] == [("p", "decides top two")]


def test_a_step_that_would_lift_an_arm_outside_the_top_two_past_the_second_is_queued():
    r = _judged_arm(0.5, 0.1, {"x": 2, "y": 3, "z": 4})
    s = _scores({"p": arm(0.9, 0.9), "q": arm(0.5, 0.5), "r": r})
    assert [(i["arm"], i["reason"]) for i in review.queue(s, "s", 0.0)] == [("r", "decides top two")]


def test_measured_steps_never_enter_the_queue_even_at_full_sampling():
    q = review.queue(_scores({"p": arm(0.9, 0.9, lenses={"x": 0, "y": 2, "z": 4}), "q": arm(0.1, 0.1)}), "s", 1.0)
    assert {(i["part"], i["arm"], i["step"]) for i in q} == {("a", "p", 1)}


def test_a_step_that_swings_the_top_two_is_queued_and_one_that_cannot_is_not():
    s = _scores({"p": _judged_arm(0.5, 0.5, {"x": 1, "y": 2, "z": 3}),
                 "q": arm(0.45, 0.5),
                 "r": _judged_arm(0.0, 0.0, {"x": 1, "y": 2, "z": 3})})
    q = review.queue(s, "s", 0.0)
    assert [(i["arm"], i["reason"]) for i in q] == [("p", "decides top two")]
    assert q[0]["lenses"] == {"x": 1, "y": 2, "z": 3}


def test_a_step_with_an_owner_verdict_is_not_queued_again():
    a = arm(0.9, 0.9, lenses={"x": 0, "y": 2, "z": 4})
    a["dimensions"]["a"]["parts"]["a"]["steps"]["1"]["owner"] = {"score": 2}
    assert review.queue(_scores({"p": a, "q": arm(0.1, 0.1)}), "s", 1.0) == []


def test_queue_does_not_mutate_its_input():
    s = _scores({"p": _judged_arm(0.5, 0.5, {"x": 1, "y": 2, "z": 3}), "q": arm(0.45, 0.5)})
    before = copy.deepcopy(s)
    review.queue(s, "s", 1.0)
    assert s == before


def test_arm_level_steps_keep_the_arm_key():
    a = arm(0.9, 0.9)
    a["dimensions"]["a"]["parts"]["a"]["steps"] = {"arm": {"score": 0.5, "disputed": True, "lenses": {"x": 0, "y": 4}}}
    q = review.queue(_scores({"p": a, "q": arm(0.1, 0.1)}), "s", 0.0)
    assert [i["step"] for i in q] == ["arm"]


# ---- the sheet and the import --------------------------------------------------------------------------------------

PART = "req_test_code"


def _write_judged(out, arm_, nn, lens_to_score, evidence="evidence"):
    d = out / "judged" / PART / arm_ / nn
    d.mkdir(parents=True, exist_ok=True)
    for lens, sc in lens_to_score.items():
        (d / f"{lens}.json").write_text(json.dumps({"score": sc, "status": "ok", "evidence": evidence,
                                                    "notes": f"notes on {arm_}", "raw": "RAW"}))


def _step(lenses, **kw):
    return {"score": sorted(lenses.values())[len(lenses) // 2] / 4, "disputed": max(lenses.values()) - min(lenses.values()) >= 2,
            "lenses": lenses, **kw}


def _arm(step):
    return {"dimensions": {"a": {"score": 0, "max": 50, "parts": {PART: {"score": 0, "steps": {"3": step}}}},
                           "b": {"score": 0, "max": 50, "parts": {"b": {"score": 0.5, "steps": {"1": {"score": 0.5}}}}}}}


@pytest.fixture
def rv(tmp_state):
    """Two arms, alpha's step 3 disputed; a scores.json, anon key and judged files on disk."""
    out, labels = anon_fixture()
    lz = {"auditor": 0, "maintainer": 2, "newcomer": 4}
    scores = _scores({"alpha": _arm(_step(lz)), "beta": _arm(_step({"auditor": 3, "maintainer": 3, "newcomer": 3}))})
    (out / "scores.json").write_text(json.dumps(scores))
    _write_judged(out, "alpha", "03", lz, evidence="the work was done; see speckit notes")
    _write_judged(out, "beta", "03", {"auditor": 3, "maintainer": 3, "newcomer": 3})
    return "p", out, labels


def _fill(pass_, score="2", reason="because"):
    f = paths.scoring_out(pass_) / "review" / "review-sheet.md"
    text = f.read_text().replace("score:\n", f"score: {score}\n").replace("reason:\n", f"reason: {reason}\n")
    f.write_text(text)
    return f


def test_the_sheet_shows_the_label_the_levels_and_the_lenses_but_no_arm_name(rv):
    pass_, out, labels = rv
    text = review.sheet(pass_).read_text()
    assert labels["alpha"] in text and "alpha" not in text.lower()
    assert "beta" not in text.lower()
    rub = inputs.load_rubrics()[PART]
    assert rub.levels[4] in text and rub.levels[0] in text
    assert all(l in text for l in ("auditor", "maintainer", "newcomer")) and "notes on" in text
    assert "RAW" not in text
    assert "score:\n" in text and "reason:\n" in text


def test_the_sheet_scrubs_method_names_out_of_judge_evidence(rv):
    pass_, *_ = rv
    assert "speckit" not in review.sheet(pass_).read_text()


def test_the_sheet_does_not_say_why_an_item_is_on_it(rv):
    pass_, *_ = rv
    text = review.sheet(pass_).read_text()
    assert "disputed" not in text and "decides top two" not in text


def test_import_writes_verdicts_under_the_real_arm_name_in_the_aggregate_format(rv):
    pass_, out, labels = rv
    review.sheet(pass_)
    _fill(pass_, "3", "the newcomer was right")
    f = review.import_sheet(pass_, today=date(2026, 10, 6))
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    assert f == out / "review" / "verdicts.jsonl"
    assert {(r["arm"], r["step"], r["score"]) for r in rows} >= {("alpha", 3, 3)}
    assert all(r["decided"] == "owner 2026-10-06" and r["reason"] == "the newcomer was right" and r["part"] == PART
               for r in rows)
    assert len(aggregate.read_verdicts(pass_)) == len(rows)           # aggregate itself accepts the file


def test_import_names_the_item_and_field_and_writes_nothing_on_a_bad_score(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _fill(pass_, "7")
    with pytest.raises(inputs.InputError, match=r"item 1.*score"):
        review.import_sheet(pass_)
    assert not (out / "review" / "verdicts.jsonl").exists()


def test_import_refuses_a_blank_reason(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _fill(pass_, "2", "")
    with pytest.raises(inputs.InputError, match=r"item 1.*reason"):
        review.import_sheet(pass_)
    assert not (out / "review" / "verdicts.jsonl").exists()


def test_import_refuses_a_blank_score_when_a_reason_is_given(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _fill(pass_, "", "a reason")
    with pytest.raises(inputs.InputError, match=r"item 1.*score"):
        review.import_sheet(pass_)
    assert not (out / "review" / "verdicts.jsonl").exists()


def test_import_refuses_a_duplicate_of_an_existing_verdict_and_leaves_the_file_alone(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    v = out / "review" / "verdicts.jsonl"
    old = json.dumps({"part": PART, "arm": "alpha", "step": 3, "score": 1, "reason": "earlier", "decided": "owner 2026-10-01"}) + "\n"
    v.write_text(old)
    _fill(pass_)
    with pytest.raises(inputs.InputError, match="already"):
        review.import_sheet(pass_)
    assert v.read_text() == old


def test_import_appends_to_existing_verdicts_for_other_steps(rv):
    pass_, out, _ = rv
    v = out / "review" / "verdicts.jsonl"
    v.parent.mkdir(parents=True, exist_ok=True)
    other = json.dumps({"part": PART, "arm": "beta", "step": 5, "score": 1, "reason": "earlier", "decided": "owner 2026-10-01"})
    v.write_text(other)                                          # no trailing newline
    review.sheet(pass_)
    _fill(pass_)
    review.import_sheet(pass_, today=date(2026, 10, 6))
    rows = [json.loads(l) for l in v.read_text().splitlines()]
    assert rows[0]["step"] == 5 and any(r["arm"] == "alpha" and r["step"] == 3 for r in rows[1:])


def test_import_without_a_sheet_says_to_run_the_sheet_stage(rv):
    with pytest.raises(inputs.InputError, match="review-sheet"):
        review.import_sheet("p")


def test_a_sheet_the_owner_has_started_is_not_overwritten(rv):
    pass_, *_ = rv
    review.sheet(pass_)
    _fill(pass_)
    with pytest.raises(inputs.InputError, match="already"):
        review.sheet(pass_)


def test_the_review_stages_are_registered():
    assert {"review-sheet", "review-import"} <= set(scli.STAGES)


# ---- partial import, idempotence, headings, parsing ----------------------------------------------------------------

def _edit(pass_, fn):
    f = paths.scoring_out(pass_) / "review" / "review-sheet.md"
    f.write_text(fn(f.read_text()))


def _answer(pass_, n, score, reason):
    """Fill item n only (its first blank `score:` / `reason:` pair)."""
    def go(t):
        head, _, rest = t.partition(f"## Item {n}:")
        body, sep, tail = rest.partition("## Item ")
        body = body.replace("score:\n", f"score: {score}\n", 1).replace("reason:\n", f"reason: {reason}\n", 1)
        return head + f"## Item {n}:" + body + sep + tail
    _edit(pass_, go)


def _rows(out):
    f = out / "review" / "verdicts.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def test_an_item_with_both_fields_blank_is_skipped_and_counted(rv, capsys):
    pass_, out, labels = rv
    review.sheet(pass_)
    _answer(pass_, 2, "3", "fine")
    review.import_sheet(pass_, today=date(2026, 10, 6))
    assert [(r["arm"], r["step"], r["score"]) for r in _rows(out)] == [("beta", 3, 3)]
    assert "1 of 2 imported, 1 left blank" in capsys.readouterr().out


def test_import_finish_later_import_again_adds_only_the_new_item(rv, capsys):
    pass_, out, _ = rv
    review.sheet(pass_)
    _answer(pass_, 2, "3", "fine")
    review.import_sheet(pass_, today=date(2026, 10, 6))
    _answer(pass_, 1, "1", "weak")
    review.import_sheet(pass_, today=date(2026, 10, 7))
    rows = _rows(out)
    assert [(r["arm"], r["score"], r["decided"]) for r in rows] == [("beta", 3, "owner 2026-10-06"),
                                                                    ("alpha", 1, "owner 2026-10-07")]
    assert "1 of 2 imported, 0 left blank" in capsys.readouterr().out.splitlines()[-1]


def test_re_importing_an_unchanged_sheet_writes_nothing_new(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _fill(pass_)
    review.import_sheet(pass_, today=date(2026, 10, 6))
    before = (out / "review" / "verdicts.jsonl").read_text()
    review.import_sheet(pass_, today=date(2026, 11, 1))
    assert (out / "review" / "verdicts.jsonl").read_text() == before


def test_changing_an_already_imported_answer_is_an_error_and_writes_nothing(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _answer(pass_, 2, "3", "fine")
    review.import_sheet(pass_)
    before = (out / "review" / "verdicts.jsonl").read_text()
    _edit(pass_, lambda t: t.replace("score: 3", "score: 4"))
    _answer(pass_, 1, "1", "weak")
    with pytest.raises(inputs.InputError, match=r"item 2.*already"):
        review.import_sheet(pass_)
    assert (out / "review" / "verdicts.jsonl").read_text() == before


def test_one_invalid_item_blocks_the_valid_ones(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _answer(pass_, 1, "2", "ok")
    _answer(pass_, 2, "9", "bad")
    with pytest.raises(inputs.InputError, match=r"item 2.*score"):
        review.import_sheet(pass_)
    assert not (out / "review" / "verdicts.jsonl").exists()


def test_a_reason_without_a_score_blocks_the_import(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _answer(pass_, 2, "", "just a reason")
    with pytest.raises(inputs.InputError, match=r"item 2.*score"):
        review.import_sheet(pass_)


def test_a_changed_item_heading_is_refused(rv):
    pass_, out, labels = rv
    review.sheet(pass_)
    _fill(pass_)
    _edit(pass_, lambda t: t.replace(f"## Item 1: {PART}, {labels['alpha']}", f"## Item 1: {PART}, {labels['beta']}"))
    with pytest.raises(inputs.InputError, match=r"item 1.*heading"):
        review.import_sheet(pass_)
    assert not (out / "review" / "verdicts.jsonl").exists()


def test_the_sheet_is_ordered_by_label_not_by_arm(rv):
    pass_, out, _ = rv
    (out / "anon-key.json").write_text(json.dumps({"Arm A": "beta", "Arm B": "alpha"}))
    text = review.sheet(pass_).read_text()
    assert text.index("Item 1: " + PART + ", Arm A") < text.index("Item 2: " + PART + ", Arm B")
    _answer(pass_, 1, "3", "x")
    review.import_sheet(pass_)
    assert [r["arm"] for r in _rows(out)] == ["beta"]               # item 1 is labelled Arm A, which is beta


def test_a_reason_may_run_over_following_lines_and_may_start_on_the_next_line(rv):
    pass_, out, _ = rv
    review.sheet(pass_)
    _edit(pass_, lambda t: t.replace("score:\nreason:\n", "score: 2\nreason: first line\nsecond line\n\nthird\n", 1)
          .replace("score:\nreason:\n", "score: 3\nreason:\n  starts below\n", 1))
    review.import_sheet(pass_)
    assert [r["reason"] for r in _rows(out)] == ["first line second line third", "starts below"]


def test_a_duplicated_item_heading_is_an_error_not_a_crash(rv):
    pass_, *_ = rv
    review.sheet(pass_)
    _fill(pass_)
    _edit(pass_, lambda t: t + "\n## Item 1: again\nscore: 1\nreason: a\nreason: b\n")
    with pytest.raises(inputs.InputError, match=r"item 1.*twice"):
        review.import_sheet(pass_)


def test_a_repeated_field_names_its_item(rv):
    pass_, *_ = rv
    review.sheet(pass_)
    _fill(pass_)
    _edit(pass_, lambda t: t.replace("score: 2\n", "score: 2\nscore: 3\n", 1))
    with pytest.raises(inputs.InputError, match=r"item 1.*two score"):
        review.import_sheet(pass_)


def test_a_failed_replace_leaves_the_existing_verdicts_untouched(rv, monkeypatch):
    pass_, out, _ = rv
    v = out / "review" / "verdicts.jsonl"
    v.parent.mkdir(parents=True, exist_ok=True)
    old = json.dumps({"part": PART, "arm": "beta", "step": 5, "score": 1, "reason": "r", "decided": "owner 2026-10-01"}) + "\n"
    v.write_text(old)
    review.sheet(pass_)
    _fill(pass_)

    def boom(*a):
        raise OSError("disk")
    monkeypatch.setattr(review.os, "replace", boom)
    with pytest.raises(OSError):
        review.import_sheet(pass_)
    assert v.read_text() == old


def test_forced_totals_are_renormalised_so_an_arm_with_an_unmeasured_dimension_can_decide_the_top_two():
    # R34: p measures only a (0.5 -> total 50); q 0.55 on both (55). Its highest lens (3 -> 0.75) lifts p to 75 over q;
    # under the old plain sum p would be 25 -> 37.5 and never reach q. r measures nothing (no total) and is ignored.
    from tests.runner.scoring.test_confidence import _unmeasured_b
    p = _unmeasured_b(0.5)
    p["dimensions"]["a"]["parts"]["a"]["steps"]["1"] = {"score": 0.5, "disputed": False,
                                                        "lenses": {"x": 1, "y": 2, "z": 3}}
    r = _unmeasured_b(0.0)
    r["dimensions"]["a"]["score"] = None
    r["dimensions"]["a"]["parts"]["a"] = {"score": None, "steps": {"1": {"score": None}}}
    s = _scores({"p": p, "q": arm(0.55, 0.55), "r": r})
    assert review._forced(s, "p", "a", "1", 0.75)["p"] == pytest.approx(75)
    assert [(i["arm"], i["reason"]) for i in review.queue(s, "s", 0.0)] == [("p", "decides top two")]



def test_the_review_import_refuses_when_the_key_changed_since_the_sheet(rv):
    pass_, out, labels = rv
    review.sheet(pass_)
    _fill(pass_)
    k = json.loads((out / "anon-key.json").read_text())
    (out / "anon-key.json").write_text(json.dumps({**k, "salt": "another salt"}))
    with pytest.raises(inputs.InputError, match="different anonymisation key"):
        review.import_sheet(pass_)
    assert not (out / "review" / "verdicts.jsonl").exists()
