import pytest
from .history import core, events
from .theatre import build

CFG = ".troupe/troupe.yml"

@pytest.mark.steps(1)
def test_first_command_imports_every_leaf(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb:\n  c: x\nl:\n  - p\n  - q\nprompt: file:p.md\n", ".troupe/p.md": "hi\n"})
    evs = events(cli, tmp_theatre)
    assert sorted(core(e) for e in evs) == sorted([
        ("import", "a", None, 1), ("import", "b.c", None, "x"),
        ("import", "l.0", None, "p"), ("import", "l.1", None, "q"),
        ("import", "prompt", None, "hi\n")])
    assert [e["seq"] for e in evs] == list(range(1, 6))

@pytest.mark.steps(1)
def test_set_records_one_event_per_changed_leaf_and_seq_continues(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb: 2\n"})
    cli("set", "a", "10", theatre=tmp_theatre)
    cli("set", "b", "20", theatre=tmp_theatre)
    evs = events(cli, tmp_theatre)
    assert [core(e) for e in evs[-2:]] == [("set", "a", 1, 10), ("set", "b", 2, 20)]
    assert [e["seq"] for e in evs] == list(range(1, len(evs) + 1))

@pytest.mark.steps(1)
def test_set_to_the_same_value_records_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    before = events(cli, tmp_theatre)
    # the import must have been recorded first, else "nothing changed" is vacuous on a CLI that records nothing
    assert before and any(e["op"] == "import" and e["path"] == "a" for e in before)
    assert cli("set", "a", "1", theatre=tmp_theatre).code == 0
    assert events(cli, tmp_theatre) == before

@pytest.mark.steps(1)
def test_replacing_a_section_with_a_value_records_removes_and_a_set(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "m:\n  x: 1\n  y: 2\n"})
    cli("set", "m", "flat", theatre=tmp_theatre)
    tail = sorted(core(e) for e in events(cli, tmp_theatre) if e["op"] != "import")
    assert tail == sorted([("remove", "m.x", 1, None), ("remove", "m.y", 2, None), ("set", "m", None, "flat")])

@pytest.mark.steps(1)
def test_history_path_filter_matches_path_and_descendants_only(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "ab: 1\na:\n  b: 2\n  c: 3\n"})
    assert sorted(e["path"] for e in events(cli, tmp_theatre, "a")) == ["a.b", "a.c"]

@pytest.mark.steps(1)
def test_failed_set_records_nothing(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "prompt: file:p.md\n", ".troupe/p.md": "x\n"})
    before = events(cli, tmp_theatre)
    assert cli("set", "prompt", "5", theatre=tmp_theatre).code == 3
    assert events(cli, tmp_theatre) == before
