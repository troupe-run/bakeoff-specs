import pytest
from runner import config, owner
from runner.po import Decision


def D(): return Decision("approval", "Approved: consistent with the contract.", [], True, None, "", False)


def term(lines, **kw):
    it, shown = iter(lines), []
    ticks = iter(range(0, 1000, 5))
    return owner.Owner(input_fn=lambda prompt="": next(it), out=shown.append, clock=lambda: next(ticks), **kw), shown


def raise_eof(prompt=""):
    raise EOFError()


class FakeClock:
    """A settable clock: `input_fn` can advance `.t` to simulate time passing while the owner was typing."""
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


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
    choice, title, body, why, test_body, secs = o.substitute_bug(arm, "all discriminating step-6 tests already pass")
    assert (choice, title, body, why, test_body, secs) == ("planted", "", "", "", "", 5)
    assert any("already pass" in s for s in shown)


def test_substitute_bug_s_lets_the_owner_type_a_replacement_with_its_acceptance_test():
    o, _ = term(["s", "Alias handling bug", "Body line 1", ".",
                 "Because plan A no longer discriminates", ".",
                 "def test_alias_is_rejected():", "    assert False", "."])
    arm = config.load_arm("control")
    choice, title, body, why, test_body, _ = o.substitute_bug(arm, "precheck passed")
    assert choice == "substitute"
    assert title == "Alias handling bug"
    assert body == "Body line 1"
    assert why == "Because plan A no longer discriminates"
    assert test_body == "def test_alias_is_rejected():\n    assert False"


# --- Park: unattended, EOF, timeout, and owner-choice ("p" / "k" where "p" is already taken) -----------------

def test_gate_parks_immediately_when_unattended_without_reading_anything():
    reads = []
    o = owner.Owner(input_fn=lambda prompt="": reads.append(prompt) or "NEVER",
                     out=lambda s: None, clock=lambda: 0.0, now_fn=lambda: 111.0, unattended=True)
    result = o.gate("msg", D(), "")
    assert isinstance(result, owner.Park)
    assert result.prompt == "gate" and result.reason == "unattended" and result.at == 111.0
    assert reads == []
    assert o.parks == [result]


def test_confirm_parks_when_unattended():
    o = owner.Owner(input_fn=lambda prompt="": "NEVER", out=lambda s: None,
                     clock=lambda: 0.0, now_fn=lambda: 5.0, unattended=True)
    result = o.confirm("Push?")
    assert isinstance(result, owner.Park) and result.prompt == "confirm" and result.reason == "unattended"


def test_gate_parks_on_eof_without_raising():
    o = owner.Owner(input_fn=raise_eof, out=lambda s: None, clock=lambda: 0.0, now_fn=lambda: 222.0)
    result = o.gate("msg", D(), "")
    assert isinstance(result, owner.Park)
    assert result.prompt == "gate" and result.reason == "eof" and result.at == 222.0


def test_escalation_parks_on_eof_without_raising():
    o = owner.Owner(input_fn=raise_eof, out=lambda s: None, clock=lambda: 0.0, now_fn=lambda: 1.0)
    result = o.escalation("Floats?", "ctx")
    assert isinstance(result, owner.Park) and result.reason == "eof"


def test_gate_parks_when_the_owner_takes_longer_than_the_timeout():
    clock = FakeClock(0.0)

    def slow_input(prompt=""):
        clock.t = 20.0          # simulate 20s passing while the owner was answering
        return ""

    o = owner.Owner(input_fn=slow_input, out=lambda s: None, clock=clock, now_fn=lambda: 9.0, timeout=10)
    result = o.gate("msg", D(), "")
    assert isinstance(result, owner.Park) and result.reason == "timeout"


def test_gate_p_then_confirming_yes_parks_by_choice():
    o, _ = term(["p", "y"])
    result = o.gate("msg", D(), "")
    assert isinstance(result, owner.Park) and result.reason == "owner-choice" and result.prompt == "gate"


def test_gate_p_then_confirming_no_falls_back_to_the_normal_prompt():
    o, _ = term(["p", "n", ""])
    reply, action, _ = o.gate("msg", D(), "")
    assert action == "accept" and reply == "Approved: consistent with the contract."


def test_step_review_p_still_means_pause_not_park_and_k_parks():
    o, _ = term(["p"])
    assert o.step_review("# Step 2 summary") == ("pause", 5)
    o2, _ = term(["k", "y"])
    result = o2.step_review("# Step 2 summary")
    assert isinstance(result, owner.Park) and result.reason == "owner-choice"


def test_park_is_recorded_with_timestamp_reason_and_prompt():
    o = owner.Owner(input_fn=raise_eof, out=lambda s: None, clock=lambda: 3.0, now_fn=lambda: 42.0)
    result = o.reclassify("turn-seconds breach", "detail")
    assert result == owner.Park(prompt="reclassify", reason="eof", at=42.0, seconds=0.0)
    assert o.parks[-1] is result


# --- ScriptedOwner ----------------------------------------------------------------------------------------

def test_scripted_owner_is_refused_for_real_arms(tmp_path):
    (tmp_path / "s.toml").write_text("[escalations]\ndefault = 'x'\n")
    with pytest.raises(PermissionError):
        owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("control"))


def test_scripted_owner_refuses_every_method_when_not_bound(tmp_path):
    (tmp_path / "s.toml").write_text("[escalations]\ndefault = 'x'\n[gates]\ndefault = 'accept'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml")  # never bound
    with pytest.raises(PermissionError):
        o.escalation("q?", "")
    with pytest.raises(PermissionError):
        o.gate("msg", D(), "")
    with pytest.raises(PermissionError):
        o.confirm("Push?")
    with pytest.raises(PermissionError):
        o.items([("OV1", "a")])
    with pytest.raises(PermissionError):
        o.setup_reply("hi")
    with pytest.raises(PermissionError):
        o.step_review("# Step 1")
    with pytest.raises(PermissionError):
        o.reclassify("what", "detail")
    with pytest.raises(PermissionError):
        o.substitute_bug(config.load_arm("dryrun"), "precheck")
    with pytest.raises(PermissionError):
        _ = o.escalation_answer


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


def test_scripted_owner_gate_override_with_no_reply_raises_a_clear_error(tmp_path):
    (tmp_path / "s.toml").write_text("[gates]\ndefault = 'override'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    with pytest.raises(ValueError, match=r"\[gates\]\.default"):
        o.gate("please approve", D(), "")


def test_scripted_owner_gate_rejects_an_unknown_script_value(tmp_path):
    (tmp_path / "s.toml").write_text("[gates]\ndefault = 'maybe'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    with pytest.raises(ValueError, match=r"\[gates\]\.default"):
        o.gate("please approve", D(), "")


def test_scripted_owner_substitute_bug_keeps_the_planted_bug_by_default(tmp_path):
    (tmp_path / "s.toml").write_text("[substitute]\ndefault = 'planted'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    choice, title, body, why, test_body, secs = o.substitute_bug(config.load_arm("dryrun"), "precheck passed")
    assert (choice, title, body, why, test_body, secs) == ("planted", "", "", "", "", 0.0)


def test_scripted_owner_substitute_bug_can_be_scripted_to_substitute_with_its_test(tmp_path):
    (tmp_path / "s.toml").write_text(
        "[substitute]\ndefault = 'substitute'\ntitle = 'Alias handling bug'\nbody = 'Body'\nwhy = 'Because'\n"
        "test_body = 'def test_x():\\n    assert False'\n")
    o = owner.ScriptedOwner(tmp_path / "s.toml").bind(config.load_arm("dryrun"))
    choice, title, body, why, test_body, secs = o.substitute_bug(config.load_arm("dryrun"), "precheck passed")
    assert (choice, title, body, why, test_body, secs) == (
        "substitute", "Alias handling bug", "Body", "Because", "def test_x():\n    assert False", 0.0)
