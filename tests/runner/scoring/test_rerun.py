"""Owner rulings O1-O4 (2026-10-08): mutmut's original method re-run on crashed pass-1 arm-steps, kept beside the
original evidence, and the scoring layer's use of it; control's subprocess-only tests labelled unmeasured."""
import json
from pathlib import Path

import pytest

from runner import hidden, paths, quality
from runner.scoring import evidence
from runner.scoring import rerun as rr


def _orig(**c) -> dict:
    counts = {**quality.ZERO_MUTATION, **c, "total": sum(c.values())}
    return quality.mutation_summary(counts, partial=c.get("not_checked", 0) > 0, baseline_failed=False)


CRASHED = {**_orig(not_checked=200), "crashed": True, "score": None, "mutmut_run_rc": 1, "baseline_rc": 0}
STOP_EARLY = ("49 passed in 31.92s\nStopping early, because we could not find any test case for any mutant. It seems "
              "that the selected tests do not cover any code that we mutated.\n\n__run_rc=1\n")


def _step(tmp_path, original: dict, rerun: dict | None = None, sha_after="abc", log: str = "") -> Path:
    d = tmp_path / "03"
    (d / "quality").mkdir(parents=True)
    (d / "git.json").write_text(json.dumps({"sha_after": sha_after}))
    (d / "quality" / "summary.json").write_text(json.dumps({"mypy_errors": 2, "ruff_findings": 1, "mutation": original}))
    (d / "quality" / "mutmut.log").write_text(log)
    if rerun is not None:
        (d / "quality" / "rerun").mkdir()
        (d / "quality" / "rerun" / "mutation.json").write_text(json.dumps(rerun))
    return d


def _rerun(sha="abc", reason="O1", nodeid_rewrites=2, **c) -> dict:
    return {**_orig(**c), "nodeid_rewrites": nodeid_rewrites,
            "rerun": {"reason": reason, "ruling": rr.REASONS[reason], "method": "mutmut", "sha": sha,
                      "date": "2026-10-08", "harness_error": None}}


# --- evidence ------------------------------------------------------------------------------------------------------

def test_a_measured_current_rerun_replaces_a_crashed_original_and_says_so(tmp_path):
    q = evidence.quality(_step(tmp_path, CRASHED, _rerun(killed=6, survived=2, no_tests=2)))["value"]
    assert q["mutation_state"] == "measured" and q["mutation_score"] == 0.75
    assert q["mutation_method"] == "mutmut"          # the same method: R35's mixed-method flag must not fire
    assert q["mutation_source"].endswith("quality/rerun/mutation.json")
    assert q["mutation_rerun"] == {"reason": "O1", "date": "2026-10-08", "nodeid_rewrites": 2}
    assert q["rerun_ignored"] is None and q["mypy_errors"] == 2


def test_a_measured_original_is_never_replaced_by_a_rerun(tmp_path):
    q = evidence.quality(_step(tmp_path, _orig(killed=8, survived=2), _rerun(killed=1, survived=9)))["value"]
    assert q["mutation_score"] == 0.8 and q["mutation_source"].endswith("quality/summary.json")
    assert q["mutation_rerun"] is None and q["rerun_ignored"] == "the original run is measured"


def test_a_stale_or_unmeasured_rerun_is_ignored_and_says_why(tmp_path):
    q = evidence.quality(_step(tmp_path / "a", CRASHED, _rerun(sha="old", killed=5)))["value"]
    assert q["mutation_state"] == "crashed" and q["rerun_ignored"] == "stale: rerun sha old, git.json sha_after abc"
    crashed = {**_rerun(), **{k: v for k, v in CRASHED.items()}}
    q = evidence.quality(_step(tmp_path / "b", CRASHED, crashed))["value"]
    assert q["mutation_state"] == "crashed" and q["rerun_ignored"] == "not measured: crashed"


def test_no_rerun_leaves_the_original_untouched(tmp_path):
    q = evidence.quality(_step(tmp_path, CRASHED))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_rerun"] is None and q["rerun_ignored"] is None


def test_a_crash_that_is_mutmuts_subprocess_blind_spot_is_unmeasured_with_the_reason(tmp_path):
    # O4: pass 1 control 01-07 -- the tests reach the code only through `subprocess`, which mutmut cannot attribute
    q = evidence.quality(_step(tmp_path / "a", CRASHED, log="$ .venv/bin/mutmut run ...\n" + STOP_EARLY))["value"]
    assert q["mutation_state"] == "unmeasured" and q["mutation_score"] is None
    assert q["mutation_why"] == evidence.SUBPROCESS_ONLY == "subprocess-only tests are invisible to mutmut"
    q = evidence.quality(_step(tmp_path / "b", CRASHED, log="BadTestExecutionCommandsException\n__run_rc=1\n"))["value"]
    assert q["mutation_state"] == "crashed" and q["mutation_why"] is None


def test_the_subprocess_label_never_touches_a_measured_or_baseline_failed_run(tmp_path):
    q = evidence.quality(_step(tmp_path / "a", _orig(killed=3, survived=1), log=STOP_EARLY))["value"]
    assert q["mutation_state"] == "measured"
    bf = {**_orig(), "baseline_failed": True}
    assert evidence.quality(_step(tmp_path / "b", bf, log=STOP_EARLY))["value"]["mutation_state"] == "baseline_failed"


# --- rerun.one -----------------------------------------------------------------------------------------------------

class Fake:
    def __init__(self, tmp_path: Path, ok: bool = True, boom: Exception | None = None):
        self.a, self.b = tmp_path / "copies" / "a", tmp_path / "copies" / "b"
        (self.a / "src").mkdir(parents=True)
        self.b.mkdir(parents=True)
        self.ok, self.boom, self.calls = ok, boom, []

    def install(self, monkeypatch):
        monkeypatch.setattr(rr, "_prepare", self.prepare)
        monkeypatch.setattr(quality, "_mutation", self.mutation)
        return self

    def prepare(self, p, sha, label, out_dir):
        self.calls.append(("prepare", sha, label, out_dir))
        return hidden.Prepared(self.a, self.b, {"quality": {"ok": self.ok}})

    def mutation(self, p, copy, tg, out_dir, pins, log_dir=None):
        if self.boom:
            raise self.boom
        self.calls.append(("mutation", copy, tg, out_dir, log_dir))
        (log_dir / "mutmut.log").write_text("log")
        return {**_orig(killed=3, survived=1), "nodeid_rewrites": 2}


def _pass_step(tmp_state, arm="ccsdd", step=1, sha="abc123") -> Path:
    d = paths.RESULTS / "pass1" / arm / f"{step:02d}"
    (d / "quality").mkdir(parents=True)
    (d / "git.json").write_text(json.dumps({"sha_after": sha}))
    (d / "quality" / "summary.json").write_text(json.dumps({"mutation": CRASHED}))
    return d


def test_one_writes_beside_the_original_with_provenance_and_never_touches_it(tmp_state, monkeypatch):
    d = _pass_step(tmp_state)
    before = (d / "quality" / "summary.json").read_text()
    f = Fake(tmp_state).install(monkeypatch)
    out = rr.one("pass1", "ccsdd", 1, "O1", today="2026-10-08")
    assert out == d / "quality" / "rerun" / "mutation.json"
    s = json.loads(out.read_text())
    assert s["score"] == 0.75 and s["nodeid_rewrites"] == 2
    assert s["rerun"] == {"reason": "O1", "ruling": rr.REASONS["O1"], "method": "mutmut", "sha": "abc123",
                          "date": "2026-10-08", "harness_error": None}
    assert f.calls[0][1:3] == ("abc123", "01-rerun") and f.calls[1][2] == ["src"]
    assert f.calls[1][4] == d / "quality" / "rerun" and (d / "quality" / "rerun" / "mutmut.log").exists()
    assert (d / "quality" / "summary.json").read_text() == before
    assert not (d / "quality" / "mutmut.log").exists()          # the original log is not written over either


def test_one_refuses_to_overwrite_a_rerun(tmp_state, monkeypatch):
    _pass_step(tmp_state)
    Fake(tmp_state).install(monkeypatch)
    rr.one("pass1", "ccsdd", 1, "O1")
    with pytest.raises(FileExistsError):
        rr.one("pass1", "ccsdd", 1, "O1")


def test_one_records_a_harness_failure_as_crashed_and_still_writes(tmp_state, monkeypatch):
    _pass_step(tmp_state)
    Fake(tmp_state, boom=RuntimeError("docker went away")).install(monkeypatch)
    s = json.loads(rr.one("pass1", "ccsdd", 1, "O3").read_text())
    assert s["crashed"] is True and s["score"] is None and s["rerun"]["harness_error"] == "RuntimeError: docker went away"
    assert set(s) - {"rerun"} == set(quality._mutation_placeholder("n/a"))


def test_one_with_a_failed_install_is_crashed(tmp_state, monkeypatch):
    _pass_step(tmp_state)
    Fake(tmp_state, ok=False).install(monkeypatch)
    s = json.loads(rr.one("pass1", "ccsdd", 1, "O2").read_text())
    assert s["crashed"] is True and s["rerun"]["harness_error"] == "RuntimeError: quality copy install failed"


def test_one_refuses_an_unknown_reason(tmp_state):
    with pytest.raises(ValueError):
        rr.one("pass1", "ccsdd", 1, "O9")


# --- the queue driver ----------------------------------------------------------------------------------------------

def test_the_queue_runs_each_item_in_turn_records_failures_and_flags_unexpected_rewrites(tmp_path):
    from runner.scoring import rerun_queue
    fake_lock = tmp_path / "lock.py"   # stands in for the docker-lock wrapper: argv = uv run python -m mod pass arm step reason
    fake_lock.write_text(
        "import json, sys\n"
        "a = sys.argv[1:]\n"
        "arm, step = a[6], a[7]\n"
        "if step == '3':\n    sys.exit(2)\n"
        "print('noise')\n"
        "print(json.dumps({'out': 'x', 'crashed': False, 'score': 0.5, 'nodeid_rewrites': 2 if arm != 'ok' else 0}))\n")
    log = tmp_path / "scoring" / "mutmut-reruns.log"
    assert rerun_queue.main(["pass1", str(log), str(fake_lock), "ccsdd:2:O1", "ccsdd:3:O1", "speckitty:7:O3",
                             "ok:1:O3"]) == 0
    ev = [json.loads(ln) for ln in log.read_text().splitlines()]
    assert [e["event"] for e in ev] == ["queue-start", "start", "end", "start", "end", "start", "end", "assertion",
                                        "start", "end", "queue-end"]
    ends = [e for e in ev if e["event"] == "end"]
    assert [(e["arm"], e["step"], e["rc"]) for e in ends] == [("ccsdd", 2, 0), ("ccsdd", 3, 2), ("speckitty", 7, 0),
                                                              ("ok", 1, 0)]
    assert ends[0]["result"]["score"] == 0.5 and ends[1]["result"] is None
    assert next(e for e in ev if e["event"] == "assertion")["arm"] == "speckitty"
    assert (tmp_path / "scoring" / "mutmut-rerun-ccsdd-02.out").exists()



# --- fix round 1 (review of 35a8407) -------------------------------------------------------------------------------

def test_a_rerun_never_replaces_an_original_that_is_not_crashed(tmp_path):            # I-1
    bf = {**_orig(), "baseline_failed": True}
    q = evidence.quality(_step(tmp_path / "a", bf, _rerun(killed=6, survived=2)))["value"]
    assert q["mutation_state"] == "baseline_failed" and q["rerun_ignored"] == "the original run is baseline_failed"
    nt = {**_orig(no_tests=5)}                                                          # unmeasured: no coverage
    q = evidence.quality(_step(tmp_path / "b", nt, _rerun(killed=6, survived=2)))["value"]
    assert q["mutation_state"] == "unmeasured" and q["rerun_ignored"] == "the original run is unmeasured"


def test_a_rerun_replaces_an_o4_relabelled_crash(tmp_path):                             # I-1
    q = evidence.quality(_step(tmp_path, CRASHED, _rerun(killed=6, survived=2), log="$ .venv/bin/mutmut run x\n" + STOP_EARLY))["value"]
    assert q["mutation_state"] == "measured" and q["mutation_rerun"]["reason"] == "O1"


def test_one_refuses_a_step_whose_original_is_not_crashed(tmp_state, monkeypatch):    # I-1
    d = _pass_step(tmp_state)
    (d / "quality" / "summary.json").write_text(json.dumps({"mutation": _orig(killed=3, survived=1)}))
    f = Fake(tmp_state).install(monkeypatch)
    with pytest.raises(ValueError, match="measured"):
        rr.one("pass1", "ccsdd", 1, "O1")
    assert f.calls == [] and not (d / "quality" / "rerun").exists()


def test_a_harness_failed_rerun_can_be_retried_and_the_old_record_is_kept(tmp_state, monkeypatch):   # I-2
    d = _pass_step(tmp_state)
    Fake(tmp_state, boom=RuntimeError("docker went away")).install(monkeypatch)
    rr.one("pass1", "ccsdd", 1, "O1")
    Fake(tmp_state / "second").install(monkeypatch)
    s = json.loads(rr.one("pass1", "ccsdd", 1, "O1").read_text())
    assert s["score"] == 0.75 and s["rerun"]["harness_error"] is None
    old = json.loads((d / "quality" / "rerun" / "attempt-1" / "mutation.json").read_text())
    assert old["rerun"]["harness_error"] == "RuntimeError: docker went away"
    with pytest.raises(FileExistsError):                  # a record without a harness error is final
        rr.one("pass1", "ccsdd", 1, "O1")


def test_evidence_says_a_rerun_hit_a_harness_error(tmp_path):                         # I-2
    r = {**_rerun(), **{k: v for k, v in CRASHED.items()}}
    r["rerun"] = {**r["rerun"], "harness_error": "RuntimeError: docker went away"}
    q = evidence.quality(_step(tmp_path, CRASHED, r))["value"]
    assert q["mutation_state"] == "crashed" and q["rerun_ignored"] == "harness error: RuntimeError: docker went away"


def test_an_o3_rerun_whose_baseline_is_killed_again_makes_the_step_unmeasured(tmp_path):   # I-3
    killed = {**_rerun(reason="O3", nodeid_rewrites=None), **{k: v for k, v in CRASHED.items()}, "baseline_rc": 137}
    killed["rerun"] = _rerun(reason="O3")["rerun"]
    orig = {**CRASHED, "baseline_rc": 137, "mutmut_run_rc": None}
    q = evidence.quality(_step(tmp_path / "a", orig, killed))["value"]
    assert q["mutation_state"] == "unmeasured" and q["mutation_why"] == evidence.KILLED_AGAIN
    other = {**killed, "baseline_rc": 1}
    q = evidence.quality(_step(tmp_path / "b", orig, other))["value"]
    assert q["mutation_state"] == "crashed"


def test_o4_needs_mutmut_run_rc_1_a_passing_baseline_and_the_message_after_the_run_line(tmp_path):   # M-3
    run_log = "$ .venv/bin/mutmut run x\n" + STOP_EARLY
    q = evidence.quality(_step(tmp_path / "a", {**CRASHED, "mutmut_run_rc": None}, log=run_log))["value"]
    assert q["mutation_state"] == "crashed"
    q = evidence.quality(_step(tmp_path / "b", {**CRASHED, "baseline_rc": 137}, log=run_log))["value"]
    assert q["mutation_state"] == "crashed"
    q = evidence.quality(_step(tmp_path / "c", CRASHED, log=STOP_EARLY + "$ .venv/bin/mutmut run x\n"))["value"]
    assert q["mutation_state"] == "crashed"


def test_a_rerun_superseded_by_a_measured_remeasure_says_so(tmp_path):                # M-4
    from runner.scoring import remeasure as rm
    d = _step(tmp_path, CRASHED, _rerun(killed=6, survived=2))
    (d / "quality" / "remeasure.json").write_text(json.dumps(rm.summarise({"m1": "killed", "m2": "survived"}, sha="abc")))
    q = evidence.quality(d)["value"]
    assert q["mutation_method"] == "whole-suite-per-mutant" and q["mutation_rerun"] is None
    assert q["rerun_ignored"] == "superseded by remeasure"


def test_one_with_the_real_mutation_writes_its_log_only_in_the_rerun_folder(tmp_state, monkeypatch):   # M-2
    d = _pass_step(tmp_state)
    f = Fake(tmp_state)
    monkeypatch.setattr(rr, "_prepare", f.prepare)
    (f.b / "pyproject.toml").write_text('[project]\nname = "x"\n')
    responses = iter([quality.ToolRun(0, "5 passed\n", "", False),
                      quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False),
                      quality.ToolRun(0, "__run_rc=0\n", "", False),
                      quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)])
    monkeypatch.setattr(quality, "_run", lambda p, copy, cmd, timeout, env=None: next(responses))
    s = json.loads(rr.one("pass1", "ccsdd", 1, "O1").read_text())
    rd = d / "quality" / "rerun"
    assert s["score"] == 1.0 and (rd / "mutmut.log").exists()
    assert not (rd / "quality").exists() and not (d / "quality" / "mutmut.log").exists()


def test_the_queue_logs_an_error_for_a_bad_item_and_carries_on(tmp_path):                       # M-5
    from runner.scoring import rerun_queue
    fake_lock = tmp_path / "lock.py"
    fake_lock.write_text("import json\nprint(json.dumps({'out': 'x', 'score': 1.0, 'nodeid_rewrites': None}))\n")
    log = tmp_path / "q.log"
    assert rerun_queue.main(["pass1", str(log), str(fake_lock), "not-an-item", "ccsdd:2:O1"]) == 0
    ev = [json.loads(ln) for ln in log.read_text().splitlines()]
    assert [e["event"] for e in ev] == ["queue-start", "error", "start", "end", "queue-end"]
    assert ev[1]["item"] == "not-an-item" and "ValueError" in ev[1]["error"]
