"""Base, proxy and tester images: pin by digest, build once, save, lock (design §6, §11; spike B Q1).

Build once (review S-5): `build_all` refuses to overwrite an existing `images.lock.json` unless `rebuild=True`.
Trust on first use: `pin()` records what the Claude installer and the registries serve today; every later
build verifies against those records (`FROM` by digest; the Dockerfile checks the binary's SHA-256).
"""
from __future__ import annotations
import hashlib, json, re, subprocess, tomllib
from pathlib import Path
from runner import config, paths

IMAGES = Path(__file__).resolve().parent / "images"
LOCK = config.CONFIG_DIR / "images.lock.json"
VERSION_PROBES = {"claude": ["claude", "--version"], "uv": ["uv", "--version"], "python3": ["python3", "--version"],
                  "node": ["node", "--version"], "gh": ["gh", "--version"], "git": ["git", "--version"]}
ARM_VERSION_PROBES = {
    "openspec": {"openspec": ["openspec", "--version"]},
    "speckit": {"specify": ["specify", "version"]},
    "speckitty": {"spec-kitty": ["spec-kitty", "--version"], "bd": ["bd", "version"],
                  "bd-sha256": ["sh", "-c", "sha256sum \"$(readlink -f \"$(command -v bd)\")\""]},   # S-5
    "ccsdd": {"cc-sdd": ["sh", "-c", "npm ls -g cc-sdd --depth=0 --json"]},       # parsed by npm_version (C-15)
}


class NotPinned(RuntimeError):
    pass


def _sh(*argv: str) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout.strip()


def current_id(tag: str) -> str:
    return _sh("docker", "image", "inspect", "--format", "{{.Id}}", tag)


def _existing(arms: list[str]) -> list[str]:
    """Arms whose toml exists yet (Tasks 3 and 6 add them); lets Task 2 build and pin with only control present."""
    return [a for a in arms if (config.ARMS_DIR / f"{a}.toml").exists()]


def npm_version(json_text: str, pkg: str) -> str:
    return json.loads(json_text)["dependencies"][pkg]["version"]


def check_pinned() -> None:
    p = config.load_pins()
    missing = ([k for k, v in p.digests.items() if not v]
               + (["binary_sha256"] if not p.binary_sha256 else [])
               + (["images.tinyproxy"] if not p.images.get("tinyproxy") else []))
    if missing:
        raise NotPinned(f"unpinned: {missing}; run `uv run python -m runner images pin` and commit the result")


def base_build_args(p: config.Pins) -> dict[str, str]:
    im = p.images
    return {"DEBIAN_IMAGE": f"debian:bookworm-slim@{p.digests['debian']}",
            "NODE_IMAGE": f"node:{im['node_major']}-bookworm-slim@{p.digests['node']}",
            "UV_IMAGE": f"ghcr.io/astral-sh/uv:{im['uv']}@{p.digests['uv']}",
            "CLAUDE_VERSION": p.claude_version, "CLAUDE_SHA256": p.binary_sha256, "GH_VERSION": im["gh"]}


def proxy_build_args(p: config.Pins) -> dict[str, str]:
    im = p.images
    return {"ALPINE_IMAGE": f"alpine:{im['alpine']}@{p.digests['alpine']}", "TINYPROXY_VERSION": im["tinyproxy"]}


def _build(tag: str, context: Path, dockerfile: Path | None = None, target: str | None = None, **args: str) -> None:
    argv = ["docker", "build", "-q", "-t", tag]
    if dockerfile:
        argv += ["-f", str(dockerfile)]
    if target:
        argv += ["--target", target]
    for k, v in args.items():
        argv += ["--build-arg", f"{k}={v}"]
    subprocess.run([*argv, str(context)], check=True)


def _digest(ref: str) -> str:
    out = _sh("docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest.Digest}}")
    return json.loads(out)


def _apk_version(image: str, pkg: str) -> str:
    """The version-release string apk would install for `pkg` on `image` right now (review m1: pin the
    proxy's tinyproxy the same way every FROM is pinned — apk has no digest, so we record its version)."""
    out = _sh("docker", "run", "--rm", "--network", "bridge", image, "sh", "-c",
               f"apk update -q >/dev/null 2>&1 && apk list -a {pkg} 2>/dev/null | head -1")
    # e.g. "tinyproxy-1.11.1-r2 x86_64 {tinyproxy} (BSD-2-Clause) [...]"
    m = re.match(rf'^{re.escape(pkg)}-(\S+)', out)
    if not m:
        raise RuntimeError(f"could not determine apk version for {pkg!r} from: {out!r}")
    return m.group(1)


def _set_toml_value(path: Path, key: str, value: str, table: str | None = None) -> None:
    """Replace `key = "..."` (first occurrence) in a toml file, keeping every other byte.

    With `table`, the replacement is confined to that table's body (between its `[table]` header and the
    next top-level-or-deeper `[`-prefixed header, or EOF) — so writing a digest into `[images.digests]`
    can never clobber a same-named key in a different table, e.g. `[images] uv = "0.12.19"` (review B1).
    """
    text = path.read_text()
    if table is None:
        new, n = re.subn(rf'(?m)^({re.escape(key)}\s*=\s*)"[^"]*"', rf'\g<1>"{value}"', text, count=1)
        if n != 1:
            raise RuntimeError(f"{path}: key {key!r} not found")
        path.write_text(new)
        return
    header = f"[{table}]"
    start = text.find(header)
    if start == -1:
        raise RuntimeError(f"{path}: table {table!r} not found")
    body_start = start + len(header)
    m = re.search(r"(?m)^\[", text[body_start:])
    end = body_start + m.start() if m else len(text)
    head, body, tail = text[:body_start], text[body_start:end], text[end:]
    new_body, n = re.subn(rf'(?m)^({re.escape(key)}\s*=\s*)"[^"]*"', rf'\g<1>"{value}"', body, count=1)
    if n != 1:
        raise RuntimeError(f"{path}: key {key!r} not found in table {table!r}")
    path.write_text(head + new_body + tail)


def pin() -> dict:
    p = config.load_pins()
    im, pins_file = p.images, config.CONFIG_DIR / "pins.toml"
    got = {"debian": _digest("debian:bookworm-slim"), "node": _digest(f"node:{im['node_major']}-bookworm-slim"),
           "uv": _digest(f"ghcr.io/astral-sh/uv:{im['uv']}"), "alpine": _digest(f"alpine:{im['alpine']}")}
    for k, v in got.items():                                   # write only inside [images.digests] (review B1)
        _set_toml_value(pins_file, k, v, table="images.digests")
    args = base_build_args(config.load_pins()) | {"CLAUDE_SHA256": ""}
    _build("bakeoff-claude-stage:pin", IMAGES / "base", target="claude", **args)
    sha = _sh("docker", "run", "--rm", "--network", "none", "bakeoff-claude-stage:pin",
              "sha256sum", "/home/actor/claude-bin").split()[0]
    _set_toml_value(pins_file, "binary_sha256", sha)
    got["binary_sha256"] = sha
    tinyproxy = _apk_version(f"alpine:{im['alpine']}@{got['alpine']}", "tinyproxy")
    _set_toml_value(pins_file, "tinyproxy", tinyproxy)
    got["tinyproxy"] = tinyproxy
    for arm_name in _existing(config.all_arms()):              # OD9 B: tag -> commit SHA, recorded per plugin
        arm_file = config.ARMS_DIR / f"{arm_name}.toml"
        for pl in config.load_arm(arm_name).plugins:
            from runner import gitops                          # Task 8; imported lazily so Task 2 stands alone
            commit = gitops.ls_remote_tag(pl.repo, pl.tag)
            text = arm_file.read_text()
            text = text.replace(f'tag = "{pl.tag}", sha = "{pl.sha}"', f'tag = "{pl.tag}", sha = "{commit}"', 1)
            arm_file.write_text(text)
            got[f"{arm_name}:{pl.name}"] = commit
    print("Pinned. Review `git diff runner/config` and commit it.")
    return got


def _versions(tag: str, extra: dict[str, list[str]]) -> dict[str, str]:
    out = {}
    for name, cmd in {**VERSION_PROBES, **extra}.items():
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", tag, *cmd], capture_output=True, text=True)
        text = (r.stdout or r.stderr).strip()
        if name == "cc-sdd" and r.returncode == 0:
            text = npm_version(r.stdout, "cc-sdd")
        out[name] = text.splitlines()[0] if text else f"exit {r.returncode}"
    return out


def _save(tag: str) -> str:
    paths.IMAGES_SAVE.mkdir(parents=True, exist_ok=True)
    out = paths.IMAGES_SAVE / (tag.replace(":", "_").replace("/", "_") + ".tar")
    subprocess.run(["docker", "save", "-o", str(out), tag], check=True)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def build_all(arms: list[str], rebuild: bool = False) -> dict:
    check_pinned()
    if LOCK.exists() and not rebuild:
        raise RuntimeError("images.lock.json exists: images are built once (review S-5); use --rebuild deliberately")
    p = config.load_pins()
    im = p.images
    _build(im["base"], IMAGES / "base", **base_build_args(p))
    _build(im["proxy"], IMAGES / "proxy", **proxy_build_args(p))
    _build(im["tester"], paths.REPO_ROOT, dockerfile=IMAGES / "tester" / "Dockerfile", BASE_IMAGE=im["base"])
    if (IMAGES / "dryrun" / "Dockerfile").exists():
        _build(im["dryrun"], paths.REPO_ROOT, dockerfile=IMAGES / "dryrun" / "Dockerfile", BASE_IMAGE=im["base"])
    lock: dict = {"digests": p.digests, "binary_sha256": p.binary_sha256, "images": {}, "arms": {}}
    for tag in [im["base"], im["proxy"], im["tester"]] + ([im["dryrun"]] if (IMAGES / "dryrun").exists() else []):
        lock["images"][tag] = {"id": current_id(tag), "tar_sha256": _save(tag)}
    lock["images"][im["base"]]["versions"] = _versions(im["base"], {})
    for name in _existing(arms):
        arm = config.load_arm(name)
        df = IMAGES / "arm" / name / "Dockerfile"
        if df.exists():
            _build(arm.image, IMAGES / "arm" / name, BASE_IMAGE=im["base"],
                   **{f"PLUGIN_{i}_{k.upper()}": getattr(pl, k) for i, pl in enumerate(arm.plugins)
                      for k in ("name", "repo", "tag", "sha", "subdir")})
        lock["arms"][name] = {"image": arm.image, "id": current_id(arm.image),
                              "tar_sha256": _save(arm.image) if df.exists() else lock["images"][im["base"]]["tar_sha256"],
                              "versions": _versions(arm.image, ARM_VERSION_PROBES.get(name, {}))}
    LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    return lock


def load_saved() -> None:
    for tar in sorted(paths.IMAGES_SAVE.glob("*.tar")):
        subprocess.run(["docker", "load", "-i", str(tar)], check=True)


def lock() -> dict:
    return json.loads(LOCK.read_text())
