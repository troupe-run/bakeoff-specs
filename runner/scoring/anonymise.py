"""Plan 3 Task 16: anonymised copies of every arm-step, so judges and the owner score without knowing which method
produced what. Arm identities are scrubbed from file contents, file and directory names, the diff, the transcript,
questions and gates. `anon-key.json` ({label: arm}) is written last and lives OUTSIDE `anon/` (a judge mounts only
labelled directories under `anon/`). The host never runs git: trees and diffs come from `runner.gitops` (container)."""
from __future__ import annotations
import functools
import gzip
import json
import os
import re
import shutil
import sys
import zlib
import random
from pathlib import Path
from runner import config, docker, gitops, paths
from runner.paths import Paths
from runner.scoring import collect, evidence, values

# The ONLY hard-coded knowledge: what config cannot tell us. Everything else (arm, repo, tool, plugin, spec folders,
# entry / must_run commands) is derived from runner/config/arms/<arm>.toml in scrub_terms().
_TABLE = {
    "to_repo": "repo",                       # bakeoff-specs-<arm>, the config's repo_name
    "to_method": "method",                   # arm names, tool names, plugin names, aliases
    "to_folder": "spec/",                    # tool-specific folders (specs/ .specify/ openspec/ .kiro/ kitty-specs/ ...)
    "to_command": "/method-command",         # slash commands
    "to_bare_command": "method-command",     # the same family without its slash (skill folder names)
    "command_families": r"(?:speckit-|opsx:|kiro-|spec-kitty\.|superpowers:)[\w-]+",
    "generic_spec_paths": {"docs/"},         # spec_paths that name no method (control's docs/)
    "tracker_paths": {".beads/": "tracker/"},   # a tracker's folder: it identifies the arm that uses it (R24)
    "generic_owners": {"github"},            # tool-name parts too common to scrub ("github/spec-kit")
    "aliases": {"ccsdd": ["kiro"], "openspec": ["opsx"]},   # names for a method that its config does not carry
    "min_part": 4,
}
TRAILERS = re.compile(r"^[+\- ]?(?:Co-Authored-By|Claude-Session|Signed-off-by):.*$\n?", re.I | re.M)
MAX_TEXT = 1024 * 1024
MAX_TOOL_INPUT = 2000
_STEP_DIR = re.compile(r"^\d\d$")

class Rx(str):
    """A term that is a regular expression, not a literal (a str, so every term's first item is one)."""


Term = tuple[str, str]


def labels(arms: list[str], seed: str) -> dict[str, str]:
    order = sorted(arms)
    random.Random(seed).shuffle(order)
    return {a: f"Arm {chr(65 + i)}" for i, a in enumerate(order)}


def _load(arm: str):
    try:
        return config.load_arm(arm)
    except FileNotFoundError:               # fixture arms have no arms/<name>.toml
        return None


def _command_of(line: str) -> str | None:
    tok = line.strip().split(None, 1)[0] if line.strip() else ""
    return tok if tok.startswith("/") and len(tok) > 1 else None


def scrub_terms(arm: str) -> list[Term]:
    """(what, replacement) pairs, regex families first, then literals longest first."""
    a = _load(arm)
    names: list[str] = [] if arm == "control" else [arm]       # `control` is an ordinary English word
    repos = [f"bakeoff-specs-{arm}"] + ([a.repo_name] if a else [])
    folders: list[str] = []
    trackers: list[str] = []
    commands: list[str] = []
    if a:
        tool = a.tool.strip()
        if not re.search(r"\s", tool):                          # "plain Claude Code, no methodology" is prose
            names.append(tool)
            for part in tool.split("/"):
                if len(part) >= _TABLE["min_part"] and part.lower() not in _TABLE["generic_owners"]:
                    names.append(part)
        names += [p.name for p in a.plugins]
        for sp in a.spec_paths:
            if sp.path in _TABLE["tracker_paths"]:
                trackers.append(sp.path)
            elif sp.path not in _TABLE["generic_spec_paths"] and "*" not in sp.path:
                folders.append(sp.path)
        cmds = [a.entry, a.bug_entry, *a.must_run, *(f.get("command", "") for f in a.fresh_session_before)]
        commands = [c for c in map(_command_of, cmds) if c]
    names += _TABLE["aliases"].get(arm, [])
    for n in list(names):                                       # spec-kit and speckit are the same name in prose
        if "-" in n:
            names.append(n.replace("-", ""))
    literals: dict[str, str] = {}
    for r in repos:
        literals[r] = _TABLE["to_repo"]
    for n in names:
        literals.setdefault(n, _TABLE["to_method"])
    for c in commands:
        literals[c] = _TABLE["to_command"]
    for f in folders:
        stem = f.rstrip("/")
        literals[f if f.endswith("/") else f + "/"] = _TABLE["to_folder"]
        if stem.startswith(".") or "-" in stem:                 # `.specify` / `kitty-specs` without the slash
            literals.setdefault(stem, _TABLE["to_folder"].rstrip("/"))
    for t in trackers:
        to = _TABLE["tracker_paths"][t]
        literals[t] = to
        literals.setdefault(t.rstrip("/"), to.rstrip("/"))
    families: list[Term] = [(Rx("/" + _TABLE["command_families"]), _TABLE["to_command"]),
                            (Rx(r"(?<![\w/])" + _TABLE["command_families"]), _TABLE["to_bare_command"])]
    return families + sorted(literals.items(), key=lambda kv: (-len(kv[0]), kv[0]))


def pass_terms(arms: list[str]) -> list[Term]:
    """One term list for the whole pass: every arm's names are scrubbed from every arm's files (a spec or a question
    may mention another method, even one this pass did not run). Families first, literals longest first, as scrub_terms()."""
    fams: dict[str, Term] = {}
    lits: dict[str, str] = {}
    for a in sorted({*arms, *(f.stem for f in config.ARMS_DIR.glob("*.toml"))}):   # every configured arm, run or not
        for t, r in scrub_terms(a):
            if isinstance(t, Rx):
                fams.setdefault(str(t), (t, r))
            else:
                lits.setdefault(t, r)
    return list(fams.values()) + sorted(lits.items(), key=lambda kv: (-len(kv[0]), kv[0]))


@functools.lru_cache(maxsize=64)
def _compiled(key: tuple) -> tuple[re.Pattern, dict[str, str]]:
    parts, repl = [], {}
    for i, (is_re, pat, rep) in enumerate(key):
        parts.append(f"(?P<t{i}>{pat if is_re else re.escape(pat)})")
        repl[f"t{i}"] = rep
    return re.compile("|".join(parts), re.I), repl


def scrub(text: str, terms: list[Term]) -> str:
    """Trailers out, then every term in ONE pass (so no replacement is itself re-scrubbed), longest first."""
    text = TRAILERS.sub("", text)
    if not terms:
        return text
    rx, repl = _compiled(tuple((isinstance(t, Rx), str(t), r)
                               for t, r in terms))
    return rx.sub(lambda m: repl[m.lastgroup], text)


# --- the tree --------------------------------------------------------------------------------------------------
def _safe_rel(rel: str) -> str:
    return "/".join(c if c not in ("", ".", "..") else "_" for c in rel.split("/"))


def copy_scrubbed(src: Path, dest: Path, terms: list[Term]) -> list[str]:
    """Every file under `src` into `dest`, content and path scrubbed. Text (UTF-8, < 1 MB) is scrubbed, anything
    else copied as is. A symlink is never followed or recreated: it becomes a regular file `<name>.symlink` holding
    its scrubbed target. Returns the scrubbed paths of the files copied UNSCRUBBED (binary, or 1 MB and over). Two files whose scrubbed paths collide keep the first and suffix the rest `~2`, `~3`."""
    used: set[str] = set()
    unscrubbed: list[str] = []

    def put(rel: str, data: bytes, raw: bool = False) -> None:
        out = _safe_rel(scrub(rel, terms))
        n, cand = 1, out
        while cand in used:
            n += 1
            cand = f"{out}~{n}"
        used.add(cand)
        t = dest / cand
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(data)
        if raw:
            unscrubbed.append(cand)

    for root, dirs, files in os.walk(src, followlinks=False):
        dirs.sort()
        base = Path(root)
        for name in sorted(dirs + files):
            f = base / name
            rel = f.relative_to(src).as_posix()
            if f.is_symlink():
                put(rel + ".symlink", ("-> " + scrub(os.readlink(f), terms) + "\n").encode())
            elif f.is_file():
                data, raw = f.read_bytes(), True
                if len(data) < MAX_TEXT:
                    try:
                        data, raw = scrub(data.decode("utf-8"), terms).encode("utf-8"), False
                    except UnicodeDecodeError:
                        pass
                put(rel, data, raw)
    return sorted(unscrubbed)


# --- per-step evidence ------------------------------------------------------------------------------------------
def _turn_lines(stream: Path) -> list[str]:
    out: list[str] = []
    try:
        with gzip.open(stream, "rt", errors="replace") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(o, dict) or o.get("type") != "assistant":
                    continue
                content = (o.get("message") or {}).get("content")
                for b in content if isinstance(content, list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text" and isinstance(b.get("text"), str):
                        out.append("assistant: " + b["text"].replace("\n", "\\n"))
                    elif b.get("type") == "tool_use":
                        inp = json.dumps(b.get("input"), sort_keys=True, ensure_ascii=False)
                        if len(inp) > MAX_TOOL_INPUT:
                            inp = inp[:MAX_TOOL_INPUT] + f"...[truncated {len(inp) - MAX_TOOL_INPUT} chars]"
                        out.append(f"tool: {b.get('name')} {inp}")
    except (OSError, EOFError, zlib.error):
        out.append("(this turn's stream could not be read)")
    return out


def transcript(step_dir: Path) -> str:
    td = step_dir / "turns"
    found = sorted((int(m[1]), f) for f in (td.iterdir() if td.is_dir() else [])
                   if (m := evidence._ARM_STREAM.match(f.name)))
    if not found:
        return "(no transcript recorded)\n"
    last = max(a for a, _ in found)
    lines: list[str] = []
    for _, f in (x for x in found if x[0] == last):
        lines += [f"## {f.name.removesuffix('.stream.jsonl.gz')}", *_turn_lines(f), ""]
    return "\n".join(lines)


def _records(p: Path) -> list[dict] | None:
    r = evidence._jsonl(p)
    return None if r is None else r[0]


def _one(v) -> str:
    return "" if v is None else str(v).replace("\r", "")


def questions_md(step_dir: Path) -> str:
    out, any_file = [], False
    for title, p in (("Scored run", step_dir / "questions.jsonl"), ("Discovery run", step_dir / "a" / "questions.jsonl")):
        recs = _records(p)
        if recs is None:
            continue
        any_file = True
        out.append(f"## {title}\n")
        for q in recs:
            out.append(f"### Question {q.get('n')} ({q.get('kind')}, answered by {q.get('answered_by')})\n")
            out.append(f"Arm asked: {_one(q.get('arm_message'))}\n")
            out.append(f"Reply: {_one(q.get('reply', q.get('final_reply')))}\n")
            if q.get("escalated"):
                out.append(f"Escalated: {json.dumps(q['escalated'], sort_keys=True, ensure_ascii=False)}\n")
        if not recs:
            out.append("(none)\n")
    return "\n".join(out) if any_file else "(no questions recorded)\n"


def gates_md(step_dir: Path) -> str:
    recs = _records(step_dir / "owner-gates.jsonl")
    if recs is None:
        return "(no gates recorded)\n"
    out = []
    for g in recs:
        out.append(f"### Gate {g.get('n')} (attempt {g.get('attempt')}, {g.get('kind')})\n")
        out.append(f"Arm asked: {_one(g.get('arm_message'))}\n")
        out.append(f"PO verdict: {_one(g.get('po_verdict'))}\n")
        out.append(f"Owner action: {_one(g.get('owner_action'))}; approved: {_one(g.get('approved'))}\n")
        out.append(f"Final reply: {_one(g.get('final_reply', g.get('reply')))}\n")
    return "\n".join(out) if out else "(none)\n"


def _shas(step_dir: Path) -> tuple[str, str] | None:
    g = evidence.read_json(step_dir / "git.json")
    if values.is_missing(g) or not isinstance(g["value"], dict):
        return None
    a, b = g["value"].get("sha_before"), g["value"].get("sha_after")
    return (a, b) if isinstance(a, str) and a and isinstance(b, str) and b else None


def _step_dirs(arm_dir: Path) -> list[str]:
    return sorted(c.name for c in arm_dir.iterdir() if c.is_dir() and _STEP_DIR.match(c.name))


def _w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _unscrubbed_note(dest: Path, listed: list[str]) -> None:
    if listed:
        _w(dest / "UNSCRUBBED.txt", "Copied without scrubbing (binary or 1 MB and over):\n" + "\n".join(listed) + "\n")


def _missing(dest: Path, what: str, why: str, terms: list[Term]) -> None:
    _w(dest / "MISSING.md", scrub(f"# Missing\n\n- What: {what}\n- Why: {why}\n", terms))


def run(pass_: str) -> Path:
    """Writes scoring_out/anon/<label>/<NN>/{repo/, diff.patch, transcript.md, questions.md, gates.md,
    others-questions.md} and, last, scoring_out/anon-key.json. Returns the anon/ directory."""
    out = paths.scoring_out(pass_)
    anon, key_path, tmp = out / "anon", out / "anon-key.json", out / "anon-tmp"
    for d in (anon, tmp):
        shutil.rmtree(d, ignore_errors=True)
    key_path.unlink(missing_ok=True)                # no key until the whole run finished
    pass_dir = paths.RESULTS / pass_
    arms = collect.arms(pass_dir)
    lab = labels(arms, pass_)
    terms = {a: pass_terms(arms) for a in arms}
    steps = {a: _step_dirs(pass_dir / a) for a in arms}
    failures: list[str] = []
    anon.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        for nn in steps[arm]:
            sd, t, dest = pass_dir / arm / nn, terms[arm], anon / lab[arm] / nn
            p = Paths(pass_, arm)
            shas = _shas(sd)
            if shas is None:
                _missing(dest, "repo/ and diff.patch", "git.json has no sha_before/sha_after for this step", t)
            else:
                work = tmp / arm / nn
                try:
                    gitops.export_tree(p, shas[1], work)
                    listed = copy_scrubbed(work, dest / "repo", t)
                    _w(dest / "diff.patch", scrub(gitops.diff_text(p, *shas), t))
                    _unscrubbed_note(dest, listed)
                except (gitops.GitError, docker.ContainerError, OSError) as e:
                    failures.append(f"{arm}/{nn}: {e}")
                    shutil.rmtree(dest / "repo", ignore_errors=True)
                    (dest / "diff.patch").unlink(missing_ok=True)
                    (dest / "UNSCRUBBED.txt").unlink(missing_ok=True)
                    _missing(dest, "repo/ and diff.patch", f"export or diff failed: {e}", t)
                finally:
                    shutil.rmtree(work, ignore_errors=True)
            _w(dest / "transcript.md", scrub(transcript(sd), t))
            _w(dest / "questions.md", scrub(questions_md(sd), t))
            _w(dest / "gates.md", scrub(gates_md(sd), t))
    for arm in arms:                                # R24: the setup records, for the setup_effort and fit judges
        setup = pass_dir / arm / "00-setup"
        if setup.is_dir():
            _unscrubbed_note(anon / lab[arm] / "setup", copy_scrubbed(setup, anon / lab[arm] / "setup", terms[arm]))
    for arm in arms:                                # R6: the OTHER arms' questions at the same step
        for nn in steps[arm]:
            parts = [f"## {lab[o]}\n\n" + scrub(questions_md(pass_dir / o / nn), terms[o])
                     for o in sorted((o for o in arms if o != arm and nn in steps[o]), key=lab.get)]
            _w(anon / lab[arm] / nn / "others-questions.md", "\n".join(parts) if parts else "(no other arm has this step)\n")
    shutil.rmtree(tmp, ignore_errors=True)
    for f in failures:
        print(f"anonymise: {f}", file=sys.stderr)
    key_path.write_text(values.dump({lab[a]: a for a in arms}), encoding="utf-8")   # last
    return anon
