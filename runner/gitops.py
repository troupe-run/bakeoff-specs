"""Git operations. Host-side helpers only for now (review B2): `ls_remote_tag` resolves a plugin's pinned
tag to a commit SHA *before* any arm image or container exists, so `images.pin()` (Task 2) can bake vendored
plugins in at a verified commit (OD9 B). Task 8 extends this module with the in-container helpers used once
arm repos are running (`spec`, `git`, `head`, `main_sha`, `state`, `init_repo`, ...); those are out of scope
here.
"""
from __future__ import annotations
import os
import subprocess


class TagNotFound(RuntimeError):
    """`repo_slug`'s remote has no such tag. Callers park the plugin rather than pinning to nothing
    (review B2: e.g. `bmad-code-org/bmad-plugins` carries no tags at all)."""


def _host_env() -> dict[str, str]:
    """Environment for a host-side `git` call: no interactive credential prompt, no local/global git
    config leaking in. This call is read-only and must be reproducible regardless of the operator's own
    git setup (aliases, credential helpers, includeIf rules, ...)."""
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}


def ls_remote_tag(repo_slug: str, tag: str) -> str:
    """The commit SHA `tag` points at on `https://github.com/<repo_slug>` (peeled to the target commit if
    the tag is annotated). Read-only, host-side, no clone. Raises `TagNotFound` if the remote has no such
    tag or the call itself fails.

    Queries every tag rather than passing `tag` as a refspec pattern: `git ls-remote --tags <url> <tag>`
    matches only the tag ref itself and drops the server's synthetic `^{}` peeled-commit line for an
    annotated tag, silently returning the tag *object* SHA instead of the commit it points at."""
    r = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{repo_slug}"],
                        capture_output=True, text=True, env=_host_env(), timeout=30)
    if r.returncode != 0:
        raise TagNotFound(f"{repo_slug}@{tag}: git ls-remote failed: {r.stderr.strip()}")
    refs = dict(line.split(maxsplit=1)[::-1] for line in r.stdout.splitlines() if line.strip())
    want = f"refs/tags/{tag}"
    sha = refs.get(f"{want}^{{}}") or refs.get(want)
    if not sha:
        raise TagNotFound(f"{repo_slug}@{tag}: no such tag on the remote")
    return sha
