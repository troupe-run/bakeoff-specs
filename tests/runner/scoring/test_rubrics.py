from runner.scoring import inputs

JUDGED = {"stale_updated", "hand_edit", "req_test_code", "change_reason", "step6_spec_trace", "question_value",
          "research_first", "gates", "test_names", "process", "setup_effort", "fit"}


def test_every_judged_part_has_a_rubric_whose_dimension_has_that_part():
    rs = inputs.load_rubrics()
    w = inputs.load_weights()
    assert set(rs) == JUDGED
    for name, r in rs.items():
        assert name in w.parts[r.dimension], name


def test_each_rubric_has_three_distinct_lenses_and_five_anchored_levels():
    for r in inputs.load_rubrics().values():
        assert len(r.lenses) == 3 and len({l["name"] for l in r.lenses}) == 3
        assert sorted(r.levels) == [0, 1, 2, 3, 4] and all(len(t) > 20 for t in r.levels.values())
        assert set(r.evidence) <= inputs.EVIDENCE_KINDS and r.evidence


def test_step_scoped_parts_name_the_steps_they_apply_to():
    rs = inputs.load_rubrics()
    assert rs["hand_edit"].steps == (2,) and rs["stale_updated"].steps == (3, 5, 7)
    assert rs["step6_spec_trace"].steps == (6,)
    assert rs["setup_effort"].unit == "arm" and rs["fit"].unit == "arm"


def test_question_value_answers_no_question_as_not_applicable_and_fit_reads_transcripts():
    rs = inputs.load_rubrics()
    qv = rs["question_value"]
    assert qv.not_applicable and qv.unit == "step"
    assert not any("asked nothing" in qv.levels[n] and "no genuine ambiguity" in qv.levels[n] for n in range(5))
    assert "two or more" in " ".join(qv.levels.values()) and "wasteful" in qv.levels[2]
    assert rs["fit"].unit == "arm" and "transcript" in rs["fit"].evidence and "setup" in rs["fit"].evidence
    assert "transcript" not in rs["setup_effort"].evidence
