"""Runs an arm's `troupe config` CLI as a black box. Only stdout, stderr, exit code and theatre files are observable."""
from __future__ import annotations
import os, subprocess
from dataclasses import dataclass
from pathlib import Path

CAP = 64 * 1024


def cap(text: str) -> str:
    """What assertions see of arm output: at most the last 64 KB, with a marker saying how much was cut (Task 18
    fix round 3: an untruncated assertion message is a way to flood the junit)."""
    b = text.encode(errors="replace")
    if len(b) <= CAP:
        return text
    tail = b[-CAP:].decode(errors="ignore")
    return f"[... {len(b) - len(tail.encode())} bytes truncated ...]\n{tail}"


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

# The arm's CLI gets an ALLOWLISTED environment, never the harness's os.environ (Task 18 fix round 2): nothing
# naming the reference step, pytest or harness paths reaches it. `forward` adds named variables back — only the
# reference's own TROUPE_REF_STEP, and only when the implementation under test IS the reference (see forwarded()).
ENV_ALLOW = ("PATH", "HOME", "LANG", "TZ", "TMPDIR", "LOGNAME", "USER", "PYTHONDONTWRITEBYTECODE")
ENV_ALLOW_PREFIXES = ("LC_", "UV_")


def forwarded(impl: str, prefix: str | None, flag: bool, reference: Path) -> tuple[str, ...]:
    """TROUPE_REF_STEP reaches the CLI only for the reference: when asked (`--forward-ref-step`, the runner's
    reference-flake runs) or on a plain host run of the repo's own reference (Plan 1)."""
    if flag or (not prefix and Path(impl).resolve() == reference.resolve()):
        return ("TROUPE_REF_STEP",)
    return ()


class Cli:
    def __init__(self, prefix: list[str], forward: tuple[str, ...] = ()):
        self.prefix = prefix
        self.forward = forward

    def _argv(self, sub: str, args: tuple[str, ...], theatre: Path) -> list[str]:
        return [*self.prefix, "config", sub, "--theatre", str(theatre), *args]

    def _env(self, env: dict[str, str] | None) -> dict[str, str]:
        merged = {k: v for k, v in os.environ.items()
                  if k in ENV_ALLOW or k.startswith(ENV_ALLOW_PREFIXES) or k in self.forward}
        merged.update(env or {})           # tests set identity (TROUPE_ACTOR) explicitly
        return merged

    def __call__(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None,
                 timeout: float = 60) -> Result:
        p = subprocess.run(self._argv(sub, args, theatre), capture_output=True, text=True,
                           env=self._env(env), timeout=timeout)
        return Result(p.returncode, cap(p.stdout), cap(p.stderr))

    def spawn(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
        return subprocess.Popen(self._argv(sub, args, theatre), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=self._env(env), start_new_session=True)
