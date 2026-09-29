import os, signal, threading, time
from .driver import cap

def wait_for(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()

class Watching:
    """Runs `config watch` for the duration of a `with` block.

    Both of the child's pipes are drained continuously by background threads for its whole life, so a
    candidate that logs heavily can never block on a full pipe. Readiness is the first stdout line that
    starts with "watching".

    Stopping sends SIGTERM to the spawned process only (the group leader) — not the whole process
    group. The leader is usually a wrapper (`uv run …`) that forwards SIGTERM to the candidate; a
    group-wide SIGTERM would deliver it to the candidate twice. SIGKILL to the whole group remains the
    fallback when the leader does not exit in time.
    """

    def __init__(self, cli, theatre, ready_timeout: float = 20):
        self.cli, self.theatre, self.ready_timeout = cli, theatre, ready_timeout
        self.code = None
        self.out: list[str] = []
        self.err: list[str] = []
        self._ready = threading.Event()

    def _drain(self, stream, sink: list[str], watch_ready: bool):
        for line in iter(stream.readline, ""):
            sink.append(line)
            if watch_ready and line.startswith("watching"):
                self._ready.set()
        stream.close()

    def __enter__(self):
        self.p = self.cli.spawn("watch", theatre=self.theatre)
        self._threads = [
            threading.Thread(target=self._drain, args=(self.p.stdout, self.out, True), daemon=True),
            threading.Thread(target=self._drain, args=(self.p.stderr, self.err, False), daemon=True),
        ]
        for t in self._threads:
            t.start()
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            if self._ready.wait(0.2):
                return self
            if self.p.poll() is not None:
                break
        self._stop()
        raise AssertionError(f"`config watch` never printed its readiness line; stderr: {cap(''.join(self.err))}")

    def _stop(self):
        if self.p.poll() is None:
            os.kill(self.p.pid, signal.SIGTERM)
            try:
                self.p.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(self.p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.p.wait()
        for t in self._threads:
            t.join(timeout=5)
        self.code = self.p.returncode

    def __exit__(self, *exc):
        self._stop()
