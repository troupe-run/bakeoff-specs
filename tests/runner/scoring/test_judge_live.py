# tests/runner/scoring/test_judge_live.py
"""Plan 3 Task 17, step 5: ONE real judge call (spends a little quota; needs Docker, the base image, the keychain
credential, and `dry1` anonymised first: `anonymise.run("dry1")`). Run only after pass 1, with
`--run-live --run-docker`."""
import pytest
from runner import paths
from runner.scoring import inputs, judge

pytestmark = [pytest.mark.live, pytest.mark.docker]


def test_one_container_judge_call_on_dry1_step_1_returns_a_parseable_verdict_and_a_clean_pin_report():
    key = judge.anon_key("dry1")                         # InputError if dry1 is not anonymised yet
    arm = sorted(key.values())[0]
    d, files = judge.inputs_for("dry1", "req_test_code", arm, "01")
    assert not judge.absent(d, files), f"dry1 step 1 inputs are missing: {judge.absent(d, files)}"
    r = inputs.load_rubrics()["req_test_code"]
    j = judge.ContainerJudge("dry1")
    v = judge.parse(j.ask(judge.prompt(r, r.lenses[0], "01", files), d, files))
    assert v.status == "ok" and 0 <= v.score <= 4 and v.evidence
    assert j.last_pin is not None and j.last_pin.ok and not j.last_pin.violations
    assert j.last_dir.is_relative_to(paths.scoring_out("dry1") / "judge-calls")
