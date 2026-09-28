"""Reference implementation CLI. Exit codes per scenario/contract.md."""
from __future__ import annotations
import argparse, getpass, json, os, signal, sys, threading
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from watchfiles import watch as fs_watch

from .config import ConfigError
from .loader import LoadError, load
from .render import render_with_sources, render_yaml
from .service import Service
from .step import STEP
from .surgical import RejectedSet, SpliceError

EXIT_OK, EXIT_USAGE, EXIT_REFUSED, EXIT_LOAD, EXIT_PATH = 0, 2, 3, 4, 5

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="troupe")
    top = p.add_subparsers(dest="area", required=True)
    config = top.add_parser("config").add_subparsers(dest="sub", required=True)
    names = ("show", "set", "history")
    if STEP >= 2:
        names = (*names, "watch")
    if STEP >= 3:
        names = (*names, "get")
    for name in names:
        sp = config.add_parser(name)
        sp.add_argument("--theatre", default=".")
        if name == "show":
            sp.add_argument("--sources", action="store_true")
        if name == "set" and STEP >= 4:
            sp.add_argument("--reason")
        if name == "set" and STEP >= 5:
            sp.add_argument("--in-include", action="store_true",
                            help="write a new key into the included file instead of as an override")
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

def cmd_get(svc, args) -> tuple[int, str]:
    value = lookup(load(svc.theatre).merged, args[0])
    if isinstance(value, (dict, list)):
        raise PathError(f"{args[0]}: is a section; use `troupe config show {args[0]}`")
    return EXIT_OK, print_scalar(value)

def cmd_show(svc, args, sources: bool = False) -> tuple[int, str]:
    cfg = load(svc.theatre)
    path = tuple(int(s) if s.isdigit() else s for s in args[0].split(".")) if args else ()
    value = lookup(cfg.merged, args[0]) if args else cfg.merged
    if STEP < 3:
        if isinstance(value, (dict, list)):
            raise PathError(f"{args[0]}: is a section, not a value")
        return EXIT_OK, print_scalar(value)
    if not isinstance(value, (dict, list)):
        return EXIT_OK, print_scalar(value)
    return EXIT_OK, render_with_sources(cfg, path, svc.theatre) if sources else render_yaml(value)

class Refused(Exception):
    pass

class UsageError(Exception):
    pass

def actor_from_env() -> dict:
    raw = os.environ.get("TROUPE_ACTOR")
    if raw is None:
        return {"kind": "human", "id": getpass.getuser()}
    kind, sep, ident = raw.partition(":")
    if kind not in ("human", "agent") or not sep or not ident:
        raise UsageError(f"TROUPE_ACTOR must be human:<id> or agent:<id>, got {raw!r}")
    return {"kind": kind, "id": ident}

def parse_value(text: str):
    """The contract's VALUE rule: a single YAML 1.2 (core schema) flow node."""
    y = YAML(typ="safe")  # YAML 1.2 core schema
    return y.load(text)

def cmd_set(svc, args, in_include: bool = False) -> tuple[int, str]:
    path, raw = args[0], args[1]
    try:
        value = parse_value(raw)
    except YAMLError as e:
        raise UsageError(f"{path}: VALUE is not a YAML flow node: {e}") from e
    try:
        svc.set(path, value, **({"in_include": True} if in_include else {}))
    except LookupError as e:  # IndexError: index beyond the list's length; KeyError: wrong kind of node
        raise PathError(f"{path}: {e.args[0] if e.args else e}") from e
    except (RejectedSet, SpliceError, ConfigError) as e:  # ReadOnlyIncludeError is a ConfigError
        raise Refused(f"{path}: {e}") from e
    return EXIT_OK, ""

def cmd_history(svc, args) -> tuple[int, str]:
    rows = svc.store.history(args[0] if args else None)
    return EXIT_OK, "".join(json.dumps(r) + "\n" for r in rows)

def _is_relevant(path: str) -> bool:
    # Ignore the state dir (the SQLite db + its -wal/-shm/-journal siblings and the lock file
    # live there — a watcher that reconciled on its own store writes would loop forever) and the
    # atomic-write temp files `_atomic_write` (config.py) creates via
    # `tempfile.mkstemp(prefix=".troupe-tmp-")`, e.g. ".troupe-tmp-8f3a2b1c" — a fixed suffix
    # check would never match since mkstemp appends random characters after the prefix.
    return "/state/" not in path and not Path(path).name.startswith(".troupe-tmp-")

def cmd_watch(svc, args) -> tuple[int, str]:
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    troupe_dir = svc.theatre / ".troupe"
    print(f"watching {svc.theatre}", flush=True)
    for changes in fs_watch(troupe_dir, stop_event=stop, debounce=100, step=20, rust_timeout=200,
                            yield_on_timeout=True):
        if any(_is_relevant(p) for _, p in changes):
            try:
                svc.reconcile("file")
            except Exception as e:           # a half-saved file: report and keep watching
                print(f"warning: {e}", file=sys.stderr, flush=True)
    return EXIT_OK, ""

COMMANDS = {"show": cmd_show, "set": cmd_set, "history": cmd_history, "watch": cmd_watch, "get": cmd_get}

# Per-command argument-count rules, as a function of STEP (some commands' arity changes across
# steps, e.g. `show`'s PATH becomes optional at STEP >= 3 — Task 7). Keyed by subcommand name so
# later tasks can add "set" (always 2 args) and "history" (0 or 1) without touching this shape.
# Checked in main() before dispatch, so a wrong argument count is a clean usage error (exit 2)
# rather than an IndexError/traceback from inside the command.
ARITY = {
    "show": lambda step: (0, 1) if step >= 3 else (1, 1),
    "set": lambda step: (2, 2),
    "history": lambda step: (0, 1),
    "watch": lambda step: (0, 0),
    "get": lambda step: (1, 1),
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
        # Actor is computed before the Service exists, so a malformed TROUPE_ACTOR is a clean
        # usage error that records nothing — not even the first-run import.
        actor = actor_from_env() if STEP >= 4 else None
        reason = getattr(ns, "reason", None)
        svc = Service(Path(ns.theatre), actor=actor, reason=reason)
        svc.ensure_imported()
        # Every command reconciles first (file edits made while nothing was running are picked
        # up), except `history`, which only ever reports what has been recorded — and except
        # before STEP 2, where reconcile-first isn't a feature yet (only the first-run import is).
        if STEP >= 2 and ns.sub != "history":
            svc.reconcile("file")
        # Pass every subparser option through as a keyword, generically: a command whose
        # subparser adds flags beyond --theatre/args (e.g. `show --sources`, and later
        # `--in-include`, `--expand-alias`, `--include`) receives them without main() naming that
        # command specially. A command with no extra options just gets **{}, which matches its
        # existing (svc, args) signature. `reason` is excluded: it's consumed above to build the
        # Service (lineage), not forwarded to the command — Config.set has no `reason` kwarg.
        opts = {k: v for k, v in vars(ns).items() if k not in ("area", "sub", "theatre", "args", "reason")}
        code, out = COMMANDS[ns.sub](svc, ns.args, **opts)
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
