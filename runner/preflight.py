"""Pre-run checks. Task 18: `idle()`. Task 23: `check_images` (the images a run uses are the locked ones, by
content, and the reference baked into `bakeoff-tester-ref` is the repo's `reference/`) and `lock()` (one runner
at a time). `NotReady` is `checklist.NotReady`: one refusal type for everything that must not start."""
from __future__ import annotations
import contextlib, fcntl, json, os, subprocess
from runner import config, docker, images, paths
from runner.checklist import NotReady

__all__ = ["NotReady", "idle", "check_images", "lock"]


def _vm_load() -> tuple[float, int]:
    """The Docker VM's 1-minute load and CPU count, read in a throwaway network-less container (review §3
    NOTE 8: on Docker Desktop the host load does not show the VM's)."""
    img = config.load_pins().images["base"]
    r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--label", "bakeoff.preflight=1", img,
                        "sh", "-c", "cat /proc/loadavg; nproc"], capture_output=True, text=True, timeout=60)
    lines = r.stdout.split("\n")
    if r.returncode != 0 or len(lines) < 2:
        raise RuntimeError(f"cannot read the Docker VM load ({r.returncode}): {r.stderr[:300]}")
    return float(lines[0].split()[0]), int(lines[1])


def idle() -> tuple[bool, str]:
    """No other `bakeoff.run` container, host 1-minute load < load_factor x cpus, and the Docker VM's likewise."""
    others = docker.running("bakeoff.run")
    f = config.load_pins().limits.load_factor
    host, hcpu = os.getloadavg()[0], os.cpu_count() or 1
    vm, vcpu = _vm_load()
    ok = not others and host < f * hcpu and vm < f * vcpu
    return ok, (f"containers={len(others)} host_load1={host:.2f} host_limit={f * hcpu:.1f} "
                f"vm_load1={vm:.2f} vm_cpus={vcpu} vm_limit={f * vcpu:.1f}")


# ---- images (design §2: no upgrade mid-bake-off; Task 23 rulings) --------------------------------------------------

def _want(entry: dict) -> str | None:
    """A lock or setup record's content identity: the platform manifest digest (`content`), else the id."""
    return entry.get("content") or entry.get("id")


def check_images(arm_name: str, p) -> None:
    """Refuse (NotReady) unless every image a step of this arm uses — the arm's own (the dry-run image for a dry
    arm), the base (PO, teammate), the tester, the reference tester and the egress proxy — has the CONTENT recorded
    in `images.lock.json` (not only the same local id); the arm's image is the one recorded at its setup
    (`00-setup/versions.json`); and `reference/` is the tree the reference image baked (`reference_tree`)."""
    lk = images.lock()
    arm = config.load_arm(arm_name)
    im = config.load_pins().images
    if arm.dry:
        own = {"image": im["dryrun"], **lk.get("images", {}).get(im["dryrun"], {})}
    else:
        own = lk.get("arms", {}).get(arm_name) or {}
    if not _want(own) or own.get("error"):
        raise NotReady(f"{arm_name}: no built image in images.lock.json ({own.get('error', 'missing')})")
    tags = {own["image"]: _want(own)}
    for key in ("base", "tester", "tester_ref", "proxy"):
        e = lk.get("images", {}).get(im[key]) or {}
        if not _want(e):
            raise NotReady(f"image {im[key]} is not in images.lock.json")
        tags[im[key]] = _want(e)
    for tag, want in tags.items():
        try:
            got = images.content_id(tag)
        except (subprocess.CalledProcessError, OSError) as e:
            raise NotReady(f"image {tag} is not loaded ({e}); `runner images load`") from None
        if got != want:
            raise NotReady(f"image {tag} content {got} differs from images.lock.json ({want}) — design §2: no "
                           f"upgrade mid-bake-off")
    if not lk.get("reference_tree"):
        raise NotReady("images.lock.json has no reference_tree: rebuild only the reference image "
                       "(`runner images build --only tester_ref`) to record it")
    if (now := images.reference_tree()) != lk["reference_tree"]:
        raise NotReady(f"reference/ ({now[:12]}) is not the tree baked into {im['tester_ref']} "
                       f"({lk['reference_tree'][:12]}): rebuild only that image (`runner images build --only tester_ref`)")
    vf = p.setup_results / "versions.json"
    if not vf.is_file():
        raise NotReady(f"{arm_name}: no {vf} (run setup first)")
    at_setup = json.loads(vf.read_text()).get("image") or {}
    if _want(at_setup) != _want(own):
        raise NotReady(f"{arm_name}: image differs from the one recorded at setup ({_want(at_setup)} vs "
                       f"{_want(own)}) — design §2")


@contextlib.contextmanager
def lock():
    """One runner at a time: an exclusive, non-blocking `flock` on `state/runner.lock`."""
    paths.LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(paths.LOCK, "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise NotReady(f"another runner holds {paths.LOCK} (one thing at a time)") from None
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
