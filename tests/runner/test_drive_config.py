# Review Focus 2 and F-5: arm differences are data, cited, uniform in rule
import pytest
from runner import config

@pytest.mark.parametrize("name", config.all_arms())
def test_must_run_is_cited_or_empty_with_a_reason(name):
    a = config.load_arm(name)
    assert a.must_run_source, "every arm states its closing-command source, even when it has none"
    assert all(c.startswith("/") for c in a.must_run)

@pytest.mark.parametrize("name", config.all_arms())
def test_fresh_session_entries_are_cited(name):                                   # OD19
    assert all(x["command"].startswith("/") and x["source"] for x in config.load_arm(name).fresh_session_before)

def test_speckit_is_the_one_arm_with_an_export_step_after_tasks():                # OD24 B (preflight m8: ==, not <=)
    assert {n for n in config.all_arms() if config.load_arm(n).export_after} == {"speckit"}
    assert config.load_arm("speckit").export_after == "/speckit-tasks"
