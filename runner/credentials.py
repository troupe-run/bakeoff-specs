"""The OAuth token lives only in this process's memory and on one container's stdin (spike B option a′).

Never in argv, in env visible to `docker inspect`, in the image, in a file under the repo/results, or in logs.
Spike B showed anything inside the actor container is readable by the model's tools — accepted (OD11/OD16).
"""
from __future__ import annotations
import hashlib, subprocess
from runner.config import Arm, Pins, github_slug


class Credential:
    __slots__ = ("_t", "_dummy")

    def __init__(self, token: str, dummy: bool = False):
        self._t, self._dummy = token.strip(), dummy

    def payload(self) -> bytes:
        """Bytes for the container's stdin (→ fd 3 inside); the only place the token leaves this process."""
        return (self._t + "\n").encode()

    def fingerprint(self) -> str:
        return hashlib.sha256(self._t.encode()).hexdigest()

    def raw_for_scanner(self) -> str:
        """Only runner.secrets calls this, to search evidence for the literal token; never logged."""
        return self._t

    def check_turn(self, dry: bool) -> None:
        """Called by session.run_turn on every turn (review C-14): no mixing dummy and real credentials."""
        if self._dummy and not dry:
            raise PermissionError("the dummy credential may only drive dry-run arms")
        if dry and not self._dummy:
            raise PermissionError("the real credential never drives a dry-run arm")

    def __repr__(self) -> str:
        return "<credential>"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return "<credential>"

    def __copy__(self) -> "Credential":
        return self

    def __deepcopy__(self, memo) -> "Credential":
        return self

    def __reduce__(self):
        raise TypeError("a credential is not picklable (it would land on disk)")


def from_keychain(service: str = "bakeoff-claude-oauth") -> Credential:
    r = subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        # never include r.stdout (or stderr, which is not ours to vouch for) in the message (review S-6)
        raise RuntimeError(f"no usable keychain item {service!r} (exit {r.returncode}); "
                           "see checklists/README.md (owner one-time step)")
    return Credential(r.stdout)


def dummy() -> Credential:
    return Credential("dry-run-dummy-token", dummy=True)


def session_env(pins: Pins, arm: Arm, *, role: str, isolated: bool, tools: str = "", resume: str = "",
                mcp: bool = False, pass_: str = "") -> dict[str, str]:
    """Non-secret environment for one Claude session. `pass_` only feeds GH_REPO (preflight M4)."""
    m = pins.model
    env = {
        "BK_MODEL": m, "BK_PERMISSION_MODE": pins.permission_mode,
        "BK_DISALLOWED": ",".join(pins.disallowed_tools),
        "ANTHROPIC_DEFAULT_OPUS_MODEL": m, "ANTHROPIC_DEFAULT_SONNET_MODEL": m,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": m, "CLAUDE_CODE_SUBAGENT_MODEL": m,
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "CLAUDE_CODE_MAX_RETRIES": str(pins.max_retries),
        "CLAUDE_CONFIG_DIR": "/home/actor/.claude", "OPENSPEC_TELEMETRY": "0",
        **(arm.env if role == "arm" else {}),
    }
    if role == "arm" and pins.plugin_route == "plugin-dir" and arm.plugins:
        env["BK_PLUGIN_DIRS"] = " ".join(f"/opt/plugins/{p.name}" for p in arm.plugins)
    if role == "arm" and mcp:
        env["BK_MCP_CONFIG"] = "/home/actor/.bk-mcp.json"        # OD24 B with MCP only (speckit)
    if role == "arm" and arm.tracker == "github" and not arm.dry:
        slug = github_slug(pass_, arm.name)
        if slug:
            env["GH_REPO"] = slug                                 # M4: origin is local (B4), so gh needs this
    if isolated:
        env["BK_ISOLATED"] = "1"
    if tools:
        env["BK_TOOLS"] = tools
    if resume:
        env["BK_RESUME"] = resume
    return env
