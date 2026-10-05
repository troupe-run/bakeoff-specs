from runner.config import SpecPath
from runner.scoring import churn, inputs

STALE = inputs.StaleList(step=3, stale=[], legitimate=["src/**", "tests/**", "README.md"])


def test_lines_outside_legitimate_and_spec_paths_are_collateral():
    rows = [(10, 2, "src/a.py"), (5, 5, "docs/unrelated.md"), (3, 0, "specs/003/spec.md")]
    out = churn.collateral(rows, STALE, [SpecPath("specs/", "w")])
    assert out == {"lines": 10, "files": ["docs/unrelated.md"], "total_lines": 25}


def test_renames_are_judged_by_their_new_path():
    assert churn.normalise("old.py => src/new.py") == "src/new.py"
    assert churn.normalise("src/{old => new}/x.py") == "src/new/x.py"
    assert churn.collateral([(1, 1, "docs/{a => b}.md")], STALE, [])["files"] == ["docs/b.md"]


def test_spec_path_patterns_without_a_slash_are_fnmatch():
    out = churn.collateral([(4, 0, "openspec/changes/x/proposal.md")], STALE, [SpecPath("openspec/*", "w")])
    assert out["lines"] == 0
