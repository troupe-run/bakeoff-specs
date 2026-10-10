import shutil

import pytest

from runner import hidden, quality
from runner.paths import Paths, REPO_ROOT

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    p = Paths("dryquality", "dryrun")
    base = tmp_path_factory.mktemp("q")
    a, b = base / "a" / "bakeoff-specs-dryrun", base / "b" / "bakeoff-specs-dryrun"
    for d in (a, b):
        shutil.copytree(REPO_ROOT / "reference", d, ignore=shutil.ignore_patterns(".venv", "__pycache__"))
    return p, hidden.prepare_copy(p, a, base, "ref", quality_copy=b)


def test_quality_numbers_are_measured_on_the_reference(prepared, tmp_path):
    p, prep = prepared
    s = quality.run_all(p, prep, tmp_path)
    assert s["mutation"]["total"] > 0 and s["mypy_errors"] >= 0 and s["targets"] == ["src"]
    assert not (prep.hidden_copy / ".venv" / "bin" / "mutmut").exists()        # review C-1: copy A untouched


def test_mutmut_can_list_mutants_without_running_them(prepared, tmp_path):    # the OD15 B precondition
    p, prep = prepared
    names = quality.list_mutants(p, prep.quality_copy, ["src"])
    assert len(names) > 0


def test_size_in_the_container_matches_the_host_walk_of_the_same_copy(prepared):
    """The quality stage's tool-listed file counts (ruff --show-files, mypy's sources) agree with the host walk the
    pass-1 backfill uses, on the same tree."""
    from runner.scoring import size
    p, prep = prepared
    r = quality._run(p, prep.hidden_copy, size.container_cmd(["src"]), 300)
    got = size.parse_container(r.rc, r.stdout)
    assert got is not None, r.combined
    want = size.measure_tree(prep.hidden_copy, ["src"])
    assert (got["lint_lines"], got["type_lines"]) == (want["lint_lines"], want["type_lines"])
    assert 0 < got["type_lines"] < got["lint_lines"]
