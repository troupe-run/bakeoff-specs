"""Hidden tests against an arm, inside a tester container (OD23).

The arm's committed `refs/heads/main` is exported (in a container — never untarred on the host) into a copy
that sits at the same path the arm used (`/work/bakeoff-specs-<arm>`). A prep container (PyPI-only egress)
installs it; then every test run happens in a separate, network-less tester container, outside every arm
session, with the harness's `tests/` mounted read-only only there. pytest and the arm's CLI are one process tree
in one container under one uid, so every PLAN-2 NOTE from Plan 1 is resolved by construction:

- same user for `getpass.getuser()`: no `USER`/`LOGNAME` in the env, both sides read the passwd entry;
- `served`/`remote.py`: one network namespace, `127.0.0.1` on loopback (which exists under `--network none`);
- theatre tmp dirs: there is no "outside"; env vars (`TROUPE_ACTOR`, `TROUPE_REF_STEP`): no `docker exec`,
  `driver.Cli` passes env to a local subprocess; signals: `Watching` signals the local `uv run` leader, no
  `--cmd-prefix` wrapper, `--init` reaps, the container is removed.

The tester never mounts `p.scratch` itself, the arm's home or its work tree: only the copy's own parent, a fresh
empty home per container, and `/out` for results.
"""
from __future__ import annotations
import json, os, shutil, stat, time, uuid, xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from pathlib import Path
from runner import config, docker, egress, gitops, repo
from runner.docker import Mount, RunSpec
from runner.paths import Paths, REPO_ROOT
from harness.validate_suites import ALLOW   # single source for the allowlist parse (review m10)

ENV = {"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1", "UV_CACHE_DIR": "/tmp/uv-cache",
       "HOME": "/home/actor", "UV_PYTHON_DOWNLOADS": "never"}
PYTEST = ["/opt/harness/bin/python", "-m", "pytest"]
MAIN = "refs/heads/main"


# --- pure ----------------------------------------------------------------------------------------------------

def parse_junit(xml: str) -> dict[str, str]:
    """Same outcome rule as `harness/validate_suites.run` (Plan 1's validated instrument; review m10)."""
    out = {}
    for tc in ET.fromstring(xml).iter("testcase"):
        o = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
            "skipped" if tc.find("skipped") is not None else "passed"
        out[f"{tc.get('classname')}::{tc.get('name')}"] = o
    return out


def parse_collected(text: str) -> list[str]:
    ids = []
    for line in text.splitlines():
        if "::" in line and line.startswith("tests/"):
            path, _, name = line.strip().partition("::")
            ids.append(path.removesuffix(".py").replace("/", ".") + "::" + name)
    return ids


def to_nodeid(junit_id: str) -> str:
    mod, _, name = junit_id.partition("::")
    return mod.replace(".", "/") + ".py::" + name


def flake_verdict(outcomes: list[str]) -> str:
    return "failed" if all(o == "failed" for o in outcomes) else "flaky"


@dataclass
class Summary:
    step: int
    total: int
    passed: int
    failed: int
    flaky: int
    flaky_arm: int
    tests: dict[str, str]
    new_at_step: list[str]
    new_passed: int
    new_discriminating_passed: int
    exit_code: int
    install_failed: bool = False

    def write(self, out_dir: Path) -> None:
        (out_dir / "hidden").mkdir(parents=True, exist_ok=True)
        (out_dir / "hidden" / "summary.json").write_text(json.dumps(asdict(self), indent=2, sort_keys=True))


def summarise(step, tests, new_at_step, flaky, flaky_arm, exit_code, install_failed=False) -> Summary:
    """Harness flakes (`flaky`: flaky on the reference too) are neither passed nor failed; arm flakes
    (`flaky_arm`: stable on the reference) count as failed for the arm and are recorded (review C-2).
    `install_failed` (prep failed twice): every test counts as failed."""
    if install_failed:    # the arm's result: every test fails (a test may pass vacuously on uv's own exit 2)
        final = {t: "failed" for t in tests}
    else:
        final = {t: ("flaky" if t in flaky else "failed" if t in flaky_arm else o) for t, o in tests.items()}
    new = [t for t in new_at_step if t in final]
    return Summary(step, len(final), sum(o == "passed" for o in final.values()),
                   sum(o == "failed" for o in final.values()), sum(o == "flaky" for o in final.values()),
                   len([t for t in flaky_arm if t in final]), final, new, sum(final[t] == "passed" for t in new),
                   sum(final[t] == "passed" and t.split("::")[-1].split("[")[0] not in ALLOW for t in new),
                   exit_code, install_failed)


@dataclass
class Prepared:
    hidden_copy: Path
    quality_copy: Path | None
    prep: dict = field(default_factory=dict)


# --- containers ----------------------------------------------------------------------------------------------

def _rmtree(path: Path) -> None:
    """Delete a copy or tester home without following links; arm code may have left read-only dirs."""
    def fix(func, p_, exc):
        os.chmod(os.path.dirname(p_), stat.S_IRWXU)
        if func is not os.unlink and os.path.isdir(p_) and not os.path.islink(p_):
            os.chmod(p_, stat.S_IRWXU); shutil.rmtree(p_, onexc=fix)
        else:
            func(p_)
    if os.path.lexists(path):
        shutil.rmtree(path, onexc=fix)


def _tester_root(p: Paths) -> Path:
    """Harness-owned tester dirs (fresh homes, the reference-flake dummy): beside, never inside, scratch/home."""
    return p.base / "tester"


def _spec(p: Paths, copy: Path, cmd: list[str], *, network: str = "none", proxy: bool = False,
          out: Path | None = None, env: dict | None = None, workdir: str | None = None,
          name: str = "tester") -> RunSpec:
    """Pure apart from creating a fresh, empty home for this one container (removed by `_run`)."""
    home = _tester_root(p) / f"home-{uuid.uuid4().hex[:12]}"
    home.mkdir(parents=True)
    mounts = [Mount(copy.parent, "/work", False), Mount(home, "/home/actor", False),
              Mount(REPO_ROOT / "tests", "/harness/tests", True),
              Mount(REPO_ROOT / "pyproject.toml", "/harness/pyproject.toml", True)]
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        mounts.append(Mount(out, "/out", False))
    pins = config.load_pins()
    return RunSpec(name=f"bk-{name}-{p.pass_}-{p.arm}-{int(time.time() * 1000) % 10**8}-{uuid.uuid4().hex[:4]}",
                   image=pins.images["tester"], label=f"bakeoff.run={p.pass_}/{p.arm}",
                   network=network, mounts=mounts, env={**ENV, **(env or {})},
                   workdir=workdir or f"/work/{copy.name}", cmd=cmd, stdin=False, limits=pins.limits, proxy=proxy)


def _run(s: RunSpec, timeout: float):
    try:
        return docker.run(s, timeout=timeout)
    finally:
        for m in s.mounts:
            if m.ctr == "/home/actor":
                _rmtree(m.host)


def _sync(p: Paths, copy: Path, st: egress.Stage, with_mutmut: bool) -> dict:
    lock = (copy / "uv.lock").exists()
    cmd = "uv sync --frozen" if lock else "uv sync"
    if with_mutmut:       # mutmut only in copy B (review C-1)
        cmd += " && uv pip install --python .venv/bin/python --require-hashes -r /opt/mutmut-requirements.txt"
    rec: dict = {"lockfile": lock, "command": cmd, "tries": []}
    for _ in (1, 2):      # a failed sync is retried once; a second failure is install_failed (the arm's result)
        r = _run(_spec(p, copy, ["bash", "-c", cmd], network=st.net, proxy=True,
                       env={"UV_OFFLINE": "0", "UV_NO_SYNC": "0"}, name="prep"), timeout=1800)
        rec["tries"].append({"exit": r.returncode, "log": (r.stdout + r.stderr).decode(errors="replace")[-4000:]})
        if r.returncode == 0:
            rec["ok"] = True
            return rec
    rec["ok"] = False
    return rec


def prepare_copy(p: Paths, copy: Path, out_dir: Path, label: str, quality_copy: Path | None = None,
                 source: dict | None = None) -> Prepared:
    """Install an already-exported copy (and optionally copy B) in a PyPI-only prep container."""
    pins = config.load_pins()
    rec: dict = {**(source or {})}
    with egress.Stage(p.pass_, p.arm, "tester", pins.egress_tester_prep, out_dir / "egress-tester.log") as st:
        rec["hidden"] = _sync(p, copy, st, False)
        if quality_copy is not None:
            rec["quality"] = _sync(p, quality_copy, st, True)
    (out_dir / "hidden").mkdir(parents=True, exist_ok=True)
    (out_dir / "hidden" / f"prep-{label}.json").write_text(json.dumps(rec, indent=2))
    return Prepared(copy, quality_copy, rec)


def prepare(p: Paths, sha: str, label: str, out_dir: Path, with_quality: bool = False,
            require_main: bool = True) -> Prepared:
    """Export the committed tree (in a container) into copy A (`scratch/<label>/a/`) and, with `with_quality`,
    copy B (`…/b/`), then install. Hidden tests run on exactly `refs/heads/main`: `sha` may be that ref, and
    otherwise must be the commit it points to (`require_main=False` only for a deliberate re-test of a
    recorded commit)."""
    main = gitops.main_sha(p)
    commit = main if sha == MAIN else sha
    if commit is None:
        raise RuntimeError(f"{p.pass_}/{p.arm}: the arm repo has no {MAIN}")
    if require_main and commit != main:
        raise ValueError(f"{p.pass_}/{p.arm}: hidden tests run on {MAIN} ({main}), not {sha}")
    base = p.scratch / label
    _rmtree(base)
    a = base / "a" / f"bakeoff-specs-{p.arm}"
    repo.export(p, commit, a)
    b = None
    if with_quality:
        b = base / "b" / f"bakeoff-specs-{p.arm}"
        repo.export(p, commit, b)
    return prepare_copy(p, a, out_dir, label, b, source={"ref": sha, "commit": commit, "main": main})


def _pytest(p: Paths, copy: Path, args: list[str], out: Path, impl: str | None = None,
            env: dict | None = None, timeout: int = 1800):
    cmd = [*PYTEST, *args, "--impl", impl or f"/work/{copy.name}", "-q", "-p", "no:cacheprovider",
           "--rootdir", "/harness"]
    return _run(_spec(p, copy, cmd, out=out, env=env, workdir="/harness"), timeout=timeout)


def run_script(p: Paths, copy: Path, script: str) -> str:
    """A shell script in the tester sandbox (network none, no /out); used by the hand-edit probe."""
    return _run(_spec(p, copy, ["bash", "-c", script]), timeout=600).stdout.decode(errors="replace")


def classify_flaky(p: Paths, step: int, nodeid: str) -> str:
    """Run the test 3x alone against the reference image copy (`/opt/reference`, `TROUPE_REF_STEP=step`):
    any failure there = a harness flake ("harness"); stable there = an arm flake ("arm") (review C-2)."""
    root = _tester_root(p) / "ref-flake"
    dummy = root / "bakeoff-specs-ref"
    dummy.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(3):
            r = _pytest(p, dummy, [nodeid, "--step", str(step)], root / "out", impl="/opt/reference",
                        env={"TROUPE_REF_STEP": str(step)}, timeout=600)
            if r.returncode != 0:
                return "harness"
        return "arm"
    finally:
        _rmtree(root)


def run(p: Paths, copy: Path, step: int, out_dir: Path, install_failed: bool = False) -> Summary:
    """Collect the tests first valid at `step`, run the step's suite, re-run each failure twice alone in fresh
    containers, classify flakes against the reference. Writes `hidden/{summary,flake}.json`, `pytest.log`."""
    hd = out_dir / "hidden"
    hd.mkdir(parents=True, exist_ok=True)
    (hd / "junit.xml").unlink(missing_ok=True)
    col = _pytest(p, copy, ["tests/hidden", "--step", str(step), "--first-step-only", str(step), "--collect-only"], hd)
    if col.returncode != 0:
        raise RuntimeError(f"hidden collection failed ({col.returncode}): {col.stdout.decode(errors='replace')[-800:]}")
    new_at_step = parse_collected(col.stdout.decode(errors="replace"))
    r = _pytest(p, copy, ["tests/hidden", "--step", str(step), "--junitxml=/out/junit.xml"], hd)
    (hd / "pytest.log").write_bytes(r.stdout + b"\n--- stderr ---\n" + r.stderr)
    if not (hd / "junit.xml").exists():      # never score a crashed harness run as "0 tests" (pytest exit 2-4)
        raise RuntimeError(f"hidden run wrote no junit (exit {r.returncode}); see {hd / 'pytest.log'}")
    tests = parse_junit((hd / "junit.xml").read_text())
    flaky: list[str] = []
    flaky_arm: list[str] = []
    reruns: dict[str, list[str]] = {}
    for t, o in tests.items():
        if o != "failed" or install_failed:
            continue
        outcomes = ["failed"]
        for _ in range(2):
            rr = _pytest(p, copy, [to_nodeid(t), "--step", str(step)], hd / "rerun", timeout=600)
            outcomes.append("passed" if rr.returncode == 0 else "failed")
        reruns[t] = outcomes
        if flake_verdict(outcomes) == "flaky":
            (flaky if classify_flaky(p, step, to_nodeid(t)) == "harness" else flaky_arm).append(t)
    (hd / "flake.json").write_text(json.dumps({"reruns": reruns, "harness_flaky": flaky, "arm_flaky": flaky_arm,
                                               "report": [f"flaky-test:{to_nodeid(t)}" for t in flaky]}, indent=2))
    s = summarise(step, tests, new_at_step, flaky, flaky_arm, r.returncode, install_failed)
    s.write(out_dir)
    return s
