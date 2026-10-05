import json
import pytest
from runner import gitops, paths
from runner.paths import Paths
from runner.scoring import anonymise as an

pytestmark = pytest.mark.docker


def test_diff_text_returns_the_unified_diff_between_two_shas():
    d = paths.RESULTS / "dry1" / "dryrun" / "03"
    if not (d / "git.json").exists():
        pytest.skip(f"{d / 'git.json'} absent (results/dry1 snapshot not present)")
    g = json.loads((d / "git.json").read_text())
    text = gitops.diff_text(Paths("dry1", "dryrun"), g["sha_before"], g["sha_after"])
    assert text.startswith("diff --git ") and "src/troupe_ref/step.py" in text


def test_dry1_anonymised_hides_the_arm_name_and_the_key_maps_one_label_to_it():
    if not (paths.RESULTS / "dry1" / "dryrun" / "03" / "git.json").exists():
        pytest.skip("results/dry1 snapshot not present")
    anon = an.run("dry1")
    hits = [f for f in anon.rglob("*") if f.is_file() and "dryrun" in f.read_text(errors="replace").lower()]
    assert hits == []
    key = an.read_key("dry1")
    assert list(key.values()).count("dryrun") == 1
