import pytest
from runner import paths
from runner.scoring import churn, evidence, inputs

pytestmark = pytest.mark.docker


def test_real_step_has_nonzero_total_lines():
    d = paths.RESULTS / "dry1" / "dryrun" / "03"
    out = churn.for_step("dry1", "dryrun", evidence.read_json(d / "git.json"), inputs.load_stale(3))
    assert out["value"]["total_lines"] > 0
