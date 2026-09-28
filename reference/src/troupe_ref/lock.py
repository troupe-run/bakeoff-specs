import contextlib, fcntl
from pathlib import Path

@contextlib.contextmanager
def theatre_lock(theatre: Path):
    state = theatre / ".troupe" / "state"
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
