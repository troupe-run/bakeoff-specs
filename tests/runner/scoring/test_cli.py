import json
from runner import cli, paths
from runner.scoring import aggregate, collect, inputs
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


def test_default_runs_collect_aggregate_confidence_report_in_order(p, monkeypatch):
    calls = []
    monkeypatch.setattr(collect, "run", lambda pass_, docker=True: calls.append(("collect", docker)) or [])
    real = aggregate.run
    monkeypatch.setattr(aggregate, "run", lambda *a, **k: calls.append(("aggregate",)) or real(*a, **k))
    assert cli.main(["score", p, "--no-docker"]) == 0
    assert calls == [("collect", False), ("aggregate",)]
    out = paths.scoring_out(p)
    assert all((out / f).exists() for f in ("scores.json", "confidence.json", "report.md", "report.html"))


def test_score_on_a_pass_without_a_ledger_is_not_halted(p):
    assert cli.main(["score", p, "--stage", "aggregate"]) == 0
