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


def test_a_skipped_marker_beats_a_forged_earlier_one_and_leaves_the_name_unchecked():
    got = rm.parse_batch("__rc pkg.m.x_f__mutmut_1 1\n__rc pkg.m.x_f__mutmut_1 skipped\n", ["pkg.m.x_f__mutmut_1"])
    assert got == {}


def test_a_137_from_timeouts_kill_grace_is_a_timeout_not_suspicious():
    got = rm.parse_batch("__rc pkg.m.x_f__mutmut_1 137\n", ["pkg.m.x_f__mutmut_1"])
    assert got == {"pkg.m.x_f__mutmut_1": None} and rm.verdict(got["pkg.m.x_f__mutmut_1"]) == "timeout"


# --- the per-batch shell script, run on the host against a stub interpreter (no arm code) -------------------------

def _stub_copy(tmp_path: Path, codes: dict[str, int]) -> tuple[Path, Path]:
    """A copy dir whose `.venv/bin/python` is a bash stub: it prints a forged marker for every name, records the
    MUTANT_UNDER_TEST and PYTHONPATH it saw, and exits with codes[MUTANT_UNDER_TEST]. `timeout` is stubbed to just
    log its timeout seconds to timeouts.txt and run its command (macOS has none)."""
    copy = tmp_path / "copy"
    (copy / "mutants" / "src").mkdir(parents=True)
    (copy / ".venv" / "bin").mkdir(parents=True)
    seen = tmp_path / "seen.txt"
    case = "\n".join(f'  {json.dumps(k)}) exit {v};;' for k, v in codes.items())
    py = copy / ".venv" / "bin" / "python"
    py.write_text(f"""#!/bin/bash
echo "$MUTANT_UNDER_TEST|$PYTHONPATH|$PWD|$*" >> {seen}
[ -n "${{STUB_SLEEP:-}}" ] && sleep "$STUB_SLEEP"
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
    t.write_text(f'#!/bin/bash\n[ "$1" = -k ] && shift 2\necho "$1" >> {tmp_path / "timeouts.txt"}\nshift\nexec "$@"\n')
    t.chmod(0o755)
    return copy, bindir


def test_the_batch_script_records_each_exit_code_after_all_arm_output(tmp_path):
    names = ["pkg.m.x_f__mutmut_1", "pkg.m.x_f__mutmut_2", "fail"]
    copy, bindir = _stub_copy(tmp_path, {"pkg.m.x_f__mutmut_1": 1, "pkg.m.x_f__mutmut_2": 0, "fail": 5})
    cmd = rm.batch_command(names, 60, 1000)
    r = subprocess.run(cmd, cwd=copy, capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"})
    assert rm.parse_batch(r.stdout, names) == {"pkg.m.x_f__mutmut_1": 1, "pkg.m.x_f__mutmut_2": 0, "fail": 5}
    seen = [ln.split("|") for ln in (tmp_path / "seen.txt").read_text().splitlines()]
    assert [s[0] for s in seen] == names
    m = str((copy / "mutants").resolve())
    assert all(s[1] == f"{m}/src:{m}" and Path(s[2]).resolve() == Path(m) for s in seen)
    assert all(s[3] == "-m pytest -q -x -p no:cacheprovider" for s in seen)


def test_budget_truncation_never_produces_a_timeout_verdict(tmp_path):
    names = ["pkg.m.x_f__mutmut_1", "pkg.m.x_f__mutmut_2", "pkg.m.x_f__mutmut_3"]
    copy, bindir = _stub_copy(tmp_path, {n: 1 for n in names})
    # the stub `timeout` exits 124 whenever it is given less than the full per-mutant timeout (60 s): a mutant started
    # on a truncated budget would show up as a fake timeout
    t = bindir / "timeout"
    t.write_text(f'#!/bin/bash\n[ "$1" = -k ] && shift 2\necho "$1" >> {tmp_path / "timeouts.txt"}\n'
                 '[ "$1" -lt 60 ] && exit 124\nshift\nexec "$@"\n')
    r = subprocess.run(rm.batch_command(names, 60, 61), cwd=copy, capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "STUB_SLEEP": "2.2"})
    # mutant 1 starts with 61 s left (>= 60); after it ~59 s are left, under a full timeout: 2 and 3 never start
    got = rm.parse_batch(r.stdout, names)
    assert got == {"pkg.m.x_f__mutmut_1": 1} and None not in got.values()
    assert (tmp_path / "timeouts.txt").read_text().split() == ["60"]
    assert "__rc pkg.m.x_f__mutmut_2 skipped" in r.stdout and "__rc pkg.m.x_f__mutmut_3 skipped" in r.stdout


def test_the_batch_script_with_no_budget_left_runs_nothing(tmp_path):
    names = ["pkg.m.x_f__mutmut_1"]
    copy, bindir = _stub_copy(tmp_path, {n: 1 for n in names})
    r = subprocess.run(rm.batch_command(names, 60, 0), cwd=copy, capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"})
    assert rm.parse_batch(r.stdout, names) == {} and not (tmp_path / "seen.txt").exists()


def test_run_batch_clamps_the_container_timeout_to_the_remaining_budget(tmp_path, monkeypatch):
    seen = []
    def fake_run(p, copy, cmd, timeout, env=None):
        seen.append((cmd, timeout))
        return quality.ToolRun(0, "", "")
    monkeypatch.setattr(quality, "_run", fake_run)
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(20)]
    rm.run_batch(paths.Paths("p", "alpha"), tmp_path / "copy", names, 600, remaining=100)
    rm.run_batch(paths.Paths("p", "alpha"), tmp_path / "copy", names[:1], 30, remaining=10_000)
    (cmd1, t1), (cmd2, t2) = seen
    assert t1 == 100 + rm.CONTAINER_SLACK_S and cmd1[4:6] == ["600", "100"]
    assert t2 == 1 * (30 + 15) + 120 and cmd2[4:6] == ["30", "10000"]


# --- target selection ---------------------------------------------------------------------------------------------

def test_targets_are_the_collected_steps_whose_mutation_crashed(tmp_state):
    crashed = {"mypy_errors": 0, "ruff_findings": 0, "mutation_score": None, "mutation_state": "crashed"}
    write_collected("p", "beta", 2, quality=crashed)
    write_collected("p", "alpha", 3, quality=crashed)
    write_collected("p", "alpha", 1)                                                   # measured
    write_collected("p", "alpha", 4, quality={**crashed, "mutation_state": "baseline_failed"})
    write_collected("p", "gamma", 1, quality=values.missing("x", "no such file"))
    assert rm.targets("p") == [("alpha", 3), ("beta", 2)]


def test_targets_with_a_malformed_collected_record_refuse(tmp_state):
    write_collected("p", "alpha", 1)
    (paths.scoring_out("p") / "collected" / "alpha" / "02.json").write_text("{not json")
    with pytest.raises(inputs.InputError, match="02.json"):
        rm.targets("p")


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
        self.remaining: list = []

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

    def run_batch(self, p, copy, names, timeout, log=None, remaining=None):
        self.remaining.append(remaining)
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


def test_one_where_no_mutant_is_killed_and_all_survived_is_crashed_dispatch_unverified(tmp_state, monkeypatch):
    _step(tmp_state)
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(5)]
    Fake(tmp_state, names, {n: 0 for n in names}).install(monkeypatch)
    s = _read(rm.one("p", "alpha", 3))
    assert s["crashed"] is True and s["score"] is None and s["survived"] == 5
    assert s["harness_error"] == "no mutant killed: dispatch unverified"


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


# --- evidence: scores over checked mutants, prefers a measured and current re-measure -----------------------------

def _counts(**c) -> dict:
    return {**quality.ZERO_MUTATION, **c, "total": sum(c.values())}


def _quality_dir(tmp_path, remeasure: dict | None, mutation: dict | None = None, sha_after="abc") -> Path:
    d = tmp_path / "03"
    (d / "quality").mkdir(parents=True)
    (d / "git.json").write_text(json.dumps({"sha_after": sha_after}))
    (d / "quality" / "summary.json").write_text(json.dumps(
        {"mypy_errors": 2, "ruff_findings": 1,
         "mutation": mutation if mutation is not None else {**quality.ZERO_MUTATION, "crashed": True, "score": None}}))
    if remeasure is not None:
        (d / "quality" / "remeasure.json").write_text(json.dumps(remeasure))
    return d


def _orig(**c) -> dict:
    return quality.mutation_summary(_counts(**c), partial=c.get("not_checked", 0) > 0, baseline_failed=False)


def test_a_full_run_scores_killed_over_checked(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, None, _orig(killed=8, survived=2)))["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.8
    assert q["mutation_partial"] is False and q["mutation_checked_fraction"] == 1.0


def test_a_partial_run_above_half_checked_scores_over_the_checked_mutants_only(tmp_path):
    # eligible = 12 - 2 no_tests = 10; checked = 10 - 4 not_checked = 6; score 3/6 (quality.py itself says 3/10)
    q = evidence.quality(_quality_dir(tmp_path, None, _orig(killed=3, survived=3, not_checked=4, no_tests=2)))["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.5
    assert q["mutation_partial"] is True and q["mutation_checked_fraction"] == 0.6


def test_sampled_names_mutmut_never_reported_count_as_unchecked(tmp_path):
    m = {**_orig(killed=10), "missing_results": 90}           # 100 sampled, 10 reported, all killed
    q = evidence.quality(_quality_dir(tmp_path, None, m))["value"]
    assert q["mutation_checked_fraction"] == 0.1 and q["mutation_state"] == "unmeasured" and q["mutation_score"] is None


def test_a_partial_run_below_half_checked_is_unmeasured_and_says_why(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, None, _orig(killed=2, not_checked=8)))["value"]
    assert q["mutation_state"] == "unmeasured" and q["mutation_score"] is None
    assert q["mutation_why"] == "partial: under 50% of sampled mutants checked"
    assert q["mutation_checked_fraction"] == 0.2


def test_crashed_and_baseline_failed_states_are_kept(tmp_path):
    crashed = {**_orig(killed=5, survived=5), "crashed": True, "score": None}
    assert evidence.quality(_quality_dir(tmp_path / "a", None, crashed))["value"]["mutation_state"] == "crashed"
    bf = {**_orig(), "baseline_failed": True}
    assert evidence.quality(_quality_dir(tmp_path / "b", None, bf))["value"]["mutation_state"] == "baseline_failed"


def test_evidence_prefers_a_measured_remeasure(tmp_path):
    r = rm.summarise({"m1": "killed", "m2": "survived", "m3": "not_checked"}, sha="abc")
    q = evidence.quality(_quality_dir(tmp_path, r))["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.5 and q["mypy_errors"] == 2
    assert q["mutation_method"] == "whole-suite-per-mutant" and q["mutation_source"].endswith("remeasure.json")
    assert q["mutation_partial"] is True and q["remeasure_ignored"] is None


def test_evidence_ignores_a_crashed_remeasure_and_says_why(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, rm.summarise({}, crashed=True, sha="abc")))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_method"] == "mutmut"
    assert q["remeasure_ignored"] == "not measured: crashed"


def test_evidence_ignores_a_stale_remeasure_and_says_why(tmp_path):
    r = rm.summarise({"m1": "killed"}, sha="old")
    q = evidence.quality(_quality_dir(tmp_path, r, sha_after="abc"))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_source"].endswith("summary.json")
    assert q["remeasure_ignored"] == "stale: remeasure sha old, git.json sha_after abc"


def test_evidence_without_a_remeasure_is_unchanged(tmp_path):
    q = evidence.quality(_quality_dir(tmp_path, None))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_source"].endswith("summary.json")
    assert q["remeasure_ignored"] is None


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
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(80)]         # four batches of 20
    f = Fake(tmp_state, names, {n: 1 for n in names}).install(monkeypatch)
    clock = [0.0]
    monkeypatch.setattr(rm, "_clock", lambda: clock[0])
    real_batch = f.run_batch
    def timed_batch(*a, **k):
        clock[0] += 30.0                                            # every container takes 30 s
        return real_batch(*a, **k)
    monkeypatch.setattr(rm, "run_batch", timed_batch)
    pins = config.load_pins()
    pins = dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, mutation_seconds=130, mutation_sample=0))
    s = _read(rm.one("p", "alpha", 3, pins=pins))
    # per-mutant timeout 60 s (the floor). Control at 0 s (130 left), batches 1 and 2 at 30 s and 60 s (100, 70 left);
    # at 90 s only 40 s are left, under one full mutant timeout: batches 3 and 4 never start
    assert len(f.batches) == 2 and s["killed"] == 40 and s["not_checked"] == 40
    assert s["partial"] is True and s["crashed"] is False and s["score"] == 40 / 80
    assert s["budget_s"] == 130 and s["budget_exhausted"] is True and f.remaining == [130, 100, 70]


def test_the_control_container_counts_against_the_budget(tmp_state, monkeypatch):
    _step(tmp_state)
    names = [f"pkg.m.x_f__mutmut_{i}" for i in range(5)]
    f = Fake(tmp_state, names, {n: 1 for n in names}).install(monkeypatch)
    clock = [0.0]
    monkeypatch.setattr(rm, "_clock", lambda: clock[0])
    real_batch = f.run_batch
    def slow_control(*a, **k):
        clock[0] += 60.0
        return real_batch(*a, **k)
    monkeypatch.setattr(rm, "run_batch", slow_control)
    pins = config.load_pins()
    pins = dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, mutation_seconds=50, mutation_sample=0))
    s = _read(rm.one("p", "alpha", 3, pins=pins))
    assert f.remaining == [50] and f.batches == [] and s["budget_exhausted"] is True and s["not_checked"] == 5
