"""Decision review context (plan `2026-10-09-decision-context.md`; spec §8.4 as amended 2026-10-09): for each topic,
what its routes DO, so the owner can rate behaviour rather than one line of text. Owner, 2026-10-09: "I don't care as
much about the code as I do about what it results in".

Per topic (resumable; `decisions/context/<topic id>.json`):
1. **plan** - one judge call. Its inputs are the topic as the sheet numbers it (routes, reasoning, outcome; no labels)
   and the contract and step specs. It replies with example inputs that tell the routes apart: files for a fresh
   theatre, then `troupe` commands. A topic with nothing to run (process, planning) says so.
2. **run** - the harness runs those commands in a fresh theatre against every label's FINAL-step code, in the tester
   sandbox (arm uid, no capabilities, no network; `hidden.run_script`). For each command it captures the exit code,
   stdout, stderr and the files named in `show`. Output is scrubbed of arm names and grouped by route; arms on one
   route with identical results are merged, so no arm is ever named or numbered.
3. **write** - one judge call over the topic and those results. It replies with the stakes, each example's results
   per route (observed, or inferred where nothing ran) and the trade-off; the sheet renders it.

No stage here reads `anon-key.json` except `ArmRunner`, which needs the arm behind a label to export its code. The
mapping never reaches a judge or the written context."""
from __future__ import annotations
import base64, json, re, shlex
from pathlib import Path
from typing import Any, Protocol
from runner import paths
from runner.scoring import anonymise, decisions as dz, inputs, judge, leakcheck, values

ITEM_PREFIX = "_decisions/context-"            # anon/<ITEM_PREFIX><topic id>/: <label>/<item> depth for check_mounts
SPEC_FILES = ("contract.md",)                  # + every scenario/steps/*.md, concatenated into steps.md
MAX_COMMANDS, MAX_FILES, CMD_SECONDS = 12, 6, 20
# `config watch` runs in the background between a start and a stop step: a start waits at most WATCH_READY_SECONDS
# for its `watching` line, a stop at most WATCH_STOP_SECONDS for it to exit (then SIGKILL), and `timeout` ends it
# after WATCH_SECONDS whatever the plan does. Sleeps add up to MAX_SLEEP_SECONDS. No step outlasts CMD_SECONDS + 2,
# so a plan ends well inside `hidden.run_script`'s 600 s (`worst_seconds`).
WATCH_READY_SECONDS, WATCH_STOP_SECONDS, WATCH_SECONDS, MAX_SLEEP_SECONDS = 15, 5, 240, 10
SIGNALS = ("SIGINT", "SIGTERM")
CAP = 4000                                     # characters kept per stdout, stderr or file
# relative, no "..", no component starting with "-" (it would be read as an option by dirname/head)
_REL = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*(?:^|/)-)[\w.\-/]+$")
_ENV = re.compile(r"^[A-Z][A-Z0-9_]*$")
# USER and LOGNAME may be set or unset (null): with "passwd": false that leaves the arm no login name at all
_ENV_DENY = {"PATH", "HOME", "VIRTUAL_ENV", "TMPDIR", "SHELL", "IFS"}
_ENV_DENY_PREFIX = ("UV_", "PYTHON", "LD_", "DYLD_", "BAKEOFF", "BASH")
_KINDS = ("edit", "sleep", "symlink", "list", "watch")   # a step that is not a plain command has exactly one


def worst_seconds() -> float:
    """An upper bound on one plan's run: every step at its longest, every sleep, and the final watch cleanup."""
    return MAX_COMMANDS * (CMD_SECONDS + 2) + MAX_SLEEP_SECONDS + WATCH_STOP_SECONDS + 1


class RunFailed(RuntimeError):
    """The harness could not run a plan in a label's code (no install, no container, no records): never a result."""


def out_dir(pass_: str) -> Path:
    return dz._dir(pass_) / "context"


def out_path(pass_: str, tid: str) -> Path:
    return out_dir(pass_) / f"{tid}.json"


def item_dir(pass_: str, tid: str) -> Path:
    return paths.scoring_out(pass_) / "anon" / f"{ITEM_PREFIX}{tid}"


# ---- the topic as the owner sees it ---------------------------------------------------------------------------------

def topic_view(t: dict, clean) -> dict:
    """A sheet-ordered topic (`decisions._ordered`) without labels: what a judge may see."""
    return {"question": clean(t["question"]), "kind": t["kind"],
            "routes": [{"route_no": r["route_no"], "route": clean(r["route"]),
                        "reasoning_given": clean(r["reason_given"]), "outcome": clean(r["outcome"])}
                       for r in t["routes"]]}


def fingerprint(t: dict) -> list[list]:
    """What a context was written for: each route's text and labels, in sheet order. A re-alignment that changes
    either makes the context stale (the sheet then shows none). Kept in the context record, never on the sheet."""
    return [[r["route"], sorted(r["labels"])] for r in t["routes"]]


# ---- 1. plan ---------------------------------------------------------------------------------------------------------

def plan_prompt(ask: str | None = None) -> str:
    owner = (f"\n\nThe owner asked for this topic to be re-run with: {ask}\nMake sure the examples cover that."
             if ask else "")
    return (
        "You are preparing a blind comparison of how several implementations of the same CLI behave. The owner must "
        "rate the routes in /judge/topic.json - different answers the implementations gave to one design question - "
        "and wants to see what each route RESULTS IN, not code.\n\n"
        "Inputs (read-only; Read, Glob, Grep): /judge/topic.json (the question and its numbered routes; \"not "
        "considered\" means some implementations never addressed it), /judge/contract.md (the CLI contract) and "
        "/judge/steps.md (the seven change requests the implementations were built through).\n\n"
        "Design 1 to 5 example commands that make the routes' differences visible, including the edge cases that "
        "separate them. They will be run, unchanged, against EVERY implementation's final code, each in a fresh "
        "empty directory that is the theatre (the current directory), with the files you list created first. The "
        "program is invoked as `troupe <args>`, so give args such as [\"config\", \"set\", \"retry\", \"-1e3\"]; "
        "--theatre defaults to the current directory. `--theatre <dir>` or `--theatre=<dir>` may appear anywhere in "
        "args, before `config` too ([\"--theatre\", \".\", \"config\", \"get\", \"x\"]), with a RELATIVE <dir> "
        "inside the theatre (\".\", \"sub\", a symlink you created). "
        f"Up to {MAX_COMMANDS} steps run in order in the same theatre, each command with a {CMD_SECONDS}-second "
        "limit, no network and no input. `env` sets variables for one command; null unsets one "
        "({\"USER\": null}). `show` lists files (relative to the theatre) to print whenever a step changed them.\n\n"
        "Besides a command, a step may be (each is one JSON object in \"commands\"):\n"
        "- {\"edit\": {\"path\": \".troupe/troupe.yml\", \"content\": \"<the whole new file>\"}}: edit a file BY "
        "HAND, as a person would in an editor (no troupe call);\n"
        f"- {{\"sleep\": 3}}: wait (0.1 to {MAX_SLEEP_SECONDS} seconds in all, across the plan);\n"
        "- {\"symlink\": {\"path\": \"linked\", \"target\": \"sub\"}}: create a symlink at path pointing to target, "
        "both relative (target relative to the link's directory, as `ln -s` takes it), no \"..\";\n"
        "- {\"list\": \".troupe\"}: list what is under a directory of the theatre (\".\" for all), recursively: each "
        "file's path and size in bytes, directories ending in /, symlinks as `path -> target`; never contents, so "
        "it shows whether a command created state (e.g. a history database) on disk;\n"
        "- {\"watch\": \"start\", \"args\": [\"config\", \"watch\"], \"env\": {}}: start `troupe config watch` in "
        f"the background; the step waits up to {WATCH_READY_SECONDS} s for its `watching` line (or for it to "
        "exit, e.g. on a broken config) and reports what it printed so far. Further steps (edits, sleeps, "
        "commands) run while it watches; it reacts to a change within 2 seconds, so sleep about 3 seconds after an "
        "edit before looking at the result. Only one watch at a time;\n"
        "- {\"watch\": \"stop\", \"signal\": \"SIGINT\"} (or \"SIGTERM\"): signal the running watch (its whole "
        f"process group, as Ctrl-C would), wait up to {WATCH_STOP_SECONDS} s (then it is killed), and report its "
        "exit code and everything it printed. Every start needs a stop later in the plan; a watch is also ended "
        f"after {WATCH_SECONDS} s.\n\n"
        "Limits of the sandbox: commands run as a user whose login name is set (LOGNAME and USER) and found in the "
        "account database. To show a user with NO login name, unset LOGNAME and USER (and LNAME, USERNAME) in env "
        "and set \"passwd\": false at the top of the plan: then the user has no account entry, so a lookup of the "
        "login name fails. \"passwd\" applies to the whole plan, never to one command (env still can set USER for "
        "one command). env may not set PATH, HOME, TMPDIR, SHELL, IFS, VIRTUAL_ENV or UV_*, PYTHON*, LD_*, BASH* "
        "variables. Nothing may refer outside the theatre: no absolute paths and no \"..\", in --theatre, files, "
        "edits, symlinks or lists. Only `troupe config ...` runs; nothing waits for input or a terminal.\n\n"
        "If the question cannot be shown by running commands (it is about planning, process, documentation, test "
        "structure or internals with no visible effect), set \"runnable\" to false and say why.\n\n"
        "Reply with exactly one JSON object and nothing else:\n"
        '{"runnable": true, "why": "<one line: what the examples show>", '
        '"files": {".troupe/troupe.yml": "<content>"}, '
        '"commands": [{"args": ["config", "show", "x"], "env": {"TROUPE_ACTOR": "human:owner"}}], '
        '"show": [".troupe/troupe.yml"], "passwd": true}' + owner)


def parse_plan(text: str) -> dict:
    v = dz._json_value(text)
    if not isinstance(v, dict) or not isinstance(v.get("runnable"), bool):
        raise judge.BadReply('needs one JSON object with "runnable": true or false')
    why = v.get("why") if isinstance(v.get("why"), str) else ""
    if not v["runnable"]:
        return {"runnable": False, "why": why}
    files, cmds, show = v.get("files", {}), v.get("commands"), v.get("show", [])
    if not isinstance(files, dict) or len(files) > MAX_FILES or not all(
            isinstance(k, str) and _REL.match(k) and isinstance(c, str) for k, c in files.items()):
        raise judge.BadReply(f'"files" must map at most {MAX_FILES} relative paths (no "..") to text')
    if not isinstance(cmds, list) or not 1 <= len(cmds) <= MAX_COMMANDS:
        raise judge.BadReply(f'"commands" must list 1 to {MAX_COMMANDS} commands')
    passwd = v.get("passwd", True)
    if not isinstance(passwd, bool):
        raise judge.BadReply('"passwd" must be true or false')
    out_cmds, slept, watching = [], 0.0, False
    for i, c in enumerate(cmds, 1):
        if not isinstance(c, dict):
            raise judge.BadReply(f"command {i}: must be a JSON object")
        if len(kinds := [k for k in _KINDS if k in c]) > 1:
            raise judge.BadReply(f"command {i}: one step kind per step, not {' and '.join(kinds)}")
        kind = kinds[0] if kinds else None
        if kind == "edit":                               # a hand edit between commands: the harness writes the file
            e = c["edit"]
            if not isinstance(e, dict) or not isinstance(e.get("path"), str) or not _REL.match(e["path"]) \
                    or not isinstance(e.get("content"), str):
                raise judge.BadReply(f'command {i}: "edit" must be {{"path": <relative path>, "content": <text>}}')
            out_cmds.append({"edit": {"path": e["path"], "content": e["content"]}, "args": [], "env": {}})
        elif kind == "sleep":
            s = c["sleep"]
            if isinstance(s, bool) or not isinstance(s, (int, float)) or not 0.1 <= s <= MAX_SLEEP_SECONDS \
                    or (slept := slept + round(s, 1)) > MAX_SLEEP_SECONDS:
                raise judge.BadReply(f'command {i}: "sleep" must be 0.1 to {MAX_SLEEP_SECONDS} seconds, '
                                     f"{MAX_SLEEP_SECONDS} in all")
            out_cmds.append({"sleep": round(s, 1), "args": [], "env": {}})
        elif kind == "symlink":
            ln = c["symlink"]
            if not isinstance(ln, dict) or not all(isinstance(ln.get(k), str) and _REL.match(ln[k])
                                                   for k in ("path", "target")):
                raise judge.BadReply(f'command {i}: "symlink" must be {{"path": <relative path>, "target": '
                                     '<relative path>}, no ".." and nothing absolute')
            out_cmds.append({"symlink": {"path": ln["path"], "target": ln["target"]}, "args": [], "env": {}})
        elif kind == "list":
            if not isinstance(c["list"], str) or not _REL.match(c["list"]):
                raise judge.BadReply(f'command {i}: "list" must be a relative directory (".", ".troupe"), no ".."')
            out_cmds.append({"list": c["list"], "args": [], "env": {}})
        elif kind == "watch" and c["watch"] == "stop":
            if c.get("signal") not in SIGNALS:
                raise judge.BadReply(f'command {i}: a watch stop needs "signal": {" or ".join(SIGNALS)}')
            if not watching:
                raise judge.BadReply(f"command {i}: no watch is running to stop")
            watching = False
            out_cmds.append({"watch": "stop", "signal": c["signal"], "args": [], "env": {}})
        elif kind == "watch" and c["watch"] != "start":
            raise judge.BadReply(f'command {i}: "watch" must be "start" or "stop"')
        else:
            if kind == "watch" and watching:
                raise judge.BadReply(f"command {i}: a watch is already running; stop it first")
            args, env = _args(i, c.get("args"), watch=kind == "watch"), _env(i, c.get("env"))
            watching = watching or kind == "watch"
            out_cmds.append({**({"watch": "start"} if kind == "watch" else {}), "args": args, "env": env})
    if watching:
        raise judge.BadReply('the plan ends with watch running: add {"watch": "stop", "signal": "SIGINT"}')
    if not isinstance(show, list) or not all(isinstance(s, str) and _REL.match(s) for s in show) or len(show) > MAX_FILES:
        raise judge.BadReply(f'"show" must list at most {MAX_FILES} relative paths')
    return {"runnable": True, "why": why, "files": files, "commands": out_cmds, "show": show, "passwd": passwd}


def _args(i: int, args: Any, *, watch: bool) -> list[str]:
    """`troupe` argv: `config` first after any `--theatre <relative dir>`; `watch` only in a watch start."""
    if not isinstance(args, list) or not args or not all(isinstance(a, str) for a in args):
        raise judge.BadReply(f'command {i}: "args" must be a non-empty list of strings')
    if any("\x00" in a for a in args):
        raise judge.BadReply(f"command {i}: no NUL in args")
    words, k = [], 0
    while k < len(args):
        a, name = args[k], args[k].partition("=")[0]
        if name == "--theatre":
            d = a.partition("=")[2] if "=" in a else (args[k + 1] if k + 1 < len(args) else "")
            if not _REL.match(d):
                raise judge.BadReply(f"command {i}: --theatre takes a relative directory inside the theatre "
                                     '(".", "sub"), never an absolute path or ".."')
            k += 1 if "=" in a else 2
            continue
        if len(name) > 2 and "--theatre".startswith(name):    # argparse would take an abbreviation as --theatre
            raise judge.BadReply(f"command {i}: spell --theatre out in full, not {name}")
        words.append(a)
        k += 1
    sub = next((w for w in words[1:] if not w.startswith("-")), None)
    if words[:1] != ["config"]:
        raise judge.BadReply(f"command {i}: only `troupe config <subcommand>` commands")
    if watch != (sub == "watch"):
        raise judge.BadReply(f'command {i}: `config watch` runs only as {{"watch": "start", "args": [...]}}, '
                             "and a watch start runs `config watch`")
    return args


def _env(i: int, env: Any) -> dict[str, str | None]:
    env = env or {}
    if not isinstance(env, dict) or not all(
            isinstance(k, str) and _ENV.match(k) and k not in _ENV_DENY and not k.startswith(_ENV_DENY_PREFIX)
            and (x is None or isinstance(x, str) and "\x00" not in x) for k, x in env.items()):
        raise judge.BadReply(f'command {i}: "env" must map variable names to strings, or null to unset one (not '
                             f"{sorted(_ENV_DENY)} or {', '.join(_ENV_DENY_PREFIX)}*)")
    return env


# ---- 2. run ----------------------------------------------------------------------------------------------------------

def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def script(plan: dict, impl: str) -> str:
    """Bash for the tester sandbox: a fresh theatre, the plan's files, then each command (`timeout`), printing one
    `R`/`F` record per line with base64 fields, so what the arm prints to its own stdout or stderr is never read as
    a record. (An arm process that outlives its command could still write to the container's stdout; the harness's
    record for a command is printed after it, and the last record wins.) A shown file is printed after a command
    only when that command changed it (`S` once at the start, so the reader knows the starting content).

    Job control (`set -m`) puts a background watch in its own process group with SIGINT not ignored, so a stop
    signals the group as a terminal's Ctrl-C would. `wstop` ends it (signal, wait, SIGKILL); the EXIT trap runs it
    for a watch still running however the script ends. A start's record has rc `-` while watch runs; the stop's
    record carries everything watch printed. The 8th field of a watch record says what happened."""
    q = shlex.quote
    lines = ["set -u", "set -m", 'T="$(mktemp -d)"', 'cd "$T"', 'S="$(mktemp -d)"', "enc() { base64 | tr -d '\\n'; }",
             "W=; WRC=; note=",
             "alive() { [ -n \"$W\" ] && kill -0 \"$W\" 2>/dev/null; }",
             "wstop() { if alive; then kill -s \"$1\" -- \"-$W\" 2>/dev/null || kill -s \"$1\" \"$W\" 2>/dev/null; "
             f"note=stopped; n=0; while alive && [ $n -lt {WATCH_STOP_SECONDS * 10} ]; do sleep 0.1; n=$((n+1)); done; "
             "if alive; then kill -s KILL -- \"-$W\" 2>/dev/null; kill -s KILL \"$W\" 2>/dev/null; note=killed; fi; "
             "wait \"$W\"; rc=$?; else note=exited-before-stop; if [ -n \"$W\" ]; then wait \"$W\"; WRC=$?; fi; "
             "rc=$WRC; fi; W=; }",
             "trap 'if [ -n \"$W\" ]; then wstop TERM; fi' EXIT"]
    for rel, content in plan["files"].items():
        lines += [f"mkdir -p -- \"$(dirname -- {q(rel)})\"", f"printf %s {q(_b64(content))} | base64 -d > {q(rel)}"]
    for k, s in enumerate(plan["show"]):                   # snapshot k: the file as last printed ("-" = absent)
        lines.append(f'if [ -f {q(s)} ]; then cp -- {q(s)} "$S/{k}"; else printf -- - > "$S/{k}.absent"; fi')
    troupe = f"uv run --quiet --project {q(impl)} troupe"
    for i, c in enumerate(plan["commands"], 1):
        env = " ".join([f"-u {k}" for k, v in c["env"].items() if v is None]
                       + [f"{k}={q(v)}" for k, v in c["env"].items() if v is not None])
        argv = " ".join(q(a) for a in c["args"])
        out, err, note = '"$S/out"', '"$S/err"', ""
        if "edit" in c:                                  # by hand, as a person in an editor would: no troupe call
            rel = c["edit"]["path"]
            lines += [f"mkdir -p -- \"$(dirname -- {q(rel)})\"",
                      f"printf %s {q(_b64(c['edit']['content']))} | base64 -d > {q(rel)}; : > \"$S/out\"; "
                      f': > "$S/err"; rc=0']
        elif "sleep" in c:
            lines.append(f'sleep {c["sleep"]}; : > "$S/out"; : > "$S/err"; rc=0')
        elif "symlink" in c:
            p, t = q(c["symlink"]["path"]), q(c["symlink"]["target"])
            lines.append(f': > "$S/out"; if [ -e {p} ] || [ -L {p} ]; then echo "{c["symlink"]["path"]} already '
                         f'exists" > "$S/err"; rc=1; else mkdir -p -- "$(dirname -- {p})" && ln -s -- {t} {p} '
                         f'2>"$S/err"; rc=$?; fi')
        elif "list" in c:                                # paths and sizes only: a binary store is never printed
            d = q(c["list"])
            lines.append(f': > "$S/err"; if [ -d {d} ]; then find -H {d} -mindepth 1 2>"$S/err" | LC_ALL=C sort | '
                         'while IFS= read -r f; do p="${f#./}"; if [ -L "$f" ]; then printf \'%s -> %s\\n\' "$p" '
                         '"$(readlink "$f")"; elif [ -d "$f" ]; then printf \'%s/\\n\' "$p"; else '
                         'z="$(wc -c < "$f" 2>/dev/null | tr -d " ")"; printf \'%s  %s bytes\\n\' "$p" "${z:-?}"; '
                         f'fi; done > "$S/out"; rc=0; else : > "$S/out"; echo "no directory {c["list"]}" > "$S/err"; '
                         'rc=1; fi')
        elif c.get("watch") == "start":
            lines += [f"WRC=; env {env} timeout -k 2 {WATCH_SECONDS} {troupe} {argv} </dev/null >\"$S/wout\" "
                      f"2>\"$S/werr\" & W=$!",
                      f"note=no-watching-line; rc=-; n=0; while [ $n -lt {WATCH_READY_SECONDS * 10} ]; do "
                      "if grep -qi '^watching' \"$S/wout\" 2>/dev/null; then note=watching; break; fi; "
                      "if ! alive; then wait \"$W\"; WRC=$?; W=; rc=$WRC; note=exited; break; fi; "
                      "sleep 0.1; n=$((n+1)); done"]
            out, err, note = '"$S/wout"', '"$S/werr"', " $note"
        elif c.get("watch") == "stop":
            lines.append(f"wstop {c['signal'][3:]}")
            out, err, note = '"$S/wout"', '"$S/werr"', " $note"
        else:
            lines += [f"env {env} timeout -k 2 {CMD_SECONDS} {troupe} {argv} "
                      f"</dev/null >\"$S/out\" 2>\"$S/err\"; rc=$?"]
        lines += [f'echo "R {i} $rc $(head -c {CAP} {out} | enc) $(head -c {CAP} {err} | enc) '
                  f'$(wc -c < {out} | tr -d " ") $(wc -c < {err} | tr -d " "){note}"']
        for k, s in enumerate(plan["show"]):
            lines.append(
                f'if [ -f {q(s)} ]; then if [ -f "$S/{k}.absent" ] || ! cmp -s -- {q(s)} "$S/{k}"; then '
                f'rm -f "$S/{k}.absent"; cp -- {q(s)} "$S/{k}"; '
                f'echo "F {i} {_b64(s)} $(head -c {CAP} -- {q(s)} | enc) $(wc -c < {q(s)} | tr -d " ")"; fi; '
                f'elif [ ! -f "$S/{k}.absent" ]; then rm -f "$S/{k}"; printf -- - > "$S/{k}.absent"; '
                f'echo "F {i} {_b64(s)} -"; fi')
    return "\n".join(lines) + "\n"


def parse_output(out: str, plan: dict) -> list[dict]:
    """One result per command: {"args", "rc", "stdout", "stderr", "files": {path: text | None}} - `files` holds only
    the shown files that command changed (None: it deleted the file). Raises RunFailed when any command has no
    record: the sandbox died or never started, which is the harness's failure, never the arm's result."""
    def dec(x: str) -> str:
        try:
            return base64.b64decode(x).decode(errors="replace")
        except ValueError:
            return ""
    res = [{"args": c["args"], "env": c["env"], "rc": None, "stdout": "", "stderr": "", "files": {},
            **_step_keys(c)} for c in plan["commands"]]
    seen: set[int] = set()
    for line in out.splitlines():
        p = line.split(" ")
        if p[0] == "R" and len(p) >= 3 and p[1].isdigit() and 1 <= int(p[1]) <= len(res) \
                and re.fullmatch(r"-?\d+|-", p[2]):
            r = res[int(p[1]) - 1]
            seen.add(int(p[1]))
            r["rc"] = None if p[2] == "-" else int(p[2])      # "-": a watch still running after its start
            r["stdout"], r["stderr"] = _capped(p, 3, 5), _capped(p, 4, 6)
            if "watch" in r and len(p) > 7:
                r["watch_state"] = watch_states().get(p[7], p[7])
        elif p[0] == "F" and len(p) >= 4 and p[1].isdigit() and 1 <= int(p[1]) <= len(res):
            res[int(p[1]) - 1]["files"][dec(p[2])] = None if p[3] == "-" else _capped(p, 3, 4)
    if missing := [str(i) for i in range(1, len(res) + 1) if i not in seen]:
        raise RunFailed(f"no record for command(s) {', '.join(missing)}: the sandbox did not finish them")
    for r in res:
        limit = WATCH_SECONDS if "watch" in r else None if {"hand_edit", "sleep", "symlink", "list"} & set(r) \
            else CMD_SECONDS                                  # `timeout`'s 124; a harness step never runs under it
        if r["rc"] == 124 and limit:
            r["stderr"] = (r["stderr"] + f"\n[harness: stopped after {limit} s]").strip()
    return res


def watch_states() -> dict[str, str]:
    """A watch record's 8th field, in words for the write call."""
    return {"watching": "printed its watching line and is running",
            "no-watching-line": f"running, but no watching line within {WATCH_READY_SECONDS} s",
            "exited": "exited before printing a watching line", "stopped": "exited after the signal",
            "killed": f"still running {WATCH_STOP_SECONDS} s after the signal, so killed",
            "exited-before-stop": "had already exited before the signal"}


def _step_keys(c: dict) -> dict:
    """What a result says about the step that is not a troupe command (or is a watch)."""
    if "edit" in c:
        return {"hand_edit": c["edit"]["path"]}
    if "watch" in c:
        return {"watch": c["watch"], **({"signal": c["signal"]} if "signal" in c else {})}
    return {k: c[k] for k in ("sleep", "symlink", "list") if k in c}


def _capped(p: list[str], i: int, size_at: int) -> str:
    """Field `i` decoded, with a marker when the full size (field `size_at`) was over CAP."""
    try:
        text = base64.b64decode(p[i]).decode(errors="replace") if len(p) > i else ""
    except ValueError:
        text = ""
    size = int(p[size_at]) if len(p) > size_at and p[size_at].isdigit() else 0
    return text + (f"\n[harness: {size - CAP} more bytes not shown]" if size > CAP else "")


class Runner(Protocol):
    def ready(self, labels: list[str]) -> None: ...
    def run(self, label: str, plan: dict) -> list[dict]: ...


class ArmRunner:
    """Each label's final-step code, exported and installed once (`hidden.prepare`), then `hidden.run_script` per
    topic. The only reader of anon-key.json here: it needs the arm behind a label."""

    def __init__(self, pass_: str):
        self.pass_ = pass_
        self._prep: dict[str, tuple[Any, Path] | str] = {}          # a failure is cached, never re-prepared

    def _copy(self, label: str) -> tuple[Any, Path]:
        if label not in self._prep:
            from runner import hidden                 # lazy, as rerun.py does: Docker-only imports
            from runner.paths import Paths
            p = Paths(self.pass_, judge.anon_key(self.pass_)[label])
            try:                                      # install records stay in the arm's own state/, never results/
                prep = hidden.prepare(p, _final_sha(p), "context-final", p.base / "context-prep", require_main=False)
                ok = bool(prep.prep.get("hidden", {}).get("ok"))
                self._prep[label] = (p, prep.hidden_copy) if ok else "installing the final code failed"
            except Exception as e:                     # noqa: BLE001 - cached, reported by ready()/run()
                self._prep[label] = f"preparing the final code failed: {type(e).__name__}"
        got = self._prep[label]
        if isinstance(got, str):
            raise RunFailed(f"{label}: {got}")
        return got

    def ready(self, labels: list[str]) -> None:
        """Every label prepared and `troupe config --help` answering, before any topic is spent on."""
        probe = {"files": {}, "commands": [{"args": ["config", "--help"], "env": {}}], "show": []}
        bad = []
        for lab in labels:
            try:
                if self.run(lab, probe)[0]["rc"] != 0:
                    bad.append(f"{lab}: `troupe config --help` failed")
            except RunFailed as e:
                bad.append(str(e))
        if bad:
            raise inputs.InputError("the context stage cannot run every arm's code; nothing spent:\n"
                                    + "\n".join(f"- {b}" for b in bad))

    def run(self, label: str, plan: dict) -> list[dict]:
        from runner import hidden
        p, copy = self._copy(label)
        try:
            out = hidden.run_script(p, copy, script(plan, f"/work/{copy.name}"), arm_entry=plan.get("passwd", True))
        except Exception as e:                         # noqa: BLE001 - the harness's failure, never a result
            raise RunFailed(f"{label}: the sandbox failed: {type(e).__name__}") from e
        return parse_output(out, plan)


def _final_sha(p) -> str:
    """The `sha_after` of the arm's last step with a git record."""
    from runner.scoring import evidence
    for step in range(9, 0, -1):
        f = p.step(step) / "git.json"
        if f.exists():
            g = evidence.read_json(f)
            sha = None if values.is_missing(g) else (g.get("value") or {}).get("sha_after")
            if sha:
                return sha
    raise RuntimeError(f"{p.pass_}/{p.arm}: no step has a recorded sha_after")


def _scrub_results(res: list[dict], arms: list[str]) -> list[dict]:
    terms = anonymise.pass_terms(arms)

    def s(x: str) -> str:
        x = re.sub(r"/work/bakeoff-specs-[\w.-]+", "/work/project", x)
        x = re.sub(r"/tmp/tmp\.\w+", "/theatre", x)
        return anonymise.scrub(x, terms)
    return [{**r, "stdout": s(r["stdout"]), "stderr": s(r["stderr"]),          # the other keys come from the plan
             "files": {k: (None if v is None else s(v)) for k, v in r["files"].items()}} for r in res]


def by_route(t: dict, results: dict[str, list[dict]], clean=lambda x: x) -> list[dict]:
    """[{"route_no", "route", "outcomes": [{"arms": n, "results": [...]}]}]: arms on a route with identical results
    merged into one outcome and counted, never named or numbered."""
    out = []
    for r in t["routes"]:
        groups: list[dict] = []
        for lab in r["labels"]:
            for g in groups:
                if g["results"] == results[lab]:
                    g["arms"] += 1
                    break
            else:
                groups.append({"arms": 1, "results": results[lab]})
        out.append({"route_no": r["route_no"], "route": clean(r["route"]), "outcomes": groups})
    return out


# ---- 3. write --------------------------------------------------------------------------------------------------------

def write_prompt(runnable: bool) -> str:
    ran = ("/judge/results.json holds what actually happened: for each route, the outcomes of the implementations "
           "on it (identical ones merged, with a count), per command: exit code, stdout, stderr, and the files "
           "listed after it; a step with \"hand_edit\" is the file edited by hand, \"sleep\" a pause, \"symlink\" a "
           "symlink the harness made and \"list\" a listing of files (paths and sizes) - none of these ran troupe. A "
           "step with \"watch\": \"start\" started `config watch` in the background (stdout and stderr: what it "
           "printed by then; rc null while it ran); \"watch\": \"stop\" sent it \"signal\" (stdout, stderr and "
           "rc: everything it printed and its exit code); \"watch_state\" says what happened. Steps between a start "
           "and its stop ran while watch was running. plan.passwd false means the user had no account entry. A "
           "shown file appears only after a step that changed it (null: deleted), and its "
           "starting content is in plan.files. Report those results faithfully; mark an example \"observed\": true only when every "
           "route's result in it comes from results.json, and say plainly when arms on one route behaved "
           "differently (\"two arms: ...; one arm: ...\")."
           if runnable else
           "Nothing could be run for this topic. Explain in plain words what each route means in practice for "
           "someone using or maintaining the software, without code; set examples to [] unless a concrete "
           "illustration helps, and then mark it \"observed\": false.")
    return (
        "You are writing the context the owner reads before rating the routes in /judge/topic.json, in a blind "
        "comparison of implementations. The owner wants results, not code: what you type, what happens. Example "
        "of the style: \"`config set note -h` -> shows help, sets nothing; `config set note -hello` -> stores "
        "\\\"-hello\\\"\".\n\n"
        f"{ran}\n\n"
        "Never name an implementation, arm, method or tool, and never use letters for arms; refer to routes by "
        "number. Keep each result short. When a file's content is the point, give the outcome on the first line "
        "(e.g. \"exit 0; the file now reads:\") and then the file's relevant lines EXACTLY as they are - real line "
        "breaks in the JSON string, indentation and comments kept - never joined with \" / \" or flattened onto one "
        "line. Do not rate the routes.\n\n"
        "Reply with exactly one JSON object and nothing else:\n"
        '{"stakes": "<one or two sentences: what is at stake for a user>", '
        '"examples": [{"input": "<what is typed, e.g. `config set retry -1e3`>", '
        '"before": "<the starting file, if it matters, else empty>", '
        '"results": {"1": "<route 1 result>", "2": "..."}, "observed": true}], '
        '"in_practice": "<plain words, when examples alone do not show it; else empty>", '
        '"tradeoff": "<one line: what each route costs>"}')


def parse_written(text: str, route_nos: list[int], labels: list[str], arms: tuple[str, ...] | list[str] = (),
                  runnable: bool = True) -> dict:
    v = dz._json_value(text)
    if not isinstance(v, dict):
        raise judge.BadReply("needs one JSON object")
    out: dict[str, Any] = {k: dz._str(v, k, "context") for k in ("stakes", "tradeoff")}
    out["in_practice"] = v.get("in_practice") if isinstance(v.get("in_practice"), str) else ""
    exs = v.get("examples", [])
    if not isinstance(exs, list):
        raise judge.BadReply('"examples" must be a list')
    want = {str(n) for n in route_nos}
    out["examples"] = []
    for i, e in enumerate(exs, 1):
        if not isinstance(e, dict) or not isinstance(e.get("results"), dict):
            raise judge.BadReply(f"example {i}: needs \"results\" by route number")
        got = {str(k): x for k, x in e["results"].items()}
        if set(got) != want or not all(isinstance(x, str) and x.strip() for x in got.values()):
            raise judge.BadReply(f"example {i}: \"results\" must give every route {sorted(want, key=int)} a result")
        out["examples"].append({"input": dz._str(e, "input", f"example {i}", nonempty=True),
                                "before": e.get("before") if isinstance(e.get("before"), str) else "",
                                "results": got, "observed": runnable and e.get("observed") is True})
    if not out["examples"] and not out["in_practice"].strip():
        raise judge.BadReply('give examples, or "in_practice" when there are none')
    texts = [out["stakes"], out["tradeoff"], out["in_practice"]] + [x for e in out["examples"]
                                                                     for x in (e["input"], e["before"], *e["results"].values())]
    if refs := [c for x in texts for c in leakcheck.label_refs(x, labels)]:
        raise judge.BadReply(f"the text names an arm ({'; '.join(refs[:3])}): refer to routes by number only")
    if hits := leakcheck.check_text("\n".join(texts), list(arms), []):
        raise judge.BadReply(f"the text names a method or tool ({hits[0]}): never name one")
    return out


# ---- the stage -------------------------------------------------------------------------------------------------------

def _record(f: Path):
    try:
        return json.loads(f.read_text()) if f.exists() else None
    except (OSError, ValueError):
        return None


def failed_path(f: Path) -> Path:
    return f.with_name(f"{f.stem}.failed.json")


def _archived(f: Path) -> list[Path]:
    """Earlier records of `f` kept by a redo: `<id>.<n>.json`."""
    pat = re.compile(rf"^{re.escape(f.stem)}\.(\d+)\.json$")
    return sorted((x for x in f.parent.glob(f"{f.stem}.*.json") if pat.match(x.name)),
                  key=lambda x: int(pat.match(x.name)[1]))


def _land(f: Path, rec: dict) -> None:
    """Write a topic's record without ever losing an earlier one. An `ok` record replaces the current one, which is
    first kept as `<id>.<n>.json` (a redo's history); a failure never replaces an `ok` record (it is written beside
    it, as `<id>.failed.json`, so a failed --redo leaves the written context in place) but does replace an earlier
    failure. A successful write removes any `<id>.failed.json`."""
    old = _record(f)
    if rec.get("status") != "ok":
        if isinstance(old, dict) and old.get("status") == "ok":
            dz._write(failed_path(f), values.dump(rec))
        else:
            dz._write(f, values.dump(rec))
        return
    if isinstance(old, dict) and old.get("status") == "ok":
        n = 1 + max((int(x.name.split(".")[-2]) for x in _archived(f)), default=0)
        dz._write(f.with_name(f"{f.stem}.{n}.json"), f.read_text())
    dz._write(f, values.dump(rec))
    failed_path(f).unlink(missing_ok=True)


def _unfinished(f: Path, t: dict, retry_failed: bool) -> bool:
    r = _record(f)
    if not isinstance(r, dict) or r.get("routes") != fingerprint(t):
        return True                                   # never written, unreadable, or for routes that changed
    return r.get("status") != "ok" and retry_failed


def _topics(pass_: str) -> list[dict]:
    tf = dz._dir(pass_) / "topics.json"
    if not tf.exists():
        raise inputs.InputError(f"{tf} is missing: run the decisions-align stage first")
    return dz._ordered(json.loads(tf.read_text())["topics"])


def _spec_text() -> tuple[str, str]:
    sc = paths.REPO_ROOT / "scenario"
    steps = "\n\n".join(f.read_text() for f in sorted((sc / "steps").glob("*.md")))
    return (sc / "contract.md").read_text(), steps


def run(pass_: str, j: judge.Judge, runner: Runner, *, retry_failed: bool = False,
        only: list[str] | None = None, redo: bool = False, ask: str | None = None) -> dict:
    """Context for every unfinished topic (or only the sheet ids / topic ids in `only`), one at a time. Each topic's
    record is written as it lands: `{"status": "ok", "routes", "runnable", "context"}` or
    `{"status": "context_failed", "routes", "why", "raw"?}`. `redo` (with `only`) writes the named topics again,
    keeping each earlier record as `<id>.<n>.json` once the new one is written (`_land`: a failed redo, or a crash
    such as a PinViolation, leaves the earlier record in place); `ask` is the owner's request for what the examples
    must cover. An `ok` record holds the plan it ran (`plan`), so a later stage can run it again unchanged."""
    if (redo or ask) and not only:
        raise inputs.InputError("--redo and --ask need --only: name the topics to write again")
    arms, labs = dz._arms(pass_), dz.labels(pass_)
    clean = dz._cleaner(arms)
    contract, steps = _spec_text()
    counts = {"written": 0, "failed": 0, "skipped": 0}
    todo = [t for t in _topics(pass_) if not only or t["sheet_id"] in only or t["id"] in only]
    pending = [t for t in todo if redo or _unfinished(out_path(pass_, t["id"]), t, retry_failed)]
    counts["skipped"] = len(todo) - len(pending)
    if pending:                     # every arm's code installed and answering before anything is spent (review F2/F5)
        runner.ready(sorted({lab for t in pending for r in t["routes"] for lab in r["labels"]}))
    for t in pending:
        f = out_path(pass_, t["id"])
        rec = {"routes": fingerprint(t)}
        item = item_dir(pass_, t["id"])
        view = topic_view(t, clean)
        dz._write(item / "topic.json", values.dump(view))
        dz._write(item / "contract.md", contract)
        dz._write(item / "steps.md", steps)
        plan, why, raw = dz._ask(j, plan_prompt(ask), item, ["topic.json", "contract.md", "steps.md"], parse_plan,
                                 "one JSON object")
        if plan is None:
            _land(f, {**rec, "status": "context_failed", "why": f"plan: {why}", "raw": raw})
            counts["failed"] += 1
            continue
        files = ["topic.json"]
        if plan["runnable"]:
            results: dict[str, list[dict]] = {}
            try:
                for lab in sorted({lab for r in t["routes"] for lab in r["labels"]}):
                    results[lab] = _scrub_results(runner.run(lab, plan), arms)
            except RunFailed as e:          # the harness's failure: the topic fails (retryable), never a result
                _land(f, {**rec, "status": "context_failed", "why": f"run: {e}"})
                counts["failed"] += 1
                continue
            dz._write(item / "results.json", values.dump({"plan": {k: plan[k] for k in ("files", "commands", "show", "passwd")},
                                                          "routes": by_route(t, results, clean)}))
            files.append("results.json")
        got, why, raw = dz._ask(j, write_prompt(plan["runnable"]), item, files,
                                lambda x: parse_written(x, [r["route_no"] for r in t["routes"]], labs, arms,
                                                        plan["runnable"]),
                                "one JSON object")
        if got is None:
            _land(f, {**rec, "status": "context_failed", "why": f"write: {why}", "raw": raw})
            counts["failed"] += 1
            continue
        _land(f, {**rec, "status": "ok", "runnable": plan["runnable"], "plan_why": plan["why"], "plan": plan,
                  "context": got})
        counts["written"] += 1
    return counts


def load(pass_: str, topics: list[dict]) -> dict[str, dict]:
    """{topic id: context} for the sheet: only `ok` records written for the topic's current routes."""
    out = {}
    for t in topics:
        r = _record(out_path(pass_, t["id"]))
        if isinstance(r, dict) and r.get("status") == "ok" and r.get("routes") == fingerprint(t):
            out[t["id"]] = r
    return out


def estimate(pass_: str, *, retry_failed: bool = False) -> dict:
    """Two calls (plan, write) per unfinished topic; parse retries not counted."""
    try:
        ts = _topics(pass_)
    except inputs.InputError:
        return {"calls": 0, "topics": 0}
    n = sum(1 for t in ts if _unfinished(out_path(pass_, t["id"]), t, retry_failed))
    return {"calls": 2 * n, "topics": n}
