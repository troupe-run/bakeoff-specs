"""Per-arm, per-phase egress stage: an --internal network plus an allowlisting tinyproxy (spike B Q3)."""
from __future__ import annotations
import re, subprocess, tempfile
from pathlib import Path
from runner import config

_CONNECT = re.compile(r"CONNECT ([^:\s]+):\d+")
_REFUSED = re.compile(r'refused on filtered domain "([^"]+)"')

def allowlist_text(hosts: list[str]) -> str:
    return "".join(h + "\n" for h in hosts)

def decisions(log: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in log.splitlines():
        if m := _CONNECT.search(line):
            out.append((m.group(1), "allowed"))
        elif (m := _REFUSED.search(line)) and out and out[-1][0] == m.group(1):
            out[-1] = (m.group(1), "refused")
    return out

class Stage:
    """Creates `bk-net-<pass>-<arm>-<phase>` (--internal, labelled) and a tinyproxy sidecar
    `bk-proxy-<pass>-<arm>-<phase>` (alias `egress`); on exit appends the proxy log to `log_to`
    and removes both (review C-13: a partial `__enter__` failure leaves the network behind for
    the next `docker.sweep()` to remove — negligible, not fixed here)."""

    def __init__(self, pass_: str, arm: str, phase: str, hosts: list[str], log_to: Path):
        self.net = f"bk-net-{pass_}-{arm}-{phase}"
        self.proxy = f"bk-proxy-{pass_}-{arm}-{phase}"
        self.label = f"bakeoff.run={pass_}/{arm}"
        self.hosts, self.log_to = hosts, log_to

    def __enter__(self) -> "Stage":
        self._allow = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        self._allow.write(allowlist_text(self.hosts)); self._allow.close()
        Path(self._allow.name).chmod(0o644)
        subprocess.run(["docker", "network", "create", "--internal", "--label", self.label, self.net],
                       check=True, capture_output=True)
        # Hardened like every other container in this project (fix round 1, item 3): read-only root with a
        # small noexec tmpfs for tinyproxy's own scratch use, all caps dropped, no-new-privileges, --init,
        # and an explicit non-root user (the image's own `USER nobody` already does this; passing it again
        # here makes the guarantee independent of the Dockerfile and assertable from the run argv/inspect).
        subprocess.run(["docker", "run", "-d", "--name", self.proxy, "--label", self.label, "--network", "bridge",
                        "--init", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m",
                        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "nobody",
                        "-v", f"{self._allow.name}:/etc/tinyproxy/allow.txt:ro",
                        config.load_pins().images["proxy"]], check=True, capture_output=True)
        subprocess.run(["docker", "network", "connect", "--alias", "egress", self.net, self.proxy],
                       check=True, capture_output=True)
        return self

    def log_text(self) -> str:
        """The proxy's log so far (final fix batch A2: a failed install is classified from it)."""
        log = subprocess.run(["docker", "logs", self.proxy], capture_output=True, text=True, timeout=60)
        return log.stdout + log.stderr

    def _save_log(self) -> None:
        log = subprocess.run(["docker", "logs", self.proxy], capture_output=True, text=True)
        self.log_to.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_to, "a") as fh:
            fh.write(log.stdout + log.stderr)

    def __exit__(self, *exc) -> None:
        # Fix round 1, item 2: teardown must happen even if fetching/writing the proxy log raises (disk
        # full, permission error, etc). The log write is best-effort and its failure must never mask
        # whatever exception (if any) is already propagating out of the `with` body, so it's swallowed
        # here rather than left to propagate through `finally`.
        try:
            self._save_log()
        except Exception:
            pass
        finally:
            subprocess.run(["docker", "rm", "-f", self.proxy], capture_output=True)
            subprocess.run(["docker", "network", "rm", self.net], capture_output=True)
            Path(self._allow.name).unlink(missing_ok=True)
