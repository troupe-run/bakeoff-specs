import shutil

import pytest

# runner/hidden.py is Task 18's file (round 4 as of this writing) and is not merged into this lane. Skip this
# whole module cleanly (not a collection error) until it lands, rather than hard-failing `pytest tests/runner
# -q` for every other task's tests too. Once merged, this import succeeds and these tests run exactly as
# specified (still gated by the `docker` marker/--run-docker below).
pytest.importorskip("runner.hidden", reason="runner/hidden.py (Task 18) not yet present in this lane")

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
