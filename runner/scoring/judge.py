"""Judged parts (spec §6): three lenses per part, anonymised inputs, one JSON verdict per call, written as it lands.

A judge sees only one item's anonymised inputs (`anon/<label>/<NN>/` or `anon/<label>/setup/`), read-only at
`/judge`. Verdicts are written under the REAL arm name (`judged/<part>/<arm>/<NN|arm>/<lens>.json`), a path the
judge never sees; the arm -> label map comes from `anon-key.json`, which is read here on the host and never mounted
or quoted. A verdict is `ok` (score 0-4 with evidence), `not_applicable` (only where the rubric offers it, R5),
`judge_failed` (two unusable replies) or `input_missing` (the item's evidence is absent, so no judge is asked,
R24(d)). Only `ok` is a score."""
from __future__ import annotations
import hashlib, json, os, re, shutil, time
from datetime import date
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol
from runner import config, credentials, egress, paths, session, transcripts
from runner.docker import Mount
from runner.scoring import anonymise, inputs, values

TOOLS = "Read,Glob,Grep"
TRANSIENT = ("no_result", "is_error")        # retried in place with limits.transient_backoff (as po.decide)
AT_ONCE = ("auth_failed", "timeout")         # never retried: a credential fault / a hung judge is the harness's
_FILES = {"repo": "repo/", "diff": "diff.patch", "transcript": "transcript.md", "questions": "questions.md",
          "gates": "gates.md", "stale_list": "stale-list.toml"}
_APPROVAL = re.compile(r"approved (\d{4}-\d{2}-\d{2}) (\d+)")


class BadReply(ValueError):
    pass


class PinViolation(RuntimeError):
    """A judge call ran on (or could not be shown to run on) the pinned model: a harness fault, never a score."""


class SessionError(RuntimeError):
    """The judge session itself failed (auth, timeout, or transient failures past the backoff schedule)."""

    def __init__(self, outcome: str, detail: str = ""):
        super().__init__(f"judge session {outcome}: {detail[:200]}")
        self.outcome, self.detail = outcome, detail


@dataclass
class Verdict:
    score: int | None
    status: str
    evidence: list[str] = field(default_factory=list)
    notes: str = ""
    raw: str = ""


def _evidence(o: dict) -> list[str]:
    ev = o.get("evidence")
    if not isinstance(ev, list) or not ev or not all(isinstance(x, str) and x.strip() for x in ev):
        raise BadReply("needs at least one evidence citation (path, sha or transcript line)")
    return ev


def parse(text: str, *, na_allowed: bool = False) -> Verdict:
    """One JSON object: `{"score": 0-4, "evidence": [...], "notes": str}`, or (R5, where `na_allowed`)
    `{"score": null, "status": "not_applicable", "evidence": [...], "notes": str}`. Anything else is a BadReply."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        o = json.loads(m[0]) if m else None
    except json.JSONDecodeError as e:
        raise BadReply(f"not JSON: {e}") from e
    if not isinstance(o, dict):
        raise BadReply("needs one JSON object")
    status = o.get("status", "ok")
    if status == "not_applicable":
        if not na_allowed:
            raise BadReply("'not applicable' is not an option for this part: give an integer score 0-4")
        if o.get("score") is not None:
            raise BadReply("a not_applicable reply carries \"score\": null")
        return Verdict(None, "not_applicable", _evidence(o), str(o.get("notes", "")), text)
    if status != "ok":
        raise BadReply(f"unknown status {status!r}")
    if type(o.get("score")) is not int or not 0 <= o["score"] <= 4:
        raise BadReply("needs an integer score 0-4")
    return Verdict(o["score"], "ok", _evidence(o), str(o.get("notes", "")), text)


class Judge(Protocol):
    def ask(self, prompt: str, inputs: Path, files: list[str] = ...) -> str: ...


class FakeJudge:
    def __init__(self, replies: list[str]):
        self.replies, self.prompts, self.inputs, self.files = list(replies), [], [], []

    def ask(self, prompt: str, inputs: Path, files: list[str] = ()) -> str:
        self.prompts.append(prompt)
        self.inputs.append(inputs)
        self.files.append(list(files))
        return self.replies.pop(0)


def ask_with_retry(j: Judge, prompt: str, inputs_dir: Path, files: list[str] = (), *,
                   na_allowed: bool = False) -> Verdict:
    """A BadReply gets one more ask with the parse error appended; a second is `judge_failed`, never a score.
    `files` are the item's selected inputs (relative to `inputs_dir`): the only ones a container judge mounts."""
    reply = j.ask(prompt, inputs_dir, files)
    try:
        return parse(reply, na_allowed=na_allowed)
    except BadReply as e:
        reply = j.ask(f"{prompt}\n\nYour previous reply could not be used ({e}). Reply with one JSON object only.",
                      inputs_dir, files)
        try:
            return parse(reply, na_allowed=na_allowed)
        except BadReply as e2:
            return Verdict(None, "judge_failed", notes=str(e2), raw=reply)


# ---- what to judge ---------------------------------------------------------------------------------------------

def na_allowed(r: inputs.Rubric) -> bool:
    """R5/R27: 'not applicable' is an answer only where the rubric sets `not_applicable = true` (step units only)."""
    return r.not_applicable and r.unit == "step"


def prompt(rubric: inputs.Rubric, lens: dict, key: str, files: list[str]) -> str:
    transcripts = any(f.endswith("/transcript.md") for f in files)
    where = (("as a whole, from its setup record" + (" and its step transcripts" if transcripts else ""))
             if key == "arm" else f"at step {int(key)}")
    levels = "\n".join(f"{n}: {rubric.levels[n]}" for n in range(5))
    listing = "\n".join(f"- /judge/{f}" for f in files)
    na = ("\n\nIf, and only if, the rubric or your lens says there is nothing to judge here, reply instead with\n"
          '{"score": null, "status": "not_applicable", "evidence": ["<where you checked>"], "notes": "<why>"}'
          if na_allowed(rubric) else "")
    return (f"You are a judge in a blind comparison of software development methods. You are judging Arm X {where}; "
            "you do not know which method it used and must not guess.\n\n"
            f"Part: {rubric.part} (dimension: {rubric.dimension}).\n\n"
            f"Score it 0-4 against these anchored levels:\n{levels}\n\n"
            f"Your lens ({lens['name']}): {lens['perspective']}\n\n"
            f"Your inputs (read-only; use Read, Glob and Grep):\n{listing}\n\n"
            "Cite at least one file path with line, commit, or transcript line for your score.\n\n"
            "Reply with exactly one JSON object and nothing else:\n"
            '{"score": <integer 0-4>, "evidence": ["<path:line, commit sha or transcript line>", ...], '
            '"notes": "<one or two sentences>"}' + na)


def anon_key(pass_: str) -> dict[str, str]:
    """{label: arm}. Read on the host only; never mounted into, or quoted to, a judge."""
    f = paths.scoring_out(pass_) / anonymise.KEY
    if not f.exists():
        raise inputs.InputError(f"{f} is missing: run the anonymise stage first")
    return anonymise.read_key(pass_)


def key_digest(pass_: str) -> str:
    """anonymise.key_digest, refusing clearly when there is no key."""
    anon_key(pass_)
    return anonymise.key_digest(pass_)


def check_key(pass_: str, recorded: str | None, what: str) -> None:
    """R37: refuse when `what` was made under a different anon-key.json (labels may differ) or records none."""
    now = key_digest(pass_)
    if recorded != now:
        raise inputs.InputError(
            f"{what} was made under {'a different' if recorded else 'an unrecorded'} anonymisation key "
            f"(anon-key.json sha256 {now[:12]}, recorded {recorded[:12] if recorded else 'none'}): its labels may not "
            f"match. Restore the anon-key.json it was made with, or redo it under the current key.")


def _label(pass_: str, arm: str) -> str:
    return {a: lab for lab, a in anon_key(pass_).items()}[arm]


def items(pass_: str) -> list[tuple[str, str, str, str]]:
    """(part, arm, key, lens) for every judged part x arm x applicable step with an anonymised copy (or `"arm"`
    for arm-unit parts) x the rubric's three lenses — sorted."""
    anon = paths.scoring_out(pass_) / "anon"
    labels = {a: lab for lab, a in anon_key(pass_).items()}
    out = []
    for part, r in inputs.load_rubrics().items():
        for arm in sorted(labels):
            keys = ["arm"] if r.unit == "arm" else [f"{n:02d}" for n in r.steps if (anon / labels[arm] / f"{n:02d}").is_dir()]
            out += [(part, arm, k, l["name"]) for k in keys for l in r.lenses]
    return sorted(out)


def inputs_for(pass_: str, part: str, arm: str, key: str) -> tuple[Path, list[str]]:
    """The item's anonymised directory and the files its rubric's evidence kinds select (relative to it). Pure: it
    writes nothing (anonymise writes every input, `stale-list.toml` included)."""
    r = inputs.load_rubrics()[part]
    base = paths.scoring_out(pass_) / "anon" / _label(pass_, arm)
    if r.unit == "arm":
        setup = base / "setup"
        files = sorted(f"setup/{f.relative_to(setup)}" for f in setup.rglob("*") if f.is_file()) if setup.is_dir() else []
        if "transcript" in r.evidence and files:                 # the arm's own steps, every one it reached
            files += sorted(f"{s.name}/transcript.md" for s in base.iterdir() if s.is_dir() and s.name.isdigit())
        return base, sorted(files)
    d = base / key
    files = {_FILES[k] for k in r.evidence if k in _FILES}
    if part == "question_value":
        files.add("others-questions.md")                         # R6: other arms' questions at the same step
    return d, sorted(files)


def _missing_json(d: Path) -> dict[str, str]:
    """anonymise's MISSING.json (`[{"files": [...], "why": ...}]`) as {file: why}."""
    f = d / "MISSING.json"
    try:
        entries = json.loads(f.read_text()) if f.exists() else []
        return {name: e["why"] for e in entries for name in e["files"]}
    except (ValueError, KeyError, TypeError) as e:
        raise inputs.InputError(f"{f}: unreadable ({e!r}); re-run anonymise") from e


def absent(d: Path, files: list[str]) -> list[str]:
    """R24(d): what of the item's required input is absent (or named in MISSING.json). Empty means ask a judge."""
    if not d.is_dir() or not files:
        return [f"{d.name}/: no evidence recorded"]
    named = _missing_json(d)
    return [f"{f}: {named.get(f, 'absent')}" for f in files if f in named or not (d / f).exists()]


def out_path(pass_: str, part: str, arm: str, key: str, lens: str) -> Path:
    return paths.scoring_out(pass_) / "judged" / part / arm / key / f"{lens}.json"


def _write(out: Path, v: Verdict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(values.dump(asdict(v)))
    os.replace(tmp, out)                                      # never a half-written file a resume would skip


def _unfinished(out: Path, retry_failed: bool) -> bool:
    """No verdict yet; or `input_missing` (re-checked every run, R27); or `judge_failed` when `retry_failed`."""
    if not out.exists():
        return True
    try:
        status = json.loads(out.read_text()).get("status")
    except (OSError, ValueError, AttributeError):
        return True
    return status == "input_missing" or (retry_failed and status == "judge_failed")


def run(pass_: str, j: Judge, *, retry_failed: bool = False) -> dict:
    """Asks every unfinished item (resumable) and writes each verdict as it lands."""
    rubrics, counts = inputs.load_rubrics(), {"asked": 0, "skipped": 0, "input_missing": 0}
    for part, arm, key, lens in items(pass_):
        out = out_path(pass_, part, arm, key, lens)
        if not _unfinished(out, retry_failed):
            counts["skipped"] += 1
            continue
        d, files = inputs_for(pass_, part, arm, key)
        r = rubrics[part]
        gone = absent(d, files)
        if gone:
            v = Verdict(None, "input_missing", [], "; ".join(gone))
            counts["input_missing"] += 1
        else:
            lens_d = next((l for l in r.lenses if l["name"] == lens), {"name": lens, "perspective": ""})
            v = ask_with_retry(j, prompt(r, lens_d, key, files), d, files, na_allowed=na_allowed(r))
            counts["asked"] += 1
        _write(out, v)
    return counts


def _size(p: Path) -> int:
    if p.is_symlink():
        return 0
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink()) if p.is_dir() else 0


def estimate(pass_: str, *, retry_failed: bool = False) -> dict:
    """Calls the judge stage would make now (unfinished items with their inputs present, input_missing ones that
    are now answerable included; parse retries not counted) and the size of the inputs those calls read."""
    calls, size = 0, 0
    for part, arm, key, lens in items(pass_):
        if not _unfinished(out_path(pass_, part, arm, key, lens), retry_failed):
            continue
        d, files = inputs_for(pass_, part, arm, key)
        if absent(d, files):
            continue
        calls += 1
        size += sum(_size(d / f) for f in files)
    return {"calls": calls, "input_mb": round(size / 1e6, 3)}


def check_approval(pass_: str, calls: int) -> None:
    """The owner's `judge-approved` file: one line `approved <YYYY-MM-DD> <calls>`. Refuses (InputError) when it is
    absent or malformed, or when `calls` (the current estimate) exceeds the approved number."""
    f = paths.scoring_out(pass_) / "judge-approved"
    how = (f"run `runner score {pass_} --stage judge-estimate`, read it, then write {f} with one line: "
           "approved <date> <calls>")
    if not f.exists():
        raise inputs.InputError(f"{f} is missing: {how}")
    m = _APPROVAL.fullmatch(f.read_text().strip())
    try:
        ok = m is not None and date.fromisoformat(m[1]) is not None
    except ValueError:
        ok = False
    if not ok:
        raise inputs.InputError(f"{f} is malformed: {how}")
    if calls > int(m[2]):
        raise inputs.InputError(f"the judge and decision stages would now make {calls} calls, but {f} has approved "
                                f"{m[2]}: re-read the estimate and approve again")


def implied_cost(pass_: str, calls: int) -> dict:
    """The judge stage's cost if a judge call costs what a PO call did on average in this pass (cost.json)."""
    usd, turns = 0.0, 0
    for f in sorted((paths.RESULTS / pass_).glob("*/*/cost.json")):
        try:
            po = json.loads(f.read_text()).get("po") or {}
            usd, turns = usd + float(po.get("usd") or 0), turns + int(po.get("turns") or 0)
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    if not turns:
        return {"po_usd_per_call": None, "implied_usd": None}
    return {"po_usd_per_call": round(usd / turns, 4), "implied_usd": round(usd / turns * calls, 2)}


# ---- the container judge -----------------------------------------------------------------------------------------

def judge_env(pins: config.Pins) -> dict[str, str]:
    return credentials.session_env(pins, config.load_arm("control"), role="judge", isolated=True, tools=TOOLS) \
        | {"CLAUDE_CODE_SAFE_MODE": "1"}


def mounts(home: Path, item_dir: Path, files: list[str]) -> list[Mount]:
    """The call's fresh home, and each selected input read-only at `/judge/<name>` — never the whole item."""
    return [Mount(home, "/home/actor", False),
            *(Mount(item_dir / f.rstrip("/"), f"/judge/{f.rstrip('/')}", True) for f in files)]


def check_mounts(ms: list[Mount], pass_: str) -> None:
    """A judge sees one fresh home (a directory strictly under `judge_home`) and ONE item's selected inputs, each
    read-only under `/judge/` — nothing else: never anon-key.json, a whole item, label or anon/, results/ outside
    them, tests/, reference/ or state/<pass>/ (nor a directory containing any of them)."""
    root, out = paths.REPO_ROOT.resolve(), paths.scoring_out(pass_).resolve()
    anon, home = out / "anon", paths.judge_home(pass_).resolve()
    forbidden = [out / "anon-key.json", root / "tests", root / "reference", (paths.STATE / pass_).resolve()]

    def under(h: Path, r: Path) -> bool:
        return h == r or h.is_relative_to(r)

    items_seen: set[tuple[str, ...]] = set()
    for m in ms:
        h = Path(m.host).resolve()
        for f in forbidden:
            if under(h, f) or under(f, h):
                raise PermissionError(f"a judge may not see {m.host} (it is or holds {f})")
        if m.ctr == "/home/actor":
            if m.ro or h == home or not h.is_relative_to(home):
                raise PermissionError(f"a judge's home must be a fresh writable directory under {home}: {m.host}")
            continue
        if not m.ctr.startswith("/judge/") or not m.ro:
            raise PermissionError(f"a judge's inputs are read-only and under /judge/: {m.ctr} <- {m.host}")
        rel = h.relative_to(anon).parts if h.is_relative_to(anon) else ()
        if len(rel) < 3:                                       # <label>/<NN|setup>/<input>, never more at once
            raise PermissionError(f"a judge may not see {m.host}: only one item's selected inputs under anon/")
        items_seen.add(rel[:2])
    if len(items_seen) > 1:
        raise PermissionError(f"a judge's inputs must come from one item, not {sorted(items_seen)}")


class ContainerJudge:
    """One fresh Claude session per call, modelled on `po.decide`: base image, pinned model, Read/Glob/Grep only,
    safe mode, egress `pins.egress_po`. Turns, transcripts, the reply and `model-pin.json` land in
    `scoring_out/judge-calls/<label>/<NN|setup>/<prompt digest>-<k>/`; a pin violation raises. Each call runs in a
    fresh home (removed once its transcripts are collected), so no lens or arm can read an earlier call's session."""

    def __init__(self, pass_: str, cred: credentials.Credential | None = None, pins: config.Pins | None = None):
        self.pass_, self._cred, self.pins = pass_, cred, pins
        self.last_dir: Path | None = None
        self.last_pin: transcripts.PinReport | None = None

    def ask(self, prompt: str, inputs: Path, files: list[str] = ()) -> str:
        if not files:
            raise ValueError("a container judge mounts only the item's selected inputs: none given")
        pins = self.pins or config.load_pins()
        if self._cred is None:
            self._cred = credentials.from_keychain()
        anon = paths.scoring_out(self.pass_) / "anon"
        try:
            rel = Path(inputs).resolve().relative_to(anon.resolve())
        except ValueError as e:
            raise PermissionError(f"a judge's inputs must be under {anon}: {inputs}") from e
        digest, k = hashlib.sha256(prompt.encode()).hexdigest()[:12], 1
        base = paths.scoring_out(self.pass_) / "judge-calls" / rel
        while (base / f"{digest}-{k}").exists():
            k += 1
        d = base / f"{digest}-{k}"
        slug = f"{rel.parts[0].replace(' ', '-')}-{rel.parts[1]}-{digest}-{k}"
        home = paths.judge_home(self.pass_) / slug              # fresh per call (R27)
        ms = mounts(home, Path(inputs), list(files))
        check_mounts(ms, self.pass_)
        d.mkdir(parents=True)
        shutil.rmtree(home, ignore_errors=True)
        (home / ".claude").mkdir(parents=True)
        step = int(rel.name) if rel.name.isdigit() else 0
        env = judge_env(pins)
        before = transcripts.snapshot(home / ".claude")
        turns: list[session.TurnResult] = []
        backoff = list(pins.limits.transient_backoff)
        reply, n, pin = "", 0, None
        try:
            with egress.Stage(f"{self.pass_}-scoring", "judge", "judge", pins.egress_po, d / "egress-judge.log") as st:
                while True:
                    n += 1
                    t = session.Turn(f"{self.pass_}-scoring", "judge", step, 1, n, pins.images["base"], prompt, env,
                                     ms, st.net, True, "/judge", paths.judge_inbox(self.pass_), "judge", False,
                                     home / ".claude")
                    r = session.run_turn(t, self._cred, d, pins.limits.turn_seconds)
                    turns.append(r)
                    if r.outcome in AT_ONCE:
                        raise SessionError(r.outcome, r.final_text)
                    if r.outcome in TRANSIENT:
                        if not backoff:
                            raise SessionError(r.outcome, r.final_text)
                        time.sleep(backoff.pop(0))
                        continue
                    reply = r.final_text
                    break
        finally:
            skipped: list[dict] = []
            files = transcripts.collect(home / ".claude", before, d / "transcripts", skipped=skipped)
            streams = {x.stream_path: x.outcome for x in turns if x.stream_path}
            pin = transcripts.verify_pin(files, list(streams), pins, unsafe=skipped, stream_outcomes=streams)
            (d / "model-pin.json").write_text(pin.to_json())
            self.last_dir, self.last_pin = d, pin
            shutil.rmtree(home, ignore_errors=True)            # collected: no later call can read this one
        if not pin.ok:
            raise PinViolation(f"judge call {d}: model pin not verified ({d / 'model-pin.json'})")
        (d / "reply.md").write_text(reply)
        return reply
