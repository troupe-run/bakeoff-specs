import json
from runner.scoring import evidence, inputs


def _summary(d, step, tests):
    (d / f"{step:02d}" / "hidden").mkdir(parents=True)
    (d / f"{step:02d}" / "hidden" / "summary.json").write_text(json.dumps(
        {"step": step, "tests": tests, "scoreable": True, "passed": 0, "total": len(tests)}))


def test_only_tests_every_arm_failed_are_listed(tmp_path):
    _summary(tmp_path / "a", 4, {"t1": "failed", "t2": "failed", "t3": "passed"})
    _summary(tmp_path / "b", 4, {"t1": "failed", "t2": "passed", "t3": "passed"})
    assert evidence.all_fail(tmp_path, ["a", "b"]) == {4: ["t1"]}


def test_an_arm_without_a_summary_does_not_veto_or_join(tmp_path):
    _summary(tmp_path / "a", 4, {"t1": "failed"})
    (tmp_path / "b" / "04").mkdir(parents=True)
    out = evidence.all_fail(tmp_path, ["a", "b"])
    assert out == {4: ["t1"]}


def test_missing_summary_is_missing_not_empty(tmp_path):
    (tmp_path / "04").mkdir()
    assert evidence.hidden_summary(tmp_path / "04")["why"]


def test_exclusions_split_defects_from_hard(tmp_path):
    p = tmp_path / "x.toml"
    p.write_text('[[test]]\nid = "t1"\nverdict = "defect"\nreason = "contract silent"\ndecided = "owner 2026-10-06"\n'
                 '[[test]]\nid = "t2"\nverdict = "hard"\nreason = "contract explicit"\ndecided = "owner 2026-10-06"\n')
    x = inputs.load_excluded(p)
    assert x.defects == {"t1"} and x.reviewed == {"t1", "t2"}
