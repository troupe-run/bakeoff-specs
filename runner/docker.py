"""docker argv builders (pure) and the few effectful calls. The argv is built only from declared inputs:
no env pass-through, no implicit mounts (spike B Q2)."""
from __future__ import annotations
import contextlib, os, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from runner.config import Limits

@dataclass(frozen=True)
class Mount:
    host: Path
    ctr: str
    ro: bool

@dataclass(frozen=True)
class RunSpec:
    name: str
    image: str
    label: str
    network: str                 # a network name, or "none"
    mounts: list[Mount]
    env: dict[str, str]
    workdir: str
    cmd: list[str]
    stdin: bool
    limits: Limits
    proxy: bool
    user: str = "1000:1000"          # default for the other containers; the tester sets its own (hidden._spec):
                                     # prep runs as the arm uid 1001:1001 directly, while harness and script modes
                                     # start as 0:0 only to drop (harness: pytest as 1000, the arm as 1001; script:
                                     # 1001 alone)
    cap_add: tuple[str, ...] = ()    # added back after --cap-drop ALL
    tmpfs: tuple[str, ...] = ()      # extra tmpfs mounts ("path:opts"), beside the fixed /tmp
    remove: bool = True              # --rm; an arm session container is kept until its exit state is read (A5)

_recorder: list[RunSpec] | None = None

@contextlib.contextmanager
def recording() -> Iterator[list[RunSpec]]:
    global _recorder
    got: list[RunSpec] = []
    prev, _recorder = _recorder, got
    try:
        yield got
    finally:
        _recorder = prev

def run_argv(s: RunSpec) -> list[str]:
    for m in s.mounts:
        if ":" in str(m.host) or ":" in m.ctr:
            raise ValueError(
                f"mount path contains ':', which the docker -v host:ctr:mode syntax cannot represent "
                f"unambiguously (fix round 1, item 5): {m.host!r} -> {m.ctr!r}"
            )
        if not os.path.exists(m.host):
            # Docker would silently create an empty directory in its place — e.g. an arm home lost mid-restore
            # would come back as an empty home (Task 8 fix round 2).
            raise FileNotFoundError(f"mount source does not exist: {m.host} -> {m.ctr}")
    if _recorder is not None:
        _recorder.append(s)
    a = ["docker", "run", *(["--rm"] if s.remove else []), "--init", "--name", s.name, "--label", s.label,
         "--read-only", "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=4g", *[x for t in s.tmpfs for x in ("--tmpfs", t)],
         "--user", s.user, "--cap-drop", "ALL", *[x for c in s.cap_add for x in ("--cap-add", c)],
         "--security-opt", "no-new-privileges",
         "--pids-limit", str(s.limits.pids), "--cpus", s.limits.cpus, "--memory", s.limits.memory,
         "--network", s.network, "-w", s.workdir]
    if s.stdin:
        a.append("-i")
    env = dict(s.env)
    if s.proxy:
        env |= {"HTTPS_PROXY": "http://egress:3128", "HTTP_PROXY": "http://egress:3128",
                "NO_PROXY": "localhost,127.0.0.1"}
    for k in sorted(env):
        a += ["-e", f"{k}={env[k]}"]
    for m in s.mounts:
        a += ["-v", f"{m.host}:{m.ctr}:{'ro' if m.ro else 'rw'}"]
    return [*a, s.image, *s.cmd]

def stop_argv(name: str, grace: int = 30) -> list[str]:
    return ["docker", "stop", "-t", str(grace), name]

def rm_argv(name: str) -> list[str]:
    return ["docker", "rm", "-f", name]

class ContainerError(RuntimeError):
    """A container the runner started failed (docker, git-in-container, tar-in-container, the egress proxy). Task 22
    fix round 1 (L-1): stepflow records exactly this (and `subprocess.SubprocessError`) as `infra-container`; any
    other exception from a step is a runner bug and propagates."""


def stop(name: str, grace: int = 30) -> None:
    """Graceful then hard; never relies on killing the local docker CLI (spike B Q5)."""
    subprocess.run(stop_argv(name, grace), capture_output=True)
    subprocess.run(rm_argv(name), capture_output=True)

def exit_state(name: str) -> tuple[bool, int | None]:
    """(OOMKilled, exit code) of an exited container kept for inspection (A5); (False, None) if it cannot be read."""
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.OOMKilled}} {{.State.ExitCode}}", name],
                       capture_output=True, text=True, timeout=60)
    parts = r.stdout.split()
    if r.returncode != 0 or len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        return False, None
    return parts[0] == "true", int(parts[1])


def remove(name: str) -> None:
    subprocess.run(rm_argv(name), capture_output=True)


def run(spec: RunSpec, input: bytes | None = None, timeout: float | None = None,
        stop_grace: int = 30) -> subprocess.CompletedProcess:
    """A short container (git, verify, tester): stdout/stderr captured, container removed on timeout."""
    try:
        return subprocess.run(run_argv(spec), input=input, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        stop(spec.name, stop_grace)
        raise

def sweep(label: str = "bakeoff.run") -> dict[str, list[str]]:
    """Remove every container and network carrying `label` — and nothing else (controller ruling: this
    Docker host also runs unrelated vcplus-*/vcnext-*/rfpvisualcareai-*/ecotone-* containers, so the
    `--filter label=...` scoping is load-bearing, not cosmetic)."""
    ids = subprocess.run(["docker", "ps", "-aq", "--filter", f"label={label}"],
                         capture_output=True, text=True).stdout.split()
    for i in ids:
        subprocess.run(rm_argv(i), capture_output=True)
    nets = subprocess.run(["docker", "network", "ls", "-q", "--filter", f"label={label}"],
                          capture_output=True, text=True).stdout.split()
    for n in nets:
        subprocess.run(["docker", "network", "rm", n], capture_output=True)
    return {"containers": ids, "networks": nets}

def running(label: str = "bakeoff.run") -> list[str]:
    return subprocess.run(["docker", "ps", "-q", "--filter", f"label={label}"],
                          capture_output=True, text=True).stdout.split()
