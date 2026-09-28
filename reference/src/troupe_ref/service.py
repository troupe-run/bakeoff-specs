"""Event-sourced config projection: reconcile-first CLI, `ensure_imported`, `set`.

Loop safety comes from ONE rule: every path into the projection (CLI set, file watcher, startup)
goes through `reconcile()`, which diffs the files' current merged content against the projection and
emits only the differences. A write-back from a CLI set therefore diffs to nothing when the watcher
sees it. No echo-suppression flags, no "ignore next event for file X".
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
from .loader import load
from .step import STEP
from .store import ConfigStore

_MISSING = object()

def diff(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, str, Any, Any]]:
    out = []
    for k, v in after.items():
        old = before.get(k, _MISSING)
        if old is _MISSING or old != v or type(old) is not type(v):
            out.append(("set", k, None if old is _MISSING else old, v))
    for k in sorted(before.keys() - after.keys()):
        out.append(("remove", k, before[k], None))
    return out

class Service:
    def __init__(self, theatre: Path, lineage_for_cli: dict | None = None):
        self.theatre = theatre
        self.store = ConfigStore(theatre)
        self.cli_lineage = lineage_for_cli or {}

    def ensure_imported(self) -> None:
        if not self.store.exists() or not self.store.history(None):
            flat = load(self.theatre).flat()
            self.store.record_many([("import", k, None, v) for k, v in flat.items()], self._lineage("import"))

    def reconcile(self, via: str) -> int:
        changes = diff(self.store.values(), load(self.theatre).flat())
        if changes:
            self.store.record_many(changes, self._lineage(via))
        return len(changes)

    def set(self, path: str, value: Any, **opts) -> int:
        cfg = load(self.theatre)
        cfg.set(path, value, **opts)       # raises before writing if refused
        return self.reconcile("cli")

    def _lineage(self, via: str) -> dict:
        return {}                          # Task 8 fills this in (step 4)
