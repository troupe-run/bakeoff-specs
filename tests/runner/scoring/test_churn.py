from runner import docker, gitops
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


def test_renames_with_an_empty_side_give_the_new_path():
    assert churn.normalise("{ => sub}/x.py") == "sub/x.py"
    assert churn.normalise("x/{a => }/y") == "x/y"
    assert churn.normalise("{a => }/y") == "y"


GIT = {"value": {"sha_before": "aaa", "sha_after": "bbb"}, "source": "git.json"}


def test_for_step_without_a_stale_list_is_missing():
    assert "missing" in churn.for_step("p", "a", GIT, None)


def test_for_step_passes_a_missing_git_json_through():
    m = {"missing": "git.json", "why": "no such file"}
    assert churn.for_step("p", "a", m, STALE) == m


def test_for_step_with_no_sha_after_is_missing():
    g = {"value": {"sha_before": "aaa", "sha_after": None}, "source": "git.json"}
    assert churn.for_step("p", "a", g, STALE)["why"] == "no sha_before/sha_after"


def test_for_step_container_and_git_failures_are_missing(monkeypatch):
    for exc in (docker.ContainerError("boom"), gitops.GitError("bad"), ValueError("malformed")):
        def fail(*a, _e=exc):
            raise _e
        monkeypatch.setattr(churn.gitops, "numstat", fail)
        out = churn.for_step("p", "a", GIT, STALE)
        assert out["missing"] == "git.json" and "numstat failed" in out["why"]
