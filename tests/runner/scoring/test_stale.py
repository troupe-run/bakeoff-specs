import pytest
from runner.scoring import inputs

CHANGE_STEPS = (2, 3, 4, 5, 6, 7)


@pytest.mark.parametrize("step", CHANGE_STEPS)
def test_every_change_step_has_a_valid_list(step):
    s = inputs.load_stale(step)
    assert s.step == step and s.legitimate
    for item in s.stale:
        assert item["kind"] in {"requirement", "test", "doc", "code"} and item["what"] and item["why"]
    assert len({i["id"] for i in s.stale}) == len(s.stale)


def test_step_1_has_no_list():
    assert inputs.load_stale(1) is None


def test_contradicting_steps_name_stale_items():
    # steps 3, 5 and 7 contradict earlier behaviour (design §4), so something must go stale
    assert all(inputs.load_stale(n).stale for n in (3, 5, 7))


def test_legitimate_matches_globs():
    s = inputs.StaleList(step=9, stale=[], legitimate=["src/**", "README.md"])
    assert inputs.legitimate("src/troupe/x.py", s) and inputs.legitimate("README.md", s)
    assert not inputs.legitimate("docs/other.md", s)
