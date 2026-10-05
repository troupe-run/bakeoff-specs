import pytest
from runner.scoring import inputs


def test_shipped_weights_match_the_spec():
    w = inputs.load_weights()
    assert w.dimensions == {"coping": 20, "correctness": 20, "traceability": 10, "interaction": 10,
                            "code_quality": 15, "decision_quality": 10, "setup": 10, "time": 5}
    assert w.parts["coping"] == {"regressions": 7, "stale_updated": 7, "churn": 3, "hand_edit": 3}
    assert w.parts["decision_quality"] == {"choice": 6, "process": 4}
    assert w.parts["setup"] == {"setup_effort": 4, "fit": 4, "violations": 2}


def test_part_share_is_fraction_of_its_dimension():
    w = inputs.load_weights()
    assert w.part_share("coping", "regressions") == pytest.approx(7 / 20)


def test_weights_not_summing_to_100_are_refused(tmp_path):
    p = tmp_path / "w.toml"
    p.write_text('[dimensions]\ncoping = 50\n[parts.coping]\nregressions = 50\n')
    with pytest.raises(inputs.InputError, match="sum to 100"):
        inputs.load_weights(p)


def test_parts_not_summing_to_their_dimension_are_refused(tmp_path):
    p = tmp_path / "w.toml"
    p.write_text('[dimensions]\ncoping = 100\n[parts.coping]\nregressions = 7\nchurn = 3\n')
    with pytest.raises(inputs.InputError, match="coping"):
        inputs.load_weights(p)
