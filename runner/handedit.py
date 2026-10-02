"""The unannounced step-2 hand edit (OD1; plan Task 16).

Before the step-2 brief is handed over, a "teammate" commits a small feature straight to `main`, outside the
method's workflow: `TROUPE_THEATRE`, when set and non-empty, becomes the default for `--theatre`; an explicit
`--theatre` still wins. It is contract-compatible (hidden tests never set `TROUPE_THEATRE`), so it cannot change a
hidden-test result, but it touches the CLI surface every method's specs describe — the drift design §4 wants
detected.

`apply(ctx, step1_tests)` — called ONCE per arm, before step 2's first run (2.a in the N.a/N.b structure; the
orchestration is Task 23):

  recover → precondition (on `main`, clean) → snapshot("02-pre-edit") → teammate turn → transcripts collected
  (after the container has exited) and pin-checked → scope plan (side effects cleaned and recorded) → commit IN
  THE ARM'S CONTAINER as Sam Teammate (`gitops.commit_all`: the arm's image, the repo's hooks run — e.g. beads'
  `bd` hooks for speckitty) → probe → step-1 hidden recheck (same outcomes as step 1's record) → snapshot(2).

`snapshot(2)` is therefore the post-edit state: the reset after 2.a, and any harness re-run of step 2, keep the
edit.

The teammate session (binding ruling 1): plain Claude in the base image (the dry-run image for dry arms), the same
pinned model, `--setting-sources ""` (`BK_ISOLATED`), a fresh throwaway home (`Paths.teammate_home(k)`, wiped
before the try and removed once its transcripts are collected) and its own inbox (`Paths.inbox("teammate")`).
Neither is under the arm's mounts (its home and /work), so the arm can never read the prompt (review C-12); the
prompt's record lives under results. Its cost is HARNESS cost: `HandEdit.turns` (every try's turns, failed ones
included) goes to `evidence.finalise(extra_turns={"teammate": edit.turns})`, never with the arm's or the PO's.
On a fault the turns so far ride on the exception as `hand_edit_turns`.

Defence in depth (fix round 1): the prompt tells the teammate to ignore project instructions and method
workflows; the session runs in 2.1.281's safe mode (`CLAUDE_CODE_SAFE_MODE=1`: no CLAUDE.md, skills, plugins or
hooks); the repo's `.git` is mounted read-only for the turn (the commit happens later, in its own container); and
the scope plan rejects any change under a dot-directory (tool caches aside) or the arm's own method artefacts
(`denylist`, from its config). New ignored paths are removed; ignored paths that already existed are kept and
recorded. Files a commit hook adds are recorded (`hook_added`), never failed.

Fault precedence for a teammate turn (ruling 3): `auth_failed` (infra-auth) > a persisted credential > an off-pin
model anywhere in the evidence > the session's own outcome (`hand-edit`/`session`) > a pin report without
evidence. Only `hand-edit` faults with a signature in `RETRIED` get the second try; everything else (infra-auth,
model-pin, credential-persisted, precondition, recheck-unscoreable) restores `02-pre-edit` and propagates at once.
Each retry starts from `02-pre-edit` restored; after the last failure the tree is restored too.
"""
from __future__ import annotations
import gzip, json, os
from dataclasses import dataclass, field, asdict
from pathlib import Path

from runner import checklist, config, credentials, egress, faults, gitops, hidden, repo, session, transcripts
from runner.docker import Mount
from runner.faults import HarnessFault
from runner.paths import Paths

MESSAGE = "Let TROUPE_THEATRE set the default theatre"
PROMPT = (config.CONFIG_DIR / "teammate-prompt.md").read_text().split("-->", 1)[-1].strip() + "\n"
NEEDLE = "TROUPE_THEATRE"
PRE_EDIT = "02-pre-edit"
RETRIED = ("session", "scope", "commit", "probe", "changed-hidden-results")
PROBE_KEYS = ("env_default", "flag_wins", "unchanged_without_env")

PROBE_SH = r"""set -u
mkdir -p /tmp/t/.troupe /tmp/u/.troupe
printf 'a: 1\n' > /tmp/t/.troupe/troupe.yml; printf 'a: 2\n' > /tmp/u/.troupe/troupe.yml
a=$(TROUPE_THEATRE=/tmp/t uv run troupe config show a 2>/dev/null); ra=$?
b=$(TROUPE_THEATRE=/tmp/t uv run troupe config show --theatre /tmp/u a 2>/dev/null); rb=$?
c=$(env -u TROUPE_THEATRE uv run troupe config show --theatre /tmp/t a 2>/dev/null); rc=$?
jq -cn --arg a "$a" --arg b "$b" --arg c "$c" --argjson ra $ra --argjson rb $rb --argjson rc $rc \
  '{env_default:($ra==0 and $a=="1"), flag_wins:($rb==0 and $b=="2"), unchanged_without_env:($rc==0 and $c=="1")}'
"""


# --- pure ----------------------------------------------------------------------------------------------------

@dataclass
class ScopePlan:
    py: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)
    restore: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    removed_ignored: list[str] = field(default_factory=list)        # new ignored paths, removed
    ignored_preexisting: list[str] = field(default_factory=list)    # ignored before the turn: kept, not checked


# Tool caches: dot-directories whose untracked content is a side effect (removed), never a method's area.
TOOL_CACHES = (".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".tox", ".venv", ".uv-cache")


def denylist(arm: config.Arm) -> list[str]:
    """The arm's method artefacts in the repo, from its config: what its setup checklist hashes as the method's
    install (`checklist.effective_manifest_paths`), repo-relative entries only (`~/...` and absolute paths live
    outside the repo)."""
    return [m.rstrip("/") for m in checklist.effective_manifest_paths(arm) if not m.startswith(("~", "/"))]


def _denied(path: str, deny) -> bool:
    parts = path.rstrip("/").split("/")
    if any(d.startswith(".") and d not in TOOL_CACHES for d in parts[:-1]):      # a dot-directory
        return True
    return any(path == d or path.startswith(d + "/") for d in deny)


def _is_lock(path: str) -> bool:
    return path == "uv.lock" or path.endswith("/uv.lock")


def scope_plan(porcelain: str, deny: list[str] | tuple[str, ...] = ()) -> ScopePlan:
    """`git status --porcelain -uall` after the teammate's turn → what is in scope (Python files), what is a side
    effect (untracked non-Python files and directories — an untracked nested repository is listed as `dir/` —
    removed; a rewritten `uv.lock`: restored) and what is a violation (a change of ANY kind, Python included, under
    a dot-directory other than a tool cache or under a `deny` path — the arm's method artefacts, `denylist`; any
    other tracked non-Python change, a deletion, a rename/copy, an unmerged path, a quoted path, or no Python
    change at all; review C-11, fix round 1)."""
    plan = ScopePlan()
    for line in sorted(l for l in porcelain.splitlines() if l.strip()):
        code, path = line[:2], line[3:]
        if path.startswith('"'):
            plan.violations.append(f"{path} (unusual name)")      # git quoted it; never guessed at
        elif "U" in code or code in ("AA", "DD"):
            plan.violations.append(f"{path} (unmerged)")
        elif "R" in code or "C" in code:
            plan.violations.append(f"{path} (renamed or copied)")
        elif _denied(path, deny):
            plan.violations.append(f"{path} (method or tool area)")
        elif "D" in code:
            plan.violations.append(f"{path} (deleted)")
        elif path.endswith(".py"):
            plan.py.append(path)
        elif code == "??":
            plan.remove.append(path)                    # __pycache__, .pytest_cache, … : side effects, cleaned
        elif _is_lock(path):
            plan.restore.append(path)                   # `uv run` may rewrite the lock: a side effect, restored
        else:
            plan.violations.append(f"{path} (modified)")
    plan.violations.sort()
    if not plan.py and not plan.violations:
        plan.violations.append("no Python file changed")
    plan.py.sort(); plan.remove.sort(); plan.restore.sort()
    return plan


def clean_side_effects(p: Paths, deny: list[str] | tuple[str, ...] = (),
                       ignored_before: list[str] | None = None) -> ScopePlan:
    """The scope plan of the arm repo as it is now; with no violation, its side effects are cleaned (in
    containers, via gitops): untracked paths with `clean -ffd` (nested repositories too), the lock restored, and —
    given `ignored_before` (`gitops.ignored` before the turn) — every ignored path that is new since then removed
    with `clean -ffdX`. Ignored paths that already existed (e.g. the arm's `.venv`, which the teammate may have
    re-synced) are kept and recorded: deleting them would destroy the arm's state, and a path diff cannot see
    changes inside them."""
    plan = scope_plan(gitops.porcelain(p), deny)
    if not plan.violations:
        gitops.remove_untracked(p, plan.remove, dirs=True)
        gitops.checkout_paths(p, plan.restore)
        if ignored_before is not None:
            now = gitops.ignored(p)
            plan.removed_ignored = sorted(set(now) - set(ignored_before))
            plan.ignored_preexisting = sorted(set(now) & set(ignored_before))
            gitops.remove_ignored(p, plan.removed_ignored)
    return plan


def _assistant_blocks(ev) -> list[dict]:
    if not isinstance(ev, dict) or ev.get("type") != "assistant":
        return []
    msg = ev.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [c for c in content if isinstance(c, dict)] if isinstance(content, list) else []


def mentions(files: list[Path], needle: str) -> int:
    """How often `needle` appears in assistant text and tool inputs (never tool results: those are the arm
    reading the code, not the arm noticing; review C-10). A block seen twice — the same message id in the
    runner-captured stream and in the transcript — is counted once."""
    n, seen = 0, set()
    for f in files:
        with (gzip.open(f, "rt", errors="replace") if f.suffix == ".gz" else open(f, errors="replace")) as fh:
            for line in fh:
                if needle not in line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                blocks = _assistant_blocks(ev)
                mid = ev["message"].get("id") if blocks else None
                for c in blocks:
                    if mid:
                        key = (mid, json.dumps(c, sort_keys=True))
                        if key in seen:
                            continue
                        seen.add(key)
                    if c.get("type") == "text" and isinstance(c.get("text"), str):
                        n += c["text"].count(needle)
                    elif c.get("type") == "tool_use":
                        n += json.dumps(c.get("input")).count(needle)
    return n


def facts_from(*, probe_ok, non_py_mentions, session_mentions, po_mentions, teammate_test_kept) -> dict:
    """Detection facts: recorded, never scored."""
    return {"feature_kept": probe_ok, "documented_in": sorted(non_py_mentions),
            "mentioned_in_session": session_mentions > 0, "session_mentions": session_mentions,
            "raised_with_po": po_mentions > 0, "teammate_test_kept": teammate_test_kept}


def parse_probe(stdout: str) -> dict:
    """The probe's last stdout line as its three booleans; anything else is a failed probe with the reason."""
    lines = stdout.strip().splitlines()
    try:
        got = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        got = None
    if not isinstance(got, dict) or set(got) != set(PROBE_KEYS) or not all(isinstance(v, bool) for v in got.values()):
        return {**{k: False for k in PROBE_KEYS}, "error": f"unparseable probe output: {stdout[-300:]!r}"}
    return got


def probe_ok(probe: dict) -> bool:
    return all(probe.get(k) is True for k in PROBE_KEYS)


def compare(step1: dict[str, str], after: dict[str, str]) -> tuple[dict, list[str]]:
    """(differences, not compared). A harness flake ("flaky") in either record says nothing about the edit, so it
    is not compared; a test present in one record only is a difference."""
    diff, skipped = {}, []
    for t in sorted(set(step1) | set(after)):
        a, b = step1.get(t), after.get(t)
        if "flaky" in (a, b):
            skipped.append(t)
        elif a != b:
            diff[t] = [a, b]
    return diff, skipped


def _is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{path}"


# --- the edit ------------------------------------------------------------------------------------------------

@dataclass
class HandEdit:
    sha: str
    files: list[str]
    numstat: list
    probe: dict
    tries: int
    side_effects: dict
    turns: list = field(default_factory=list)     # every teammate turn, all tries: harness cost (Task 20)
    pin: dict = field(default_factory=dict)       # the landing try's pin report
    commit_files: list[str] = field(default_factory=list)   # what the commit actually holds (hooks may add)
    hook_added: list[str] = field(default_factory=list)     # commit_files the teammate did not change: recorded only


def _precondition(p: Paths) -> None:
    """The teammate commits straight to `main`: the arm's tree must be on `main` and clean, or the commit would
    carry the arm's own leftovers under Sam Teammate's name (or land on a feature branch)."""
    st = gitops.state(p)
    why = [w for w, bad in ((f"on branch {st.branch!r}, not main", st.branch != "main"),
                            ("the working tree is dirty", st.dirty)) if bad]
    g = p.repo / ".git"
    if g.is_symlink() or not g.is_dir():            # it is bind-mounted read-only for the turn: never via a link
        why.append(f"{g.name} is not a plain directory")
    if why:
        raise HarnessFault("hand-edit", "precondition", "; ".join(why))


def _fresh(home: Path) -> None:
    repo.remove_tree(home)
    (home / ".claude").mkdir(parents=True)


def _git_dir(p: Paths) -> Path:
    """m-2: the teammate's `.git` bind-mount source is arm-writable work: Docker resolves it on the HOST, so a link
    (or a `gitdir:` file) left by the arm could mount any host directory. lstat it: only a real directory directly
    in the repo that has a HEAD file is mounted. Follow-up 9: a link to a real git directory INSIDE the repo is repaired — the link is removed
    (never followed) and that directory moved into place as `.git` — and recorded as an arm violation; a link out of
    the repo, a file, or anything else stops for the owner (not a harness fault: the arm made it)."""
    import stat as _stat
    g = p.repo / ".git"
    try:
        st = os.lstat(g)
    except FileNotFoundError:
        raise checklist.NotReady(f"{g} is missing: nothing to mount for the teammate") from None
    repo_real = os.path.realpath(p.repo)
    if _stat.S_ISLNK(st.st_mode):
        target = os.path.realpath(g)
        inside = os.path.dirname(target) == repo_real and not os.path.islink(target)
        looks_git = os.path.isfile(os.path.join(target, "HEAD")) and not os.path.islink(os.path.join(target, "HEAD"))
        if not (inside and os.path.isdir(target) and looks_git):                          # round 2, item 4
            raise checklist.NotReady(f"{g} is a link out of the repo (or to no directory); refusing to mount or "
                                     f"follow it for the teammate — repair it (`runner shell`)")
        os.unlink(g)
        os.rename(target, g)
        checklist.record_arm_violation(p, {"kind": "link-in-repo", "path": str(g), "step": 2,
                                           "repaired": f"unlinked, {os.path.basename(target)} moved to .git"})
        st = os.lstat(g)
    if not _stat.S_ISDIR(st.st_mode) or os.path.realpath(g) != os.path.join(repo_real, ".git"):
        raise checklist.NotReady(f"{g} is not a real directory in the repo (a file the arm left); "
                                 f"refusing to mount it for the teammate — repair it (`runner shell`)")
    head = g / "HEAD"
    if os.path.islink(head) or not head.is_file():            # round 2, item 4: it must look like a git dir
        raise checklist.NotReady(f"{g} has no HEAD file: not a git directory; refusing to mount it for the teammate")
    return g


def teammate_env(pins: config.Pins, arm: config.Arm) -> dict[str, str]:
    """The teammate session's environment — the one `_teammate_turn` sends and the live probe (Task 25, P7) tests.
    BK_ISOLATED gives `--setting-sources ""`. CLAUDE_CODE_SAFE_MODE=1 is 2.1.281's `--safe-mode` (documented in its
    --help: CLAUDE.md, skills, plugins, hooks, custom commands and agents off; auth, model, built-in tools and
    permissions unchanged; "Sets CLAUDE_CODE_SAFE_MODE=1", and the binary reads that variable as the switch) — the
    env form needs no image rebuild. Whether it holds against a real repo is for the live probe (Task 25, P7)."""
    return credentials.session_env(pins, arm, role="teammate", isolated=True) | {
        "PYTHONDONTWRITEBYTECODE": "1", "CLAUDE_CODE_SAFE_MODE": "1"}


def _teammate_turn(ctx, k: int, out: Path, turns: list) -> transcripts.PinReport:
    p, pins, arm = ctx.paths, ctx.pins, ctx.arm
    git_dir = _git_dir(p)                      # before any mount is built (m-2)
    home = p.teammate_home(k)
    _fresh(home)
    before = transcripts.snapshot(home / ".claude")
    env = teammate_env(pins, arm)
    image = pins.images["dryrun"] if arm.dry else pins.images["base"]
    r, primary = None, None
    try:
        with egress.Stage(ctx.pass_, arm.name, "teammate", pins.egress_run_common, out / "egress.log") as st:
            t = session.Turn(ctx.pass_, arm.name, 2, k, 1, image, PROMPT, env,
                             [Mount(home, p.container_home, False), Mount(p.work, "/work", False),
                              Mount(git_dir, f"{p.container_repo}/.git", True)],   # the commit is later
                             st.net, True,
                             p.container_repo, p.inbox("teammate"), "teammate", arm.dry, home / ".claude")
            r = session.run_turn(t, ctx.cred, out, pins.limits.turn_seconds)
            turns.append(r)
    except BaseException as e:
        primary = e
        raise
    finally:                                   # the container has exited (run_turn stops it on every path)
        try:
            skipped: list[dict] = []
            files = transcripts.collect(home / ".claude", before, out / "transcripts" / f"t{k}", skipped=skipped)
            streams = {r.stream_path: r.outcome} if r is not None and r.stream_path else {}
            pin = transcripts.verify_pin(files, list(streams), pins, unsafe=skipped, stream_outcomes=streams)
            (out / f"model-pin-t{k}.json").write_text(pin.to_json())
            repo.remove_tree(home)             # throwaway: its transcripts are collected (kept if that failed)
        except Exception as ce:
            if primary is None:
                raise
            primary.add_note(f"collecting the teammate's evidence failed too: {ce!r}")   # never masks the turn's
    if r.outcome == "auth_failed":             # ruling 3: before anything else about the turn
        raise HarnessFault("infra-auth", "authentication_failed", f"teammate try {k}")
    if r.credential_files:                     # review S-3
        raise HarnessFault("credential-persisted", r.credential_files[0], ", ".join(r.credential_files))
    if pin.violations:                         # an off-pin model is never excused by the turn's outcome
        raise faults.classify_pin(pin, "teammate")
    if r.outcome != "ok":
        raise HarnessFault("hand-edit", "session", f"{r.outcome}: {(r.final_text or '')[:400]}")
    if (f := faults.classify_pin(pin, "teammate")):
        raise f
    if not pin.ok:
        raise HarnessFault("model-pin", "unverified", f"teammate: unverified streams {pin.unverified_streams}")
    return pin


def _work_entries(p: Paths) -> set[str]:
    return set(os.listdir(p.work)) if p.work.is_dir() else set()


def _land(ctx, k: int, step1_tests: dict[str, str], out: Path, pin, turns: list, work_before: set[str],
          ignored_before: list[str]) -> HandEdit:
    p = ctx.paths
    plan = clean_side_effects(p, denylist(ctx.arm), ignored_before)
    if plan.violations:
        raise HarnessFault("hand-edit", "scope", "; ".join(plan.violations))
    beside = sorted(_work_entries(p) - work_before)            # /work is the teammate's too: nothing may stay there
    for name in beside:
        entry = p.work / name
        if entry.is_dir() and not entry.is_symlink():
            repo.remove_tree(entry)               # never follows links
        else:
            entry.unlink()
    try:
        sha = gitops.commit_all(p, gitops.TEAMMATE, MESSAGE)   # in the arm's container: its hooks run
    except RuntimeError as e:
        raise HarnessFault("hand-edit", "commit", str(e)[:500]) from e
    landed = gitops.log(p, f"{sha}~1", sha)
    if gitops.main_sha(p) != sha or [c["author"] for c in landed] != [gitops.TEAMMATE[0]]:
        raise HarnessFault("hand-edit", "commit", f"expected one commit by {gitops.TEAMMATE[0]} on main at {sha}; "
                                                  f"main={gitops.main_sha(p)} log={landed}")
    prep = hidden.prepare(p, sha, "02-hand-edit", out)
    installed = bool(prep.prep.get("hidden", {}).get("ok"))
    probe = parse_probe(hidden.run_script(p, prep.hidden_copy, PROBE_SH))
    (out / "probe.json").write_text(json.dumps({**probe, "installed": installed}, indent=2))
    if not probe_ok(probe):
        raise HarnessFault("hand-edit", "probe", json.dumps({**probe, "installed": installed})[:500])
    recheck = hidden.run(p, prep.hidden_copy, 1, out / "recheck", install_failed=not installed)
    if not recheck.scoreable:
        raise HarnessFault("hand-edit", "recheck-unscoreable", str(recheck.attribution)[:500])
    diff, skipped = compare(step1_tests, recheck.tests)
    (out / "recheck.json").write_text(json.dumps({"step1": step1_tests, "after_edit": recheck.tests,
                                                  "differences": diff, "not_compared": skipped}, indent=2))
    if diff:
        raise HarnessFault("hand-edit", "changed-hidden-results", json.dumps(diff)[:500])
    ns = gitops.numstat(p, f"{sha}~1", sha)
    commit_files = sorted(f for _, _, f in ns)
    hook_added = sorted(set(commit_files) - set(plan.py))          # e.g. beads' hooks: recorded, never failed
    (out / "diff.patch").write_text(gitops.show(p, sha))
    side = {"removed": plan.remove, "restored": plan.restore, "removed_beside_repo": beside,
            "removed_ignored": plan.removed_ignored, "ignored_preexisting_not_checked": plan.ignored_preexisting}
    edit = HandEdit(sha, plan.py, ns, probe, k, side, list(turns), asdict(pin), commit_files, hook_added)
    (out / "edit.json").write_text(json.dumps({                                                   # review F-11
        "sha": sha, "author": gitops.TEAMMATE[0], "message": MESSAGE, "files": plan.py, "commit_files": commit_files,
        "hook_added": hook_added, "tries": k,
        "lines_added": sum(a for a, _, _ in ns), "lines_removed": sum(d for _, d, _ in ns), "numstat": ns,
        "side_effects": side, "harness_cost_usd": round(sum(t.cost_usd for t in turns), 6)}, indent=2))
    return edit


def _try(ctx, k: int, step1_tests: dict[str, str], out: Path, turns: list) -> HandEdit:
    work_before = _work_entries(ctx.paths)
    ignored_before = gitops.ignored(ctx.paths)
    pin = _teammate_turn(ctx, k, out, turns)
    return _land(ctx, k, step1_tests, out, pin, turns, work_before, ignored_before)


def _restore_keeping(p: Paths, exc: BaseException) -> None:
    """Restore the pre-edit state; a failure to do so is noted on `exc`, which the caller re-raises (never masked),
    and flagged as `exc.restore_failed`: the tree is then NOT the pre-edit state, so a retry must restore it first
    (`stepflow.hand_edit`) — `apply` re-snapshots 02-pre-edit from whatever tree it starts on."""
    try:
        repo.restore(p, PRE_EDIT)
    except Exception as e:
        exc.add_note(f"restoring {PRE_EDIT} failed too: {e!r}")
        exc.restore_failed = True


def apply(ctx, step1_tests: dict[str, str]) -> HandEdit:
    """The hand edit, landed and verified; `snapshot(2)` is its result. `step1_tests` is step 1's recorded hidden
    outcomes (`Summary.tests`). Raises `HarnessFault` (see the module docstring), with `hand_edit_turns`."""
    p = ctx.paths
    out = ctx.out / "hand-edit"; out.mkdir(parents=True, exist_ok=True)
    turns: list = []
    try:
        repo.recover(p)                        # before any home or work access outside gitops
        _precondition(p)
    except HarnessFault as f:
        f.hand_edit_turns = turns
        raise
    repo.snapshot(p, PRE_EDIT)
    for k in (1, 2):
        if k > 1:
            try:
                repo.restore(p, PRE_EDIT)      # every retry starts from the pre-edit state
            except Exception as e:             # 2026-10-02: a harness fault, never a traceback
                from runner import stepflow
                if not isinstance(e, stepflow.RESTORE_ERRORS):
                    raise
                f = stepflow.restore_fault(e)
                f.hand_edit_turns, f.restore_failed = turns, True
                raise f from e
        try:
            edit = _try(ctx, k, step1_tests, out, turns)
        except HarnessFault as f:
            f.hand_edit_turns = turns
            (out / f"try-{k}-failed.json").write_text(json.dumps({"kind": f.kind, "signature": f.signature,
                                                                  "detail": f.detail}, indent=2))
            if k == 2 or f.kind != "hand-edit" or f.signature not in RETRIED:
                _restore_keeping(p, f)
                raise
            if f.signature == "session" and ctx.pins.limits.transient_backoff:
                ctx.sleep(ctx.pins.limits.transient_backoff[0])
            continue
        except BaseException as e:
            _restore_keeping(p, e)
            raise
        repo.snapshot(p, 2)
        return edit
    raise AssertionError("unreachable")


# --- detection -----------------------------------------------------------------------------------------------

def detect(ctx, edit: HandEdit, end_sha: str, arm_files: list[Path] | None = None) -> dict:
    """At the end of step 2 (the scored run): is the feature still there, is it documented in any non-Python
    file, did the arm mention it (assistant text and tool inputs) or raise it with the PO, and is the teammate's
    test still in the tree. Recorded in `hand-edit/detection.json`, never scored. `arm_files` defaults to the
    step's runner-captured arm streams (`turns/arm-*.stream.jsonl.gz`) and collected transcripts
    (`transcripts/**/*.jsonl.gz`)."""
    p, out = ctx.paths, ctx.out / "hand-edit"
    out.mkdir(parents=True, exist_ok=True)
    prep = hidden.prepare(p, end_sha, "02-detect", out)
    probe_end = parse_probe(hidden.run_script(p, prep.hidden_copy, PROBE_SH))
    (out / "probe-end.json").write_text(json.dumps({**probe_end, "sha": end_sha,
                                                    "installed": bool(prep.prep.get("hidden", {}).get("ok"))}, indent=2))
    if arm_files is None:
        arm_files = sorted((ctx.out / "turns").glob("arm-*.stream.jsonl.gz")) + \
            sorted((ctx.out / "transcripts").rglob("*.jsonl.gz"))
    qa_f = ctx.out / "questions.jsonl"
    qa = [json.loads(l) for l in qa_f.read_text().splitlines() if l.strip()] if qa_f.exists() else []
    kept_files = set(gitops.ls_files(p, end_sha))
    teammate_tests = [f for f in edit.files if _is_test(f)]
    facts = facts_from(probe_ok=probe_ok(probe_end),
                       non_py_mentions=gitops.grep_files(p, end_sha, NEEDLE, ":!*.py"),
                       session_mentions=mentions(arm_files, NEEDLE),
                       po_mentions=sum(str(q.get("arm_message") or "").count(NEEDLE) for q in qa),
                       teammate_test_kept=bool(teammate_tests) and all(f in kept_files for f in teammate_tests))
    (out / "detection.json").write_text(json.dumps(facts, indent=2))
    return facts
