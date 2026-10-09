"""Final review I2: the leak check over a written anon/ tree (contents and paths, repo/ and diff.patch included)."""
import pytest
from runner import cli, paths
from runner.scoring import anonymise as an, leakcheck
from tests.runner.scoring.test_anonymise import world  # noqa: F401  (fixture re-export)


def test_the_mini_fixture_run_has_no_leak_anywhere_under_anon_repo_and_diff_included(world):
    anon = an.run("p1")
    assert any((anon / lab / "01" / "repo").is_dir() for lab in ("Arm A", "Arm B"))
    assert leakcheck.check(anon, ["speckit", "control"]) == []


def test_a_name_left_in_a_repo_file_a_diff_or_a_path_is_reported(world):
    anon = an.run("p1")
    step = anon / "Arm A" / "01"
    (step / "repo" / "src" / "b.py").write_text("# made with OpenSpec\n")
    (step / "diff.patch").write_text("+ see kitty-specs/ for details\n")
    (step / "repo" / "kiro-notes.md").write_text("plain text\n")
    (step / "repo" / "esc.json").write_text('{"x": "\\nbd ready"}')
    got = leakcheck.check(anon, ["speckit", "control"])
    assert ("Arm A/01/repo/src/b.py", "openspec") in got
    assert ("Arm A/01/diff.patch", "kitty-specs") in got
    assert ("Arm A/01/repo/kiro-notes.md", "kiro") in got
    assert ("Arm A/01/repo/esc.json", "bd") in got


def test_short_words_count_only_at_word_boundaries():
    assert not leakcheck.hits("embedding", "bd") and leakcheck.hits("run bd ready", "bd")
    assert leakcheck.hits("\\nbd ready", "bd") and not leakcheck.hits("kiroshi", "kiro")


def test_the_leak_check_stage_exits_non_zero_and_names_the_hits(world, capsys):
    an.run("p1")
    assert cli.main(["score", "p1", "--stage", "leak-check"]) == 0
    assert "no leaks" in capsys.readouterr().out
    (paths.scoring_out("p1") / "anon" / "Arm B" / "01" / "repo" / "x.md").write_text("superpowers\n")
    assert cli.main(["score", "p1", "--stage", "leak-check"]) == 1
    out = capsys.readouterr().out
    assert "Arm B/01/repo/x.md: superpowers" in out


def test_the_leak_check_stage_refuses_without_an_anon_tree(world, capsys):
    assert cli.main(["score", "p1", "--stage", "leak-check"]) == 1
    assert "run the anonymise stage first" in capsys.readouterr().out


LABELS = [f"Arm {x}" for x in "ABCDEF"]


@pytest.mark.parametrize("text", [
    "Outcome: kept; A pins ruamel and checks spans",          # the 2026-10-09 sheet's own forms
    "Outcome: C fixed chained includes in step 5; kept",
    "10 s (C and F: a total deadline over DNS, connect and read)",
    "Rendered from the resolved value (D also copies an aliased include's content)",
    "per-event ids (C pre-lineage-<seq>; D change null)",
    "Arm B took it", "Arms C and E", "(A: _Planner._add; B: apply._apply)"])
def test_an_arm_letter_used_as_an_arms_name_is_found(text):
    assert leakcheck.label_refs(text, LABELS)


@pytest.mark.parametrize("text", [
    "A PyYAML loader subclass recording *name tokens", "A corrupted row should give exit 4",
    "(A) Nearest including file", "option (B) wins", "Option B was rejected", "E2E tests", "exit 2; a/b/c",
    "the A-side of the diff", "U+2028 and LS", "Gives G and H"])          # G, H: not a label in this pass
def test_ordinary_text_is_not_an_arm_reference(text):
    assert leakcheck.label_refs(text, LABELS) == []


def test_check_text_reports_arm_words_and_labels_together(monkeypatch):
    monkeypatch.setattr(leakcheck, "words", lambda arms: ["speckit"])
    got = leakcheck.check_text("uses speckit; C fixed it", ["speckit"], LABELS)
    assert got[0] == "arm word 'speckit'" and got[1].startswith("arm label: …") and "C fixed" in got[1]
