"""Event-sourced config projection: reconcile-first CLI, `ensure_imported`, `set`.

Loop safety comes from ONE rule: every path into the projection (CLI set, file watcher, startup)
goes through `reconcile()`, which diffs the files' current merged content against the projection and
emits only the differences. A write-back from a CLI set therefore diffs to nothing when the watcher
sees it. No echo-suppression flags, no "ignore next event for file X".
"""

from __future__ import annotations
import contextlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .loader import load
from .lock import theatre_lock
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
    def __init__(self, theatre: Path, actor: dict | None = None, reason: str | None = None):
        self.theatre = theatre
        self.actor = actor
        self.reason = reason
        self.store = ConfigStore(theatre)
        self._lock_depth = 0

    @contextlib.contextmanager
    def _locked(self):
        """Re-entrant within this Service instance/process: a second nested acquisition (e.g.
        `set`'s own call to `reconcile`) doesn't take the OS lock again — a fresh `open()` on the
        lock file would get a distinct open file description and flock() would deadlock against
        the outer hold. Tracks depth so only the outermost call actually takes/releases the lock."""
        if self._lock_depth:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
        else:
            with theatre_lock(self.theatre):
                self._lock_depth = 1
                try:
                    yield
                finally:
                    self._lock_depth = 0

    def ensure_imported(self) -> None:
        with self._locked():
            if not self.store.exists() or not self.store.history(None):
                flat = load(self.theatre).flat()
                self.store.record_many([("import", k, None, v) for k, v in flat.items()], self._lineage("import"))

    def reconcile(self, via: str) -> int:
        with self._locked():
            changes = diff(self.store.values(), load(self.theatre).flat())
            if changes:
                self.store.record_many(changes, self._lineage(via))
            return len(changes)

    def set(self, path: str, value: Any, **opts) -> int:
        with self._locked():                # held across write-back AND its own reconcile
            cfg = load(self.theatre)
            cfg.set(path, value, **opts)     # raises before writing if refused
            return self.reconcile("cli")

    def _lineage(self, via: str) -> dict:
        if STEP < 4:
            return {}
        actor = self.actor if via == "cli" else {"kind": "unknown", "id": None}
        return {"actor": actor, "via": via,
                "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "reason": self.reason if via == "cli" else None,
                "change": str(uuid.uuid4())}     # called once per record_many, i.e. once per command
