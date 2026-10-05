import json
import shutil
from pathlib import Path
import pytest
from runner import paths
from runner.scoring import collect

MINI = Path(__file__).parent / "fixtures" / "mini"


@pytest.fixture
def mini_pass(tmp_state):
    shutil.copytree(MINI, paths.RESULTS / "mini")
    return "mini"


def test_arms_are_step_holding_directories(mini_pass):
    assert collect.arms(paths.RESULTS / mini_pass) == ["alpha", "control"]


def test_collect_writes_one_record_per_arm_step(mini_pass):
    out = collect.run(mini_pass, docker=False)
    assert sorted(p.relative_to(paths.scoring_out(mini_pass)).as_posix() for p in out) == [
        "collected/alpha/01.json", "collected/alpha/02.json", "collected/control/01.json",
        "collected/control/02.json"]


def test_collect_is_byte_identical_on_a_rerun(mini_pass):
    a = [p.read_bytes() for p in collect.run(mini_pass, docker=False)]
    b = [p.read_bytes() for p in collect.run(mini_pass, docker=False)]
    assert a == b


def test_a_step_without_hidden_results_is_missing_not_zero(mini_pass):
    collect.run(mini_pass, docker=False)
    rec = json.loads((paths.scoring_out(mini_pass) / "collected" / "control" / "02.json").read_text())
    assert "missing" in rec["hidden"] and "value" not in rec["hidden"]


def test_without_docker_churn_is_deferred(mini_pass):
    collect.run(mini_pass, docker=False)
    rec = json.loads((paths.scoring_out(mini_pass) / "collected" / "alpha" / "02.json").read_text())
    assert rec["churn"]["why"].startswith("deferred")
