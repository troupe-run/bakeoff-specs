"""Runs an arm's `troupe config` CLI as a black box. Only stdout, stderr, exit code and theatre files are observable."""
from __future__ import annotations
import os, subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

class Cli:
    def __init__(self, prefix: list[str]):
        self.prefix = prefix

    def _argv(self, sub: str, args: tuple[str, ...], theatre: Path) -> list[str]:
        return [*self.prefix, "config", sub, "--theatre", str(theatre), *args]

    def _env(self, env: dict[str, str] | None) -> dict[str, str]:
        merged = dict(os.environ)
        merged.pop("TROUPE_ACTOR", None)  # tests set identity explicitly
        merged.update(env or {})
        return merged

    def __call__(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None,
                 timeout: float = 60) -> Result:
        p = subprocess.run(self._argv(sub, args, theatre), capture_output=True, text=True,
                           env=self._env(env), timeout=timeout)
        return Result(p.returncode, p.stdout, p.stderr)

    def spawn(self, sub: str, *args: str, theatre: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
        return subprocess.Popen(self._argv(sub, args, theatre), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=self._env(env), start_new_session=True)
