# Ruling 7 (Task 15): the real owner's terminal input has a real, select-based timeout — a prompt nobody answers
# parks after `timeout` seconds instead of blocking the run forever inside input(). Fix round 1: input typed
# before a prompt was shown (type-ahead, or a line left over from a timed-out prompt) is discarded, never taken
# as the answer to a prompt the owner has not seen.
import builtins, os, threading, time
import pytest
from runner import owner
from runner.po import Decision


def D(): return Decision("approval", "Approved.", [], True, None, "", False)


def pipe():
    r, w = os.pipe()
    return os.fdopen(r, "r"), os.fdopen(w, "w")


def later(wr, text, close=False, delay=0.15):
    """Write `text` after the prompt has started (anything written before it is type-ahead and discarded)."""
    def go():
        wr.write(text); wr.flush()
        if close:
            wr.close()
    t = threading.Timer(delay, go); t.start()
    return t


def test_an_unanswered_prompt_parks_after_the_timeout_without_blocking():
    rd, wr = pipe()                                   # nothing is ever written: input() would block forever
    try:
        o = owner.Owner(out=lambda s: None, timeout=0.3, stdin=rd, prompt_out=lambda s: None)
        t0 = time.monotonic()
        res = o.gate("msg", D(), "")
        assert isinstance(res, owner.Park) and res.reason == "timeout"
        assert time.monotonic() - t0 < 5
    finally:
        rd.close(); wr.close()


def test_a_prompt_answered_in_time_is_read_from_the_stream():
    rd, wr = pipe()
    try:
        o = owner.Owner(out=lambda s: None, timeout=5, stdin=rd, prompt_out=lambda s: None)
        later(wr, "\n")
        reply, action, secs = o.gate("msg", D(), "")
        assert (reply, action) == ("Approved.", "accept") and 0 <= secs < 5
    finally:
        rd.close(); wr.close()


def test_multi_line_answers_are_read_line_by_line_with_the_timeout():
    rd, wr = pipe()
    try:
        o = owner.Owner(out=lambda s: None, timeout=5, stdin=rd, prompt_out=lambda s: None)
        later(wr, "Floats exactly.\nAs written.\n.\n")
        ans, secs = o.escalation("Floats?", "ctx")
        assert ans == "Floats exactly.\nAs written." and secs >= 0
    finally:
        rd.close(); wr.close()


def test_eof_on_the_stream_parks_as_eof():
    rd, wr = pipe()
    wr.close()
    try:
        o = owner.Owner(out=lambda s: None, timeout=5, stdin=rd, prompt_out=lambda s: None)
        res = o.escalation("Floats?", "ctx")
        assert isinstance(res, owner.Park) and res.reason == "eof"
    finally:
        rd.close()


def test_a_partial_last_line_before_eof_is_read_with_its_cr_stripped():
    rd, wr = pipe()
    try:
        o = owner.Owner(out=lambda s: None, timeout=5, stdin=rd, prompt_out=lambda s: None)
        later(wr, "Floats exactly.\r\n.\r", close=True)   # the "." terminator has no newline, then EOF
        ans, _ = o.escalation("Floats?", "ctx")
        assert ans == "Floats exactly."
    finally:
        rd.close()


def test_the_timeout_is_per_prompt_across_all_its_lines():
    rd, wr = pipe()
    try:
        o = owner.Owner(out=lambda s: None, timeout=0.3, stdin=rd, prompt_out=lambda s: None)
        later(wr, "first line only\n", delay=0.05)                 # never finished with "."
        res = o.escalation("Floats?", "ctx")
        assert isinstance(res, owner.Park) and res.reason == "timeout"
    finally:
        rd.close(); wr.close()


def test_a_line_typed_after_a_timed_out_gate_never_accepts_the_next_gate():   # fix round 1, item 1
    rd, wr = pipe()
    try:
        o = owner.Owner(out=lambda s: None, timeout=0.3, stdin=rd, prompt_out=lambda s: None)
        assert o.gate("first", D(), "").reason == "timeout"
        wr.write("\n"); wr.flush()                    # late Enter meant for the first gate
        res = o.gate("second", D(), "")
        assert isinstance(res, owner.Park) and res.reason == "timeout"
    finally:
        rd.close(); wr.close()


def test_type_ahead_before_a_prompt_is_discarded():
    rd, wr = pipe()
    try:
        wr.write("e\nsneaky override\n.\n"); wr.flush()
        o = owner.Owner(out=lambda s: None, timeout=0.3, stdin=rd, prompt_out=lambda s: None)
        res = o.gate("msg", D(), "")
        assert isinstance(res, owner.Park) and res.reason == "timeout"
    finally:
        rd.close(); wr.close()


@pytest.mark.parametrize("stdin", [None, object()])
def test_no_usable_stdin_parks_as_eof_rather_than_raising(monkeypatch, stdin):   # fix round 1, item 8
    monkeypatch.setattr(owner.sys, "stdin", None)
    o = owner.Owner(out=lambda s: None, timeout=1, stdin=stdin, prompt_out=lambda s: None)
    for res in (o.gate("msg", D(), ""), o.escalation("q", "ctx"), o.confirm("ok?")):
        assert isinstance(res, owner.Park) and res.reason == "eof"


def test_the_default_owner_never_calls_input(monkeypatch):
    def boom(*a): raise AssertionError("input() must not be used by the default owner")
    monkeypatch.setattr(builtins, "input", boom)
    rd, wr = pipe()
    try:
        o = owner.Owner(out=lambda s: None, timeout=0.2, stdin=rd, prompt_out=lambda s: None)
        res = o.gate("msg", D(), "")
        assert isinstance(res, owner.Park) and res.reason == "timeout"
    finally:
        rd.close(); wr.close()
