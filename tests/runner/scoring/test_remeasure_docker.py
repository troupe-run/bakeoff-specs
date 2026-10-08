"""Task 20, after pass 1 only (Docker, the arms' state/ scratch, and the runner lock — run with `--run-docker` once
pass 1 has finished and nothing else holds `state/runner.lock`)."""
import json
import shutil

import pytest

from runner import config, hidden, paths, preflight, quality
from runner.paths import Paths
from runner.scoring import evidence
from runner.scoring import remeasure as rm

pytestmark = pytest.mark.docker


def _sha(pass_: str, arm: str, step: int) -> str:
    d = paths.RESULTS / pass_ / arm / f"{step:02d}"
    if not (d / "git.json").exists():
        pytest.skip(f"{d / 'git.json'} absent (results/{pass_} snapshot not present)")
    if not Paths(pass_, arm).repo.exists():
        pytest.skip(f"{Paths(pass_, arm).repo} absent (the arm's state is not in this checkout)")
    return json.loads((d / "git.json").read_text())["sha_after"]


def test_spike_trampoline_honours_mutant_under_test_from_a_whole_suite_run(tmp_path):
    """Brief Step 1 on pass1/ccsdd/04: from `mutants/`, a name matching no mutant passes the suite (the baseline),
    the trampoline's `fail` sentinel fails it, and at least one of the first sampled mutants is killed (rc 1). If
    this fails, mutmut 3.8.0's trampoline does not work this way: stop and report to the owner (fallback: select
    tests by file from mutants/mutmut-stats.json)."""
    p = Paths("pass1", "ccsdd")
    sha = _sha("pass1", "ccsdd", 4)
    with preflight.lock():
        prep = hidden.prepare(p, sha, "04-remeasure-spike", tmp_path, with_quality=True, require_main=False)
        assert prep.quality_copy is not None and prep.prep["quality"]["ok"]
        tg = quality.targets(prep.hidden_copy)
        names = quality.list_mutants(p, prep.quality_copy, tg)
        assert names, "mutmut listed no mutants"
        log: list[str] = []
        ctl = rm.run_batch(p, prep.quality_copy, [rm.BASELINE_NAME, rm.SENTINEL_NAME], 600, log)
        print("\n".join(log))
        # the sentinel only has to FAIL the suite, as `remeasure._measure` requires (rc not 0, not a timeout): on
        # ccsdd it raises while conftest imports a trampolined function, which is pytest rc 4, not 1 (2026-10-08)
        assert ctl.get(rm.BASELINE_NAME) == 0, f"baseline from mutants/: rc {ctl.get(rm.BASELINE_NAME)} (None: timeout)"
        assert ctl.get(rm.SENTINEL_NAME) not in (0, None), f"sentinel rc {ctl.get(rm.SENTINEL_NAME)}"
        first = quality.sample(names, config.load_pins().limits.mutation_sample)[:rm.BATCH]
        got = rm.run_batch(p, prep.quality_copy, first, 600, log)
        print(log[-1])
        assert set(got) == set(first) and 1 in got.values()


def test_remeasure_of_dry1_dryrun_01_writes_a_scored_summary():
    sha = _sha("dry1", "dryrun", 1)
    qd = paths.RESULTS / "dry1" / "dryrun" / "01" / "quality"
    created = [qd / "remeasure.json", qd / "remeasure.log", qd / "remeasure-prep"]
    assert not any(f.exists() for f in created), "a previous re-measure is already in the snapshot"
    try:
        with preflight.lock():
            out = rm.one("dry1", "dryrun", 1)
        s = json.loads(out.read_text())
        assert s["sha"] == sha and s["crashed"] is False, s["harness_error"]
        assert s["score"] is not None and s["method"] == "whole-suite-per-mutant"
        assert s["killed"] > 0 and s["score"] > 0       # dispatch reached at least one mutant (R32)
        q = evidence.quality(qd.parent)["value"]
        assert q["mutation_method"] == "whole-suite-per-mutant", q["remeasure_ignored"]
    finally:                                        # leave the shared results/dry1 snapshot as it was
        for f in created:
            shutil.rmtree(f) if f.is_dir() else f.unlink(missing_ok=True)
