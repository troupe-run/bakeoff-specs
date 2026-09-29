"""Positive: suite N passes on the reference at step N. Negative: tests first valid at step N fail on the
reference at step N-1 (else they may be vacuous). Flake: watcher suites pass 5 times in a row."""
from __future__ import annotations
import os, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALLOW = {l.split("#")[0].strip() for l in (REPO / "harness/negative_allowlist.txt").read_text().splitlines()
         if l.split("#")[0].strip()}

def allowlisted(test_id: str) -> bool:
    """`module::name[params]` is allowlisted iff its last `::` part is an entry verbatim (a parametrised id is
    not the bare entry). The runner's hidden.summarise uses this same function (Task 18, review m10)."""
    return test_id.split("::")[-1] in ALLOW

WATCHER_SUITES = ["tests/hidden/test_step2_sync.py", "tests/hidden/test_step4_lineage.py"]

def run(step: int, ref_step: int, extra: list[str], xml: Path,
        targets: list[str] = ["tests/hidden"]) -> tuple[dict[str, str], int]:
    env = {**os.environ, "TROUPE_REF_STEP": str(ref_step)}
    proc = subprocess.run(["uv", "run", "pytest", *targets, "--step", str(step), "-q", "-p", "no:cacheprovider",
                    f"--junitxml={xml}", *extra], cwd=REPO, env=env)
    out = {}
    try:
        for tc in ET.parse(xml).iter("testcase"):
            outcome = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
                      "skipped" if tc.find("skipped") is not None else "passed"
            out[f"{tc.get('classname')}::{tc.get('name')}"] = outcome
    except (ET.ParseError, FileNotFoundError):
        pass
    return out, proc.returncode

def main() -> int:
    tmp = REPO / "results/tmp"; tmp.mkdir(parents=True, exist_ok=True)
    lines, ok = ["# Instrument validation", ""], True
    for n in range(1, 8):
        res, rc = run(n, n, [], tmp / f"pos{n}.xml")
        bad = [t for t, o in res.items() if o != "passed"]
        crashed = rc not in (0, 1)
        ok &= not bad and bool(res) and not crashed
        lines.append(f"- step {n} positive: {len(res)} tests, {len(bad)} not passing {bad or ''}"
                     + (f" [FAIL: pytest exit {rc}]" if crashed else ""))
    for n in range(2, 8):
        res, rc = run(n, n - 1, ["--first-step-only", str(n)], tmp / f"neg{n}.xml")
        crashed = rc not in (0, 1)
        none_selected = not res
        passing = [t for t, o in res.items() if o == "passed"]
        unexplained = [t for t in passing if not allowlisted(t)]
        ok &= not unexplained and not crashed and not none_selected
        lines.append(f"- step {n} negative: {len(res)} new tests, {len(passing)} pass at step {n-1} "
                     f"(allowlisted: {len(passing) - len(unexplained)}; unexplained: {unexplained or 'none'})"
                     + (f" [FAIL: pytest exit {rc}]" if crashed else "")
                     + (" [FAIL: no tests selected]" if none_selected else ""))
    for i in range(5):
        res, rc = run(4, 4, [], tmp / f"flake{i}.xml", WATCHER_SUITES)
        crashed = rc not in (0, 1)
        none_selected = not res
        bad = [t for t, o in res.items() if o != "passed"]
        ok &= not bad and not crashed and not none_selected
        lines.append(f"- watcher run {i + 1}/5: {len(res)} tests, {len(bad)} not passing {bad or ''}"
                     + (f" [FAIL: pytest exit {rc}]" if crashed else "")
                     + (" [FAIL: no tests selected]" if none_selected else ""))
    lines += ["", f"**Result: {'PASS' if ok else 'FAIL'}**", ""]
    (REPO / "results/instrument-validation.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
