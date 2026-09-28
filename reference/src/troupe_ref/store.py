"""Event-sourced projection of a theatre's configuration, persisted under `.troupe/state/`.

One `ConfigLog` aggregate per theatre database (fixed id via `create_id`), recording one `Changed`
event per changed leaf. `history()` replays the event store directly rather than the current
projection, so it reports what happened even for leaves that have since been removed.
"""
from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any
from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event

LOG_ID = uuid.uuid5(uuid.NAMESPACE_URL, "troupe:config-log")

class ConfigLog(Aggregate):
    @event("Created")
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    @event("Changed")
    def changed(self, op: str, path: str, old: Any, new: Any, lineage: dict) -> None:
        if op == "remove":
            self.values.pop(path, None)
        else:
            self.values[path] = new

    @classmethod
    def create_id(cls) -> uuid.UUID:
        return LOG_ID

class ConfigStore:
    def __init__(self, theatre: Path):
        state = theatre / ".troupe" / "state"
        state.mkdir(parents=True, exist_ok=True)
        self.app = Application(env={"PERSISTENCE_MODULE": "eventsourcing.sqlite",
                                    "SQLITE_DBNAME": str(state / "events.sqlite")})

    def exists(self) -> bool:
        try:
            self.app.repository.get(LOG_ID)
            return True
        except Exception:
            return False

    def _log(self) -> ConfigLog:
        if not self.exists():
            log = ConfigLog()
            self.app.save(log)
        return self.app.repository.get(LOG_ID)

    def values(self) -> dict[str, Any]:
        return dict(self._log().values)

    def record(self, op: str, path: str, old: Any, new: Any, **lineage: Any) -> None:
        self.record_many([(op, path, old, new)], lineage)

    def record_many(self, changes: list[tuple[str, str, Any, Any]], lineage: dict) -> None:
        if not changes:
            return
        log = self._log()
        for op, path, old, new in changes:
            log.changed(op=op, path=path, old=old, new=new, lineage=lineage)
        self.app.save(log)   # one atomic save per command

    def history(self, path: str | None) -> list[dict]:
        out = []
        for e in list(self.app.repository.event_store.get(LOG_ID))[1:]:   # skip Created
            if path and not (e.path == path or e.path.startswith(path + ".")):
                continue
            out.append({"seq": e.originator_version - 1, "op": e.op, "path": e.path,
                        "old": e.old, "new": e.new, **e.lineage})
        return out
