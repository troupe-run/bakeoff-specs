# Ruling 7 (Task 15): the real owner's terminal input has a real, select-based timeout — a prompt nobody answers
# parks after `timeout` seconds instead of blocking the run forever inside input().
import os, time
from runner import owner
from runner.po import Decision


def D(): return Decision("approval", "Approved.", [], True, None, "", False)


def pipe():
    r, w = os.pipe()
    return os.fdopen(r, "r"), os.fdopen(w, "w")


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
        wr.write("\n"); wr.flush()
        o = owner.Owner(out=lambda s: None, timeout=5, stdin=rd, prompt_out=lambda s: None)
        reply, action, secs = o.gate("msg", D(), "")
        assert (reply, action) == ("Approved.", "accept") and 0 <= secs < 5
    finally:
        rd.close(); wr.close()


def test_multi_line_answers_are_read_line_by_line_with_the_timeout():
    rd, wr = pipe()
    try:
        wr.write("Floats exactly.\nAs written.\n.\n"); wr.flush()
        o = owner.Owner(out=lambda s: None, timeout=5, stdin=rd, prompt_out=lambda s: None)
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


def test_the_timeout_is_per_prompt_across_all_its_lines():
    rd, wr = pipe()
    try:
        wr.write("first line only\n"); wr.flush()                    # never finished with "."
        o = owner.Owner(out=lambda s: None, timeout=0.3, stdin=rd, prompt_out=lambda s: None)
        res = o.escalation("Floats?", "ctx")
        assert isinstance(res, owner.Park) and res.reason == "timeout"
    finally:
        rd.close(); wr.close()


def test_the_default_owner_uses_the_select_reader_not_input():
    o = owner.Owner()
    assert o._in is None
