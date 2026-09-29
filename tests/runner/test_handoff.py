from pathlib import Path
import pytest
from runner import config, handoff

ROOT = Path(__file__).resolve().parents[2] / "scenario"
C = (ROOT / "contract.md").read_text()
BRIEFS = sorted((ROOT / "steps").glob("0*.md"))
DELIVERY = handoff.MESSAGES["delivery"]

@pytest.mark.parametrize("brief", BRIEFS, ids=lambda p: p.name)
def test_every_named_section_resolves_to_exactly_one_contract_heading(brief):
    kind, names = handoff.named(brief.read_text())
    assert names and all(handoff.norm(n) in handoff.contract_sections(C) for n in names)

def test_step1_hands_over_the_five_sections_in_force_in_order():
    msg = handoff.compose(1, BRIEFS[0].read_text(), C)
    assert [l for l in msg.splitlines() if l.startswith("## ")] == [
        "## General (from step 1)", "## Includes (from step 1)", "## `show PATH` (step 1 and 2)",
        "## `set PATH VALUE` (from step 1)", "## `history [PATH]` (from step 1)"]

@pytest.mark.parametrize("step", [1, 2, 3, 4, 7])
def test_every_handoff_ends_with_the_one_identical_delivery_sentence(step):          # review F-1
    msg = handoff.compose(step, BRIEFS[step - 1].read_text(), C)
    assert msg.rstrip().endswith(DELIVERY) and msg.count(DELIVERY) == 1

def test_step3_hands_over_get_and_show_only():
    msg = handoff.compose(3, BRIEFS[2].read_text(), C)
    assert [l for l in msg.splitlines() if l.startswith("## ")][0].startswith("## `get` and `show`")
    assert msg.startswith(BRIEFS[2].read_text().rstrip("\n"))

def test_step2_handoff_is_exactly_brief_sync_section_and_delivery_with_no_harness_text():
    # Controller ruling: the step-2 handoff must not mention the harness's hand edit. Equality with the three
    # verbatim parts proves the harness adds nothing of its own (the contract's own generic "hand edit" rule
    # about users' edits is contract text, handed over verbatim like every other section).
    brief = BRIEFS[1].read_text()
    sync = handoff.contract_sections(C)["Sync with files"]
    assert handoff.compose(2, brief, C) == f"{brief.rstrip()}\n\n---\n\n{sync}\n\n---\n\n{DELIVERY}\n"
    assert "hand edit" not in brief.lower() and "hand-edit" not in brief.lower()

def test_step5_two_requests_split_cr_a_from_cr_b(monkeypatch):                      # OD6 B
    monkeypatch.setitem(handoff.STEP5, "delivery", "two-requests")
    a, b = handoff.step5(BRIEFS[4].read_text(), C)
    assert "## CR-A" in a and "## CR-B" not in a and "two change requests" not in a and "## Overrides" in a
    assert b.startswith(handoff.STEP5["cr_b_intro"]) and "## CR-B" in b and "## CR-A" not in b
    assert a.rstrip().endswith(DELIVERY) and b.rstrip().endswith(DELIVERY)

def test_step5_one_message_keeps_both_change_requests(monkeypatch):                 # OD6 A
    monkeypatch.setitem(handoff.STEP5, "delivery", "one-message")
    [m] = handoff.step5(BRIEFS[4].read_text(), C)
    assert "## CR-A" in m and "## CR-B" in m
    assert "## Overrides (from step 5" in m and "## In-include (from step 5, change request B)" in m
    assert m.count(DELIVERY) == 1

def test_cr_a_never_pre_announces_cr_b_s_answer_and_cr_b_carries_it(monkeypatch):   # coordinator ruling 1
    monkeypatch.setitem(handoff.STEP5, "delivery", "two-requests")
    a, b = handoff.step5(BRIEFS[4].read_text(), C)
    assert "--in-include" not in a and "## In-include" not in a and "In-include" not in a
    assert "## In-include (from step 5, change request B)" in b and "--in-include" in b
    assert "## Overrides" not in b and b.count(DELIVERY) == 1

def test_step5_brief_names_overrides_under_cr_a_and_in_include_under_cr_b():
    parts = BRIEFS[4].read_text().split("## CR-B")
    assert handoff.named(parts[0]) == ("added", ['Overrides (replaces rule 2 under "set PATH VALUE")'])
    assert handoff.named(parts[1]) == ("added", ["In-include"])

def test_in_include_rule_lives_only_in_its_own_section_right_after_overrides():
    secs = handoff.contract_sections(C)
    assert "--in-include" not in secs["Overrides"] and "--in-include" in secs["In-include"]
    names = list(secs)
    assert names.index("In-include") == names.index("Overrides") + 1

@pytest.mark.parametrize("name", config.all_arms())
def test_step5_messages_are_identical_for_every_arm_inside_the_entry_wrapper(name):
    arm = config.load_arm(name)
    pre, post = arm.entry.split("{handoff}")
    for m in handoff.step5(BRIEFS[4].read_text(), C):
        assert handoff.entry_message(arm, 5, m) == pre + m + post

def test_step5_default_is_two_requests_with_cr_b_after_the_second_turn():          # OD6 B approved
    assert handoff.STEP5["delivery"] == "two-requests" and handoff.STEP5["cr_b_after_turn"] == 2
    assert len(handoff.step5(BRIEFS[4].read_text(), C)) == 2

def test_issue_body_drops_the_contract_line_and_the_message_carries_the_section():
    body = handoff.issue_body(BRIEFS[5].read_text())
    assert "Contract sections" not in body and body.startswith("Our troupe.yml")
    msg = handoff.bug_message("troupe-run/bakeoff-specs-control#1", C)
    assert "troupe-run/bakeoff-specs-control#1" in msg and "## Aliases (from step 6)" in msg and msg.rstrip().endswith(DELIVERY)

def test_entry_template_is_filled_literally_even_with_braces():
    assert handoff.entry_message(config.load_arm("openspec"), 1, "x {y} z") == "/opsx:propose x {y} z"

@pytest.mark.parametrize("name", config.all_arms())
def test_every_arm_receives_the_handoff_byte_identical_inside_its_entry_wrapper(name):
    # The handoff text itself never depends on the arm; only the method's entry wrapper (entry/bug_entry) differs.
    arm, h = config.load_arm(name), handoff.compose(4, BRIEFS[3].read_text(), C)
    for step, tpl in ((4, arm.entry), (6, arm.bug_entry)):
        pre, post = tpl.split("{handoff}")
        msg = handoff.entry_message(arm, step, h)
        assert msg == pre + h + post and msg.count(DELIVERY) == 1

def test_in_force_at_step3_excludes_the_replaced_show_section():
    text = handoff.in_force(3, C)
    assert "## `get` and `show`" in text and "## `show PATH` (step 1 and 2)" not in text

def test_po_view_at_step5_excludes_in_include_until_cr_b_is_delivered():            # coordinator ruling (PO leak)
    before = handoff.in_force(5, C)
    assert "## Overrides (from step 5" in before and "## In-include" not in before and "--in-include" not in before

def test_po_view_at_step5_includes_in_include_once_cr_b_is_delivered():
    after = handoff.in_force(5, C, after_crb=True)
    assert "## Overrides (from step 5" in after and "## In-include (from step 5, change request B)" in after

@pytest.mark.parametrize("step", [6, 7])
def test_po_view_after_step5_always_includes_in_include(step):
    assert "## In-include" in handoff.in_force(step, C)

def test_po_view_before_step5_never_includes_in_include_even_with_the_flag():
    assert "## In-include" not in handoff.in_force(4, C, after_crb=True)
