import json

from .driver import cap


def events(cli, theatre, path=None, env=None) -> list[dict]:
    args = [path] if path else []
    r = cli("history", *args, theatre=theatre, env=env)
    assert r.code == 0, cap(r.err)             # arm output in a message is always capped (Task 18 advisory)
    return [json.loads(line) for line in r.out.splitlines() if line.strip()]

def core(e: dict) -> tuple:
    return (e["op"], e["path"], e["old"], e["new"])
