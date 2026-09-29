# runner/cli.py — each later task adds one `register_<x>(sub)` function to REGISTRARS.
from __future__ import annotations
import argparse, json
from typing import Callable
from runner import config, paths

REGISTRARS: list[Callable[[argparse._SubParsersAction], None]] = []


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runner", description="bakeoff-specs runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    for register in REGISTRARS:
        register(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    return int(ns.func(ns) or 0)


def register_images(sub):
    from runner import images
    p = sub.add_parser("images", help="pin, build (once) and load the container images")
    s = p.add_subparsers(dest="images_cmd", required=True)
    s.add_parser("pin").set_defaults(func=lambda ns: print(json.dumps(images.pin(), indent=2)))
    b = s.add_parser("build"); b.add_argument("--rebuild", action="store_true")
    def build(ns):
        # During development (before any real pass) --rebuild is routine; once pass 1 has results it needs the owner.
        if ns.rebuild and (paths.RESULTS / "pass1").exists() and \
                input("Images are built once (review S-5). Type 'rebuild' to rebuild: ").strip() != "rebuild":
            return 1
        lock = images.build_all(config.all_arms(), rebuild=ns.rebuild)
        print(json.dumps(lock["arms"], indent=2))
    b.set_defaults(func=build)
    s.add_parser("load").set_defaults(func=lambda ns: images.load_saved())
REGISTRARS.append(register_images)


def register_github(sub):
    from runner import repo

    def plan(ns):
        print("\n".join(repo.github_plan(ns.pass_)))
        print("\nOne token per GitHub-tracker arm (OD16):")
        print("\n".join(repo.pat_instructions(ns.pass_)))
    p = sub.add_parser("github-plan", help="print the private-repo and PAT commands for a pass (runs nothing)")
    p.add_argument("pass_", metavar="pass"); p.set_defaults(func=plan)

    def verify(ns):
        res = repo.github_verify(ns.pass_)
        print(json.dumps(res, indent=2))
        return 0 if repo.verify_ok(res) else 1
    v = sub.add_parser("github-verify", help="every arm repo exists, private, issues on, empty; none public")
    v.add_argument("pass_", metavar="pass"); v.set_defaults(func=verify)

    def publish(ns):
        try:
            from runner import secrets                       # Task 21 (review S-2)
        except ImportError:
            print("Refusing to publish: no secret scan available yet (runner.secrets, Task 21).")
            return 1
        ok = repo.publish(paths.Paths(ns.pass_, ns.arm), ns.pass_,
                          lambda q: input(q).strip().lower() in ("y", "yes"),
                          lambda d: secrets.scan_tree(d, secrets.literals()))
        return 0 if ok else 1
    u = sub.add_parser("publish", help="push an arm's main to its GitHub repo (owner-approved, from a bundle clone)")
    u.add_argument("pass_", metavar="pass"); u.add_argument("arm"); u.set_defaults(func=publish)
REGISTRARS.append(register_github)


def _cred_owner(arm: config.Arm):
    """Real arms: the keychain credential and the owner at the terminal. Dry arms: the dummy credential and the
    scripted owner (Task 24). `runner.owner` is Task 14; until it lands, tests replace this function."""
    from runner import credentials, owner as owner_mod
    if arm.dry:
        return credentials.dummy(), owner_mod.ScriptedOwner(config.CONFIG_DIR / "dryrun-owner.toml").bind(arm)
    return credentials.from_keychain(), owner_mod.Owner()


def _owner_for(arm: config.Arm):
    """The owner for a re-check (pass-2 manifest differences ask). `runner.owner` is Task 14."""
    from runner import owner as owner_mod
    if arm.dry:
        return owner_mod.ScriptedOwner(config.CONFIG_DIR / "dryrun-owner.toml").bind(arm)
    return owner_mod.Owner()


def _print_checks(checks) -> None:
    for c in checks:
        print(f"{ {'ok': 'ok  ', 'fail': 'FAIL', 'n/a': 'n/a '}[c.status]} {c.id}  {c.detail}")


def register_setup(sub):
    from runner import checklist

    def setup(ns):
        cred, owner = _cred_owner(config.load_arm(ns.arm))
        r = checklist.run_setup(ns.pass_, ns.arm, cred, owner)
        _print_checks(r.checks)
        for k, v in r.owner.items():
            print(f"{'ok  ' if v['ok'] else 'FAIL'} {k}  {v['note']}")
        print("GREEN" if r.green else "NOT GREEN — run-arm refuses step 1 (design §6)")
        return 0 if r.green else 1
    s = sub.add_parser("setup", help="set an arm up exactly per its docs, then its checklist (owner present)")
    s.add_argument("pass_", metavar="pass"); s.add_argument("arm"); s.set_defaults(func=setup)

    def check(ns):
        r = checklist.recheck(ns.pass_, ns.arm, _owner_for(config.load_arm(ns.arm)))
        _print_checks(r.checks)
        print("GREEN (setup clean)" if r.green else "NOT GREEN — setup stays dirty; run-arm refuses to start")
        return 0 if r.green else 1
    c = sub.add_parser("checklist", help="full re-check of an arm's setup (verify script + host checks); "
                                         "clears the dirty mark a shell session sets, only when green")
    c.add_argument("pass_", metavar="pass"); c.add_argument("arm"); c.set_defaults(func=check)

    h = sub.add_parser("shell", help="interactive shell in the arm's container (setup egress; history recorded)")
    h.add_argument("pass_", metavar="pass"); h.add_argument("arm")
    h.set_defaults(func=lambda ns: checklist.interactive_shell(ns.pass_, ns.arm))
REGISTRARS.append(register_setup)
