"""Harness faults (design §9). Created early by Task 9, which needs `HarnessFault` and `classify_pin` for the
setup turns' pin verification (preflight M5). The code is the plan's Task 13 (`HarnessFault`) and Task 15
(`classify_pin`) text verbatim; Task 13/15 extend this file rather than create it, and Task 22 adds the ledger.

The ledger (Task 22, design §9): every harness fault is one JSON line in `results/faults.jsonl` for the real passes
(shared, so pass 1 and pass 2 halt together) and `results/<pass>/faults.jsonl` for dry, probe and canary passes (so
they can never halt the real bake-off). The SECOND occurrence of the same `(kind, signature)` since the last owner
resolution (`resume`) writes `HALTED` next to it, and every command except `faults …` refuses to run until
`resume` records a resolution. A resolution resets every signature's count: the owner reviewed the whole ledger.

Resource exhaustion (design §9, owner 2026-09-29) is NOT a harness fault for the arm that hit it (`hidden` re-runs
an `arm-resource` death once; a repeat scores the step all-failed). Each occurrence is recorded per (pass, step, arm)
in `results/<pass>/resource-exhaustion.jsonl` (`record_resource`); Task 23 counts distinct arms per step against
`limits.suite_resource_arms` and, at the threshold, records `HarnessFault("suite-resource", str(step))`.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from runner import paths


class HarnessFault(Exception):
    def __init__(self, kind: str, signature: str, detail: str = ""):
        super().__init__(f"{kind}: {signature}")
        self.kind, self.signature, self.detail = kind, signature, detail


def classify_pin(report, who: str = "arm") -> "HarnessFault | None":
    if report is None:
        return None
    if report.no_evidence:
        return HarnessFault("model-pin", "no-evidence", f"{who}: no transcript evidence")
    for v in report.violations:
        if v["where"] == "claude_code_version":
            return HarnessFault("pin-claude-version", str(v["model"]), f"{who}: {v['file']}:{v['line']}")
    for v in report.violations:
        return HarnessFault("model-pin", str(v["model"]), f"{who}: {v['where']} {v['file']}:{v['line']}")
    return None


# ---- the ledger (Task 22) --------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ledger_paths(pass_: str) -> tuple[Path, Path]:
    if pass_ in paths.REAL_PASSES:
        return paths.FAULTS, paths.HALTED
    return paths.RESULTS / pass_ / "faults.jsonl", paths.RESULTS / pass_ / "HALTED"


def _read(f: Path) -> list[dict]:
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []


def _entries(pass_: str) -> list[dict]:
    return _read(ledger_paths(pass_)[0])


def _append_to(f: Path, entry: dict) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _append(pass_: str, entry: dict) -> None:
    _append_to(ledger_paths(pass_)[0], entry)


def _since_resolution(pass_: str, key: tuple[str, str]) -> list[dict]:
    since: list[dict] = []
    for e in _entries(pass_):
        if e.get("resolution"):
            since = []
        elif (e.get("kind"), e.get("signature")) == key:
            since.append(e)
    return since


def record(f: HarnessFault, pass_: str, arm: str, step: int, attempt: int, *,
           run: str | None = None) -> Literal["rerun", "halt"]:
    """Append `f` to the pass's ledger; "halt" (and `HALTED` written) when the same `(kind, signature)` is already
    there since the last resolution, else "rerun". `run` is "a"/"b" (the N.a/N.b run of the step) when known."""
    return _enter(pass_, {"pass": pass_, "arm": arm, "step": step, "run": run, "attempt": attempt,
                          "kind": f.kind, "signature": f.signature, "detail": f.detail})


def _enter(pass_: str, fields: dict) -> Literal["rerun", "halt"]:
    """The one halt check (design §9) for every ledger entry, recorded or declared (fix round 1 M-1)."""
    since = _since_resolution(pass_, (fields["kind"], fields["signature"]))
    entry = {"at": _now(), **fields, "action": "halt" if since else fields.get("action", "rerun")}
    _append(pass_, entry)
    if since:
        halted_file = ledger_paths(pass_)[1]
        halted_file.parent.mkdir(parents=True, exist_ok=True)
        halted_file.write_text(json.dumps({"reason": "same harness fault twice (design §9)", "first": since[-1],
                                           "second": entry}, indent=2))
        return "halt"
    return "rerun"


def halted(pass_: str) -> str | None:
    h = ledger_paths(pass_)[1]
    return h.read_text() if h.exists() else None


# ---- input from the owner (CLI) is validated: no path may leave the results tree (fix round 1 M-2) -----------------
NAME = re.compile(r"[a-z0-9-]+")


def valid_name(name: str | None) -> bool:
    """`fullmatch`, so a trailing newline is rejected (fix round 2)."""
    return bool(NAME.fullmatch(name or ""))
STEPS = range(1, 8)


def check_pass(pass_: str) -> str:
    """A real pass, or a lower-case dashed name that already exists under results/ or state/."""
    if pass_ in paths.REAL_PASSES:
        return pass_
    if not valid_name(pass_):
        raise ValueError(f"pass {pass_!r}: not a known pass and not a lower-case dashed name")
    if not ((paths.RESULTS / pass_).is_dir() or (paths.STATE / pass_).is_dir()):
        raise ValueError(f"pass {pass_!r}: unknown (no results/{pass_} or state/{pass_})")
    return pass_


def check_arm(arm: str) -> str:
    from runner import config
    if not valid_name(arm):
        raise ValueError(f"arm {arm!r}: not a lower-case dashed name")
    try:
        config.load_arm(arm)
    except FileNotFoundError:
        raise ValueError(f"arm {arm!r}: no such arm (runner/config/arms/{arm}.toml)") from None
    return arm


def resume(pass_: str, note: str) -> None:
    """A resolution resets every signature's count: the owner reviewed the whole ledger when resuming. Refused (and
    nothing appended) without a note or when the pass is not halted."""
    check_pass(pass_)
    if not (note or "").strip():
        raise ValueError("a resolution needs a note (--note \"<what was fixed>\")")
    if halted(pass_) is None:
        raise ValueError(f"{pass_} is not halted: there is nothing to resume")
    _append(pass_, {"resolution": True, "pass": pass_, "note": note, "at": _now()})
    ledger_paths(pass_)[1].unlink(missing_ok=True)


def entries(pass_: str) -> list[dict]:
    """The whole ledger a pass writes to (resolutions included), in order."""
    return _entries(pass_)


def for_step(pass_: str, arm: str, step: int) -> list[dict]:
    return [e for e in _entries(pass_) if e.get("arm") == arm and e.get("step") == step and not e.get("resolution")
            and e.get("pass", pass_) == pass_]


def declare(pass_: str, arm: str, step: int, slug: str, scope: str) -> Literal["rerun", "halt"]:
    """An owner-declared harness fault (wrong brief, allowlist too narrow, runner bug): `manual:<slug>`. It counts
    towards the halt rule like any other; the scope says what re-runs (`rerun-step` or `retest`, Task 23)."""
    if scope not in ("rerun-step", "retest"):
        raise ValueError("scope is rerun-step or retest")
    check_pass(pass_); check_arm(arm)
    if step not in STEPS:
        raise ValueError(f"step {step}: the scenario has steps 1-7")
    if not valid_name(slug):
        raise ValueError(f"slug {slug!r}: use a lower-case dashed name")
    return _enter(pass_, {"pass": pass_, "arm": arm, "step": step, "run": None, "attempt": None, "kind": "manual",
                          "signature": slug, "detail": "owner-declared", "action": scope, "scope": scope})


# ---- resource exhaustion (not a ledger fault; Task 23 counts arms per step) -------------------------------------

def resource_path(pass_: str) -> Path:
    return paths.RESULTS / pass_ / "resource-exhaustion.jsonl"


def record_resource(pass_: str, arm: str, step: int, attempt: int, exhausted: str, evidence: list) -> None:
    """`exhausted`: "repeat" (the hidden run died of resources twice: the step scored all-failed) or "once" (the
    re-run completed and was scored). `evidence` is `hidden.Summary.resource_evidence`."""
    if exhausted not in ("once", "repeat"):
        raise ValueError("exhausted is once or repeat")
    _append_to(resource_path(pass_), {"at": _now(), "pass": pass_, "arm": arm, "step": step, "attempt": attempt,
                                      "exhausted": exhausted, "evidence": evidence})


def resource_records(pass_: str, step: int) -> list[dict]:
    return [e for e in _read(resource_path(pass_)) if e.get("step") == step]
