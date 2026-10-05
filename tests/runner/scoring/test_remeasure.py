import dataclasses
import fcntl
import json
import os
import subprocess
from pathlib import Path

import pytest

from runner import cli, config, faults, hidden, paths, quality
from runner.scoring import evidence, inputs, values
from runner.scoring import cli as scli
from runner.scoring import remeasure as rm
from tests.runner.scoring.test_aggregate import write_collected


# --- verdicts and the summary ------------------------------------------------------------------------------------

def test_exit_codes_map_to_mutation_verdicts():
    assert [rm.verdict(c) for c in (0, 1, None, 5, 137)] == ["survived", "killed", "timeout", "no_tests",
                                                              "suspicious"]


def test_summary_scores_killed_over_checked_excluding_no_tests():
    s = rm.summarise({"m1": "killed", "m2": "killed", "m3": "survived", "m4": "no_tests"})
    assert s["score"] == 2 / 3 and s["method"] == "whole-suite-per-mutant" and s["crashed"] is False


def test_summary_carries_the_quality_mutation_key_set_and_the_seeded_sampling():
    s = rm.summarise({"m1": "killed"})
    plain = quality.mutation_summary(dict(quality.ZERO_MUTATION), partial=False, baseline_failed=False)
    assert set(plain) <= set(s) and s["sampling"] == "seeded-sha256"


def test_summary_with_no_real_verdict_and_unchecked_mutants_is_crashed_not_zero():
    s = rm.summarise({"m1": "not_checked", "m2": "no_tests"})
    assert s["crashed"] is True and s["score"] is None


def test_summary_with_some_unchecked_mutants_is_partial_and_counts_them_unkilled():
    # quality.mutation_summary's denominator excludes only no_tests and skipped: an unchecked mutant counts unkilled
    s = rm.summarise({"m1": "killed", "m2": "survived", "m3": "not_checked"})
    assert s["partial"] is True and s["crashed"] is False and s["score"] == 1 / 3 and s["not_checked"] == 1


def test_summary_where_every_mutant_has_no_tests_is_unmeasured_not_crashed():
    s = rm.summarise({"m1": "no_tests", "m2": "no_tests"})
    assert s["crashed"] is False and s["score"] is None and s["unmeasured"] == quality.UNMEASURED_NO_COVERAGE


def test_a_forced_crash_withholds_the_score_whatever_the_verdicts():
    s = rm.summarise({"m1": "killed"}, crashed=True)
    assert s["crashed"] is True and s["score"] is None


def test_mutant_timeout_is_ten_times_the_baseline_with_a_floor():
    assert rm.mutant_timeout(2.0) == rm.MIN_MUTANT_TIMEOUT_S
    assert rm.mutant_timeout(30.25) == 303


# --- markers ------------------------------------------------------------------------------------------------------

def test_markers_are_read_from_the_last_anchored_line_and_only_for_requested_names():
    text = ("__rc pkg.m.x_f__mutmut_1 0\n"          # forged by arm output, earlier
            "  __rc pkg.m.x_f__mutmut_2 0\n"        # not anchored: ignored
            "__rc pkg.m.x_f__mutmut_1 1\n"
            "__rc pkg.m.x_f__mutmut_2 124\n"
            "__rc other__mutmut_9 0\n")
    got = rm.parse_batch(text, ["pkg.m.x_f__mutmut_1", "pkg.m.x_f__mutmut_2", "pkg.m.x_f__mutmut_3"])
    assert got == {"pkg.m.x_f__mutmut_1": 1, "pkg.m.x_f__mutmut_2": None}


# --- the per-batch shell script, run on the host against a stub interpreter (no arm code) -------------------------

def _stub_copy(tmp_path: Path, codes: dict[str, int]) -> tuple[Path, Path]:
    """A copy dir whose `.venv/bin/python` is a bash stub: it prints a forged marker for every name, records the
    MUTANT_UNDER_TEST and PYTHONPATH it saw, and exits with codes[MUTANT_UNDER_TEST]. `timeout` is stubbed to just
    run its command (macOS has none)."""
    copy = tmp_path / "copy"
    (copy / "mutants" / "src").mkdir(parents=True)
    (copy / ".venv" / "bin").mkdir(parents=True)
    seen = tmp_path / "seen.txt"
    case = "\n".join(f'  {json.dumps(k)}) exit {v};;' for k, v in codes.items())
    py = copy / ".venv" / "bin" / "python"
    py.write_text(f"""#!/bin/bash
echo "$MUTANT_UNDER_TEST|$PYTHONPATH|$PWD|$*" >> {seen}
for n in {' '.join(codes)}; do echo "__rc $n 0"; done
case "$MUTANT_UNDER_TEST" in
{case}
esac
exit 3
""")
    py.chmod(0o755)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    t = bindir / "timeout"
    t.write_text('#!/bin/bash\n[ "$1" = -k ] && shift 2\nshift\nexec "$@"\n')
    t.chmod(0o755)
    return copy, bindir


def test_the_batch_script_records_each_exit_code_after_all_arm_output(tmp_path):
    names = ["pkg.m.x_f__mutmut_1", "pkg.m.x_f__mutmut_2", "fail"]
    copy, bindir = _stub_copy(tmp_path, {"pkg.m.x_f__mutmut_1": 1, "pkg.m.x_f__mutmut_2": 0, "fail": 5})
    cmd = rm.batch_command(names, 60)
    r = subprocess.run(cmd, cwd=copy, capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"})
    assert rm.parse_batch(r.stdout, names) == {"pkg.m.x_f__mutmut_1": 1, "pkg.m.x_f__mutmut_2": 0, "fail": 5}
    seen = [ln.split("|") for ln in (tmp_path / "seen.txt").read_text().splitlines()]
    assert [s[0] for s in seen] == names
    m = str((copy / "mutants").resolve())
    assert all(s[1] == f"{m}/src:{m}" and Path(s[2]).resolve() == Path(m) for s in seen)
    assert all(s[3] == "-m pytest -q -x -p no:cacheprovider" for s in seen)


# --- target selection ---------------------------------------------------------------------------------------------

def test_targets_are_the_collected_steps_whose_mutation_crashed(tmp_state):
    crashed = {"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None, "mutation_state": "crashed"}
    write_collected("p", "beta", 2, quality=crashed)
    write_collected("p", "alpha", 3, quality=crashed)
    write_collected("p", "alpha", 1)                                                   # measured
    write_collected("p", "alpha", 4, quality={**crashed, "mutation_state": "baseline_failed"})
    write_collected("p", "gamma", 1, quality=values.missing("x", "no such file"))
    assert rm.targets("p") == [("alpha", 3), ("beta", 2)]


def test_targets_without_collected_records_refuse(tmp_state):
    (paths.RESULTS / "p").mkdir(parents=True)
    with pytest.raises(inputs.InputError, match="collect"):
        rm.targets("p")


# --- one(): end to end with the container seam faked --------------------------------------------------------------

class Fake:
    """Every container-facing call `one()` makes, faked. `codes` maps a mutant name to its exit code."""

    def __init__(self, tmp_path: Path, names: list[str], codes: dict[str, int | None], *, baseline_rc: int | None = 0,
                 control: dict[str, int | None] | None = None, quality_ok: bool = True, dead_batches: int = 0):
        self.a, self.b = tmp_path / "a" / "copy", tmp_path / "b" / "copy"
        (self.a / "src" / "pkg").mkdir(parents=True)
        self.b.mkdir(parents=True)
        self.names, self.codes, self.baseline_rc = names, codes, baseline_rc
        self.control = control if control is not None else {"__baseline__": 0, "fail": 1}
        self.quality_ok, self.dead_batches = quality_ok, dead_batches
        self.batches: list[list[str]] = []
        self.prepared: list[tuple] = []
        self.listed_targets: list[list[str]] = []

    def install(self, monkeypatch):
        monkeypatch.setattr(rm, "_prepare", self.prepare)
        monkeypatch.setattr(rm, "_baseline", self.baseline)
        monkeypatch.setattr(rm, "_list_mutants", self.list_mutants)
        monkeypatch.setattr(rm, "run_batch", self.run_batch)
        return self

    def prepare(self, p, sha, label, out_dir):
        self.prepared.append((p, sha, label, out_dir))
        return hidden.Prepared(self.a, self.b, {"quality": {"ok": self.quality_ok}})

    def baseline(self, p, copy):
        return (self.baseline_rc, 4.0, "baseline output")

    def list_mutants(self, p, copy, tg):
        self.listed_targets.append(tg)
        return list(reversed(self.names))

    def run_batch(self, p, copy, names, timeout, log=None):
        if names in (["__baseline__", "fail"],):
            return {n: self.control[n] for n in names if n in self.control}
        self.batches.append(list(names))
        if len(self.batches) <= self.dead_batches:
            return {}
        return {n: self.codes[n] for n in names if n in self.codes}


def _step(tmp_state, pass_="p", arm="alpha", step=3, sha="abc123"):
    d = paths.RESULTS / pass_ / arm / f"{step:02d}"
    d.mkdir(parents=True)
    if sha is not None:
        (d / "git.json").write_text(json.dumps({"sha_after": sha}))
    return d


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def test_one_scores_the_same_seeded_sample_in_batches_of_twenty(tmp_state, monkeypatch):
    d = _step(tmp_state)
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(300)]
    codes = {n: (1 if i % 4 else 0) for i, n in enumerate(names)}
    f = Fake(tmp_state, names, codes).install(monkeypatch)
    out = rm.one("p", "alpha", 3)
    assert out == d / "quality" / "remeasure.json" and (d / "quality" / "remeasure.log").exists()
    s = _read(out)
    chosen = quality.sample(names, rm.config.load_pins().limits.mutation_sample)
    assert [n for b in f.batches for n in b] == chosen and all(len(b) <= 20 for b in f.batches)
    killed = sum(1 for n in chosen if codes[n] == 1)
    assert s["score"] == killed / len(chosen) and s["killed"] == killed and s["sample_size"] == len(chosen)
    assert s["method"] == "whole-suite-per-mutant" and s["crashed"] is False and s["sampling"] == "seeded-sha256"
    assert f.prepared[0][1:3] == ("abc123", "03-remeasure") and f.listed_targets == [["src"]]


def test_one_with_a_sentinel_that_does_not_fail_is_crashed_and_runs_no_mutant(tmp_state, monkeypatch):
    d = _step(tmp_state)
    names = ["pkg.m.x_f__mutmut_1"]
    f = Fake(tmp_state, names, {names[0]: 1}, control={"__baseline__": 0, "fail": 0}).install(monkeypatch)
    s = _read(rm.one("p", "alpha", 3))
    assert s["crashed"] is True and s["score"] is None and s["sentinel_rc"] == 0 and f.batches == []
    assert "trampoline" in s["harness_error"]


def test_one_with_a_failing_baseline_inside_mutants_is_crashed(tmp_state, monkeypatch):
    _step(tmp_state)
    Fake(tmp_state, ["pkg.m.x_f__mutmut_1"], {}, control={"__baseline__": 1, "fail": 1}).install(monkeypatch)
    s = _read(rm.one("p", "alpha", 3))
    assert s["crashed"] is True and s["score"] is None and s["mutants_baseline_rc"] == 1


def test_one_with_the_arms_own_suite_failing_is_baseline_failed_not_crashed(tmp_state, monkeypatch):
    _step(tmp_state)
    Fake(tmp_state, ["pkg.m.x_f__mutmut_1"], {}, baseline_rc=1).install(monkeypatch)
    s = _read(rm.one("p", "alpha", 3))
    assert s["baseline_failed"] is True and s["crashed"] is False and s["score"] is None


def test_one_with_a_dead_batch_container_marks_its_mutants_not_checked_and_partial(tmp_state, monkeypatch):
    _step(tmp_state)
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(30)]
    Fake(tmp_state, names, {n: 1 for n in names}, dead_batches=1).install(monkeypatch)
    monkeypatch.setattr(rm, "_sample_size", lambda pins: 0)          # all 30: one batch of 20, one of 10
    s = _read(rm.one("p", "alpha", 3))
    assert s["not_checked"] == 20 and s["killed"] == 10 and s["partial"] is True and s["score"] == 10 / 30


def test_one_without_a_recorded_sha_is_crashed_and_prepares_nothing(tmp_state, monkeypatch):
    _step(tmp_state, sha=None)
    f = Fake(tmp_state, [], {}).install(monkeypatch)
    s = _read(rm.one("p", "alpha", 3))
    assert s["crashed"] is True and "sha_after" in s["harness_error"] and f.prepared == []


def test_one_records_an_exception_in_the_seam_as_crashed_and_still_writes(tmp_state, monkeypatch):
    _step(tmp_state)
    f = Fake(tmp_state, ["pkg.m.x_f__mutmut_1"], {}).install(monkeypatch)
    def boom(*a, **k): raise RuntimeError("docker went away")
    monkeypatch.setattr(rm, "run_batch", boom)
    s = _read(rm.one("p", "alpha", 3))
    assert s["crashed"] is True and s["harness_error"] == "RuntimeError: docker went away"
    assert set(rm.summarise({}, crashed=True)) == set(s)


def test_every_path_writes_the_same_key_set(tmp_state, monkeypatch):
    _step(tmp_state, arm="a1")
    _step(tmp_state, arm="a2", sha=None)
    Fake(tmp_state, ["pkg.m.x_f__mutmut_1"], {"pkg.m.x_f__mutmut_1": 1}).install(monkeypatch)
    ok, bad = _read(rm.one("p", "a1", 3)), _read(rm.one("p", "a2", 3))
    assert set(ok) == set(bad)


# --- evidence prefers a measured re-measure -----------------------------------------------------------------------

def _quality_dir(tmp_path, remeasure: dict | None) -> Path:
    d = tmp_path / "03"
    (d / "quality").mkdir(parents=True)
    (d / "quality" / "summary.json").write_text(json.dumps(
        {"mypy_errors": 2, "ruff_findings": 1, "mutation": {"crashed": True, "score": None}}))
    if remeasure is not None:
        (d / "quality" / "remeasure.json").write_text(json.dumps(remeasure))
    return d


def test_evidence_prefers_a_measured_remeasure(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, rm.summarise({"m1": "killed", "m2": "survived"})))["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.5 and q["mypy_errors"] == 2
    assert q["mutation_method"] == "whole-suite-per-mutant" and q["mutation_source"].endswith("remeasure.json")


def test_evidence_ignores_a_crashed_remeasure(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, rm.summarise({}, crashed=True)))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_method"] == "mutmut"


def test_evidence_without_a_remeasure_is_unchanged(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, None))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_source"].endswith("summary.json")


# --- the CLI stage ------------------------------------------------------------------------------------------------

def test_remeasure_stage_refuses_while_another_runner_holds_the_lock(tmp_state, monkeypatch, capsys):
    (paths.RESULTS / "p").mkdir(parents=True)
    calls = []
    monkeypatch.setattr(rm, "run", lambda pass_: calls.append(pass_) or [])
    paths.LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(paths.LOCK, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert cli.main(["score", "p", "--stage", "remeasure"]) == 1
    assert calls == [] and "another runner holds" in capsys.readouterr().out


def test_remeasure_stage_runs_under_the_lock(tmp_state, monkeypatch):
    (paths.RESULTS / "p").mkdir(parents=True)
    held = []
    def run(pass_):
        with open(paths.LOCK, "a") as fh:            # a second flock on the file must fail while the stage holds it
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held.append(False)
            except BlockingIOError:
                held.append(True)
        return []
    monkeypatch.setattr(rm, "run", run)
    assert "remeasure" in scli.STAGES and "remeasure" not in scli.DEFAULT
    assert cli.main(["score", "p", "--stage", "remeasure"]) == 0
    assert held == [True]


# --- R31: a halted pass, and the per-step time budget -------------------------------------------------------------

def test_remeasure_stage_refuses_on_a_halted_pass_and_runs_nothing(tmp_state, monkeypatch, capsys):
    (paths.RESULTS / "p").mkdir(parents=True)
    faults.halt("p", "suite-resource:1 test", {"x": 1})
    calls = []
    monkeypatch.setattr(rm, "run", lambda pass_: calls.append(pass_) or [])
    assert cli.main(["score", "p", "--stage", "remeasure"]) == 1
    out = capsys.readouterr().out
    assert calls == [] and "HALTED" in out and "suite-resource:1 test" in out and "faults resume p" in out


def test_mutants_not_reached_within_the_step_budget_are_not_checked_and_partial(tmp_state, monkeypatch):
    _step(tmp_state)
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(60)]         # three batches of 20
    f = Fake(tmp_state, names, {n: 1 for n in names}).install(monkeypatch)
    clock = [0.0]
    monkeypatch.setattr(rm, "_clock", lambda: clock[0])
    real_batch = f.run_batch
    def timed_batch(*a, **k):
        clock[0] += 30.0                                            # every container takes 30 s
        return real_batch(*a, **k)
    monkeypatch.setattr(rm, "run_batch", timed_batch)
    pins = config.load_pins()
    pins = dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, mutation_seconds=50, mutation_sample=0))
    s = _read(rm.one("p", "alpha", 3, pins=pins))
    # control at 0 s, batch 1 at 30 s, then 60 s >= 50 s: batch 2 and 3 never start
    assert len(f.batches) == 1 and s["killed"] == 20 and s["not_checked"] == 40
    assert s["partial"] is True and s["crashed"] is False and s["score"] == 20 / 60
    assert s["budget_s"] == 50 and s["budget_exhausted"] is True
