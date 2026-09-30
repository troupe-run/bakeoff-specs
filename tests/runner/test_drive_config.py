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

def test_no_shipped_arm_forces_an_export_step():                                  # OD24 A (owner, 2026-09-30, after probe P11)
    assert {n for n in config.all_arms() if config.load_arm(n).export_after} == set()
