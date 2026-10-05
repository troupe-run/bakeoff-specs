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
from dataclasses import dataclass
from pathlib import Path
from runner import config, docker, gitops, paths
from runner.paths import Paths
from runner.scoring import collect, evidence, values

# The ONLY hard-coded knowledge: what config cannot tell us. Everything else (arm, repo, tool, plugin, spec folders,
# entry / must_run commands) is derived from runner/config/arms/<arm>.toml in vocabulary().
_TABLE = {
    "to_repo": "repo",                       # bakeoff-specs-<arm>, the config's repo_name
    "to_method": "method",                   # arm names, tool names, plugin names, aliases
    "to_tracker": "tracker",                 # a tracker's name (beads)
    "to_tracker_cli": "tracker-cli",         # the tracker's CLI (bd ...)
    "to_folder": "spec/",                    # tool-specific folders (specs/ .specify/ openspec/ .kiro/ kitty-specs/ ...)
    "to_command": "/method-command",         # slash commands
    "to_bare_command": "method-command",     # the same family without its slash (skill folder names)
    "command_families": r"(?:speckit-|opsx:|kiro-|spec-kitty\.|superpowers:)[\w-]+",
    "repo_family": r"bakeoff-specs-(?:[\w\-\u2026]|\.(?=\w))*",     # also truncated forms: bakeoff-specs-cc...
    "generic_spec_paths": {"docs/"},         # spec_paths that name no method (control's docs/)
    "tracker_paths": {".beads/": "tracker/"},   # a tracker's folder: it identifies the arm that uses it (R24)
    "generic_owners": {"github"},            # tool-name parts too common to scrub ("github/spec-kit")
    # names a method goes by that its config does not carry (matched on word boundaries, separator variants too)
    "aliases": {"ccsdd": ["kiro"], "openspec": ["opsx"], "speckitty": ["kitty", "kittify"]},
    "tracker_aliases": ["beads"],            # every arm: a tracker the methods use
    # CLI forms, as regexes (non-capturing groups only); replacement is the key
    "cli_forms": {
        "to_tracker_cli": [r"(?<![\w.-])bd(?![\w-])"],
        "to_method": [r"specify[-_ ]?cli", r"(?<![\w-])specify\s+(?:init|check|version|bug|extension|workflow|integration)\b"],
    },
    "min_part": 4,
    "bounded_below": 6,                      # names shorter than this (and every alias, owner part) need word boundaries
}
# Method vocabulary deliberately NOT scrubbed (it is the method's own prose or a shared platform word); the report's
# blinding disclosure quotes this list: a judge can still infer a method family from these.
RESIDUAL_VOCABULARY = (
    "steering", "mission", "WP (work package)", "claude-plugins-official", "constitution", "charter", "proposal",
    "delta spec", "converge", "brainstorming", "skills and command names without a method prefix",
)
TRAILERS = re.compile(r"^[+\- ]?(?:Co-Authored-By|Claude-Session|Signed-off-by):.*$\n?", re.I | re.M)
ESCAPED_TRAILERS = re.compile(r"(?:(?:\\n)+|(?<![\w-]))(?:Co-Authored-By|Claude-Session|Signed-off-by):[^\n\"\\]*", re.I)
MAX_TEXT = 1024 * 1024
MAX_GZ = 64 * 1024 * 1024
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


@dataclass
class Vocab:
    names: list[str]          # arm, tool, tool parts, plugins: scrubbed in every separator variant
    aliases: list[str]        # table names and trackers: same, always on word boundaries
    repos: list[str]
    folders: list[str]
    trackers: list[str]
    commands: list[str]


def vocabulary(arm: str) -> Vocab:
    a = _load(arm)
    names: list[str] = [] if arm == "control" else [arm]       # `control` is an ordinary English word
    v = Vocab(names, list(_TABLE["aliases"].get(arm, [])) + list(_TABLE["tracker_aliases"]),
              [f"bakeoff-specs-{arm}"], [], [], [])
    if a:
        v.repos.append(a.repo_name)
        tool = a.tool.strip()
        if not re.search(r"\s", tool):                          # "plain Claude Code, no methodology" is prose
            names.append(tool)
            for part in tool.split("/"):
                if len(part) >= _TABLE["min_part"] and part.lower() not in _TABLE["generic_owners"]:
                    names.append(part)
        names += [p.name for p in a.plugins]
        for sp in a.spec_paths:
            if sp.path in _TABLE["tracker_paths"]:
                v.trackers.append(sp.path)
            elif sp.path not in _TABLE["generic_spec_paths"] and "*" not in sp.path:
                v.folders.append(sp.path)
        cmds = [a.entry, a.bug_entry, *a.must_run, *(f.get("command", "") for f in a.fresh_session_before)]
        v.commands = [c for c in map(_command_of, cmds) if c]
    return v


def banned_words(arm: str) -> list[str]:
    """Every literal name a scrubbed text must not contain for `arm` (tests derive their banned list from here)."""
    v = vocabulary(arm)
    return sorted({*v.names, *v.aliases, *(f.rstrip("/") if f.startswith(".") or "-" in f else f for f in v.folders), *(t.rstrip("/") for t in v.trackers)})


def _variant(name: str, bounded: bool) -> str:
    """A name as a regex matching every `-`, `_`, space or no separator between its parts, case-insensitively."""
    split = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name.strip())           # OpenSpec -> Open Spec
    body = "[-_ ]?".join(re.escape(p).lower() for p in re.split(r"[-_ ]+", split) if p)
    return rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])" if bounded else body


def scrub_terms(arm: str) -> list[Term]:
    """(what, replacement) pairs: regex families first (commands, repo names), then literal paths and commands longest
    first, then name variants and CLI forms longest first."""
    v = vocabulary(arm)
    literals: dict[str, str] = {r: _TABLE["to_repo"] for r in v.repos}
    for c in v.commands:
        literals[c] = _TABLE["to_command"]
    for f in v.folders:
        stem = f.rstrip("/")
        literals[f if f.endswith("/") else f + "/"] = _TABLE["to_folder"]
        if stem.startswith(".") or "-" in stem:                 # `.specify` / `kitty-specs` without the slash
            literals.setdefault(stem, _TABLE["to_folder"].rstrip("/"))
    for t in v.trackers:
        to = _TABLE["tracker_paths"][t]
        literals[t] = to
        literals.setdefault(t.rstrip("/"), to.rstrip("/"))
    variants: dict[str, str] = {}
    for n in v.names:
        bounded = len(re.sub(r"[-_ /]", "", n)) < _TABLE["bounded_below"] or n in _owner_parts(arm)
        variants.setdefault(_variant(n, bounded), _TABLE["to_method"])
    for n in v.aliases:
        variants.setdefault(_variant(n, True), _TABLE["to_tracker"] if n in _TABLE["tracker_aliases"] else _TABLE["to_method"])
    for key, pats in _TABLE["cli_forms"].items():
        for pat in pats:
            variants.setdefault(pat, _TABLE[key])
    families: list[Term] = [(Rx("/" + _TABLE["command_families"]), _TABLE["to_command"]),
                            (Rx(r"(?<![\w/])" + _TABLE["command_families"]), _TABLE["to_bare_command"]),
                            (Rx(_TABLE["repo_family"]), _TABLE["to_repo"])]
    return (families + sorted(literals.items(), key=lambda kv: (-len(kv[0]), kv[0]))
            + [(Rx(k), r) for k, r in sorted(variants.items(), key=lambda kv: (-len(kv[0]), kv[0]))])


def _owner_parts(arm: str) -> set[str]:
    a = _load(arm)
    if not a or re.search(r"\s", a.tool) or "/" not in a.tool:
        return set()
    return set(a.tool.strip().split("/"))


def pass_terms(arms: list[str]) -> list[Term]:
    """One term list for the whole pass: every arm's names are scrubbed from every arm's files (a spec or a question
    may mention another method, even one this pass did not run). Same tiers as scrub_terms()."""
    fams: dict[str, Term] = {}
    lits: dict[str, str] = {}
    vars_: dict[str, str] = {}
    for a in sorted({*arms, *(f.stem for f in config.ARMS_DIR.glob("*.toml"))}):   # every configured arm, run or not
        for t, r in scrub_terms(a):
            if isinstance(t, Rx):
                (fams if t in _FAMILY_KEYS else vars_).setdefault(str(t), r)
            else:
                lits.setdefault(t, r)
    return ([(Rx(k), r) for k, r in fams.items()] + sorted(lits.items(), key=lambda kv: (-len(kv[0]), kv[0]))
            + [(Rx(k), r) for k, r in sorted(vars_.items(), key=lambda kv: (-len(kv[0]), kv[0]))])


_FAMILY_KEYS = {"/" + _TABLE["command_families"], r"(?<![\w/])" + _TABLE["command_families"], _TABLE["repo_family"]}


@functools.lru_cache(maxsize=64)
def _compiled(key: tuple) -> tuple[re.Pattern, dict[str, str]]:
    parts, repl = [], {}
    for i, (is_re, pat, rep) in enumerate(key):
        parts.append(f"(?P<t{i}>{pat if is_re else re.escape(pat)})")
        repl[f"t{i}"] = rep
    return re.compile("|".join(parts), re.I), repl


def scrub(text: str, terms: list[Term]) -> str:
    """Trailers out (own lines, and after an escaped `\\n`), then every term in ONE pass (so no replacement is itself
    re-scrubbed), in the terms' order."""
    text = ESCAPED_TRAILERS.sub("", TRAILERS.sub("", text))
    if not terms:
        return text
    rx, repl = _compiled(tuple((isinstance(t, Rx), str(t), r) for t, r in terms))
    return rx.sub(lambda m: repl[m.lastgroup], text)


# --- the tree --------------------------------------------------------------------------------------------------
def _safe_rel(rel: str) -> str:
    return "/".join(c if c not in ("", ".", "..") else "_" for c in rel.split("/"))


def _gunzip_text(f: Path) -> str | None:
    """The text of a `.gz` file, or None when it is not gzip, is over 64 MB or is not UTF-8."""
    try:
        with gzip.open(f, "rb") as g:
            data = g.read(MAX_GZ + 1)
        return data.decode("utf-8") if len(data) <= MAX_GZ else None
    except (OSError, EOFError, zlib.error, UnicodeDecodeError):
        return None


def copy_scrubbed(src: Path, dest: Path, terms: list[Term]) -> list[str]:
    """Every file under `src` into `dest`, content and path scrubbed. Text (UTF-8, < 1 MB) is scrubbed, anything
    else copied as is. A `.gz` file is NEVER copied raw: it is gunzipped and scrubbed as text under its name without
    `.gz` (or, if it cannot be read as text, left out and listed). A symlink is never followed or recreated: it
    becomes a regular file `<name>.symlink` holding its scrubbed target. Returns the scrubbed paths of the files
    copied UNSCRUBBED (binary, or 1 MB and over) and of those left out. Two files whose scrubbed paths collide keep
    the first and suffix the rest `~2`, `~3`."""
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
            elif f.is_file() and name.endswith(".gz"):
                text = _gunzip_text(f)
                if text is None:
                    unscrubbed.append(f"{scrub(rel, terms)} (left out: not readable as text)")
                else:
                    put(rel[:-3], scrub(text, terms).encode("utf-8"))
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
def _turn_lines(stream: Path, terms: list[Term]) -> list[str]:
    """One scrubbed line per assistant text and tool call (scrubbed BEFORE any truncation)."""
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
                        out.append(scrub("assistant: " + b["text"].replace("\n", "\\n"), terms))
                    elif b.get("type") == "tool_use":
                        inp = scrub(json.dumps(b.get("input"), sort_keys=True, ensure_ascii=False), terms)
                        if len(inp) > MAX_TOOL_INPUT:
                            inp = inp[:MAX_TOOL_INPUT] + f"...[truncated {len(inp) - MAX_TOOL_INPUT} chars]"
                        out.append(scrub(f"tool: {b.get('name')} ", terms) + inp)
    except (OSError, EOFError, zlib.error):
        out.append("(this turn's stream could not be read)")
    return out


def transcript(step_dir: Path, terms: list[Term]) -> str | None:
    """The final attempt's scrubbed assistant text and tool calls; None when the step has no turn streams."""
    found = evidence.arm_streams(step_dir)
    if not found:
        return None
    last = max(a for a, _ in found)
    lines: list[str] = []
    for _, f in (x for x in found if x[0] == last):
        lines += [f"## {f.name.removesuffix('.stream.jsonl.gz')}", *_turn_lines(f, terms), ""]
    return "\n".join(lines)


def _one(v) -> str:
    return "" if v is None else str(v).replace("\r", "")


def questions_md(step_dir: Path) -> str:
    """The step's questions, scored run first. Assumes the scored run exists (run.json): an absent questions.jsonl
    then means the arm asked none (R25)."""
    out = []
    for title, p in (("Scored run", step_dir / "questions.jsonl"), ("Discovery run", step_dir / "a" / "questions.jsonl")):
        got = evidence.read_jsonl(p)
        if got is None and title != "Scored run":
            continue
        recs, skipped = got or ([], 0)
        out.append(f"## {title}\n")
        for q in recs:
            out.append(f"### Question {q.get('n')} ({q.get('kind')}, answered by {q.get('answered_by')})\n")
            out.append(f"Arm asked: {_one(q.get('arm_message'))}\n")
            out.append(f"Reply: {_one(q.get('reply', q.get('final_reply')))}\n")
            if q.get("escalated"):
                out.append(f"Escalated: {json.dumps(q['escalated'], sort_keys=True, ensure_ascii=False)}\n")
        if not recs:
            out.append("The arm asked no questions at this step.\n" if title == "Scored run" else "(none)\n")
        if skipped:
            out.append(f"({skipped} malformed line(s) skipped)\n")
    return "\n".join(out)


def gates_md(step_dir: Path) -> str:
    recs = evidence.read_jsonl(step_dir / "owner-gates.jsonl")
    if recs is None:
        return "No gates recorded at this step.\n"
    out = []
    for g in recs[0]:
        out.append(f"### Gate {g.get('n')} (attempt {g.get('attempt')}, {g.get('kind')})\n")
        out.append(f"Arm asked: {_one(g.get('arm_message'))}\n")
        out.append(f"PO verdict: {_one(g.get('po_verdict'))}\n")
        out.append(f"Owner action: {_one(g.get('owner_action'))}; approved: {_one(g.get('approved'))}\n")
        out.append(f"Final reply: {_one(g.get('final_reply', g.get('reply')))}\n")
    if recs[1]:
        out.append(f"({recs[1]} malformed line(s) skipped)\n")
    return "\n".join(out) if out else "No gates recorded at this step.\n"


def _ran(step_dir: Path) -> bool:
    return not values.is_missing(evidence.run_record(step_dir))


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
        _w(dest / "UNSCRUBBED.txt", "Copied without scrubbing (binary or 1 MB and over), or left out:\n"
           + "\n".join(listed) + "\n")


def _missing(dest: Path, items: list[tuple[str, str]], terms: list[Term]) -> None:
    if items:
        _w(dest / "MISSING.md", scrub("# Missing\n\n" + "".join(f"- {w}: {why}\n" for w, why in items), terms))


def run(pass_: str) -> Path:
    """Writes scoring_out/anon/<label>/<NN>/{repo/, diff.patch, transcript.md, questions.md, gates.md,
    others-questions.md, [UNSCRUBBED.txt], [MISSING.md]}, <label>/setup/ and, last, scoring_out/anon-key.json.
    Evidence that is absent is named in MISSING.md, never written as a file that looks like input. Returns anon/."""
    out = paths.scoring_out(pass_)
    anon, key_path, tmp = out / "anon", out / "anon-key.json", out / "anon-tmp"
    for d in (anon, tmp):
        shutil.rmtree(d, ignore_errors=True)
    key_path.unlink(missing_ok=True)                # no key until the whole run finished
    pass_dir = paths.RESULTS / pass_
    arms = collect.arms(pass_dir)
    lab = labels(arms, pass_)
    t = pass_terms(arms)
    steps = {a: _step_dirs(pass_dir / a) for a in arms}
    failures: list[str] = []
    anon.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        for nn in steps[arm]:
            sd, dest, p = pass_dir / arm / nn, anon / lab[arm] / nn, Paths(pass_, arm)
            miss: list[tuple[str, str]] = []
            shas = _shas(sd)
            if shas is None:
                miss.append(("repo/ and diff.patch", "git.json has no sha_before/sha_after for this step"))
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
                    miss.append(("repo/ and diff.patch", f"export or diff failed: {e}"))
                finally:
                    shutil.rmtree(work, ignore_errors=True)
            tr = transcript(sd, t)
            if tr is None:
                miss.append(("transcript.md", "no arm turn streams"))
            else:
                _w(dest / "transcript.md", tr)
            if _ran(sd):
                _w(dest / "questions.md", scrub(questions_md(sd), t))
                _w(dest / "gates.md", scrub(gates_md(sd), t))
            else:
                miss += [("questions.md", "no run.json: the scored run is not recorded"),
                         ("gates.md", "no run.json: the scored run is not recorded")]
            _missing(dest, miss, t)
    for arm in arms:                                # R24: the setup records, for the setup_effort and fit judges
        setup = pass_dir / arm / "00-setup"
        if setup.is_dir():
            _unscrubbed_note(anon / lab[arm] / "setup", copy_scrubbed(setup, anon / lab[arm] / "setup", t))
    for arm in arms:                                # R6: the OTHER arms' questions at the same step
        for nn in steps[arm]:
            parts = [f"## {lab[o]}\n\n" + (scrub(questions_md(pass_dir / o / nn), t) if _ran(pass_dir / o / nn)
                                           else "(no scored run recorded for this arm at this step)\n")
                     for o in sorted((o for o in arms if o != arm and nn in steps[o]), key=lab.get)]
            _w(anon / lab[arm] / nn / "others-questions.md", "\n".join(parts) if parts else "(no other arm has this step)\n")
    shutil.rmtree(tmp, ignore_errors=True)
    for f in failures:
        print(f"anonymise: {f}", file=sys.stderr)
    key_path.write_text(values.dump({lab[a]: a for a in arms}), encoding="utf-8")   # last
    return anon
