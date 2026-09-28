import os, select, signal, time

def wait_for(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()

class Watching:
    def __init__(self, cli, theatre, ready_timeout: float = 20):
        self.cli, self.theatre, self.ready_timeout = cli, theatre, ready_timeout
        self.code = None

    def __enter__(self):
        self.p = self.cli.spawn("watch", theatre=self.theatre)
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            r, _, _ = select.select([self.p.stdout], [], [], 0.2)
            if r and self.p.stdout.readline().startswith("watching"):
                return self
            if self.p.poll() is not None:
                break
        self._stop()
        raise AssertionError(f"`config watch` never printed its readiness line; stderr: {self.p.stderr.read()}")

    def _stop(self):
        if self.p.poll() is None:
            os.killpg(self.p.pid, signal.SIGTERM)
            try:
                self.p.wait(timeout=10)
            except Exception:
                os.killpg(self.p.pid, signal.SIGKILL)
                self.p.wait()
        self.code = self.p.returncode

    def __exit__(self, *exc):
        self._stop()
