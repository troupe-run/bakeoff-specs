import pytest
from runner import config, owner
from runner.po import Decision


def D(): return Decision("approval", "Approved: consistent with the contract.", [], True, None, "", False)


def term(lines):
    it, shown = iter(lines), []
    ticks = iter(range(0, 1000, 5))
    return owner.Owner(input_fn=lambda prompt="": next(it), out=shown.append, clock=lambda: next(ticks)), shown


def test_enter_accepts_the_po_verdict_and_is_timed():
    o, shown = term([""])
    reply, action, secs = o.gate("Please approve the plan.", D(), " src/a.py | 3 +++")
    assert (reply, action, secs) == ("Approved: consistent with the contract.", "accept", 5)
    assert any("Approved: consistent" in s for s in shown) and any("src/a.py" in s for s in shown)


def test_e_lets_the_owner_type_an_override_ending_with_a_dot_line():
    o, _ = term(["e", "Not approved: step 3 changes show.", "Please revise.", "."])
    reply, action, _ = o.gate("Please approve.", D(), "")
    assert action == "override" and reply == "Not approved: step 3 changes show.\nPlease revise."


def test_d_shows_the_changes_again_then_falls_through_to_enter():
    o, shown = term(["d", ""])
    reply, action, _ = o.gate("Please approve.", D(), "src/b.py | 1 +")
    assert action == "accept"
    # repo_changes is shown once up front, and again on 'd'
    assert sum("src/b.py" in s for s in shown) == 2


def test_escalation_answer_is_multi_line():
    o, _ = term(["Print floats", "exactly as written.", "."])
    assert o.escalation("Floats?", "ctx")[0] == "Print floats\nexactly as written."


def test_escalation_is_timed():
    o, _ = term(["."])
    _, secs = o.escalation("Floats?", "ctx")
    assert secs == 5


def test_items_record_yes_no_and_a_note():
    o, _ = term(["y", "", "n", "constitution has extras"])
    got = o.items([("OV1", "a"), ("OV2", "b")])
    assert got["OV1"][:2] == (True, "") and got["OV2"][:2] == (False, "constitution has extras")


def test_confirm_defaults_to_no():
    o, _ = term([""])
    assert o.confirm("Push?") is False


def test_confirm_yes():
    o, _ = term(["y"])
    assert o.confirm("Push?") is True


def test_setup_reply_enter_moves_on_with_no_reply():
    o, _ = term([""])
    reply, secs = o.setup_reply("setup says hello")
    assert reply == "" and secs == 5


def test_setup_reply_r_lets_the_owner_type_a_reply():
    o, _ = term(["r", "please retry", "."])
    reply, _ = o.setup_reply("setup says hello")
    assert reply == "please retry"


def test_step_review_enter_continues_p_pauses():
    o, _ = term([""])
    assert o.step_review("# Step 1 summary")[0] == "continue"
    o2, _ = term(["p"])
    assert o2.step_review("# Step 2 summary")[0] == "pause"


def test_reclassify_defaults_to_arm_outcome():
    o, _ = term(["a"])
    assert o.reclassify("turn-seconds breach", "detail") == "arm"


def test_reclassify_h_counts_as_harness_fault():
    o, _ = term(["h"])
    assert o.reclassify("turn-seconds breach", "detail") == "harness"


def test_substitute_bug_enter_keeps_the_planted_bug_and_is_timed():
    o, shown = term([""])
    arm = config.load_arm("control")
    choice, title, body, why, secs = o.substitute_bug(arm, "all discriminating step-6 tests already pass")
    assert (choice, title, body, why, secs) == ("planted", "", "", "", 5)
    assert any("already pass" in s for s in shown)


def test_substitute_bug_s_lets_the_owner_type_a_replacement():
    o, _ = term(["s", "Alias handling bug", "Body line 1", ".", "Because plan A no longer discriminates", "."])
    arm = config.load_arm("control")
    choice, title, body, why, _ = o.substitute_bug(arm, "precheck passed")
    assert choice == "substitute"
    assert title == "Alias handling bug"
    assert body == "Body line 1"
    assert why == "Because plan A no longer discriminates"


def test_scripted_owner_is_refused_for_real_arms(tmp_path):
    (tmp_path / "s.toml").write_text("[escalations]\ndefault = 'x'\n")
    with pytest.raises(PermissionError):
        owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("control"))


def test_scripted_owner_answers_accepts_and_pauses_where_scripted(tmp_path):
    (tmp_path / "s.toml").write_text("[escalations]\ndefault = 'Keep it simple.'\n[gates]\ndefault = 'accept'\n"
                                     "[review]\ndefault = 'continue'\npause_after = [2]\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    assert o.escalation("q?", "")[0] == "Keep it simple." == o.escalation_answer
    assert o.gate("please approve", D(), "")[:2] == ("Approved: consistent with the contract.", "accept")
    assert o.step_review("# Step 1 summary")[0] == "continue"
    assert o.step_review("# Step 2 summary")[0] == "pause"
    assert o.step_review("# Step 2 summary")[0] == "continue"          # a pause fires once


def test_scripted_owner_gate_can_override(tmp_path):
    (tmp_path / "s.toml").write_text("[gates]\ndefault = 'override:Not approved: needs more work.'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    assert o.gate("please approve", D(), "")[:2] == ("Not approved: needs more work.", "override")


def test_scripted_owner_substitute_bug_keeps_the_planted_bug_by_default(tmp_path):
    (tmp_path / "s.toml").write_text("[substitute]\ndefault = 'planted'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    choice, title, body, why, secs = o.substitute_bug(config.load_arm("dryrun"), "precheck passed")
    assert (choice, title, body, why, secs) == ("planted", "", "", "", 0.0)


def test_scripted_owner_substitute_bug_can_be_scripted_to_substitute(tmp_path):
    (tmp_path / "s.toml").write_text(
        "[substitute]\ndefault = 'substitute'\ntitle = 'Alias handling bug'\nbody = 'Body'\nwhy = 'Because'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    choice, title, body, why, secs = o.substitute_bug(config.load_arm("dryrun"), "precheck passed")
    assert (choice, title, body, why, secs) == ("substitute", "Alias handling bug", "Body", "Because", 0.0)
