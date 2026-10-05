"""Rebuilds the miniature pass in ./mini (two arms, steps 01-02). Run: uv run python tests/runner/scoring/fixtures/make_mini.py
The fixture is committed; this script is its source."""
from __future__ import annotations
import gzip, json, shutil
from pathlib import Path

ROOT = Path(__file__).parent / "mini"


def w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def wj(p: Path, obj) -> None:
    w(p, json.dumps(obj, indent=2, sort_keys=True) + "\n")


def stream(path: Path, duration_ms: int | None, cum_usd: float = 0.0) -> None:
    """A stream-json turn; duration_ms=None writes no result line (a killed turn)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(path, "wb", mtime=0) as g:
        lines = [{"type": "system", "subtype": "init", "model": "claude-opus-5-5"}]
        if duration_ms is not None:
            lines.append({"type": "result", "subtype": "success", "is_error": False,
                          "duration_ms": duration_ms, "total_cost_usd": cum_usd})
        else:
            lines.append({"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]}})
        g.write("".join(json.dumps(x) + "\n" for x in lines).encode())


def turn(step: Path, stem: str, prompt: str, duration_ms: int | None, cum_usd: float = 0.0) -> None:
    stream(step / "turns" / f"{stem}.stream.jsonl.gz", duration_ms, cum_usd)
    w(step / "turns" / f"{stem}.prompt.md", prompt + "\n")


def step(arm: str, nn: str, *, attempts: int, faults: list, violations: list, mutation: dict,
         mypy_crashed=False, hidden=True) -> Path:
    d = ROOT / arm / nn
    wj(d / "run.json", {"outcome": "done", "attempts": attempts, "arm_session_seconds": 100.0, "po_seconds": 10.0,
                        "owner_wait_seconds": 5.0, "tests_seconds": 20.0, "harness_faults": faults,
                        "arm_violations": violations})
    wj(d / "cost.json", {"unit": "usd", "source": "stream", "arm": {"usd": 1.5}, "po": {"usd": 0.25},
                         "harness": {"usd": 0.0}})
    wj(d / "a" / "cost.json", {"unit": "usd", "source": "stream", "arm": {"usd": 0.75}})
    wj(d / "quality" / "summary.json", {"mypy_errors": 2, "mypy_crashed": mypy_crashed, "ruff_findings": 3,
                                         "ruff_crashed": False, "mutation": mutation})
    if hidden:
        wj(d / "hidden" / "summary.json", {"scoreable": True, "tests": {"t1": "passed", "t2": "failed"}})
    wj(d / "git.json", {"head": "0" * 40})
    q = lambda who, n: json.dumps({"n": n, "kind": "clarify", "answered_by": who, "escalated": [], "fallback": [],
                                   "arm_message": "which?", "reply": "this", "at": "2026-10-01T00:00:00Z"}) + "\n"
    w(d / "questions.jsonl", q("po", 1) + q("owner", 2))
    w(d / "a" / "questions.jsonl", q("po", 1))
    return d


def build() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ok = {"score": 0.8, "crashed": False, "unmeasured": False, "baseline_failed": False}
    crashed = {"score": None, "crashed": True, "unmeasured": False, "baseline_failed": False}

    d = step("alpha", "01", attempts=1, faults=[], violations=[], mutation=ok)
    turn(d, "arm-a1-001", "/speckit-specify # Step 1 build the thing", 60_000, 1.0)
    turn(d, "arm-a1-002", "/speckit-plan", 40_000, 1.5)

    d = step("alpha", "02", attempts=2, faults=[{"kind": "docker-restart"}],
             violations=[{"rule": "no-network", "detail": "curl"}], mutation=ok)
    turn(d, "arm-a1-001", "/speckit-specify # Step 2 first try", 11_000, 0.5)
    turn(d, "arm-a2-001", "/speckit-specify # Step 2 second try", 30_000, 0.5)
    turn(d, "arm-a2-002", "/speckit-plan", None)          # killed: no result line
    tr = d / "transcripts" / "a2" / "-work-repo" / "session-1.jsonl"
    w(tr, "".join(json.dumps(x) + "\n" for x in [         # one session: turn arm-a2-001, then the killed arm-a2-002
        {"type": "user", "timestamp": "2026-10-01T09:59:00.000Z",
         "message": {"content": "/speckit-specify # Step 2 second try"}},
        {"type": "assistant", "timestamp": "2026-10-01T09:59:30.000Z", "message": {"content": []}},
        {"type": "user", "timestamp": "2026-10-01T10:00:00.000Z", "message": {"content": "/speckit-plan"}},
        {"type": "assistant", "timestamp": "2026-10-01T10:00:20.000Z", "message": {"content": []}},
        {"type": "assistant", "timestamp": "2026-10-01T10:01:30.000Z", "message": {"content": []}},
    ]))

    d = step("control", "01", attempts=1, faults=[], violations=[], mutation=crashed)
    turn(d, "arm-a1-001", "build step 1", 50_000, 2.0)

    d = step("control", "02", attempts=2, faults=[], violations=[], mutation=ok, hidden=False)
    turn(d, "arm-a1-001", "build step 2, first try", 7_000, 0.4)
    turn(d, "arm-a2-001", "build step 2, second try", 20_000, 0.9)


if __name__ == "__main__":
    build()
