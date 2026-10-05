import json
from runner import paths
from runner.scoring import aggregate, report, values
from tests.runner.scoring.test_aggregate import p, write_collected, write_judged  # noqa: F401  (fixture re-export)


def _section(md: str, head: str) -> str:
    lines = md.splitlines()
    i = lines.index(head)
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    return "\n".join(lines[i:j])


def test_outliers_are_relative_to_the_median():
    assert report.outliers({"a": 1.0, "b": 1.1, "c": 9.0, "d": 0.2, "e": None}, 3.0) == {"c": "high", "d": "low"}


def test_report_opens_with_the_bottom_line_then_the_scorecard(p):
    aggregate.run(p)
    md = report.render(p)
    heads = [l for l in md.splitlines() if l.startswith("## ")]
    assert heads[:2] == ["## Bottom line", "## Scorecard"] and "## Confidence" in heads
    assert "## Appendix: alpha" in heads and "## Appendix: control" in heads


def test_every_scorecard_total_matches_scores_json(p):
    s = json.loads(aggregate.run(p).read_text())
    md = report.render(p)
    for arm, v in s["arms"].items():
        assert f"{v['total']:.1f}" in md


def test_report_discloses_partial_blinding_and_pre_registration(p):
    aggregate.run(p)
    md = report.render(p).lower()
    assert "blinding is partial" in md and "not fully pre-registered" in md


def test_arms_with_no_order_flip_are_ranked_one_per_line(p):
    aggregate.run(p)                                  # identical arms: every variant ties, so no flips
    md = report.render(p)
    s = json.loads((paths.scoring_out(p) / "scores.json").read_text())
    lines = _section(md, "## Bottom line").splitlines()
    assert f"- 1: alpha {s['arms']['alpha']['total']:.1f}" in lines     # no flip: ranked singly, not "within noise"
    assert f"- 2: control {s['arms']['control']['total']:.1f}" in lines


def test_an_order_flip_shows_up_as_a_within_noise_line(p, monkeypatch):
    aggregate.run(p)
    monkeypatch.setattr(report.confidence, "check", lambda s: {
        "ranking": ["alpha", "control"], "intervals": {"alpha": [1, 2], "control": [1, 2]},
        "groups": [["alpha", "control"]], "order_changes": [{"variant": "coping +5, judges low",
                                                              "order": ["control", "alpha"]}]})
    md = report.render(p)
    assert "1–2 (within noise): alpha " in _section(md, "## Bottom line")
    assert "coping +5, judges low" in _section(md, "## Confidence")


def test_flags_are_all_shown_including_draft_exclusions_and_step_sets(p):
    write_collected(p, "control", 2)
    aggregate.run(p)
    flags = json.loads((paths.scoring_out(p) / "scores.json").read_text())["flags"]
    assert any("steps collected" in f for f in flags)
    md = _section(report.render(p), "## Confidence")
    for f in flags:
        assert f in md


def test_owner_notes_are_included_verbatim_under_the_bottom_line(p):
    aggregate.run(p)
    (paths.scoring_out(p) / "report-notes.md").write_text("OWNER SAYS: read step 6 first.\n")
    assert "OWNER SAYS: read step 6 first." in _section(report.render(p), "## Bottom line")


def test_unmeasured_cells_carry_a_dagger_and_outliers_an_arrow(p):
    write_collected(p, "alpha", 1, quality={"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None,
                                            "mutation_state": "crashed"})
    aggregate.run(p)
    card = _section(report.render(p), "## Scorecard")
    row = next(l for l in card.splitlines() if l.startswith("| alpha"))
    assert "†" in row and "▲" not in row and "▼" not in row


def _patch_phases(pass_, arm, step, **phases):
    """write_collected wraps a phases dict as one leaf; real records hold {method, common} leaves, so patch them in."""
    f = paths.scoring_out(pass_) / "collected" / arm / f"{step:02d}.json"
    rec = json.loads(f.read_text())
    rec["phases"] = phases
    f.write_text(values.dump(rec))


def _turns(*ts):
    return {"seconds": sum(t["seconds"] for t in ts), "attempt": 1, "turns": list(ts)}


def test_time_and_cost_marks_killed_background_and_duration_ms_turns_and_flags_outliers(p):
    for arm, secs in (("beta", 100.0), ("gamma", 110.0), ("delta", 9000.0)):
        write_collected(p, arm, 1, time=_turns({"stem": "t1", "seconds": secs, "usd": 1.0}),
                        cost={"scored_usd": 1.0, "po_usd": 0.1, "discovery_usd": 0.0})
    write_collected(p, "alpha", 1, time=_turns({"stem": "t1", "seconds": 50.0, "usd": 1.0, "killed": True},
                                               {"stem": "t2", "seconds": 50.0, "usd": 1.0, "background_wait": True},
                                               {"stem": "t3", "seconds": 50.0, "usd": 1.0,
                                                "time_source": "duration_ms"}),
                    cost={"scored_usd": 3.0, "po_usd": 0.1, "discovery_usd": 0.0})
    aggregate.run(p)
    sec = _section(report.render(p), "## Time and cost")
    step1 = sec.split("### All steps")[0]
    alpha = next(l for l in step1.splitlines() if l.startswith("| alpha"))
    assert "‡" in alpha and "§" in alpha and "~" in alpha
    delta = next(l for l in step1.splitlines() if l.startswith("| delta"))
    assert "▲" in delta


def test_report_renders_when_cost_and_phases_are_missing(p):
    write_collected(p, "alpha", 1, cost=values.missing("results/p/alpha/01/cost.json", "unreadable"))
    _patch_phases(p, "alpha", 1, method=values.missing("results/p/alpha/01/turns", "no turns"),
                  common=values.missing("results/p/alpha/01/transcripts", "no transcripts"))
    aggregate.run(p)
    md = report.render(p)
    sec = _section(md, "## Time and cost")
    alpha = next(l for l in sec.splitlines() if l.startswith("| alpha"))
    assert "—" in alpha and "$0.00" not in alpha
    assert "unreadable" in _section(md, "## Appendix: alpha")


def test_phase_split_shows_both_views(p):
    write_collected(p, "alpha", 1)
    _patch_phases(p, "alpha", 1,
                  method=values.val([{"stem": "t", "label": "openspec:apply", "seconds": 60.0, "usd": 0.5}], "x"),
                  common=values.val({"seconds": {"implement": 90.0, "test": 30.0},
                                     "usd": {"implement": 0.4, "test": 0.1}}, "x"))
    aggregate.run(p)
    sec = _section(report.render(p), "## Time and cost")
    assert "openspec:apply" in sec and "implement" in sec


def test_appendix_links_each_number_to_its_source_and_lists_lens_evidence(p):
    write_collected(p, "alpha", 3)
    write_judged(p, "req_test_code", "alpha", "03", [1, 3, 4])
    aggregate.run(p)
    app = _section(report.render(p), "## Appendix: alpha")
    assert "([src](../../../x))" in app
    assert "req_test_code" in app and "auditor" in app and "judged/req_test_code/alpha/03/auditor.json" in app


def test_decision_review_lists_one_offs_divergent_and_unanimous(p):
    aggregate.run(p)
    d = paths.scoring_out(p) / "decisions"
    d.mkdir()
    (d / "ratings.json").write_text(json.dumps({"topics": [
        {"id": "t1", "question": "Q1?", "routes": [{"route": "A", "arms": ["alpha"], "rating": "good"},
                                                   {"route": "not considered", "arms": ["control"], "rating": "poor"}]},
        {"id": "t2", "question": "Q2?", "routes": [{"route": "A", "arms": ["alpha"], "rating": "good"},
                                                   {"route": "B", "arms": ["control"], "rating": "poor"}]},
        {"id": "t3", "question": "Q3?", "routes": [{"route": "A", "arms": ["alpha", "control"], "rating": "good"}]}]}))
    sec = _section(report.render(p), "## Decision review")
    assert "### One-offs (1)\n\n- Q1?" in sec and "### Divergent (1)\n\n- Q2?" in sec \
        and "### Unanimous (1)\n\n- Q3?" in sec


def test_a_rerun_of_report_is_byte_identical(p):
    aggregate.run(p)
    assert report.run(p).read_bytes() == report.run(p).read_bytes()
