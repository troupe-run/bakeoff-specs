import json

def events(cli, theatre, path=None, env=None) -> list[dict]:
    args = [path] if path else []
    r = cli("history", *args, theatre=theatre, env=env)
    assert r.code == 0, r.err
    return [json.loads(line) for line in r.out.splitlines() if line.strip()]

def core(e: dict) -> tuple:
    return (e["op"], e["path"], e["old"], e["new"])
