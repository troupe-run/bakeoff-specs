"""Harness faults (design §9). Created early by Task 9, which needs `HarnessFault` and `classify_pin` for the
setup turns' pin verification (preflight M5). The code is the plan's Task 13 (`HarnessFault`) and Task 15
(`classify_pin`) text verbatim; Task 13/15 extend this file rather than create it, and Task 22 adds the ledger."""
from __future__ import annotations


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
