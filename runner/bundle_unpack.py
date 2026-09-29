"""The harness bundle's unpacker. Runs INSIDE the tester as the harness uid (`/opt/harness/bin/python -c <this
source> /harness`, stdlib only) before any arm code runs; the host's tests import it too, so what is tested is
what runs. Records are `<relative path> <size>\\n<size bytes>` (runner/hidden.harness_bundle)."""
from __future__ import annotations
import os, sys

MAX_FILE = 4_000_000
MAX_HEADER = 512


def parse(data: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    i = 0
    while i < len(data):
        nl = data.find(b"\n", i, i + MAX_HEADER)
        if nl < 0:
            raise ValueError(f"bad header at byte {i}")
        try:
            name, size_s = data[i:nl].decode("utf-8").rsplit(" ", 1)
            size = int(size_s)
        except ValueError as e:
            raise ValueError(f"bad header at byte {i}") from e
        if size < 0 or size > MAX_FILE:
            raise ValueError(f"bad size {size} for {name!r}")
        parts = name.split("/")
        if not name or name.startswith("/") or any(x in ("", ".", "..") for x in parts):
            raise ValueError(f"bad path {name!r}")
        if name in seen:
            raise ValueError(f"duplicate record {name!r}")
        end = nl + 1 + size
        if end > len(data):
            raise ValueError(f"truncated record {name!r}")
        out.append((name, data[nl + 1:end]))
        seen.add(name)
        i = end
    return out


def write(data: bytes, root: str | os.PathLike) -> None:
    """Parse everything first (a bad bundle writes nothing), then create each file exclusively, no links."""
    for name, body in parse(data):
        path = os.path.join(os.fspath(root), name)
        d = os.fspath(root)
        for part in name.split("/")[:-1]:              # every directory 0700 (makedirs' mode is the leaf's only)
            d = os.path.join(d, part)
            if not os.path.isdir(d):
                os.mkdir(d, 0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)


if __name__ == "__main__":
    try:
        write(sys.stdin.buffer.read(), sys.argv[1])
    except ValueError as e:
        sys.exit(f"harness bundle refused: {e}")
