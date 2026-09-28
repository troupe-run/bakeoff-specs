import getpass, re
from datetime import datetime, timedelta, timezone
import pytest
from .history import events
from .theatre import build
from .watcher import Watching, wait_for

CFG = ".troupe/troupe.yml"
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

def last(cli, t, op="set"):
    return [e for e in events(cli, t) if e["op"] == op][-1]

@pytest.mark.steps(4)
def test_import_events_have_unknown_actor_and_via_import(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    e = events(cli, tmp_theatre)[0]
    assert (e["actor"], e["via"]) == ({"kind": "unknown", "id": None}, "import")
    assert RFC3339_Z.match(e["at"])

@pytest.mark.steps(4)
@pytest.mark.parametrize("env, actor", [
    ({"TROUPE_ACTOR": "agent:coder-7"}, {"kind": "agent", "id": "coder-7"}),
    ({"TROUPE_ACTOR": "human:martin"}, {"kind": "human", "id": "martin"}),
])
def test_cli_set_records_actor_from_env_and_via_cli(cli, tmp_theatre, env, actor):
    build(tmp_theatre, {CFG: "a: 1\n"})
    assert cli("set", "a", "2", theatre=tmp_theatre, env=env).code == 0
    e = last(cli, tmp_theatre)
    assert (e["actor"], e["via"]) == (actor, "cli")

@pytest.mark.steps(4)
def test_cli_actor_defaults_to_the_login_user(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    cli("set", "a", "2", theatre=tmp_theatre)
    assert last(cli, tmp_theatre)["actor"] == {"kind": "human", "id": getpass.getuser()}

@pytest.mark.steps(4)
@pytest.mark.parametrize("bad", ["robot:x", "agent", "agent:", ":x"])
def test_malformed_actor_is_a_usage_error_and_records_nothing(cli, tmp_theatre, bad):
    build(tmp_theatre, {CFG: "a: 1\n"})
    before = events(cli, tmp_theatre)
    r = cli("set", "a", "2", theatre=tmp_theatre, env={"TROUPE_ACTOR": bad})
    assert r.code == 2 and events(cli, tmp_theatre) == before

@pytest.mark.steps(4)
def test_timestamp_is_now_in_utc(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    cli("set", "a", "2", theatre=tmp_theatre)
    at = datetime.fromisoformat(last(cli, tmp_theatre)["at"].replace("Z", "+00:00"))
    assert abs(datetime.now(timezone.utc) - at) < timedelta(minutes=2)

@pytest.mark.steps(4)
def test_idle_edit_is_recorded_as_file_with_unknown_actor(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    build(tmp_theatre, {CFG: "a: 2\n"})
    cli("show", "a", theatre=tmp_theatre, env={"TROUPE_ACTOR": "agent:x"})
    e = last(cli, tmp_theatre)
    assert (e["actor"], e["via"]) == ({"kind": "unknown", "id": None}, "file")

@pytest.mark.steps(4)
def test_set_while_watching_is_attributed_to_the_cli_not_the_file(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\n"})
    events(cli, tmp_theatre)
    with Watching(cli, tmp_theatre):
        for i in range(2, 7):                     # repeat: a race would show up as a "file" attribution
            cli("set", "a", str(i), theatre=tmp_theatre, env={"TROUPE_ACTOR": "agent:a1"})
        sets = [e for e in events(cli, tmp_theatre) if e["op"] == "set"]
        assert [(e["new"], e["via"], e["actor"]["id"]) for e in sets] == [(i, "cli", "a1") for i in range(2, 7)]

@pytest.mark.steps(4)
def test_reason_is_recorded_when_given_and_null_otherwise(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb: 1\n"})
    assert cli("set", "--reason", "tuning for cost", "a", "2", theatre=tmp_theatre).code == 0
    cli("set", "b", "2", theatre=tmp_theatre)
    by_path = {e["path"]: e for e in events(cli, tmp_theatre) if e["op"] == "set"}
    assert (by_path["a"]["reason"], by_path["b"]["reason"]) == ("tuning for cost", None)

@pytest.mark.steps(4)
def test_one_command_shares_one_change_id_and_commands_differ(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "m: flat\nz: 1\n"})
    cli("set", "m", "{x: 1, y: 2}", theatre=tmp_theatre)     # one command, three events
    cli("set", "z", "2", theatre=tmp_theatre)
    evs = [e for e in events(cli, tmp_theatre) if e["op"] != "import"]
    first = {e["change"] for e in evs if e["path"].startswith("m")}
    second = {e["change"] for e in evs if e["path"] == "z"}
    assert len(first) == 1 and len(second) == 1 and first != second
    assert all(isinstance(c, str) and c for c in first | second)

@pytest.mark.steps(4)
def test_import_shares_one_change_id_and_a_file_reconcile_gets_its_own(cli, tmp_theatre):
    build(tmp_theatre, {CFG: "a: 1\nb: 1\n"})
    imported = {e["change"] for e in events(cli, tmp_theatre)}
    build(tmp_theatre, {CFG: "a: 2\nb: 2\n"})
    cli("show", "a", theatre=tmp_theatre)
    edited = {e["change"] for e in events(cli, tmp_theatre) if e["op"] == "set"}
    assert len(imported) == 1 and len(edited) == 1 and imported != edited
