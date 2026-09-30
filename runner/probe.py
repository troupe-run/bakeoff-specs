"""Owner-run live probe (Task 25): the first real Claude Code 2.1.281 use, checking the assumptions the runner was
built on. `runner probe` asks the owner, reads the keychain credential and runs `with_model` then `no_model`;
`runner probe --no-model` runs only `no_model` (no confirm, no credential). Every probe writes
`results/probe/P<n>.json`; `report` writes `results/probe/probe.md` with the corrections the owner applies.

Namespaces: the model probes use `probe-model` (so P9's setup runs, which start from nothing, never wipe their
evidence); P9 uses `probe` (online) and `probe-offline` (the brief's names). Every model turn runs inside an egress
stage built exactly as production builds it (run stage = `pins.egress_run_common` + the arm's `egress_run`).

The raw token is never read here: token searches go through `runner.secrets` (its only reader, enforced by a test).
"""
from __future__ import annotations
import gzip, json, os, re, shutil, stat, uuid
from pathlib import Path
from typing import Any, Iterable

from runner import (checklist, commands, config, credentials, docker, egress, gitops, handedit, paths, po, repo,
                    secrets, session, transcripts)
from runner.credentials import Credential
from runner.docker import Mount, RunSpec
from runner.paths import Paths

NS = "probe-model"                 # the model probes' namespace (see the module docstring)
SETUP_NS, OFFLINE_NS = "probe", "probe-offline"
TURN_SECONDS = 1800                # a probe turn is tiny; far below limits.turn_seconds
PINEAPPLE_MD = "Always answer PINEAPPLE.\n"
TELEMETRY_WORDS = ("analytics", "posthog", "sentry", "telemetry")
HELP_COMMANDS = {"speckitty": ["bd create --help", "spec-kitty --help", "spec-kitty tracker --help"],
                 "openspec": ["openspec config --help"]}
TELEMETRY_GREP = ("grep -rIilE 'telemetry|analytics|posthog|sentry' /opt /usr/local/lib/node_modules "
                  "2>/dev/null | head -50")


def out_dir() -> Path:
    return paths.RESULTS / "probe"


# ---- pure verdicts ----------------------------------------------------------------------------------------------
def transcript_layout(cfg: Path, cwd: str, sid: str) -> dict[str, Any]:
    """P1 (review C-6): where the fake puts a transcript — `projects/<cwd with / → ->/<session>.jsonl`."""
    rel = f"projects/{cwd.replace('/', '-')}/{sid}.jsonl"
    return {"expected": rel, "found": (cfg / rel).exists()}


def find_transcripts(cfg: Path, sid: str) -> list[str]:
    """Where `<sid>.jsonl` really is under `cfg/projects` (relative to cfg), whatever the layout."""
    root = cfg / "projects"
    return sorted(str(f.relative_to(cfg)) for f in transcripts.safe_files(root) if f.name == f"{sid}.jsonl")


def files_containing(root: Path, needle: bytes) -> list[str]:
    """Regular files under `root` (relative names only) whose bytes contain `needle`. Never follows a link and
    never opens anything but a regular file (a FIFO would block)."""
    hits = []
    for dirpath, _dirs, filenames in os.walk(root, followlinks=False):
        for f in filenames:
            p = Path(dirpath) / f
            try:
                if not stat.S_ISREG(os.lstat(p).st_mode):
                    continue
                fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except OSError:
                continue
            with os.fdopen(fd, "rb") as fh:
                if needle in fh.read():
                    hits.append(str(p.relative_to(root)))
    return sorted(hits)


def export_route(skill_text: str) -> str:
    """P11 (OD24): does speckit's taskstoissues skill use the GitHub MCP server or `gh`?"""
    if "mcp__github" in skill_text or "github-mcp" in skill_text.lower():
        return "mcp"
    if re.search(r"\bgh issue create\b", skill_text):
        return "gh"
    return "unknown"


def transcript_models(files: Iterable[Path]) -> list[str]:
    """Every `message.model` of an assistant event in these JSONL files (plain or .gz), sorted, once each."""
    found: set[str] = set()
    for f in files:
        with (gzip.open(f, "rt", errors="replace") if f.suffix == ".gz" else open(f, errors="replace")) as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict) and ev.get("type") == "assistant":
                    m = (ev.get("message") or {}).get("model")
                    if isinstance(m, str):
                        found.add(m)
    return sorted(found)


def models_pinned(models: list[str], accepted: list[str]) -> bool:
    """At least one model seen, and every one accepted (no transcript proves nothing)."""
    return bool(models) and set(models) <= set(accepted)


def hard_linked(root: Path) -> list[str]:
    """P1b: regular files under `root` with st_nlink > 1 (Claude Code must never hard-link transcripts)."""
    out = []
    for dirpath, _dirs, filenames in os.walk(root, followlinks=False):
        for f in filenames:
            p = Path(dirpath) / f
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
                out.append(str(p.relative_to(root)))
    return sorted(out)


def save_stream_if_clean(src: Path, dest: Path, literals: list[str]) -> dict[str, Any]:
    """P1a: copy the real stream (gzip, as session writes it) to `dest` only when the secret scan (gzip
    decompressed; the known values, their encodings and token shapes) finds nothing. Findings are named by
    place and kind only."""
    findings = secrets.scan_files([src], literals)
    if findings:
        return {"saved": False, "findings": secrets.describe(findings)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return {"saved": True, "path": str(dest)}


def auth_shape(text: str) -> str | None:
    """The `session.AUTH_FAILURE_SHAPES` prefix the text starts with (stripped), else None — session's rule."""
    t = (text or "").strip()
    return next((s for s in session.AUTH_FAILURE_SHAPES if t.startswith(s)), None)


def auth_case(r: session.TurnResult) -> dict[str, Any]:
    """P1c: what one auth-failure turn really said, and whether session's shapes recognise it."""
    shape = auth_shape(r.final_text)
    return {"outcome": r.outcome, "final_text": r.final_text,
            "retry_errors": [str(e.get("error")) for e in r.retries if isinstance(e, dict)],
            "shape": shape, "matches_shape": shape is not None}


def answered_ok(text: str) -> bool:
    return re.search(r"\bok\b", text or "", re.IGNORECASE) is not None


def said_pineapple(text: str) -> bool:
    return "pineapple" in (text or "").lower()


def tools_verdict(init_tools: list[str] | None, allowed: list[str], disallowed: list[str]) -> dict[str, Any]:
    """P7: `init.tools` is exactly the `--tools` list and holds none of `--disallowedTools`."""
    got = set(init_tools or [])
    v: dict[str, Any] = {"missing": sorted(set(allowed) - got), "extra": sorted(got - set(allowed)),
                         "disallowed_present": sorted(got & set(disallowed))}
    v["confirmed"] = not (v["missing"] or v["extra"] or v["disallowed_present"])
    return v


def plugin_loaded(init: dict[str, Any], name: str) -> bool:
    """P5 route B: the plugin is listed in `init.plugins`, or one of its skills/commands (`<name>:…`) in init."""
    if any(isinstance(p, dict) and p.get("name") == name for p in init.get("plugins") or []):
        return True
    return any(isinstance(x, str) and x.startswith(f"{name}:")
               for k in ("skills", "slash_commands") for x in init.get(k) or [])


def plugin_arms() -> dict[str, str]:
    """P5 (controller ruling 1): every arm with plugins → "probe", or "parked" by its config flag."""
    out = {}
    for a in config.all_arms():
        arm = config.load_arm(a)
        if arm.plugins:
            out[a] = "parked" if arm.parked else "probe"
    return out


def role_envs(pins: config.Pins, arm: config.Arm) -> dict[str, dict[str, str]]:
    """P7 (controller ruling 2): the PO's and the teammate's env, built by the functions production calls."""
    return {"po": po.po_env(pins, arm), "teammate": handedit.teammate_env(pins, arm)}


def run_hosts(log: str) -> list[str]:
    return sorted({h for h, _ in egress.decisions(log)})


def hosts_outside(log: str, patterns: list[str]) -> list[str]:
    """P8: hosts in the proxy log (allowed or refused) that no pattern allows."""
    return [h for h in run_hosts(log) if not any(re.match(x, h) for x in patterns)]


def manifest_not_created(configured: list[str], missing: list[str]) -> list[str]:
    """P9 (ruling 4b): configured manifest paths that do not exist after setup (the repo starts empty, so these
    are exactly the ones setup did not create), in configured order."""
    gone = set(missing)
    return [m for m in configured if m in gone]


def telemetry_mentions(text: str) -> list[str]:
    low = text.lower()
    return [w for w in TELEMETRY_WORDS if w in low]


# ---- credentials for P1c (no quota: both fail before any model call) ---------------------------------------------
class _NoCredential(Credential):
    """Sends an empty first stdin line, so bk-claude-turn hands Claude an EMPTY fd 3 — "no credential" — without
    touching production code. Its scanner value is a random nonce nobody writes, so session's post-turn
    credential-file scan stays meaningful (an empty needle would match every file)."""
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(f"probe-no-credential-{uuid.uuid4().hex}")

    def payload(self) -> bytes:
        return b"\n"


def no_credential() -> Credential:
    return _NoCredential()


def bogus_token() -> str:
    """Syntactically plausible (sk-ant-oat01- + ~100 url-safe chars) and recognisably FAKE."""
    return "sk-ant-oat01-PROBEFAKE" + uuid.uuid4().hex + uuid.uuid4().hex + uuid.uuid4().hex[:24] + "-AA"


# ---- effectful helpers --------------------------------------------------------------------------------------------
def _save(name: str, data: dict[str, Any]) -> dict[str, Any]:
    o = out_dir()
    o.mkdir(parents=True, exist_ok=True)
    (o / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))
    return data


def _fresh(p: Paths) -> None:
    if p.base.exists():
        repo.remove_tree(p.base)
    repo.init(p, p.arm, p.pass_)


def _turn(p: Paths, st: egress.Stage, cred: Credential, n: int, msg: str, env: dict[str, str], *, image: str,
          out: Path, home: Path | None = None) -> session.TurnResult:
    h = home or p.home
    t = session.Turn(pass_=p.pass_, arm=p.arm, step=0, attempt=1, n=n, image=image, message=msg, env=env,
                     mounts=[Mount(h, p.container_home, False), Mount(p.work, "/work", False)], network=st.net,
                     proxy=True, workdir=p.container_repo, inbox_dir=p.inbox("probe"), role="probe", dry=False,
                     config_dir=h / ".claude")
    return session.run_turn(t, cred, out, TURN_SECONDS)


def _brief(r: session.TurnResult) -> dict[str, Any]:
    return {"outcome": r.outcome, "session_id": r.session_id, "final_text": r.final_text[:2000],
            "cost_usd": r.cost_usd, "stream": str(r.stream_path) if r.stream_path else None}


def _pin(files: list[Path], r: session.TurnResult, skipped: list[dict[str, Any]], pins: config.Pins) -> Any:
    stream_files = [r.stream_path] if r.stream_path else []
    outcomes: dict[Path | str, str] = {f: r.outcome for f in stream_files}
    rep = transcripts.verify_pin(files, stream_files, pins, unsafe=skipped, stream_outcomes=outcomes)
    return json.loads(rep.to_json())


def _auth_cases(p: Paths, st: egress.Stage, image: str, env: dict[str, str]) -> dict[str, Any]:
    """P1c: two turns that spend no quota, in their own throwaway home (never the probe's config dir)."""
    home = p.base / "auth-home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    bogus = bogus_token()
    rec: dict[str, Any] = {}
    for n, (case, cred) in enumerate((("no_credential", no_credential()),
                                      ("bogus_token", credentials.Credential(bogus))), start=90):
        r = _turn(p, st, cred, n, "Reply with the word ok", env, image=image, out=out_dir() / "P1c", home=home)
        rec[case] = auth_case(r)
    rec["bogus_token_on_disk"] = files_containing(home, bogus.encode())
    rec["hard_linked"] = hard_linked(home / ".claude")
    del bogus
    return rec


def with_model(cred: Credential) -> dict[str, Any]:
    """P1–P8 and P10: real model turns (a little quota), then the on-disk token check."""
    pins, control = config.load_pins(), config.load_arm("control")
    res: dict[str, Any] = {}
    o = out_dir()
    p = Paths(NS, "control")
    _fresh(p)
    base = pins.images["base"]

    def env(**k: Any) -> dict[str, str]:
        return credentials.session_env(pins, control, role="probe", **k)

    run_log = o / "egress-run.log"
    with egress.Stage(NS, "control", "run", pins.egress_run_common + control.egress_run, run_log) as st:
        auth = _auth_cases(p, st, base, env(isolated=False))
        _save("P1c", auth)

        r1 = _turn(p, st, cred, 1, "Reply with the word ok", env(isolated=False), image=base, out=o)
        skipped: list[dict[str, Any]] = []
        files = transcripts.collect(p.config_dir, {}, o / "P1" / "transcripts", skipped=skipped)
        models = transcript_models(files)
        res["P1"] = _save("P1", {
            **_brief(r1), "init_model": r1.init.get("model"), "transcript_models": models,
            "accepted_models_should_be": models,
            "layout": transcript_layout(p.config_dir, p.container_repo, r1.session_id or ""),
            "found_at": find_transcripts(p.config_dir, r1.session_id or ""),
            "stream_saved": save_stream_if_clean(r1.stream_path, o / "P1-stream.jsonl.gz",
                                                 secrets.literals(cred, keychain=False))
            if r1.stream_path else {"saved": False, "findings": "no stream"},
            "auth_failures": auth})

        r2 = _turn(p, st, cred, 2, "What word did you reply?", env(isolated=False, resume=r1.session_id or ""),
                   image=base, out=o)
        res["P2"] = _save("P2", {**_brief(r2), "ok": answered_ok(r2.final_text)})

        before = transcripts.snapshot(p.config_dir)
        r3 = _turn(p, st, cred, 3, "Use the Task tool with model haiku to start a subagent that replies sub-ok; "
                                   "tell me its reply.", env(isolated=False), image=base, out=o)
        skipped = []
        files = transcripts.collect(p.config_dir, before, o / "P3", skipped=skipped)
        sub = [f for f in files if "subagents" in f.parts]
        res["P3"] = _save("P3", {**_brief(r3), "subagent_files": [str(f) for f in sub],
                                 "subagent_models": transcript_models(sub),
                                 "pinned": models_pinned(transcript_models(sub), pins.accepted_models),
                                 "pin_report": _pin(files, r3, skipped, pins)})

        agents = p.repo / ".claude" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "cheap.md").write_text("---\nname: cheap\ndescription: replies cheap-ok\nmodel: claude-haiku-4-5\n"
                                         "---\nReply with cheap-ok.\n")
        before = transcripts.snapshot(p.config_dir)
        r4 = _turn(p, st, cred, 4, "Use the Task tool with the cheap agent and tell me its reply.", env(isolated=False),
                   image=base, out=o)
        skipped = []
        files = transcripts.collect(p.config_dir, before, o / "P3b", skipped=skipped)
        sub = [f for f in files if "subagents" in f.parts]
        res["P3b"] = _save("P3b", {**_brief(r4), "subagent_models": transcript_models(sub),
                                   "full_id_escaped_remap": bool(sub) and not models_pinned(transcript_models(sub),
                                                                                            pins.accepted_models),
                                   "pin_report": _pin(files, r4, skipped, pins),
                                   "note": "a violation here confirms full IDs escape the alias remap (OD2, F-6)"})

        r5 = _turn(p, st, cred, 5, "Use the AskUserQuestion tool to ask me red or blue.", env(isolated=False),
                   image=base, out=o)
        res["P4"] = _save("P4", {**_brief(r5), "permission_denials": r5.permission_denials,
                                 "disallowed": pins.disallowed_tools})

        (p.repo / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
        (p.repo / ".claude" / "commands" / "hello.md").write_text("Reply with hello-ok.\n")
        (p.repo / ".claude" / "skills" / "greet").mkdir(parents=True, exist_ok=True)
        (p.repo / ".claude" / "skills" / "greet" / "SKILL.md").write_text(
            "---\nname: greet\ndescription: replies greet-ok\n---\nReply with greet-ok.\n")
        r6 = _turn(p, st, cred, 6, "/hello", env(isolated=False), image=base, out=o)
        r6b = _turn(p, st, cred, 7, "/greet", env(isolated=False), image=base, out=o)
        res["P6"] = _save("P6", {"command": "hello-ok" in r6.final_text, "skill_as_slash": "greet-ok" in r6b.final_text,
                                 "command_turn": _brief(r6), "skill_turn": _brief(r6b)})

        (p.repo / "CLAUDE.md").write_text(PINEAPPLE_MD)
        tools = "Read,Glob,Grep"
        rc = _turn(p, st, cred, 8, "Say hi.", env(isolated=False), image=base, out=o)
        r7 = _turn(p, st, cred, 9, "Say hi.", env(isolated=True, tools=tools), image=base, out=o)
        p7: dict[str, Any] = {
            "control_not_isolated": {**_brief(rc), "said_pineapple": said_pineapple(rc.final_text)},
            "setting_sources_empty": {**_brief(r7), "init_tools": r7.init.get("tools"),
                                      "tools": tools_verdict(r7.init.get("tools"), tools.split(","),
                                                             pins.disallowed_tools),
                                      "said_pineapple": said_pineapple(r7.final_text)}}
        for n, (role, role_env) in enumerate(role_envs(pins, control).items(), start=10):
            rr = _turn(p, st, cred, n, "Say hi.", role_env, image=base, out=o)
            p7[role] = {**_brief(rr), "init_tools": rr.init.get("tools"), "said_pineapple": said_pineapple(rr.final_text),
                        "env_keys": sorted(role_env)}
        p7["isolated_ignored_claude_md"] = not p7["setting_sources_empty"]["said_pineapple"]
        res["P7"] = _save("P7", p7)

    res["P5"] = _save("P5", _p5(cred, pins))
    logs = {"run": run_log, **{f"P5-run-{a}": o / "P5" / f"egress-run-{a}.log" for a, s in plugin_arms().items()
                               if s == "probe"}}
    p8 = {}
    for k, f in logs.items():
        text = f.read_text() if f.exists() else ""
        p8[k] = {"hosts": run_hosts(text), "outside_run_common": hosts_outside(text, pins.egress_run_common)}
    res["P8"] = _save("P8", p8)

    dirs = [p.config_dir] + [Paths(NS, a).config_dir for a, s in plugin_arms().items() if s == "probe"]
    lits = secrets.literals(cred, keychain=False)
    res["P10"] = _save("P10", {str(d): {"files_with_token": secrets.credential_files(d, cred, 0.0),
                                        "scan_findings": secrets.describe(secrets.scan_tree(d, lits))}
                               for d in dirs})
    res["P1"]["hard_linked"] = {str(d): hard_linked(d) for d in dirs}
    _save("P1", res["P1"])
    return res


def _p5(cred: Credential, pins: config.Pins) -> dict[str, Any]:
    """Route A (marketplace install into a scratch config, setup egress) and route B (a session with the arm's
    production env — `--plugin-dir` under the plugin-dir route — in the arm image, run egress)."""
    rec: dict[str, Any] = {"route": pins.plugin_route}
    o = out_dir() / "P5"
    for name, state in plugin_arms().items():
        if state == "parked":
            rec[name] = "parked"
            continue
        arm, pp = config.load_arm(name), Paths(NS, name)
        _fresh(pp)
        entry: dict[str, Any] = {"subdirs": {pl.name: pl.subdir for pl in arm.plugins}}
        try:
            with egress.Stage(NS, name, "setup", pins.egress_setup_common + arm.egress_setup,
                              o / f"egress-setup-{name}.log") as st:
                a = checklist.install_plugins(pp, arm, "pass1", st, o / name)
            entry["route_a"] = {"ok": bool(a) and all(v["exit"] == 0 for v in a.values()), "commands": a}
        except Exception as e:                                      # recorded; route B still runs
            entry["route_a"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
        env = credentials.session_env(pins, arm, role="arm", isolated=False, pass_=NS)
        with egress.Stage(NS, name, "run", pins.egress_run_common + arm.egress_run, o / f"egress-run-{name}.log") as st:
            r = _turn(pp, st, cred, 20, "List your available skills by name only.", env,
                      image=gitops.image_for(name), out=o / name)
        entry["route_b"] = {**_brief(r), "plugin_dirs": env.get("BK_PLUGIN_DIRS"),
                            "loaded": {pl.name: plugin_loaded(r.init, pl.name) for pl in arm.plugins},
                            "init_plugins": r.init.get("plugins"), "init_skills": r.init.get("skills"),
                            "init_slash_commands": r.init.get("slash_commands")}
        rec[name] = entry
    return rec


def container_text(image: str, cmd: str) -> str:
    """A short, network-less container of `image` running `cmd`; the last 6000 characters of its output."""
    s = RunSpec(name=f"bk-probe-{uuid.uuid4().hex[:8]}", image=image, label="bakeoff.run=probe/help", network="none",
                mounts=[], env={}, workdir="/tmp", cmd=["bash", "-lc", cmd], stdin=False,
                limits=config.load_pins().limits, proxy=False)
    r = docker.run(s, timeout=120)
    out: bytes = r.stdout + r.stderr
    return out.decode(errors="replace")[-6000:]


def _err(e: BaseException) -> dict[str, str]:
    return {"error": f"{type(e).__name__}: {e}"[:500]}


def _issues_access(p: Paths, arm: config.Arm) -> dict[str, Any]:
    """P9 (ruling 4a, observation only): the existing `github.issues-access` check against the arm's pass-1 repo,
    with the pass-1 PAT installed the production way; what the check actually runs is recorded beside its verdict."""
    try:
        checklist._install_github_pat(p, arm, "pass1")
    except RuntimeError as e:
        return _err(e)
    pins = config.load_pins()
    with egress.Stage(SETUP_NS, arm.name, "ghcheck", pins.egress_setup_common,
                      out_dir() / "P9" / f"egress-ghcheck-{arm.name}.log") as st:
        with docker.recording() as specs:
            c = checklist.issues_access_check(p, arm, "pass1", st)
    return {"status": c.status, "ok": c.ok, "detail": c.detail, "runs": [s.cmd for s in specs]}


def no_model(pats: bool) -> dict[str, Any]:
    """P9 and P11: no model turns. `pats` (the confirmed full probe only) allows the keychain PAT reads of P9's
    issues-access observation; `--no-model` reads nothing from the keychain."""
    res: dict[str, Any] = {}
    helps: dict[str, Any] = {}
    for arm_name, cmds in HELP_COMMANDS.items():
        img = gitops.image_for(arm_name)
        for c in cmds:
            try:
                text = container_text(img, c)
                helps[c] = {"output": text, "telemetry": telemetry_mentions(text)}
            except Exception as e:
                helps[c] = _err(e)
    tele: dict[str, Any] = {}
    setup: dict[str, Any] = {}
    for arm_name in config.all_arms():
        arm = config.load_arm(arm_name)
        if arm.parked:
            tele[arm_name] = setup[arm_name] = "parked"
            continue
        try:
            tele[arm_name] = container_text(gitops.image_for(arm_name), TELEMETRY_GREP)
        except Exception as e:
            tele[arm_name] = _err(e)
        entry: dict[str, Any] = {}
        for offline, ns in ((False, SETUP_NS), (True, OFFLINE_NS)):
            key = "offline" if offline else "online"
            p = Paths(ns, arm_name)
            try:
                if p.base.exists():
                    repo.remove_tree(p.base)
                checks = checklist.run_shell_only(ns, arm_name, offline=offline)
                entry[key] = {c.id: c.status for c in checks}
            except Exception as e:
                entry[key] = _err(e)
                continue
            if offline:
                continue
            try:
                lst = commands.listing(p, arm)
                entry["commands"] = {"names": sorted(lst.names), "models": lst.models}
            except Exception as e:
                entry["commands"] = _err(e)
            try:
                configured = checklist.effective_manifest_paths(arm)
                _m, missing = checklist.manifest_full(p, arm)
                entry["manifest_not_created"] = manifest_not_created(configured, missing)
            except Exception as e:
                entry["manifest_not_created"] = _err(e)
            if arm.tracker == "github" and not arm.dry:
                try:
                    entry["issues_access"] = _issues_access(p, arm) if pats else \
                        "skipped: --no-model reads no keychain item (run the full probe)"
                except Exception as e:
                    entry["issues_access"] = _err(e)
        setup[arm_name] = entry
    res["P9"] = _save("P9", {"help": helps, "telemetry_install_tree": tele, "setup": setup})
    sk = Paths(SETUP_NS, "speckit").repo / ".claude" / "skills" / "speckit-taskstoissues" / "SKILL.md"
    if sk.is_file() and not sk.is_symlink():
        res["P11"] = _save("P11", {"route": export_route(sk.read_text(errors="replace")), "skill": str(sk)})
    else:
        res["P11"] = _save("P11", {"route": "skill missing", "skill": str(sk)})
    return res


CORRECTIONS = [
    "`pins.toml accepted_models` = P1's `transcript_models` (and `init_model`).",
    "P1: replace the reconstructed parser fixture with `results/probe/P1-stream.jsonl.gz` (only if `stream_saved.saved`).",
    "P1: if `layout.found` is false, the fake's transcript layout is wrong: fix it to `found_at`.",
    "P1: any `hard_linked` entry: Claude Code hard-links transcripts — the transcript readers need the owner's decision.",
    "P1c: any case with `matches_shape` false and an outcome other than `auth_failed`: add its `final_text` prefix "
    "to `session.AUTH_FAILURE_SHAPES` (with its source); `bogus_token_on_disk` must be empty.",
    "If P2.ok is false: OD19 (resume across containers) needs the owner's decision.",
    "If P3 shows a non-pinned subagent model: OD2 needs the owner's decision before superpowers runs.",
    "P3b: expected violation — confirms the setup check; no action if `common.no-foreign-model-ids` exists.",
    "P4: record what 2.1.281 does with a disallowed AskUserQuestion (OD11).",
    "P5: route A failures or `route_b.loaded` false → fix the arm's `[setup] plugins` (subdir) before it runs.",
    "If P6.skill_as_slash is false: `commands.invocation` must send skills as `Use the <name> skill.` instead.",
    "If P7.isolated_ignored_claude_md is false: stop — the PO and teammate are not isolated.",
    "If P7 PO or teammate said PINEAPPLE: stop — that role is not isolated.",
    "P7: if `control_not_isolated.said_pineapple` is false, the PINEAPPLE checks prove nothing — re-run P7.",
    "P8: any `outside_run_common` host: listed for the owner (allow it in pins, or leave it refused).",
    "P9: correct `[setup]` / checklist ids to the real flags; record telemetry per tool in each checklist OV.",
    "P9 offline failures: note which setups fetch at setup time (pinned by the manifest comparison only).",
    "P9 `manifest_not_created`: manifest paths setup never creates — owner decides (observation only).",
    "P9 `issues_access`: what the existing check proves (it runs `runs`) — owner decides whether write access "
    "needs its own check (observation only).",
    "P10: any file listed → stop; the owner decides before any arm runs.",
    "P11: `mcp` → apply Task 12 Step 5 if OD24 = B; `gh` → nothing to add.",
]


def report(res: dict[str, Any]) -> Path:
    lines = ["# Live probe", ""]
    lines += [f"## {k}\n```json\n{json.dumps(v, indent=2, default=str)[:4000]}\n```" for k, v in sorted(res.items())]
    lines += ["", "## Corrections to apply (owner)", "", *[f"- {c}" for c in CORRECTIONS]]
    o = out_dir()
    o.mkdir(parents=True, exist_ok=True)
    (o / "probe.md").write_text("\n".join(lines) + "\n")
    return o / "probe.md"
