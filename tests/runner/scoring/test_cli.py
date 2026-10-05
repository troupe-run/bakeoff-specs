import json
import pytest
from runner import cli, faults, paths
from runner.scoring import aggregate, collect, inputs
from runner.scoring import cli as scli
from tests.runner.scoring.test_aggregate import p  # noqa: F401


def test_score_aggregate_then_report_writes_both_files(p, capsys):
    assert cli.main(["score", p, "--stage", "aggregate"]) == 0
    assert cli.main(["score", p, "--stage", "report"]) == 0
    assert (paths.scoring_out(p) / "report.md").exists() and (paths.scoring_out(p) / "report.html").exists()


def test_an_input_error_exits_1_with_its_message(p, monkeypatch, capsys):
    def boom(*a, **k): raise inputs.InputError("tests every arm failed are not reviewed: t1")
    monkeypatch.setattr(aggregate, "run", boom)
    assert cli.main(["score", p, "--stage", "aggregate"]) == 1
    assert "not reviewed: t1" in capsys.readouterr().out


def test_an_all_fail_guard_leaves_no_scores_file(p, monkeypatch, capsys):
    monkeypatch.setattr(aggregate.evidence, "all_fail", lambda d, arms: {"alpha": ["t1"]})
    assert cli.main(["score", p, "--stage", "aggregate"]) == 1
    assert "not reviewed in scoring/excluded-tests.toml: t1" in capsys.readouterr().out
    assert not (paths.scoring_out(p) / "scores.json").exists()


def test_report_without_scores_refuses_and_writes_nothing(p, capsys):
    assert cli.main(["score", p, "--stage", "report"]) == 1
    assert "scores.json is missing" in capsys.readouterr().out
    assert not (paths.scoring_out(p) / "report.md").exists() and not (paths.scoring_out(p) / "report.html").exists()


def test_confidence_stage_writes_confidence_json(p):
    assert cli.main(["score", p, "--stage", "aggregate"]) == 0
    assert cli.main(["score", p, "--stage", "confidence"]) == 0
    assert isinstance(json.loads((paths.scoring_out(p) / "confidence.json").read_text()), dict)


def test_default_runs_all_four_stages_in_order(p, monkeypatch):
    calls = []
    for name in ("collect", "aggregate", "confidence", "report"):
        real = scli.STAGES[name]
        monkeypatch.setitem(scli.STAGES, name, lambda ns, n=name, r=real: (calls.append(n), r(ns)))
    monkeypatch.setattr(collect, "run", lambda pass_, docker=True: [])
    assert cli.main(["score", p, "--no-docker"]) == 0
    assert calls == ["collect", "aggregate", "confidence", "report"]
    out = paths.scoring_out(p)
    assert all((out / f).exists() for f in ("scores.json", "confidence.json", "report.md", "report.html"))


def test_no_docker_reaches_collect_as_docker_false(p, monkeypatch):
    seen = []
    monkeypatch.setattr(collect, "run", lambda pass_, docker=True: seen.append(docker) or [])
    assert cli.main(["score", p, "--stage", "collect", "--no-docker"]) == 0
    assert seen == [False]


def test_score_runs_on_a_halted_pass_and_flags_it(p):
    faults.halt(p, "suite-resource:1 test", {"x": 1})
    assert faults.halted(p)
    assert cli.main(["score", p, "--stage", "aggregate"]) == 0
    flags = json.loads((paths.scoring_out(p) / "scores.json").read_text())["flags"]
    assert any(f.startswith(f"pass {p} is HALTED: suite-resource:1") for f in flags)


def test_an_unhalted_pass_has_no_halted_flag(p):
    assert cli.main(["score", p, "--stage", "aggregate"]) == 0
    assert not any("HALTED" in f for f in json.loads((paths.scoring_out(p) / "scores.json").read_text())["flags"])


@pytest.mark.parametrize("name", ["../evil", "bad name", ""])
def test_a_bad_pass_name_exits_1_and_creates_nothing(tmp_state, capsys, name):
    before = sorted(paths.RESULTS.parent.rglob("*")) if paths.RESULTS.parent.exists() else []
    assert cli.main(["score", name, "--stage", "report"]) == 1
    assert "pass name" in capsys.readouterr().out
    after = sorted(paths.RESULTS.parent.rglob("*")) if paths.RESULTS.parent.exists() else []
    assert before == after


def test_a_missing_pass_directory_exits_1_and_creates_nothing(tmp_state, capsys):
    assert cli.main(["score", "nope", "--stage", "aggregate"]) == 1
    assert "no such pass" in capsys.readouterr().out
    assert not (paths.RESULTS / "nope").exists()


def test_report_stage_refreshes_confidence_json(p):
    assert cli.main(["score", p, "--stage", "aggregate"]) == 0
    assert cli.main(["score", p, "--stage", "report"]) == 0
    assert (paths.scoring_out(p) / "confidence.json").exists()


def test_an_unknown_stage_is_rejected_by_argparse(p):
    with pytest.raises(SystemExit) as e:
        cli.main(["score", p, "--stage", "nonsense"])
    assert e.value.code == 2


def test_a_stage_added_to_stages_appears_in_the_choices(monkeypatch):
    monkeypatch.setitem(scli.STAGES, "extra-stage", lambda ns: None)
    assert cli.main(["score", "x", "--stage", "extra-stage"]) == 1     # parsed (no SystemExit), then pass missing
