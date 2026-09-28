"""Positive: suite N passes on the reference at step N. Negative: tests first valid at step N fail on the
reference at step N-1 (else they may be vacuous). Flake: watcher suites pass 5 times in a row."""
from __future__ import annotations
import os, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALLOW = {l.split("#")[0].strip() for l in (REPO / "harness/negative_allowlist.txt").read_text().splitlines()
         if l.split("#")[0].strip()}

def run(step: int, ref_step: int, extra: list[str], xml: Path) -> dict[str, str]:
    env = {**os.environ, "TROUPE_REF_STEP": str(ref_step)}
    subprocess.run(["uv", "run", "pytest", "tests/hidden", "--step", str(step), "-q", "-p", "no:cacheprovider",
                    f"--junitxml={xml}", *extra], cwd=REPO, env=env)
    out = {}
    for tc in ET.parse(xml).iter("testcase"):
        outcome = "failed" if tc.find("failure") is not None or tc.find("error") is not None else \
                  "skipped" if tc.find("skipped") is not None else "passed"
        out[f"{tc.get('classname')}::{tc.get('name')}"] = outcome
    return out

def main() -> int:
    tmp = REPO / "results/tmp"; tmp.mkdir(parents=True, exist_ok=True)
    lines, ok = ["# Instrument validation", ""], True
    for n in range(1, 8):
        res = run(n, n, [], tmp / f"pos{n}.xml")
        bad = [t for t, o in res.items() if o != "passed"]
        ok &= not bad and bool(res)
        lines.append(f"- step {n} positive: {len(res)} tests, {len(bad)} not passing {bad or ''}")
    for n in range(2, 8):
        res = run(n, n - 1, ["--first-step-only", str(n)], tmp / f"neg{n}.xml")
        passing = [t for t, o in res.items() if o == "passed"]
        unexplained = [t for t in passing if t.split("::")[-1] not in ALLOW]
        ok &= not unexplained
        lines.append(f"- step {n} negative: {len(res)} new tests, {len(passing)} pass at step {n-1} "
                     f"(allowlisted: {len(passing) - len(unexplained)}; unexplained: {unexplained or 'none'})")
    for i in range(5):
        res = run(4, 4, ["-k", "watch or edit"], tmp / f"flake{i}.xml")
        bad = [t for t, o in res.items() if o != "passed"]
        ok &= not bad
        lines.append(f"- watcher run {i + 1}/5: {len(bad)} not passing {bad or ''}")
    lines += ["", f"**Result: {'PASS' if ok else 'FAIL'}**", ""]
    (REPO / "results/instrument-validation.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
