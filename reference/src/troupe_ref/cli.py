"""Reference implementation CLI. Exit codes per scenario/contract.md."""
from __future__ import annotations
import argparse, sys

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

def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    print(f"troupe config {ns.sub}: not implemented", file=sys.stderr)
    return 99

if __name__ == "__main__":
    sys.exit(main())
