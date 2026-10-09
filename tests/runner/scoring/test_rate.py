"""Rating the decision sheet in chat: show a topic, write ratings back (owner, 2026-10-09)."""
import pytest
from runner.scoring import decisions as dz, rate
from tests.runner.scoring.test_decisions import TOPICS

MD = dz.render_sheet(TOPICS, arms=[])


def test_show_prints_one_whole_topic_and_nothing_of_the_next():
    t2 = rate.show(MD, "T2")
    assert t2.startswith("## T2") and "### Route 1" in t2 and "### Route 2" in t2 and "## T3" not in t2
    assert "# Unanimous" not in t2                                   # the group heading after it is not the topic's


def test_set_writes_every_route_in_order_and_the_import_reads_it():
    out = rate.set_ratings(MD, "T2", ["4", "N/A"], {2: "does   not\nmatter"})
    assert rate.rated(out, "T2") == {1: "4", 2: "n/a"}
    got = dz.parse_sheet(out.replace("rating:\nreason:", "rating: 3\nreason:"))["T2"]
    assert got == [{"route_no": 1, "rating": "4", "reason": ""}, {"route_no": 2, "rating": "n/a", "reason": "does not matter"}]
    assert rate.rated(out, "T1") == {1: "", 2: ""}                   # other topics untouched


@pytest.mark.parametrize("ratings,reasons,msg", [
    (["4"], {}, "2 route"), (["4", "6"], {}, "not on the scale"), (["4", "2"], {3: "x"}, "no route"),
])
def test_set_refuses_a_wrong_count_an_off_scale_rating_or_an_unknown_route(ratings, reasons, msg):
    with pytest.raises(ValueError, match=msg):
        rate.set_ratings(MD, "T2", ratings, reasons)


def test_progress_names_the_next_unrated_topic():
    assert rate.progress(MD) == {"rated": 0, "unrated": 3, "next": "T1"}
    out = rate.set_ratings(MD, "T1", ["5", "1"])
    assert rate.progress(out) == {"rated": 1, "unrated": 2, "next": "T2"}


def test_a_fenced_file_in_a_context_is_never_mistaken_for_a_route():
    md = MD.replace("**Kind:** divergent\n", "**Kind:** divergent\n\n~~~\n### Route 9\nrating: 1\n## T7\n~~~\n", 1)
    assert set(rate.rated(md, "T2")) == {1, 2}
    assert rate.rated(rate.set_ratings(md, "T2", ["2", "3"]), "T2") == {1: "2", 2: "3"}
