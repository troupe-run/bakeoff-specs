# tests/hidden/test_step6_aliases.py
import pytest
from .history import events
from .theatre import build, read

CFG = ".troupe/troupe.yml"
SHARED = "defaults: &d\n  model: opus\ncoder:\n  settings: *d\nreviewer:\n  settings: *d\n"

@pytest.mark.steps(6)
def test_setting_the_anchor_changes_every_alias(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    assert cli("set", "defaults.model", "sonnet", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == SHARED.replace("model: opus", "model: sonnet")
    assert cli("get", "reviewer.settings.model", theatre=tmp_theatre).out == "sonnet\n"

@pytest.mark.steps(6)
def test_setting_through_an_alias_is_refused_and_suggests_expand(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    r = cli("set", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 3 and "--expand-alias" in r.err
    assert read(tmp_theatre, CFG) == SHARED
    assert cli("get", "reviewer.settings.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(6)
def test_expand_alias_makes_a_commented_local_copy_and_overrides_it(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    r = cli("set", "--expand-alias", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    assert r.code == 0
    assert read(tmp_theatre, CFG) == ("defaults: &d\n  model: opus\n"
                                     "coder:\n  settings:  # expanded from *d by troupe\n    model: sonnet\n"
                                     "reviewer:\n  settings: *d\n")
    assert cli("get", "reviewer.settings.model", theatre=tmp_theatre).out == "opus\n"

@pytest.mark.steps(6)
def test_expanding_records_only_the_changed_leaf(cli, tmp_theatre):
    build(tmp_theatre, {CFG: SHARED})
    events(cli, tmp_theatre)
    cli("set", "--expand-alias", "coder.settings.model", "sonnet", theatre=tmp_theatre)
    changed = [(e["op"], e["path"], e["old"], e["new"]) for e in events(cli, tmp_theatre) if e["op"] != "import"]
    assert changed == [("set", "coder.settings.model", "opus", "sonnet")]

@pytest.mark.steps(6)
def test_scalar_alias_refused_and_anchor_scalar_settable(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: &x 1  # anchor\nb: *x\n"})
    assert cli("set", "b", "2", theatre=tmp_theatre).code == 3
    assert cli("set", "a", "2", theatre=tmp_theatre).code == 0
    assert read(tmp_theatre, CFG) == "a: &x 2  # anchor\nb: *x\n"
