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
MAX_COMMANDS, MAX_FILES, CMD_SECONDS = 8, 6, 20
CAP = 4000                                     # characters kept per stdout, stderr or file
# relative, no "..", no component starting with "-" (it would be read as an option by dirname/head)
_REL = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*(?:^|/)-)[\w.\-/]+$")
_ENV = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ENV_DENY = {"PATH", "HOME", "USER", "LOGNAME", "VIRTUAL_ENV", "TMPDIR", "SHELL", "IFS"}
_ENV_DENY_PREFIX = ("UV_", "PYTHON", "LD_", "DYLD_", "BAKEOFF", "BASH")


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
        "--theatre defaults to the current directory. Commands run in order in the same theatre, each with a "
        f"{CMD_SECONDS}-second limit and no network; never use `watch` or anything that waits for input. `show` "
        "lists files (relative to the theatre) to print whenever a command changed them. To edit a file BY HAND between "
        "commands (as a person would in an editor), give a step {\"edit\": {\"path\": \".troupe/troupe.yml\", "
        "\"content\": \"<the whole new file>\"}} in place of a command.\n\n"
        "Limits of the sandbox: every command runs with a login name set (LOGNAME and USER cannot be unset), so a "
        "case that needs no login name cannot be shown; env may set TROUPE_ACTOR and similar variables only. Do "
        "not pass --theatre or any path outside the theatre.\n\n"
        "If the question cannot be shown by running commands (it is about planning, process, documentation, test "
        "structure or internals with no visible effect), set \"runnable\" to false and say why.\n\n"
        "Reply with exactly one JSON object and nothing else:\n"
        '{"runnable": true, "why": "<one line: what the examples show>", '
        '"files": {".troupe/troupe.yml": "<content>"}, '
        '"commands": [{"args": ["config", "show", "x"], "env": {"TROUPE_ACTOR": "human:owner"}}], '
        '"show": [".troupe/troupe.yml"]}' + owner)


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
    out_cmds = []
    for i, c in enumerate(cmds, 1):
        if isinstance(c, dict) and "edit" in c:          # a hand edit between commands: the harness writes the file
            e = c["edit"]
            if not isinstance(e, dict) or not isinstance(e.get("path"), str) or not _REL.match(e["path"]) \
                    or not isinstance(e.get("content"), str):
                raise judge.BadReply(f'command {i}: "edit" must be {{"path": <relative path>, "content": <text>}}')
            out_cmds.append({"edit": {"path": e["path"], "content": e["content"]}, "args": [], "env": {}})
            continue
        if not isinstance(c, dict) or not isinstance(c.get("args"), list) or not c["args"] or not all(
                isinstance(a, str) for a in c["args"]):
            raise judge.BadReply(f'command {i}: "args" must be a non-empty list of strings')
        if c["args"][0] != "config" or (len(c["args"]) > 1 and c["args"][1] == "watch"):
            raise judge.BadReply(f"command {i}: only `troupe config <subcommand>` commands, never watch")
        if any(a == "--theatre" or a.startswith("--theatre=") or "\x00" in a for a in c["args"]):
            raise judge.BadReply(f"command {i}: no --theatre (the theatre is the current directory) and no NUL")
        env = c.get("env") or {}
        if not isinstance(env, dict) or not all(
                isinstance(k, str) and _ENV.match(k) and k not in _ENV_DENY and not k.startswith(_ENV_DENY_PREFIX)
                and isinstance(x, str) and "\x00" not in x for k, x in env.items()):
            raise judge.BadReply(f'command {i}: "env" must map variable names to strings (not {sorted(_ENV_DENY)} '
                                 f"or {', '.join(_ENV_DENY_PREFIX)}*)")
        out_cmds.append({"args": c["args"], "env": env})
    if not isinstance(show, list) or not all(isinstance(s, str) and _REL.match(s) for s in show) or len(show) > MAX_FILES:
        raise judge.BadReply(f'"show" must list at most {MAX_FILES} relative paths')
    return {"runnable": True, "why": why, "files": files, "commands": out_cmds, "show": show}


# ---- 2. run ----------------------------------------------------------------------------------------------------------

def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def script(plan: dict, impl: str) -> str:
    """Bash for the tester sandbox: a fresh theatre, the plan's files, then each command (`timeout`), printing one
    `R`/`F` record per line with base64 fields, so what the arm prints to its own stdout or stderr is never read as
    a record. (An arm process that outlives its command could still write to the container's stdout; the harness's
    record for a command is printed after it, and the last record wins.) A shown file is printed after a command
    only when that command changed it (`S` once at the start, so the reader knows the starting content)."""
    q = shlex.quote
    lines = ["set -u", 'T="$(mktemp -d)"', 'cd "$T"', 'S="$(mktemp -d)"', "enc() { base64 | tr -d '\\n'; }"]
    for rel, content in plan["files"].items():
        lines += [f"mkdir -p -- \"$(dirname -- {q(rel)})\"", f"printf %s {q(_b64(content))} | base64 -d > {q(rel)}"]
    for k, s in enumerate(plan["show"]):                   # snapshot k: the file as last printed ("-" = absent)
        lines.append(f'if [ -f {q(s)} ]; then cp -- {q(s)} "$S/{k}"; else printf -- - > "$S/{k}.absent"; fi')
    for i, c in enumerate(plan["commands"], 1):
        env = " ".join(f"{k}={q(v)}" for k, v in c["env"].items())
        argv = " ".join(q(a) for a in c["args"])
        if "edit" in c:                                  # by hand, as a person in an editor would: no troupe call
            rel = c["edit"]["path"]
            lines += [f"mkdir -p -- \"$(dirname -- {q(rel)})\"",
                      f"printf %s {q(_b64(c['edit']['content']))} | base64 -d > {q(rel)}; : > \"$S/out\"; "
                      f': > "$S/err"; rc=0']
        else:
            lines += [f"env {env} timeout -k 2 {CMD_SECONDS} uv run --quiet --project {q(impl)} troupe {argv} "
                      f"</dev/null >\"$S/out\" 2>\"$S/err\"; rc=$?"]
        lines += [f'echo "R {i} $rc $(head -c {CAP} "$S/out" | enc) $(head -c {CAP} "$S/err" | enc) '
                  f'$(wc -c < "$S/out" | tr -d " ") $(wc -c < "$S/err" | tr -d " ")"']
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
            **({"hand_edit": c["edit"]["path"]} if "edit" in c else {})} for c in plan["commands"]]
    for line in out.splitlines():
        p = line.split(" ")
        if p[0] == "R" and len(p) >= 3 and p[1].isdigit() and 1 <= int(p[1]) <= len(res) \
                and re.fullmatch(r"-?\d+", p[2]):
            r = res[int(p[1]) - 1]
            r["rc"] = int(p[2])
            r["stdout"], r["stderr"] = _capped(p, 3, 5), _capped(p, 4, 6)
        elif p[0] == "F" and len(p) >= 4 and p[1].isdigit() and 1 <= int(p[1]) <= len(res):
            res[int(p[1]) - 1]["files"][dec(p[2])] = None if p[3] == "-" else _capped(p, 3, 4)
    if missing := [str(i) for i, r in enumerate(res, 1) if r["rc"] is None]:
        raise RunFailed(f"no record for command(s) {', '.join(missing)}: the sandbox did not finish them")
    for r in res:
        if r["rc"] == 124:
            r["stderr"] = (r["stderr"] + f"\n[harness: stopped after {CMD_SECONDS} s]").strip()
    return res


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
            out = hidden.run_script(p, copy, script(plan, f"/work/{copy.name}"))
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
    return [{**({"hand_edit": r["hand_edit"]} if "hand_edit" in r else {}),
             "args": r["args"], "env": r["env"], "rc": r["rc"], "stdout": s(r["stdout"]), "stderr": s(r["stderr"]),
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
           "listed after it; a step with \"hand_edit\" is the file edited by hand (no troupe command ran). A shown "
           "file appears only after a command that changed it (null: deleted), and its "
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
    keeping each earlier record as `<id>.<n>.json`; `ask` is the owner's request for what the examples must cover."""
    if (redo or ask) and not only:
        raise inputs.InputError("--redo and --ask need --only: name the topics to write again")
    arms, labs = dz._arms(pass_), dz.labels(pass_)
    clean = dz._cleaner(arms)
    contract, steps = _spec_text()
    counts = {"written": 0, "failed": 0, "skipped": 0}
    todo = [t for t in _topics(pass_) if not only or t["sheet_id"] in only or t["id"] in only]
    pending = [t for t in todo if redo or _unfinished(out_path(pass_, t["id"]), t, retry_failed)]
    if redo:
        for t in pending:
            if (f := out_path(pass_, t["id"])).exists():
                n = 1 + sum(1 for _ in out_dir(pass_).glob(f"{t['id']}.*.json"))
                f.rename(f.with_name(f"{t['id']}.{n}.json"))
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
            dz._write(f, values.dump({**rec, "status": "context_failed", "why": f"plan: {why}", "raw": raw}))
            counts["failed"] += 1
            continue
        files = ["topic.json"]
        if plan["runnable"]:
            results: dict[str, list[dict]] = {}
            try:
                for lab in sorted({lab for r in t["routes"] for lab in r["labels"]}):
                    results[lab] = _scrub_results(runner.run(lab, plan), arms)
            except RunFailed as e:          # the harness's failure: the topic fails (retryable), never a result
                dz._write(f, values.dump({**rec, "status": "context_failed", "why": f"run: {e}"}))
                counts["failed"] += 1
                continue
            dz._write(item / "results.json", values.dump({"plan": {k: plan[k] for k in ("files", "commands", "show")},
                                                          "routes": by_route(t, results, clean)}))
            files.append("results.json")
        got, why, raw = dz._ask(j, write_prompt(plan["runnable"]), item, files,
                                lambda x: parse_written(x, [r["route_no"] for r in t["routes"]], labs, arms,
                                                        plan["runnable"]),
                                "one JSON object")
        if got is None:
            dz._write(f, values.dump({**rec, "status": "context_failed", "why": f"write: {why}", "raw": raw}))
            counts["failed"] += 1
            continue
        dz._write(f, values.dump({**rec, "status": "ok", "runnable": plan["runnable"], "plan_why": plan["why"],
                                  "context": got}))
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
