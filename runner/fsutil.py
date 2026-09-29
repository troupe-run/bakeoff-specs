"""Atomic record writes (Task 23 fix round 1): a temp file in the same directory, written and fsync'd, then
`os.replace` over the target (and the directory fsync'd), so a kill at any point leaves either the previous file or
the new one — never a half-written progress, consistency or suite-resource record."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path


def write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, path.stat().st_mode & 0o7777 if path.exists() else 0o644)   # mkstemp's 0600 is not the file's
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    try:
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass                                    # a directory fsync is best effort (not every filesystem allows it)


def write_json(path: Path, obj) -> None:
    write_text(path, json.dumps(obj, indent=2, default=str))
