"""Base, proxy and tester images: pin by digest, build once, save, lock (design §6, §11; spike B Q1).

Build once (review S-5): `build_all` refuses to overwrite an existing `images.lock.json` unless `rebuild=True`.
Trust on first use: `pin()` records what the Claude installer and the registries serve today; every later
build verifies against those records (`FROM` by digest; the Dockerfile checks the binary's SHA-256).
"""
from __future__ import annotations
import hashlib, json, re, subprocess, tomllib
from pathlib import Path
from runner import config, gitops, paths

IMAGES = Path(__file__).resolve().parent / "images"
LOCK = config.CONFIG_DIR / "images.lock.json"
VERSION_PROBES = {"claude": ["claude", "--version"], "uv": ["uv", "--version"], "python3": ["python3", "--version"],
                  "node": ["node", "--version"], "gh": ["gh", "--version"], "git": gitops.VERSION_PROBE}
# `command -v bd` resolves to the 1.3KB JS wrapper (bin/bd.js); the ~143MB native binary @beads/bd's
# postinstall downloads lives next to it as plain `bd` (fix-round-1 item 1) — `readlink -f "$(command -v bd)"`
# alone hashes the wrapper, not the binary that actually runs.
BD_NATIVE_BINARY_SH = 'p="$(readlink -f "$(command -v bd)")"; sha256sum "$(dirname "$p")/bd"'
ARM_VERSION_PROBES = {
    "openspec": {"openspec": ["openspec", "--version"]},
    "speckit": {"specify": ["specify", "version"]},
    "speckitty": {"spec-kitty": ["spec-kitty", "--version"], "bd": ["bd", "version"],
                  "bd-sha256": ["sh", "-c", BD_NATIVE_BINARY_SH]},   # S-5
    "ccsdd": {"cc-sdd": ["cc-sdd", "--version"]},
}


class NotPinned(RuntimeError):
    pass


def _sh(*argv: str) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout.strip()


def current_id(tag: str) -> str:
    """`{{.Id}}`: on Docker's containerd image store this is the image INDEX digest (Task 6 fix round 1)."""
    return _sh("docker", "image", "inspect", "--format", "{{.Id}}", tag)


def content_id(tag: str) -> str:
    """The image's platform manifest digest (config + layers): the content identity locked alongside the
    index id (Task 6 fix round 1, item 7). Inspecting with --platform resolves the index to that manifest."""
    platform = _sh("docker", "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", tag)
    return _sh("docker", "image", "inspect", "--platform", platform, "--format", "{{.Id}}", tag)


def _existing(arms: list[str]) -> list[str]:
    """Arms whose toml exists yet (Tasks 3 and 6 add them); lets Task 2 build and pin with only control present."""
    return [a for a in arms if (config.ARMS_DIR / f"{a}.toml").exists()]


def specify_version(text: str) -> str:
    """`specify version` always prints an ASCII banner and a boxed info panel before the version — the
    version-probe's usual `text.splitlines()[0]` would capture a banner line instead (found building the
    speckit image for real, review C-15 sibling)."""
    m = re.search(r"CLI Version\s+(\S+)", text)
    if not m:
        raise RuntimeError(f"could not find 'CLI Version' in `specify version` output: {text!r}")
    return m.group(1)


def cc_sdd_version(text: str) -> str:
    """`cc-sdd --version` prints `cc-sdd v3.1.0` — strip the name/`v` prefix so the lock reports a bare
    version like every other arm tool (fix-round-1 item 6: `cc-sdd` is now resolved via a plain symlink,
    like `openspec`, so it's no longer globally `npm install -g`'d and `npm ls -g` can't see it)."""
    m = re.search(r"(\d+\.\d+\.\d+)", text)
    if not m:
        raise RuntimeError(f"could not find a version in `cc-sdd --version` output: {text!r}")
    return m.group(1)


def check_pinned() -> None:
    p = config.load_pins()
    missing = ([k for k, v in p.digests.items() if not v]
               + (["binary_sha256"] if not p.binary_sha256 else [])
               + (["beads.sha256"] if not p.bd_sha256 else [])
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
    # No attestations: their manifests carry the build time, so every rebuild got a new index id even when
    # every layer came from cache (Task 6 fix round 1, item 7).
    argv = ["docker", "build", "-q", "--provenance=false", "--sbom=false", "-t", tag]
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


def _bd_sha256(base_image: str, speckitty_dir: Path) -> str:
    """Resolve @beads/bd's native binary hash for this pinning host/platform by actually installing it
    (network — the 'image build' phase egress is unrestricted, design table) and hashing the binary next
    to its JS wrapper, not the wrapper itself. The postinstall script downloads the binary straight from
    GitHub releases with no checksum of its own (fix-round-1 item 1) — pinning it here, the same way the
    Claude CLI binary is pinned, is what lets the speckitty Dockerfile's `sha256sum -c` catch a corrupted
    or substituted download on every later build. Independently verified 2026-09-29 against
    gastownhall/beads' own release `checksums.txt` (see task-3-report.md)."""
    out = _sh("docker", "run", "--rm", "--network", "bridge", "-v", f"{speckitty_dir}:/src:ro", base_image,
               "sh", "-c",
               'mkdir -p /tmp/beads && cp /src/package.json /src/package-lock.json /tmp/beads/ '
               '&& cd /tmp/beads && npm ci --omit=dev --no-audit --no-fund 1>&2 '
               '&& p="$(readlink -f node_modules/.bin/bd)" && sha256sum "$(dirname "$p")/bd"')
    return out.split()[0]


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
    if (IMAGES / "arm" / "speckitty").exists():                 # not present yet in a Task-2-only checkout
        bd_sha = _bd_sha256(im["base"], IMAGES / "arm" / "speckitty")
        _set_toml_value(pins_file, "sha256", bd_sha, table="beads")
        got["bd_sha256"] = bd_sha
    plugin_shas, plugin_errors = _pin_plugins(_existing(config.all_arms()))
    got.update(plugin_shas)
    if plugin_errors:
        got["errors"] = plugin_errors
        for key, msg in plugin_errors.items():
            print(f"WARNING: parked {key}: {msg} (review B2 — build_all skips this arm)")
    print("Pinned. Review `git diff runner/config` and commit it.")
    return got


def _unpinned_plugins(arm: config.Arm) -> list[str]:
    """Names of `arm`'s plugins with no recorded commit yet — `images pin` couldn't resolve their tag on
    the remote and parked them instead of raising (review B2). `build_all` refuses to build an image for
    an arm with any unpinned plugin."""
    return [pl.name for pl in arm.plugins if not pl.sha]


def _pin_plugins(arm_names: list[str]) -> tuple[dict, dict]:
    """For every plugin in every named arm: resolve its pinned tag to a commit SHA and write it into the
    arm's toml (OD9 B). A plugin whose tag doesn't exist on the remote is parked, not fatal (review B2:
    e.g. bmad-plugins carries no `v6.12.0` tag) — its sha stays empty and the failure is returned in the
    second dict, keyed `<arm>:<plugin>`, instead of raising."""
    got, errors = {}, {}
    for arm_name in arm_names:
        arm_file = config.ARMS_DIR / f"{arm_name}.toml"
        for pl in config.load_arm(arm_name).plugins:
            try:
                commit = gitops.ls_remote_tag(pl.repo, pl.tag)
            except gitops.TagNotFound as e:
                errors[f"{arm_name}:{pl.name}"] = str(e)
                continue
            text = arm_file.read_text()
            text = text.replace(f'tag = "{pl.tag}", sha = "{pl.sha}"', f'tag = "{pl.tag}", sha = "{commit}"', 1)
            arm_file.write_text(text)
            got[f"{arm_name}:{pl.name}"] = commit
    return got, errors


def _versions(tag: str, extra: dict[str, list[str]]) -> dict[str, str]:
    out = {}
    for name, cmd in {**VERSION_PROBES, **extra}.items():
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", tag, *cmd], capture_output=True, text=True)
        text = (r.stdout or r.stderr).strip()
        if name == "cc-sdd" and r.returncode == 0:
            text = cc_sdd_version(r.stdout)
        if name == "specify" and r.returncode == 0:
            text = specify_version(r.stdout)
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
    _build(im["tester_ref"], paths.REPO_ROOT, dockerfile=IMAGES / "tester-ref" / "Dockerfile", TESTER_IMAGE=im["tester"])
    if (IMAGES / "dryrun" / "Dockerfile").exists():
        _build(im["dryrun"], paths.REPO_ROOT, dockerfile=IMAGES / "dryrun" / "Dockerfile", BASE_IMAGE=im["base"])
    lock: dict = {"digests": p.digests, "binary_sha256": p.binary_sha256, "bd_sha256": p.bd_sha256,
                  "images": {}, "arms": {}}
    for tag in [im["base"], im["proxy"], im["tester"], im["tester_ref"]] + ([im["dryrun"]] if (IMAGES / "dryrun").exists() else []):
        lock["images"][tag] = {"id": current_id(tag), "content": content_id(tag), "tar_sha256": _save(tag)}
    lock["images"][im["base"]]["versions"] = _versions(im["base"], {})
    for name in _existing(arms):
        arm = config.load_arm(name)
        unpinned = _unpinned_plugins(arm)
        if unpinned:                                            # review B2: park, don't fail the other arms
            lock["arms"][name] = {"image": arm.image,
                                   "error": f"unpinned plugin(s) {unpinned}: tag not resolved by `images pin`"}
            print(f"WARNING: skipping {name}: unpinned plugin(s) {unpinned} (review B2)")
            continue
        df = IMAGES / "arm" / name / "Dockerfile"
        if df.exists():
            extra = {"BD_SHA256": p.bd_sha256} if name == "speckitty" else {}   # review fix-round-1 item 1
            _build(arm.image, IMAGES / "arm" / name, BASE_IMAGE=im["base"], **extra,
                   **{f"PLUGIN_{i}_{k.upper()}": getattr(pl, k) for i, pl in enumerate(arm.plugins)
                      for k in ("name", "repo", "tag", "sha", "subdir")})
        lock["arms"][name] = {"image": arm.image, "id": current_id(arm.image), "content": content_id(arm.image),
                              "tar_sha256": _save(arm.image) if df.exists() else lock["images"][im["base"]]["tar_sha256"],
                              "versions": _versions(arm.image, ARM_VERSION_PROBES.get(name, {}))}
    LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    return lock


def load_saved() -> None:
    for tar in sorted(paths.IMAGES_SAVE.glob("*.tar")):
        subprocess.run(["docker", "load", "-i", str(tar)], check=True)


def lock() -> dict:
    return json.loads(LOCK.read_text())
