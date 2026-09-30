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
    if ns.cmd not in ("faults", "watch"):    # design §9: halted until `faults resume --note` (Task 22); watch reads only
        from runner import faults
        pass_ = getattr(ns, "pass_", None) or "pass1"      # no pass named: the real bake-off's ledger
        if not faults.valid_name(pass_):                   # never build a ledger path from a bad name (M-2)
            pass_ = "pass1"
        if (h := faults.halted(pass_)):
            print(f"HALTED ({faults.ledger_paths(pass_)[1]}): {faults.halt_reason(pass_)} (design §9).\n{h}\n"
                  f"Review with the owner, then `runner faults resume {pass_} --note \"<resolution>\"`.")
            return 1
    return int(ns.func(ns) or 0)


def register_images(sub):
    from runner import images
    p = sub.add_parser("images", help="pin, build (once) and load the container images")
    s = p.add_subparsers(dest="images_cmd", required=True)
    s.add_parser("pin").set_defaults(func=lambda ns: print(json.dumps(images.pin(), indent=2)))
    b = s.add_parser("build"); b.add_argument("--rebuild", action="store_true")
    b.add_argument("--only", nargs="+", metavar="NAME",
                   help="build only these images (base, proxy, tester, tester_ref, dryrun or an arm name); every "
                        "other lock entry is kept (Task 23: never rebuild everything)")
    def build(ns):
        if ns.only:
            if ns.rebuild:
                ns.parser.error("--only and --rebuild are exclusive")
            lock = images.build_only(ns.only)
            print(json.dumps({k: v for k, v in {**lock.get("images", {}), **lock.get("arms", {})}.items()
                              if k in ns.only or any(k.startswith(n) for n in ns.only)}, indent=2))
            return 0
        # During development (before any real pass) --rebuild is routine; once pass 1 has results it needs the owner.
        if ns.rebuild and (paths.RESULTS / "pass1").exists() and \
                input("Images are built once (review S-5). Type 'rebuild' to rebuild: ").strip() != "rebuild":
            return 1
        lock = images.build_all(config.all_arms(), rebuild=ns.rebuild)
        print(json.dumps(lock["arms"], indent=2))
    b.set_defaults(func=build, parser=b)
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
        from runner import secrets                           # Task 21 (review S-2): tip tree + full history
        try:
            lits = secrets.literals(require_oauth=True)          # fix round 1: never publish without it
        except RuntimeError as e:
            print(f"Refusing to publish: the keychain OAuth token is needed for the secret scan ({e})")
            return 1
        try:
            ok = repo.publish(paths.Paths(ns.pass_, ns.arm), ns.pass_,
                              lambda q: input(q).strip().lower() in ("y", "yes"),
                              lambda tree, history: secrets.scan_publish(tree, history, lits))
        except secrets.SecretFound as e:
            print(f"Refusing to publish: {e}")
            for f in e.findings:
                print(f"{f.path}:{f.line} {f.kind}")
            return 1
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
        from runner import orchestrate
        cred, owner = _cred_owner(config.load_arm(ns.arm))
        try:
            r = orchestrate.setup(ns.pass_, ns.arm, cred, owner, again=ns.again)   # once per arm (Task 23)
        except checklist.NotReady as e:
            print(e)
            return 1
        _print_checks(r.checks)
        for k, v in r.owner.items():
            print(f"{'ok  ' if v['ok'] else 'FAIL'} {k}  {v['note']}")
        print("GREEN" if r.green else "NOT GREEN — run-arm refuses step 1 (design §6)")
        return 0 if r.green else 1
    s = sub.add_parser("setup", help="set an arm up exactly per its docs, then its checklist (owner present)")
    s.add_argument("pass_", metavar="pass"); s.add_argument("arm")
    s.add_argument("--again", action="store_true", help="after a setup harness fault: move the arm's state aside "
                                                         "first (refused once a step has started)")
    s.set_defaults(func=setup)

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


def register_scan(sub):
    """`runner scan [--staged] [--arm PASS ARM] [PATH…]` (Task 21, review S-2): prints `path:line kind` per
    finding (never the matched text) and exits 1 on any finding. `--staged` is the pre-commit hook
    (.githooks/pre-commit); `--arm` scans an arm's results and every snapshot (with git history)."""
    def scan(ns):
        from pathlib import Path
        from runner import gitops, secrets
        if not (ns.staged or ns.arm or ns.paths):
            ns.parser.error("nothing to scan: give --staged, --arm PASS ARM or PATH…")
        found = []
        if ns.staged:            # the hook: never the keychain (controller ruling); shapes + arm-home PAT values
            found += secrets.scan_blobs(gitops.staged_blobs(), secrets.literals(keychain=False), harness=True)
        lits = secrets.literals() if (ns.arm or ns.paths) else []   # evidence scans: keychain values too
        if ns.arm:
            found += secrets.scan_arm(paths.Paths(*ns.arm), lits)
        for x in ns.paths:
            found += secrets.scan_tree(Path(x), lits)
        for f in found:
            print(f"{f.path}:{f.line} {f.kind}")
        if found:
            print(f"{len(found)} secret finding(s); nothing is printed but where. Scrub, then re-run `runner scan`.")
        return 1 if found else 0
    p = sub.add_parser("scan", help="secret scan (token shapes and keychain/PAT values) of paths, staged files "
                                    "or an arm; exit 1 on any finding")
    p.add_argument("--staged", action="store_true", help="the harness repo's staged files (pre-commit hook)")
    p.add_argument("--arm", nargs=2, metavar=("PASS", "ARM"), help="an arm's results and snapshots")
    p.add_argument("paths", nargs="*", metavar="PATH")
    p.set_defaults(func=scan, parser=p)
REGISTRARS.append(register_scan)


def register_faults(sub):
    """`faults list [--pass P]`, `faults declare <pass> <arm> <step> <slug> --scope rerun-step|retest|record`,
    `faults resume <pass> --note "<text>"` (Task 22, design §9). The only commands that run while HALTED. Bad input
    (unknown pass or arm, step outside 1-7, an empty note, resuming a pass that is not halted) is a clean error,
    exit 2, and writes nothing (fix round 1 M-2)."""
    import sys
    from runner import faults

    def clean(fn):
        def run(ns):
            try:
                return fn(ns)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
        return run

    def list_(ns):
        pass_ = faults.check_pass(ns.pass_) if ns.pass_ else "pass1"
        for e in faults.entries(pass_):
            print(json.dumps(e))
        if (h := faults.halted(pass_)):
            print(f"HALTED: {h}")
    p = sub.add_parser("faults", help="the harness-fault ledger: list, declare, resume after a halt")
    s_ = p.add_subparsers(dest="faults_cmd", required=True)
    ls = s_.add_parser("list", help="print the ledger (the real passes' shared ledger unless --pass names another)")
    ls.add_argument("--pass", dest="pass_", default=None); ls.set_defaults(func=clean(list_))

    def declare(ns):
        action = faults.declare(ns.pass_, ns.arm, ns.step, ns.slug, ns.scope)
        if ns.scope == "rerun-step":                      # Task 23 honours it: supersede the step and re-run it
            prog = paths.Paths(ns.pass_, ns.arm).progress
            cur = json.loads(prog.read_text()) if prog.exists() else {}
            from runner import fsutil
            fsutil.write_json(prog, {**cur, "rerun": ns.step})          # atomic (Task 23 fix round 1)
        # --scope retest: the orchestrator reads it from the ledger (Task 23) and re-tests the recorded sha_after
        # --scope record: the ledger entry only (an owner stop); a plain resume handles the interrupted run
        print(f"declared manual:{ns.slug} ({ns.scope}) for {ns.pass_}/{ns.arm} step {ns.step}")
        if action == "halt":
            print(f"HALTED: manual:{ns.slug} was already recorded since the last resolution (design §9).\n"
                  f"{faults.halted(ns.pass_)}")
            return 1
    d = s_.add_parser("declare", help="record an owner-declared harness fault (manual:<slug>)")
    d.add_argument("pass_", metavar="pass"); d.add_argument("arm"); d.add_argument("step", type=int)
    d.add_argument("slug")
    d.add_argument("--scope", required=True, choices=faults.SCOPES,
                   help="rerun-step: supersede this step and every later one and re-run them; retest: re-run the "
                        "hidden tests and quality on the recorded sha_after; record: the ledger entry only (an owner "
                        "stop: Ctrl-C the runner, declare, then resume)")
    d.set_defaults(func=clean(declare))

    def resume(ns):
        faults.resume(ns.pass_, ns.note)
        print(f"resolution recorded for {ns.pass_}; HALTED cleared")
    r = s_.add_parser("resume", help="record the owner's resolution and clear HALTED")
    r.add_argument("pass_", metavar="pass"); r.add_argument("--note", required=True)
    r.set_defaults(func=clean(resume))
REGISTRARS.append(register_faults)


def _real_cred_owner():
    """The real bake-off (and the canary): the keychain credential and the owner at the terminal."""
    from runner import credentials, owner as owner_mod
    return credentials.from_keychain(), owner_mod.Owner()


def _real_owner():
    from runner import owner as owner_mod
    return owner_mod.Owner()


def _orchestrated(fn):
    """`stepflow.Halt` → the HALTED record, exit 2; `NotReady` → the reason, exit 1; otherwise the result as JSON."""
    def run(ns):
        from runner import checklist, stepflow
        try:
            res = fn(ns)
        except stepflow.Halt as h:
            from runner import faults
            pass_ = getattr(ns, "pass_", None) or "pass1"
            why = faults.halt_reason(pass_) if faults.valid_name(pass_) else None
            print(f"HALTED (design §9): {why or h}\n{h}\nReview with the owner, then "
                  f"`runner faults resume {pass_} --note \"...\"`.")
            return 2
        except checklist.NotReady as e:
            print(f"not ready: {e}")
            return 1
        if res is not None:
            print(json.dumps(res, indent=2, default=str))
            if isinstance(res, dict) and any(k in res for k in ("declined", "incomplete", "skipped", "preflight_missing",
                                                                 "setup_green", "not_finished",
                                                                 "tracker_check_failed")):
                return 1
        return 0
    return run


def register_orchestrate(sub):
    """Task 23: `order`, `run-pass`, `run-arm`, `close-out`, `status`. Every one refuses while HALTED (main)."""
    from runner import orchestrate

    def order(ns):
        print("\n".join(orchestrate.order(ns.pass_, ns.seed)))
    o = sub.add_parser("order", help="record the arm order for a pass (pass1: seeded shuffle, control not first)")
    o.add_argument("pass_", metavar="pass"); o.add_argument("--seed", type=int, default=None)
    o.set_defaults(func=_orchestrated(lambda ns: order(ns)))

    def run_pass(ns):
        cred, owner = _real_cred_owner()
        return orchestrate.run_pass(ns.pass_, cred, owner)
    rp = sub.add_parser("run-pass", help="run (or resume) every arm step-major: N.a, the consistency check, N.b")
    rp.add_argument("pass_", metavar="pass"); rp.set_defaults(func=_orchestrated(run_pass))

    def run_arm(ns):
        cred, owner = _cred_owner(config.load_arm(ns.arm))
        return orchestrate.run_arm(ns.pass_, ns.arm, cred, owner, stop_after=ns.stop_after)
    ra = sub.add_parser("run-arm", help="run (or resume) one arm step-major (canary and dry passes only)")
    ra.add_argument("pass_", metavar="pass"); ra.add_argument("arm")
    ra.add_argument("--stop-after", type=int, default=None, help="stop after this step (the canary: default and maximum 2)")
    ra.set_defaults(func=_orchestrated(run_arm))

    def close_out(ns):
        f = orchestrate.close_out(ns.pass_, _real_owner())
        print(f)
    c = sub.add_parser("close-out", help="end of a run: every arm finished, scan clean, bundles, PATs revoked")
    c.add_argument("pass_", metavar="pass"); c.set_defaults(func=_orchestrated(close_out))

    st = sub.add_parser("status", help="every arm's progress, step by step, run a and b")
    st.set_defaults(func=lambda ns: print(orchestrate.status()))

    def dry_run(ns):
        """Task 24: the four dry passes (fake claude, dummy credential, scripted owner); with --report, writes
        results/dryrun-validation.md and exits 1 unless it says PASS."""
        res = orchestrate.dry_results() if ns.report_only else orchestrate.dry_run()
        print(json.dumps(res, indent=2, default=str))
        if not (ns.report or ns.report_only):
            return 0
        out = orchestrate.dry_report(res)
        text = out.read_text()
        print(text)
        return 0 if text.rstrip().endswith("**Result: PASS**") else 1
    d = sub.add_parser("dry-run", help="the runner's own end-to-end dry run (no model, no GitHub)")
    d.add_argument("--report", action="store_true", help="write results/dryrun-validation.md; exit 1 unless PASS")
    d.add_argument("--report-only", action="store_true",
                   help="no run: regenerate the report from the passes' existing evidence; exit 1 unless PASS")
    d.set_defaults(func=dry_run)
REGISTRARS.append(register_orchestrate)


def register_probe(sub):
    def probe_cmd(ns):
        """Task 25 (owner-run): the live probe. Without --no-model the owner confirms first (a park or a no spends
        nothing), then the keychain credential drives P1–P8/P10 and P9/P11 follow; --no-model runs only P9/P11 and
        needs neither a confirm nor a credential. One runner at a time (`preflight.lock`)."""
        from runner import credentials, owner as owner_mod, preflight, probe
        from runner.checklist import NotReady
        try:
            with preflight.lock():
                cred, res, started = None, {}, False
                if not ns.no_model:
                    ok = owner_mod.Owner().confirm("Run the live probe (spends a little quota)?")
                    if ok is not True:
                        print("Not confirmed: nothing run, nothing spent.")
                        return 1
                failed: BaseException | None = None
                try:
                    started = True
                    if ns.no_model:
                        res = probe.no_model(pats=False)
                    else:
                        cred = credentials.from_keychain()
                        res = probe.with_model(cred)
                        res |= probe.no_model(pats=True)
                except BaseException as e:
                    failed = e
                    raise
                finally:
                    # Fix rounds 1–2: every file under results/probe* is scanned before anything is reported, even
                    # when a half raised (recorded in P10.json). --no-model never touches the keychain; the full probe
                    # also searches for the keychain PAT values. A failing scan never hides the original error.
                    if started:
                        try:
                            res["results_scan"] = probe.scan_results(cred, keychain=not ns.no_model)
                        except Exception as se:
                            if failed is None:
                                raise
                            failed.add_note(f"the results/probe* secret scan failed too: {se!r}")
                        else:
                            if res["results_scan"]["count"]:
                                print(f"STOP: secret findings under results/probe*: {res['results_scan']['findings']}")
                print(probe.report(res))
                if res["results_scan"]["count"]:
                    return 1
        except NotReady as e:
            print(e)
            return 1
        return 0
    p = sub.add_parser("probe", help="owner-run live probe of the headless assumptions (spends a little quota)")
    p.add_argument("--no-model", action="store_true", help="only the no-model probes (P9, P11); no credential")
    p.set_defaults(func=probe_cmd)
REGISTRARS.append(register_probe)


def register_canary(sub):
    def canary_cmd(ns):
        """Task 26 (OD25, owner-run): `canary` — pre-flight (repos and keychain items; any gap: printed, nothing
        spent, exit 1), the owner's confirm (a no or a park spends nothing), then control steps 1-2 and the tracker
        check. `canary --check` writes results/canary/canary.md and exits 1 unless it ends PASS."""
        from runner import orchestrate
        if ns.check:
            orchestrate.canary_check()
            text = (paths.RESULTS / "canary" / "canary.md").read_text()
            print(text)
            return 0 if text.rstrip().endswith("**Result: PASS**") else 1

        def run(ns):
            from runner import credentials, owner as owner_mod
            go = orchestrate.canary_resume if ns.resume else orchestrate.canary
            res = go(credentials.from_keychain, owner_mod.Owner())
            if "preflight_missing" in res:
                print("The canary cannot start; missing:")
                for m in res["preflight_missing"]:
                    print(f"  - {m}")
                print(res["hint"])
                print("Nothing was run and nothing was spent.")
            elif "not_finished" in res:
                print(f"The arm did not finish steps 1-2 ({res['not_finished']}): no GitHub issue was created; "
                      f"nothing was written to the tracker. Complete it with `{res['resume']}` (no wipe, no setup).")
            elif "tracker_check_failed" in res:
                print(f"Steps 1-2 finished, but the tracker check failed: {'; '.join(res['tracker_check_failed'])}. "
                      f"`runner canary --resume` re-runs it (the run itself is kept); `runner canary --check` "
                      f"judges the whole canary.")
            elif res.get("skipped"):
                print(f"Not confirmed ({res.get('why')}): nothing run, nothing spent.")
            return res
        return _orchestrated(run)(ns)
    p = sub.add_parser("canary", help="owner-run canary: control, steps 1-2, real model/PO/GitHub (OD25; spends quota)",
                       description="Owner-run canary: control, steps 1-2, real model/PO/GitHub (OD25; spends quota). "
                                   "An owner stop declared with `runner faults declare canary control <step> <slug> "
                                   "--scope record` is a harness fault, so `canary --check`'s no-harness-fault row "
                                   "fails: after an owner stop, run a fresh canary.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="write results/canary/canary.md; exit 1 unless it ends PASS")
    g.add_argument("--resume", action="store_true", help="complete an interrupted canary: no wipe, no setup; "
                                                         "steps 1-2 resumed, then the tracker check")
    p.set_defaults(func=canary_cmd, pass_="canary")    # main's HALTED check reads the canary's own ledger
REGISTRARS.append(register_canary)


def register_watch(sub):
    """`runner watch [--pass P] [--arm A]`: follow the running turn's live feed (runner.live) from a second terminal.
    Read-only: never takes the runner lock, never writes, and works while HALTED."""
    def watch(ns):
        import sys
        from runner import live
        try:
            live.follow(sys.stdout, ns.pass_, ns.arm, poll=ns.poll)
        except KeyboardInterrupt:
            print("\nstopped watching (the run itself is unaffected)")
        return 0
    p = sub.add_parser(
        "watch", help="follow the running turn live (tool calls, text, subagents, result); read-only",
        description="Follow the running turn's live feed (state/<pass>/<arm>/live/, secret-redacted), switching to "
                    "each new turn as it starts; with no running turn, wait for one. Read-only: no lock, no writes; "
                    "run it in a second terminal beside run-pass / run-arm / canary / dry-run. Ctrl-C here stops "
                    "watching only. To stop the RUN: Ctrl-C in the runner's terminal (the step is left interrupted), "
                    "then `runner faults declare <pass> <arm> <step> <slug> --scope record` (ledgered as "
                    "manual:<slug>), then resume — an owner stop is a harness fault, not the arm's (design §9), so a "
                    "declared stop fails a canary's no-harness-fault row (run a fresh canary). A stop during setup "
                    "(step 0) has no ledger entry: rerun the setup.")
    p.add_argument("--pass", dest="pass_", metavar="PASS", default=None, help="only this pass (default: any)")
    p.add_argument("--arm", default=None, help="only this arm (default: any)")
    p.add_argument("--poll", type=float, default=0.5, help=argparse.SUPPRESS)
    p.set_defaults(func=watch)
REGISTRARS.append(register_watch)
