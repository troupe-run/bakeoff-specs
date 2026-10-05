"""Coping with change, collateral churn: lines changed in files the step had no reason to touch (spec §3). The
step's legitimate paths (scoring/stale/step-NN.toml) plus the arm's own spec folders are never collateral."""
from __future__ import annotations
import fnmatch, re
from runner import config, docker, gitops
from runner.paths import Paths
from runner.scoring import inputs, values

_BRACE = re.compile(r"\{([^{}]*) => ([^{}]*)\}")


def normalise(path: str) -> str:
    if _BRACE.search(path):
        return re.sub(r"//+", "/", _BRACE.sub(lambda m: m[2], path)).lstrip("/")
    return path.split(" => ", 1)[1] if " => " in path else path


def _spec(path: str, spec_paths) -> bool:
    return any(path.startswith(sp.path) if sp.path.endswith("/") else fnmatch.fnmatch(path, sp.path)
               for sp in spec_paths)


def collateral(rows, stale: inputs.StaleList, spec_paths) -> dict:
    lines, files, total = 0, [], 0
    for added, deleted, raw in rows:
        path, n = normalise(raw), added + deleted
        total += n
        if not inputs.legitimate(path, stale) and not _spec(path, spec_paths):
            lines += n
            files.append(path)
    return {"lines": lines, "files": sorted(set(files)), "total_lines": total}


def for_step(pass_: str, arm: str, git_json: dict, stale: inputs.StaleList | None) -> dict:
    """Docker (gitops runs git in a network-less container — the host never runs git on an arm repo)."""
    src = git_json.get("source") or git_json.get("missing", "")
    if stale is None:
        return values.missing(src, "step 1: nothing to compare against")
    if values.is_missing(git_json):
        return git_json
    g = git_json["value"]
    a, b = (g.get("sha_before"), g.get("sha_after")) if isinstance(g, dict) else (None, None)
    if not (isinstance(a, str) and a and isinstance(b, str) and b):
        return values.missing(src, "no sha_before/sha_after")
    try:
        rows = gitops.numstat(Paths(pass_, arm), a, b)
    except (gitops.GitError, docker.ContainerError, ValueError) as e:
        return values.missing(src, f"numstat failed: {e}")
    return values.val(collateral(rows, stale, config.load_arm(arm).spec_paths), src)
