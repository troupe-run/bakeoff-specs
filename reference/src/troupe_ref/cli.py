"""Reference implementation CLI. Exit codes per scenario/contract.md."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .config import ConfigError
from .loader import LoadError, load
from .service import Service
from .step import STEP
from .surgical import RejectedSet, SpliceError

EXIT_OK, EXIT_USAGE, EXIT_REFUSED, EXIT_LOAD, EXIT_PATH = 0, 2, 3, 4, 5

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="troupe")
    top = p.add_subparsers(dest="area", required=True)
    config = top.add_parser("config").add_subparsers(dest="sub", required=True)
    for name in ("show", "set", "history"):
        sp = config.add_parser(name)
        sp.add_argument("--theatre", default=".")
        sp.add_argument("args", nargs="*")
    return p

def print_scalar(v) -> str:
    """The contract's "Printing a scalar" rule (scenario/contract.md, General)."""
    if isinstance(v, bool):
        return "true\n" if v else "false\n"
    if v is None:
        return "null\n"
    if isinstance(v, float):
        return repr(v) + "\n"
    s = str(v)
    return s if s.endswith("\n") else s + "\n"

class PathError(Exception):
    pass

def lookup(data, path: str):
    node = data
    for seg in path.split("."):
        if isinstance(node, list) and seg.isdigit() and int(seg) < len(node):
            node = node[int(seg)]
        elif isinstance(node, dict) and seg in node:
            node = node[seg]
        else:
            raise PathError(f"{path}: no such setting")
    return node

def cmd_show(svc, args) -> tuple[int, str]:
    cfg = load(svc.theatre)
    value = lookup(cfg.merged, args[0])
    if isinstance(value, (dict, list)):
        raise PathError(f"{args[0]}: is a section, not a value")
    return EXIT_OK, print_scalar(value)

class Refused(Exception):
    pass

class UsageError(Exception):
    pass

def parse_value(text: str):
    """The contract's VALUE rule: a single YAML 1.2 (core schema) flow node."""
    y = YAML(typ="safe")  # YAML 1.2 core schema
    return y.load(text)

def cmd_set(svc, args) -> tuple[int, str]:
    path, raw = args[0], args[1]
    try:
        value = parse_value(raw)
    except YAMLError as e:
        raise UsageError(f"{path}: VALUE is not a YAML flow node: {e}") from e
    try:
        svc.set(path, value)
    except LookupError as e:  # IndexError: index beyond the list's length; KeyError: wrong kind of node
        raise PathError(f"{path}: {e.args[0] if e.args else e}") from e
    except (RejectedSet, SpliceError, ConfigError) as e:  # ReadOnlyIncludeError is a ConfigError
        raise Refused(f"{path}: {e}") from e
    return EXIT_OK, ""

def cmd_history(svc, args) -> tuple[int, str]:
    rows = svc.store.history(args[0] if args else None)
    return EXIT_OK, "".join(json.dumps(r) + "\n" for r in rows)

COMMANDS = {"show": cmd_show, "set": cmd_set, "history": cmd_history}

# Per-command argument-count rules, as a function of STEP (some commands' arity changes across
# steps, e.g. `show`'s PATH becomes optional at STEP >= 3 — Task 7). Keyed by subcommand name so
# later tasks can add "set" (always 2 args) and "history" (0 or 1) without touching this shape.
# Checked in main() before dispatch, so a wrong argument count is a clean usage error (exit 2)
# rather than an IndexError/traceback from inside the command.
ARITY = {
    "show": lambda step: (0, 1) if step >= 3 else (1, 1),
    "set": lambda step: (2, 2),
    "history": lambda step: (0, 1),
}

def _arity_desc(lo: int, hi: int) -> str:
    if lo == hi:
        return f"{lo} argument" + ("" if lo == 1 else "s")
    return f"{lo}-{hi} arguments"

def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    if ns.sub not in COMMANDS:
        print(f"troupe config {ns.sub}: not implemented", file=sys.stderr)
        return 99
    arity = ARITY.get(ns.sub)
    if arity is not None:
        lo, hi = arity(STEP)
        if not (lo <= len(ns.args) <= hi):
            print(f"error: config {ns.sub}: expected {_arity_desc(lo, hi)}, got {len(ns.args)}", file=sys.stderr)
            return EXIT_USAGE
    try:
        svc = Service(Path(ns.theatre))
        svc.ensure_imported()
        # Every command reconciles first (file edits made while nothing was running are picked
        # up), except `history`, which only ever reports what has been recorded — and except
        # before STEP 2, where reconcile-first isn't a feature yet (only the first-run import is).
        if STEP >= 2 and ns.sub != "history":
            svc.reconcile("file")
        code, out = COMMANDS[ns.sub](svc, ns.args)
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_LOAD
    except PathError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_PATH
    except Refused as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_REFUSED
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_USAGE
    sys.stdout.write(out)
    return code

if __name__ == "__main__":
    sys.exit(main())
