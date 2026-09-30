"""The setup flow, the per-arm checklist (machine + owner items), the setup manifest and the model-override record
(design §2, §6, §8; plan Task 9). Tasks 10–11 write the checklists and verify scripts; this is the machinery.

Order of `run_setup` (preflight M4, M5; B4):
  repo.init → GitHub PAT into the arm's home (before anything that may need `gh`) → in the setup egress stage:
  plugins → shell → agent turns (transcripts collected into 00-setup/transcripts/ and pin-verified with their
  streams) → post-shell → smoke (collected, verified, moved out of the arm's home) → setup commit → verify script
  + host checks (incl. `setup.origin-push`) → owner items → records → snapshot 1.

The arm's GitHub PAT lives in `state/<pass>/<arm>/home/.config/gh/hosts.yml` and, for an MCP arm,
`home/.bk-mcp.json` — both created 0600, never under results/. They also end up inside `snapshots/*.tar`, and
the arm's own tools and model can read them (accepted, OD16). NOTE for Task 21's secret scanner: those paths,
plus `00-setup/shell-history.txt` (the owner may type anything in `runner shell`) and every setup transcript.

After setup, any `runner shell` session marks setup dirty; `runner checklist` (a full re-check) clears it only
when green, and `require_clean_green` is the gate every run start calls (fix round 1).
"""
from __future__ import annotations
import dataclasses, json, os, re, stat, subprocess, time, uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from runner import commands, config, credentials, docker, egress, faults, gitops, images, repo, session, transcripts
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT

CHECKS_DIR = REPO_ROOT / "checklists"
PRINCIPLES = config.CONFIG_DIR / "project-principles.md"
MCP_DIR = config.CONFIG_DIR / "mcp"                       # OD24 B with MCP only: <arm>.json with ${GITHUB_PAT}
COMMAND_ARMS = {"openspec", "speckit", "speckitty", "ccsdd", "superpowers"}   # a slash command in entry/bug_entry/must_run
SMOKE_ARMS = {"superpowers"}                             # CANDIDATES §1.1 item 3 (Task 10 configures the prompt)
HISTORY_MAX = 16 * 1024 * 1024


class NotReady(RuntimeError):
    """Setup cannot start: a parked arm (no image in the lock) or no checklist for it."""


class SetupParked(NotReady):
    """An owner prompt during setup returned `owner.Park` (Task 23 fix round 1): setup ends as parked — never a crash,
    never read as an answer. The arm is parked; `runner setup --again` (or the next `run-pass`) redoes the setup."""

    def __init__(self, park):
        super().__init__(f"setup parked: {getattr(park, 'prompt', '?')} ({getattr(park, 'reason', '?')}): "
                         f"{getattr(park, 'context', '')}")
        self.park = park


def _unparked(got):
    from runner.owner import Park
    if isinstance(got, Park):
        raise SetupParked(got)
    return got


def needed_commands(arm: config.Arm) -> list[str]:
    """The slash commands `<arm>.entry-commands` requires installed: from entry, bug_entry, must_run, and for
    OD24 B the export trigger and the export command itself."""
    needed = [c.split()[0].lstrip("/") for c in (arm.entry, arm.bug_entry, *arm.must_run) if c.startswith("/")]
    if arm.export_after:
        needed += [arm.export_after.lstrip("/"), "speckit-taskstoissues"]
    return list(dict.fromkeys(needed))                     # once each, first-seen order (entry == bug_entry is common)


def effective_manifest_paths(arm: config.Arm) -> list[str]:
    """What `manifest_full` hashes: the arm's `manifest_paths`, plus the plugin cache on route A (marketplace)."""
    extra = ["~/.claude/plugins/cache"] if config.load_pins().plugin_route == "marketplace" and arm.plugins else []
    return list(arm.manifest_paths) + extra


def conditional_ids(arm: config.Arm) -> set[str]:
    """Host checks that are OMITTED when they would check nothing (Task 10 fix round 1): no setup prompts, an empty
    effective manifest list, no slash command needed. A checklist md documents them as `- (computed)` bullets,
    never as static ids, because whether they exist is computed from config (and, for the manifest, the route)."""
    return ({"setup.agent-turns", "setup.manifest-created"}
            | ({f"{arm.name}.entry-commands"} if arm.name in COMMAND_ARMS else set()))


def host_check_ids(arm: config.Arm) -> set[str]:
    """The ids `host_checks`, `_smoke` and `agent_turns_check` produce for this arm on the current route: the
    static ones plus the conditional ones that are not empty."""
    return ({"common.no-foreign-model-ids", "setup.origin-push"}                               # B4: every arm
            | ({f"{arm.name}.entry-commands"} if arm.name in COMMAND_ARMS and needed_commands(arm) else set())
            | ({"setup.manifest-created"} if effective_manifest_paths(arm) else set())
            | ({"setup.agent-turns"} if arm.setup_agent else set())
            | ({"github.issues-access"} if arm.tracker == "github" and not arm.dry else set())
            | ({f"{arm.name}.smoke"} if arm.name in SMOKE_ARMS or arm.smoke else set()))


class _HostChecks(Mapping):
    """Every configured arm, real and dry (B4: dry arms verify origin too): `host_check_ids` on the current route
    (conditional checks omitted when empty, Task 10 FR1). Loaded lazily per arm (fix round 1): a broken arm toml never breaks importing this module,
    it fails only when that arm is looked up."""
    def __getitem__(self, arm: str) -> set[str]:
        if not (config.ARMS_DIR / f"{arm}.toml").is_file():
            raise KeyError(arm)
        return host_check_ids(config.load_arm(arm))

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(f.stem for f in config.ARMS_DIR.glob("*.toml")))

    def __len__(self) -> int:
        return len(list(config.ARMS_DIR.glob("*.toml")))


HOST_CHECKS: Mapping[str, set[str]] = _HostChecks()

STATUSES = ("ok", "fail", "n/a")


@dataclass
class Check:
    """`status` is ok | fail | n/a (fix round 1). An n/a check is never `ok`; `green` accepts it only for dry arms.
    Records written before the status existed load with it derived from `ok`."""
    id: str
    ok: bool
    detail: str
    status: str = ""

    def __post_init__(self):
        if not self.status or (self.status == "ok" and not self.ok):
            self.status = "ok" if self.ok else "fail"
        if self.status not in STATUSES:
            raise ValueError(f"check {self.id}: unknown status {self.status!r}")
        if self.status != "ok":
            self.ok = False


@dataclass
class SetupResult:
    checks: list[Check]
    owner: dict[str, dict]
    green: bool
    owner_seconds: float


# ---- pure ------------------------------------------------------------------------------------------------
def green(checks: list[Check], owner_items_: dict[str, bool], dry: bool = False) -> bool:
    """Every machine check ok (n/a counts only for a dry arm) and every owner item ok."""
    passing = ("ok", "n/a") if dry else ("ok",)
    return bool(checks) and all(c.status in passing for c in checks) and all(owner_items_.values())


def owner_items(md: str) -> list[tuple[str, str]]:
    return re.findall(r"^- \[ \] (OV\d+): (.+)$", md, re.M)


def machine_ids(md: str) -> set[str]:
    """The `- \\`id\\`` bullets of the `## Machine-verified` section only (other sections may quote ids too)."""
    m = re.search(r"^## Machine-verified\s*$(.*?)(?=^## |\Z)", md, re.M | re.S)
    return set(re.findall(r"^- `([a-z0-9.-]+)`", m.group(1), re.M)) if m else set()


def computed_ids(md: str) -> set[str]:
    """The `- (computed) <id>` bullets of `## Machine-verified`: documented, but present only when not empty."""
    m = re.search(r"^## Machine-verified\s*$(.*?)(?=^## |\Z)", md, re.M | re.S)
    return set(re.findall(r"^- \(computed\) `([a-z0-9.-]+)`", m.group(1), re.M)) if m else set()


def missing_checks(md: str, checks: list[Check], expected: set[str] | frozenset = frozenset()) -> list[Check]:
    """A listed machine check that did not run is a failure: setup is never green by omission (e.g. a verify
    script that stopped half-way). `expected` adds the ids computed for this arm (`host_check_ids`), so a
    conditional check that should exist and did not run fails too, while one computed away is not missing."""
    produced = {c.id for c in checks}
    return [Check(i, False, "listed in the checklist but not produced")
            for i in sorted((machine_ids(md) | set(expected)) - produced)]


def model_ids_check(models: list[dict], accepted: list[str]) -> Check:
    """Aliases (opus/sonnet/haiku/inherit) are remapped by OD2's env; a FULL non-pinned model ID is not."""
    aliases = {"opus", "sonnet", "haiku", "inherit", "default"}
    bad = [m for m in models if m["model"] not in aliases and m["model"] not in accepted]
    return Check("common.no-foreign-model-ids", not bad,
                 "; ".join(f"{m['file']}: {m['model']}" for m in bad) or f"{len(models)} model settings, all aliases")


def gh_hosts_yml(pat: str) -> str:
    return f"github.com:\n    oauth_token: {pat}\n    git_protocol: https\n"


def skill_matches(invoked: set[str], expect: str) -> bool:
    return any(s == expect or s.split(":")[-1] == expect for s in invoked)


def parse_verify(arm_name: str, r: subprocess.CompletedProcess) -> list[Check]:
    """The verify-script protocol: one `{"id","ok","detail"}` object per line. A line that starts like an object
    but is not one fails; a crashed script, or one that printed nothing, fails too."""
    out: list[Check] = []
    for line in r.stdout.decode(errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            o = None
        if isinstance(o, dict) and set(o) == {"id", "ok", "detail"} and isinstance(o["id"], str) \
                and isinstance(o["ok"], bool) and isinstance(o["detail"], str):
            out.append(Check(o["id"], o["ok"], o["detail"]))
        else:
            out.append(Check(f"{arm_name}.verify-output", False, f"not a check: {line[:200]}"))
    if r.returncode != 0:
        out.append(Check(f"{arm_name}.verify-script", False,
                         f"exit {r.returncode}: {r.stderr.decode(errors='replace')[:300]}"))
    elif not out:
        out.append(Check(f"{arm_name}.verify-script", False, "exit 0: no checks printed"))
    return out


def manifest_check(pass_: str, arm_name: str, m: dict[str, str], missing: list[str] = ()) -> Check:
    """Setup created every configured manifest path (fix round 1: a path the method's docs say setup creates, and
    it did not, fails, naming it). `manifest.json` records the hashes as setup evidence. The pass-1-vs-pass-2
    comparison is gone with pass 2 (m-5, final fix batch)."""
    cid = "setup.manifest-created"
    if missing:
        return Check(cid, False, f"manifest path(s) not created by setup: {', '.join(missing)}")
    return Check(cid, True, f"{pass_}: recorded ({len(m)} files)")


def agent_turns_check(arm: config.Arm, record: list[dict]) -> Check | None:
    """Fix round 1: the LAST turn of each configured setup prompt (the prompt, then any owner replies) ended ok.
    No prompts configured → None: the check is omitted, never recorded ok (Task 10 fix round 1)."""
    cid = "setup.agent-turns"
    if not arm.setup_agent:
        return None
    last = {r["prompt"]: r for r in record}
    parts, ok = [], True
    for i in range(len(arm.setup_agent)):
        r = last.get(i)
        if r is None:
            ok = False; parts.append(f"prompt {i + 1}: never ran")
        else:
            ok = ok and r["outcome"] == "ok"
            parts.append(f"prompt {i + 1}: {r['outcome']} (turn {r['turn']})")
    return Check(cid, ok, "; ".join(parts))


def applied_model_env(pins: config.Pins, arm: config.Arm, pass_: str) -> dict[str, str]:
    """The model settings every arm session actually gets (OD2): the model-related part of `session_env`."""
    env = credentials.session_env(pins, arm, role="arm", isolated=False, pass_=pass_)
    return {k: v for k, v in env.items() if "MODEL" in k}


def ask_owner(owner, items: list[tuple[str, str]]) -> tuple[dict[str, dict], float]:
    """Every listed item gets a record; an item the owner did not answer is not ok."""
    answers = _unparked(owner.items(items)) if items else {}
    rec, secs = {}, 0.0
    for iid, _ in items:
        a = answers.get(iid)
        if a is None:
            rec[iid] = {"ok": False, "note": "no answer recorded"}
        else:
            rec[iid] = {"ok": bool(a[0]), "note": a[1]}
            secs += a[2]
    return rec, secs


# ---- containers ------------------------------------------------------------------------------------------
def _gh_env(p: Paths, arm: config.Arm) -> dict[str, str]:
    """GH_REPO for GitHub-tracker arms on passes with a repo (preflight M4: origin is local, B4)."""
    slug = config.github_slug(p.pass_, arm.name) if arm.tracker == "github" and not arm.dry else None
    return {"GH_REPO": slug} if slug else {}


def arm_spec(p: Paths, arm: config.Arm, cmd: list[str], *, network: str = "none", proxy: bool = False,
             ro: bool = True, extra: list[Mount] | None = None, name: str = "verify") -> RunSpec:
    """A container of the arm's image with its home and work mounted (read-only unless `ro=False`)."""
    pins = config.load_pins()
    return RunSpec(name=f"bk-{name}-{p.pass_}-{p.arm}-{uuid.uuid4().hex[:8]}",       # unique (preflight m13)
                   image=gitops.image_for(arm.name), label=f"bakeoff.run={p.pass_}/{p.arm}", network=network,
                   mounts=[Mount(p.home, p.container_home, ro), Mount(p.work, "/work", ro), *(extra or [])],
                   env={"HOME": p.container_home, "CLAUDE_CONFIG_DIR": f"{p.container_home}/.claude",
                        "PLUGIN_ROUTE": pins.plugin_route, **arm.env, **_gh_env(p, arm),
                        # what the verify scripts compare against — single source: pins.toml and gitops
                        "BK_EXPECT_CLAUDE_VERSION": f"{pins.claude_version} (Claude Code)",
                        "BK_EXPECT_GIT_NAME": gitops.IDENTITY[0], "BK_EXPECT_ORIGIN": gitops.ORIGIN},
                   workdir=p.container_repo, cmd=cmd, stdin=False, limits=pins.limits, proxy=proxy)


_arm_spec = arm_spec            # the plan's Tasks 25/26 text uses the private name (preflight m16)


def verify_spec(p: Paths, arm: config.Arm, mode: str) -> RunSpec:
    """`checklists/verify/<arm>.sh <setup|step>`: arm image, --network none, home and work read-only; the scripts
    and the principles (openspec.context compares against them, Task 10) mounted read-only."""
    return arm_spec(p, arm, ["bash", f"/checks/{arm.name}.sh", mode],
                    extra=[Mount(CHECKS_DIR / "verify", "/checks", True),
                           Mount(PRINCIPLES, "/setup/project-principles.md", True)])


def verify(p: Paths, arm: config.Arm, mode: str) -> list[Check]:
    repo.recover(p)
    return parse_verify(arm.name, docker.run(verify_spec(p, arm, mode), timeout=300))


_MANIFEST_SH = r"""cd "$1"; shift; for x in "$@"; do y="$x"; case "$x" in "~/"*) y="$HOME/${x#\~/}";; esac
  if [ -e "$y" ]; then find "$y" -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print0; else echo "$x" >&3; fi
  done 3>/tmp/missing | sort -z | xargs -0 -r sha256sum; sed 's/^/MISSING /' /tmp/missing >&2"""


def manifest_full(p: Paths, arm: config.Arm) -> tuple[dict[str, str], list[str]]:
    """SHA-256 of every regular file under the arm's `manifest_paths`, hashed in the container (never on the host),
    and the configured paths that do not exist."""
    repo.recover(p)
    paths_ = effective_manifest_paths(arm)
    r = docker.run(arm_spec(p, arm, ["bash", "-c", _MANIFEST_SH, "manifest", p.container_repo, *paths_], name="manifest"),
                   timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"manifest failed in container ({r.returncode}): {r.stderr.decode(errors='replace')[:300]}")
    missing = [l[8:] for l in r.stderr.decode(errors="replace").splitlines() if l.startswith("MISSING ")]
    return {line[66:]: line[:64] for line in r.stdout.decode(errors="replace").splitlines() if len(line) > 66}, missing


def manifest(p: Paths, arm: config.Arm) -> dict[str, str]:
    return manifest_full(p, arm)[0]


def _shell(p: Paths, arm: config.Arm, cmd: str, st: egress.Stage, log: Path) -> int:
    s = arm_spec(p, arm, ["bash", "-lc", cmd], network=st.net, proxy=True, ro=False, name="setup",
                 extra=[Mount(PRINCIPLES, "/setup/project-principles.md", True)])
    r = docker.run(s, timeout=1800)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"$ " + cmd.encode() + b"\n" + r.stdout + b"\n--- stderr ---\n" + r.stderr
                    + f"\nexit {r.returncode}\n".encode())
    return r.returncode


def install_plugins(p: Paths, arm: config.Arm, pass_: str, st: egress.Stage, out: Path) -> dict:
    """Route A (marketplace): install into the arm's home; a failure stops setup. Route B (plugin-dir, OD9 B):
    the same commands once, pass 1 only, into a scratch config dir — the recorded ergonomics check."""
    route, rec = config.load_pins().plugin_route, {}
    if not arm.plugins or (route == "plugin-dir" and pass_ != "pass1"):
        return rec
    target_home = p.home if route == "marketplace" else p.base / "marketplace-check"
    (target_home / ".claude").mkdir(parents=True, exist_ok=True)
    for i, pl in enumerate(arm.plugins):
        cmds = ([f"claude plugin marketplace add {pl.marketplace}"] if pl.marketplace else []) + [f"claude plugin install {pl.install}"]
        for c in cmds:
            s = RunSpec(name=f"bk-plugin-{p.pass_}-{p.arm}-{i}-{uuid.uuid4().hex[:8]}", image=gitops.image_for(arm.name),
                        label=f"bakeoff.run={p.pass_}/{p.arm}", network=st.net,
                        mounts=[Mount(target_home, p.container_home, False)],
                        env={"HOME": p.container_home, "CLAUDE_CONFIG_DIR": f"{p.container_home}/.claude"},
                        workdir=p.container_home, cmd=["bash", "-lc", c], stdin=False,
                        limits=config.load_pins().limits, proxy=True)
            t0 = time.monotonic(); r = docker.run(s, timeout=600)
            rec[c] = {"exit": r.returncode, "seconds": round(time.monotonic() - t0, 1),
                      "output": (r.stdout + r.stderr).decode(errors="replace")[-2000:]}
    out.mkdir(parents=True, exist_ok=True)
    (out / ("plugins.json" if route == "marketplace" else "marketplace-check.json")).write_text(json.dumps(rec, indent=2))
    if route == "marketplace" and any(v["exit"] != 0 for v in rec.values()):
        raise RuntimeError(f"{arm.name}: plugin install failed (see {out / 'plugins.json'})")
    return rec


_plugins = install_plugins      # the plan's Tasks 25/26 text uses the private name (preflight m16)


# ---- setup turns -----------------------------------------------------------------------------------------
def _check_turn(r: session.TurnResult, who: str) -> None:
    if r.outcome == "auth_failed":
        raise faults.HarnessFault("infra-auth", "authentication_failed", who)
    if r.credential_files:                                                       # review S-3
        raise faults.HarnessFault("credential-persisted", r.credential_files[0], ", ".join(r.credential_files))


def _collect(p: Paths, before: dict[str, str], dest: Path) -> tuple[list[Path], list[dict]]:
    skipped: list[dict] = []
    return transcripts.collect(p.config_dir, before, dest, skipped=skipped), skipped


def _verify_pin(files: list[Path], skipped: list[dict], streams: dict[Path, str], report: Path, who: str) -> None:
    """Preflight M5: ALWAYS with the paired runner-captured streams, unsafe= and stream_outcomes=. A violation
    is a harness fault (setup is re-run), never a setup result."""
    rep = transcripts.verify_pin(files, list(streams), config.load_pins(), unsafe=skipped, stream_outcomes=streams)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(rep.to_json())
    if not rep.ok:
        raise faults.classify_pin(rep, who) or faults.HarnessFault("model-pin", "unverified", f"{who}: see {report}")


def _agent_turns(p, arm, pass_, cred, owner, st, out) -> tuple[float, dict[Path, str], list[dict]]:
    """The `setup.agent` prompts as `role="setup"` turns in one resumed session; after each, the owner replies
    (sent as the next turn) or moves on. Returns the owner's seconds and {stream: outcome}."""
    pins, text, sid, n, owner_s = config.load_pins(), PRINCIPLES.read_text(), None, 0, 0.0
    queue = [(i, a.replace("{principles}", text)) for i, a in enumerate(arm.setup_agent)]
    streams: dict[Path, str] = {}
    record: list[dict] = []
    while queue:
        n += 1
        env = credentials.session_env(pins, arm, role="arm", isolated=False, resume=sid or "", pass_=pass_)
        prompt, message = queue.pop(0)
        t = session.Turn(pass_, arm.name, 0, 1, n, gitops.image_for(arm.name), message, env,
                         [Mount(p.home, p.container_home, False), Mount(p.work, "/work", False)], st.net, True,
                         p.container_repo, p.inbox("setup"), "setup", arm.dry, p.config_dir)
        r = session.run_turn(t, cred, out, pins.limits.turn_seconds)
        streams[r.stream_path] = r.outcome
        record.append({"turn": n, "prompt": prompt, "session_id": r.session_id, "outcome": r.outcome, "cost_usd": r.cost_usd,
                       "wall_seconds": round(r.wall_seconds, 1), "stream": str(r.stream_path.relative_to(out))})
        (out / "setup-turns.json").write_text(json.dumps(record, indent=2))
        _check_turn(r, f"setup turn {n}")
        sid = r.session_id or sid
        reply, secs = _unparked(owner.setup_reply(r.final_text))
        owner_s += secs
        if reply:
            queue.insert(0, (prompt, reply))           # the owner's reply belongs to the prompt it answers
    if not record:
        (out / "setup-turns.json").write_text("[]")
    return owner_s, streams, record


def _smoke(p, arm, pass_, cred, st, out) -> Check:
    """The documented smoke prompt in a fresh session outside the repo (`/work/smoke`); its stream must show a
    `Skill` tool_use naming `expect_skill`. Its transcripts are collected, pin-verified and moved out of the
    arm's home; `/work/smoke` is deleted."""
    pins, smoke_dir, sout = config.load_pins(), p.work / "smoke", out / "smoke"
    smoke_dir.mkdir()
    before = transcripts.snapshot(p.config_dir)
    env = credentials.session_env(pins, arm, role="arm", isolated=False, pass_=pass_)
    t = session.Turn(pass_, arm.name, 0, 1, 99, gitops.image_for(arm.name), arm.smoke.prompt, env,
                     [Mount(p.home, p.container_home, False), Mount(p.work, "/work", False)], st.net, True,
                     "/work/smoke", p.inbox("setup"), "setup", arm.dry, p.config_dir)
    try:
        r = session.run_turn(t, cred, sout, pins.limits.turn_seconds)
        moved, skipped = _collect(p, before, sout / "transcripts")
    finally:
        for rel in set(transcripts.snapshot(p.config_dir)) - set(before):     # move, don't copy, out of the home
            (p.config_dir / "projects" / rel).unlink(missing_ok=True)
        repo._rmtree(smoke_dir)
    _check_turn(r, "setup smoke")
    _verify_pin(moved, skipped, {r.stream_path: r.outcome}, sout / "model-pin.json", "setup smoke")
    invoked = transcripts.invoked_skills(r.stream_path)
    ok = skill_matches(invoked, arm.smoke.expect_skill)
    return Check(f"{arm.name}.smoke", ok, f"expected Skill {arm.smoke.expect_skill}; invoked: {sorted(invoked) or 'none'}; "
                                          f"outcome {r.outcome}; {len(moved)} transcript(s) moved to 00-setup/smoke/transcripts")


# ---- GitHub PAT (M4) -------------------------------------------------------------------------------------
def _write_new_private(path: Path, text: str) -> None:
    """Created 0600 in one step (never write-then-chmod); refuses an existing file or link."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)


def _install_github_pat(p: Paths, arm: config.Arm, pass_: str) -> bool:
    """GitHub-tracker arms on passes with a GitHub repo: the arm's PAT (keychain `bakeoff-gh-<pass>-<arm>`) into
    `home/.config/gh/hosts.yml`, and `home/.bk-mcp.json` when `config/mcp/<arm>.json` exists (OD24 B with MCP)."""
    if arm.tracker != "github" or arm.dry or not config.github_slug(pass_, arm.name):
        return False
    pat = credentials.github_pat(pass_, arm.name)
    gh = p.home / ".config" / "gh"
    for d in (gh.parent, gh):
        d.mkdir(mode=0o700, exist_ok=True)
    _write_new_private(gh / "hosts.yml", gh_hosts_yml(pat))
    mcp = MCP_DIR / f"{arm.name}.json"
    if mcp.exists():
        _write_new_private(p.home / ".bk-mcp.json", mcp.read_text().replace("${GITHUB_PAT}", pat))
    return True


def record_arm_violation(p: Paths, rec: dict) -> None:
    """An arm violation found by the harness's own file handling (follow-up 9): `results/<pass>/<arm>/
    arm-violations.jsonl`, the file orchestrate writes its arm violations to — never the harness ledger."""
    p.results.mkdir(parents=True, exist_ok=True)
    with open(p.results / "arm-violations.jsonl", "a") as fh:
        fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **rec}) + "\n")


def require_disc_pat(pass_: str, arm: config.Arm) -> str:
    """The arm's N.a discovery PAT, or `NotReady` (follow-up 6): a missing or timed-out keychain item is the owner's
    setup to finish (`runner github-plan <pass>`), never a runner crash. The value is never in the message."""
    try:
        return credentials.github_disc_pat(pass_, arm.name)
    except RuntimeError as e:
        raise NotReady(f"{arm.name}: the N.a discovery PAT (keychain bakeoff-gh-{pass_}-disc-{arm.name}) is not "
                       f"usable: {e}; see `runner github-plan {pass_}`") from None


def install_disc_pat(p: Paths, arm: config.Arm, pass_: str) -> bool:
    """N.a (final fix batch A3): the arm's discovery-repo PAT (keychain `bakeoff-gh-<pass>-disc-<arm>`) replaces the
    normal one in `home/.config/gh/hosts.yml` (and `home/.bk-mcp.json` for an MCP arm), created 0600 in one step.
    The home comes back from the pre-step snapshot at the end of N.a, so N.b has the normal PAT again. The files are
    arm-writable: a link is removed and replaced by the real file (an arm violation, follow-up 9), never written
    through; anything that is neither a link nor the expected type is refused (`NotReady`)."""
    if config.github_disc_slug(pass_, arm.name) is None:
        return False
    targets = [p.home / ".config" / "gh" / "hosts.yml"]
    mcp = MCP_DIR / f"{arm.name}.json"
    if mcp.exists():
        targets.append(p.home / ".bk-mcp.json")
    pat = require_disc_pat(pass_, arm)                   # before anything is touched
    # follow-up 9: a link the arm left is never written through — it is removed (never followed), the real
    # directory or file is written, and it is an arm violation; anything else of the wrong type is still refused
    for d in (p.home / ".config", p.home / ".config" / "gh"):
        if os.path.islink(d):
            os.unlink(d)
            record_arm_violation(p, {"kind": "link-in-home", "path": str(d), "repaired": "unlinked, real dir made"})
        elif os.path.lexists(d) and not stat.S_ISDIR(os.lstat(d).st_mode):
            raise NotReady(f"{d} is not a directory (nor a link): the arm changed its home; not writing the N.a PAT")
    for f in targets:
        if os.path.islink(f):
            os.unlink(f)
            record_arm_violation(p, {"kind": "link-in-home", "path": str(f), "repaired": "unlinked, real file written"})
        elif os.path.lexists(f) and not stat.S_ISREG(os.lstat(f).st_mode):
            raise NotReady(f"{f} is not a regular file (nor a link): the arm changed its home; not writing the N.a PAT")
    gh = p.home / ".config" / "gh"
    for d in (gh.parent, gh):
        d.mkdir(mode=0o700, exist_ok=True)
    for f in targets:
        f.unlink(missing_ok=True)
    _write_new_private(targets[0], gh_hosts_yml(pat))
    if len(targets) > 1:
        _write_new_private(targets[1], mcp.read_text().replace("${GITHUB_PAT}", pat))
    return True


# ---- host checks -----------------------------------------------------------------------------------------
def _origin_push(p: Paths) -> Check:
    """Preflight B4 (owner answer): `git push origin main` to the local bare origin succeeds and lands main."""
    r = gitops.git(p, "push", "-q", "origin", "main", write=True, check=False)
    if r.returncode != 0:
        return Check("setup.origin-push", False, r.stderr.decode(errors="replace")[-300:])
    main = gitops.main_sha(p)
    tracked = gitops.git(p, "rev-parse", "--verify", "-q", "refs/remotes/origin/main", check=False)
    got = tracked.stdout.decode(errors="replace").strip()
    return Check("setup.origin-push", bool(main) and got == main, f"origin/main {got or '<missing>'}, main {main}")


def issues_access_check(p: Paths, arm: config.Arm, pass_: str, st: egress.Stage | None) -> Check:
    """The arm's PAT can read issues and labels of its repo. No repo on this pass → n/a (never green for a real
    arm, fix round 1); no egress stage → fail."""
    slug = config.github_slug(pass_, arm.name)
    if slug is None:
        return Check("github.issues-access", False, f"not applicable: pass {pass_} has no GitHub repo", "n/a")
    if st is None:
        return Check("github.issues-access", False, "not checked: no setup egress stage")
    s = arm_spec(p, arm, ["bash", "-lc", f"gh issue list --repo {slug} --limit 1 && gh label list --repo {slug} --limit 1"],
                 network=st.net, proxy=True, name="ghcheck")
    r = docker.run(s, timeout=120)
    return Check("github.issues-access", r.returncode == 0, (r.stdout + r.stderr).decode(errors="replace")[-300:])


def host_checks(p: Paths, arm: config.Arm, pass_: str, smoke: Check | None, st: egress.Stage | None,
                owner=None) -> list[Check]:
    repo.recover(p)
    out: list[Check] = []
    p.setup_results.mkdir(parents=True, exist_ok=True)
    lst = commands.listing(p, arm)
    (p.setup_results / "installed-commands.json").write_text(json.dumps(sorted(lst.names), indent=2))
    (p.setup_results / "model-overrides.json").write_text(json.dumps(
        {"declared": lst.models, "effective": config.load_pins().model,
         "env": applied_model_env(config.load_pins(), arm, pass_),
         "note": "OD2: every session runs with `env` (and --model BK_MODEL), so every alias resolves to the pinned "
                 "model; the method's own choices are listed under `declared`"}, indent=2))
    out.append(model_ids_check(lst.models, config.load_pins().accepted_models))
    needed = needed_commands(arm) if arm.name in COMMAND_ARMS else []
    if needed:                                                   # nothing needed → omitted (Task 10 FR1)
        missing = sorted(set(needed) - lst.names)
        out.append(Check(f"{arm.name}.entry-commands", not missing, f"needed: {sorted(set(needed))}; missing: {missing or 'none'}"))
    if smoke is not None:
        out.append(smoke)
    if arm.tracker == "github" and not arm.dry:
        out.append(issues_access_check(p, arm, pass_, st))
    if effective_manifest_paths(arm):                            # empty list → omitted, no container (Task 10 FR1)
        m, missing = manifest_full(p, arm)
        out.append(manifest_check(pass_, arm.name, m, missing))
    else:
        m = {}
    (p.setup_results / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True))
    out.append(_origin_push(p))
    return out


# ---- the flows -------------------------------------------------------------------------------------------
def _refuse_parked(arm: config.Arm) -> None:
    """Never assume an arm has an image: read the lock (bmad is PARKED, Task 3)."""
    lk = images.lock()
    if arm.dry:
        if gitops.image_for(arm.name) not in lk.get("images", {}):
            raise NotReady(f"{arm.name}: image {gitops.image_for(arm.name)} is not in the lock")
        return
    e = lk.get("arms", {}).get(arm.name) or {}
    if not e.get("id") or e.get("error"):
        raise NotReady(f"{arm.name}: no built image in the lock ({e.get('error', 'missing')}); a parked arm cannot be set up")


def _read_md(arm_name: str) -> str:
    f = CHECKS_DIR / f"{arm_name}.md"
    if not f.is_file():
        raise NotReady(f"no checklist {f} (Tasks 10/11/24)")
    return f.read_text()


def _versions_image(arm: config.Arm) -> dict:
    lk, tag = images.lock(), gitops.image_for(arm.name)
    return lk.get("arms", {}).get(arm.name) or ({"image": tag, **lk.get("images", {}).get(tag, {})} if arm.dry else {})


def run_setup(pass_: str, arm_name: str, cred, owner) -> SetupResult:
    arm, p, pins = config.load_arm(arm_name), Paths(pass_, arm_name), config.load_pins()
    _refuse_parked(arm)
    md = _read_md(arm_name)
    repo.init(p, arm_name, pass_)
    _install_github_pat(p, arm, pass_)                  # M4: before plugins, shell and agent turns (BMAD's gh setup)
    out = p.setup_results; out.mkdir(parents=True, exist_ok=True)
    with egress.Stage(pass_, arm_name, "setup", pins.egress_setup_common + arm.egress_setup, out / "egress.log") as st:
        install_plugins(p, arm, pass_, st, out)
        for i, cmd in enumerate(arm.setup_shell, 1):
            if _shell(p, arm, cmd, st, out / "shell" / f"{i:02d}.log") != 0:
                raise RuntimeError(f"setup shell step {i} failed: {cmd} (see {out/'shell'})")
        before = transcripts.snapshot(p.config_dir)                             # M5
        owner_s, streams, turns = _agent_turns(p, arm, pass_, cred, owner, st, out)
        if streams:
            files, skipped = _collect(p, before, out / "transcripts")
            _verify_pin(files, skipped, streams, out / "model-pin.json", "setup")
        for i, cmd in enumerate(arm.setup_post_shell, len(arm.setup_shell) + 1):
            if _shell(p, arm, cmd, st, out / "shell" / f"{i:02d}.log") != 0:
                raise RuntimeError(f"setup post-shell step {i} failed: {cmd} (see {out/'shell'})")
        smoke = _smoke(p, arm, pass_, cred, st, out) if arm.smoke else None
        if gitops.state(p).dirty:
            gitops.commit_all(p, gitops.IDENTITY, f"Set up {arm.tool} {arm.version}")
        turns_check = agent_turns_check(arm, turns)
        checks = verify(p, arm, "setup") + host_checks(p, arm, pass_, smoke, st, owner) \
            + ([turns_check] if turns_check else [])
    checks += missing_checks(md, checks, host_check_ids(arm))
    rec, item_s = ask_owner(owner, owner_items(md))
    owner_s += item_s
    (out / "checklist.json").write_text(json.dumps([asdict(c) for c in checks], indent=2))
    (out / "owner-checklist.json").write_text(json.dumps(rec, indent=2))
    (out / "versions.json").write_text(json.dumps({"image": _versions_image(arm),
                                                   "plugins": [asdict(x) for x in arm.plugins],
                                                   "plugin_route": pins.plugin_route,
                                                   "owner_setup_seconds": owner_s}, indent=2))
    repo.snapshot(p, 1)
    ok = green(checks, {k: v["ok"] for k, v in rec.items()}, dry=arm.dry)
    return SetupResult(checks, rec, ok, owner_s)


def run_shell_only(pass_: str, arm_name: str, offline: bool = False) -> list[Check]:
    """Tests and probe P9: repo.init + plugins + shell + post_shell steps (no model turns), then the verify script.
    offline=True gives the setup stage an EMPTY allowlist, so any network need shows up as a refusal (review G6)."""
    arm, p, pins = config.load_arm(arm_name), Paths(pass_, arm_name), config.load_pins()
    _refuse_parked(arm)
    repo.init(p, arm_name, pass_)
    out = p.setup_results; out.mkdir(parents=True, exist_ok=True)
    hosts = [] if offline else pins.egress_setup_common + arm.egress_setup
    with egress.Stage(pass_, arm_name, "setup", hosts, out / "egress.log") as st:
        install_plugins(p, arm, "pass1", st, out)
        for i, cmd in enumerate(arm.setup_shell + arm.setup_post_shell, 1):
            if _shell(p, arm, cmd, st, out / "shell" / f"{i:02d}.log") != 0:
                raise RuntimeError(f"setup shell step {i} failed: {cmd} (see {out/'shell'})")
    return verify(p, arm, "setup")


def _is_dry(arm_name: str) -> bool:
    try:
        return config.load_arm(arm_name).dry
    except Exception:
        return False                              # unknown or broken config: the strict (real-arm) rule


def is_green(p: Paths) -> bool:
    """Both records green and setup not dirty (design §6; fix round 1). `require_clean_green` is the gate."""
    d = p.setup_results
    if is_dirty(p) or not (d / "checklist.json").exists() or not (d / "owner-checklist.json").exists():
        return False
    checks = [Check(**c) for c in json.loads((d / "checklist.json").read_text())]
    owner_ = {k: v["ok"] for k, v in json.loads((d / "owner-checklist.json").read_text()).items()}
    return green(checks, owner_, dry=_is_dry(p.arm))


# ---- dirty setup (fix round 1): any owner shell after setup needs a full re-check before a run -----------
def dirty_marker(p: Paths) -> Path:
    return p.base / "setup-dirty.json"


def is_dirty(p: Paths) -> bool:
    return os.path.lexists(dirty_marker(p))


def mark_dirty(p: Paths, why: str) -> None:
    p.base.mkdir(parents=True, exist_ok=True)
    dirty_marker(p).write_text(json.dumps({"since": datetime.now(timezone.utc).isoformat(), "why": why}) + "\n")


def require_clean_green(p: Paths) -> None:
    """THE gate for anything that starts a run (`run-arm` step 1, design §6): refuses a dirty or non-green setup."""
    if is_dirty(p):
        since = json.loads(dirty_marker(p).read_text()).get("since", "?")
        raise NotReady(f"{p.arm} ({p.pass_}): setup is dirty since {since} (owner shell); "
                       f"run `runner checklist {p.pass_} {p.arm}` for a full re-check")
    if not is_green(p):
        raise NotReady(f"{p.arm} ({p.pass_}): setup checklist is not green (design §6); run `runner setup`")


CARRIED = ("setup.agent-turns",)             # turn-based results a re-check cannot re-run without model turns

# Task 20 fix round 1 (MEDIUM): the arm commits under the same neutral `gitops.IDENTITY` as `recheck`'s own
# commit below and can write any subject line, including a forged copy of the "(owner shell adjustments)"
# suffix — so a commit's message is never trustworthy evidence that it came from an owner's `runner shell`
# session. This file is the harness's own record of the shas it actually committed, kept under
# `p.setup_results` (outside the arm's repo and its home, where the arm has no write access) so
# `evidence.finalise` can trust it without pattern-matching the arm's own git log.
OWNER_SHELL_COMMITS_FILE = "owner-shell-commits.json"


def record_owner_shell_commit(out: Path, sha: str) -> None:
    """Appends `sha` (just committed by `recheck` from an owner's `runner shell` edits) to the harness-side
    record under `out` (`p.setup_results`)."""
    f = out / OWNER_SHELL_COMMITS_FILE
    entries = json.loads(f.read_text()) if f.is_file() else []
    entries.append({"sha": sha, "at": datetime.now(timezone.utc).isoformat()})
    f.write_text(json.dumps(entries, indent=2))


def recheck(pass_: str, arm_name: str, owner=None) -> SetupResult:
    """`runner checklist`: a FULL re-verify after setup — verify script + host checks + missing checks — with the
    turn-based results (setup turns, smoke) carried over from setup. Commits what a shell session left, re-takes
    snapshot 1, rewrites checklist.json, and clears the dirty marker only when green."""
    arm, p, pins = config.load_arm(arm_name), Paths(pass_, arm_name), config.load_pins()
    _refuse_parked(arm)
    md = _read_md(arm_name)
    repo.recover(p)
    out = p.setup_results; out.mkdir(parents=True, exist_ok=True)
    copy_shell_history(p)
    prev = {c["id"]: Check(**c) for c in json.loads((out / "checklist.json").read_text())} \
        if (out / "checklist.json").is_file() else {}
    carried = [dataclasses.replace(prev[i], detail=f"(from setup) {prev[i].detail}")
               for i in (*CARRIED, f"{arm.name}.smoke") if i in prev]
    with egress.Stage(pass_, arm_name, "setup", pins.egress_setup_common + arm.egress_setup, out / "egress.log") as st:
        if gitops.state(p).dirty:
            sha = gitops.commit_all(p, gitops.IDENTITY, f"Set up {arm.tool} {arm.version} (owner shell adjustments)")
            record_owner_shell_commit(out, sha)
        checks = verify(p, arm, "setup") + host_checks(p, arm, pass_, None, st, owner) + carried
    checks += missing_checks(md, checks, host_check_ids(arm))
    (out / "checklist.json").write_text(json.dumps([asdict(c) for c in checks], indent=2))
    repo.snapshot(p, 1)
    rec = json.loads((out / "owner-checklist.json").read_text()) if (out / "owner-checklist.json").is_file() else {}
    ok = green(checks, {k: v["ok"] for k, v in rec.items()}, dry=arm.dry)
    if ok:
        dirty_marker(p).unlink(missing_ok=True)
    return SetupResult(checks, rec, ok, 0.0)


# ---- owner shell -----------------------------------------------------------------------------------------
HISTFILE = "/home/actor/.bash_history"


def interactive_shell(pass_: str, arm_name: str) -> int:
    """`runner shell`: an interactive bash in the arm image, setup egress, home and work writable. Runs as a
    child (not exec) so the egress stage is always torn down."""
    arm, p, pins = config.load_arm(arm_name), Paths(pass_, arm_name), config.load_pins()
    _refuse_parked(arm)
    repo.recover(p)
    mark_dirty(p, "runner shell")                   # before the shell starts: a crash mid-session is dirty too
    out = p.setup_results; out.mkdir(parents=True, exist_ok=True)
    with egress.Stage(pass_, arm_name, "setup", pins.egress_setup_common + arm.egress_setup, out / "egress.log") as st:
        s = arm_spec(p, arm, ["bash", "-l"], network=st.net, proxy=True, ro=False, name="shell",
                     extra=[Mount(PRINCIPLES, "/setup/project-principles.md", True)])
        s = dataclasses.replace(s, stdin=True, env={**s.env, "HISTFILE": HISTFILE,
                                                    "TERM": os.environ.get("TERM", "xterm")})
        argv = docker.run_argv(s)
        argv.insert(argv.index("-i") + 1, "-t")
        return subprocess.call(argv)


def copy_shell_history(p: Paths) -> bool:
    """`home/.bash_history` → `00-setup/shell-history.txt`, read without following links (the arm's home is
    arm-controlled): a regular, single-link file of at most HISTORY_MAX bytes, or nothing is copied."""
    try:
        fd = os.open(p.home / ".bash_history", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        st_ = os.fstat(fd)
        if not stat.S_ISREG(st_.st_mode) or st_.st_nlink != 1 or st_.st_size > HISTORY_MAX:
            return False
        chunks, size = [], 0
        while size <= HISTORY_MAX and (b := os.read(fd, 1 << 20)):
            chunks.append(b); size += len(b)
        data = b"".join(chunks)
    finally:
        os.close(fd)
    p.setup_results.mkdir(parents=True, exist_ok=True)
    (p.setup_results / "shell-history.txt").write_bytes(data[:HISTORY_MAX])
    return True
