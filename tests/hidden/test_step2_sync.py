import time
import pytest
from .history import core, events
from .theatre import build
from .watcher import Watching, wait_for

CFG = ".troupe/troupe.yml"

def edit(t, rel, text):
    build(t, {rel: text})

def changes(cli, t):
    return [core(e) for e in events(cli, t) if e["op"] != "import"]

@pytest.mark.steps(2)
def test_edit_while_idle_is_picked_up_by_the_next_command(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1  # c\n"})
    events(cli, tmp_theatre)                       # import
    edit(tmp_theatre, CFG, "a: 2  # c\n")
    assert cli("show", "a", theatre=tmp_theatre).out == "2\n"
    assert changes(cli, tmp_theatre) == [("set", "a", 1, 2)]

@pytest.mark.steps(2)
def test_formatting_and_comment_only_edits_record_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb: [x, y]\n"})
    events(cli, tmp_theatre)
    edit(tmp_theatre, CFG, "# new comment\na:   1   # eol\nb:\n  - x\n  - y\n")
    cli("show", "a", theatre=tmp_theatre)
    assert changes(cli, tmp_theatre) == []

@pytest.mark.steps(2)
def test_watch_picks_up_an_edit_to_an_included_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "coder: file:coder.yaml\n", ".troupe/coder.yaml": "model: opus\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        edit(tmp_theatre, ".troupe/coder.yaml", "model: sonnet\n")
        assert wait_for(lambda: changes(cli, tmp_theatre) == [("set", "coder.model", "opus", "sonnet")], 5)

@pytest.mark.steps(2)
def test_set_while_watching_records_its_change_exactly_once(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        assert cli("set", "a", "2", theatre=tmp_theatre).code == 0
        time.sleep(3)                              # give an echo every chance to appear
        assert changes(cli, tmp_theatre) == [("set", "a", 1, 2)]

@pytest.mark.steps(2)
def test_comment_only_edit_while_watching_records_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        edit(tmp_theatre, CFG, "a: 1  # explained\n")
        time.sleep(3)
        assert changes(cli, tmp_theatre) == []

@pytest.mark.steps(2)
def test_include_added_by_hand_is_followed(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        build(tmp_theatre, {".troupe/extra.yaml": "k: v\n"})
        edit(tmp_theatre, CFG, "a: 1\nextra: file:extra.yaml\n")
        assert wait_for(lambda: ("set", "extra.k", None, "v") in changes(cli, tmp_theatre), 5)

@pytest.mark.steps(2)
def test_watch_exits_0_on_sigterm(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    with Watching(cli, tmp_theatre) as w:
        pass
    assert w.code == 0

@pytest.mark.steps(2)
def test_history_does_not_reconcile(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    edit(tmp_theatre, CFG, "a: 2\n")
    assert changes(cli, tmp_theatre) == []        # recorded only once another command runs
