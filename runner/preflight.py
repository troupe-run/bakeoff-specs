"""Pre-run checks. Task 18: `idle()`; Task 23 adds the rest."""
from __future__ import annotations
import os, subprocess
from runner import config, docker


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
