import json

import pytest
from runner import paths
from runner.scoring import anonymise, size


def _w(root, rel, text):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


@pytest.fixture
def tree(tmp_path):
    r = tmp_path / "repo"
    _w(r, "src/pkg/a.py", "import os\n\n\nx = 1\n   \n\ty = 2\n")       # 3 non-blank (whitespace-only is blank)
    _w(r, "src/pkg/b.py", "z = 3\n")                                    # 1
    _w(r, "src/pkg/notes.txt", "not python\n")
    _w(r, "tests/test_a.py", "def test_x():\n    assert True\n\n")       # 2
    _w(r, "tests/conftest.py", "")                                      # 0
    for junk in (".venv/lib/site.py", "venv/x.py", "src/pkg/__pycache__/a.py", ".mypy_cache/m.py",
                 ".ruff_cache/r.py", ".pytest_cache/p.py", ".git/hooks/h.py", "build/lib/a.py", "dist/d.py",
                 "src/pkg.egg-info/e.py", "node_modules/n.py"):
        _w(r, junk, "a = 1\nb = 2\n")
    _w(r, ".claude/hooks/hook.py", "h = 1\n")                         # hidden: ruff checks it, mypy's walk does not
    return r


def test_measure_tree_counts_non_blank_lines_and_excludes_venvs_caches_git_and_build(tree):
    m = size.measure_tree(tree, ["src"])
    assert m["type_lines"] == 4 and m["type_files"] == 2                 # mypy's target: src only
    assert m["lint_lines"] == 4 + 2 + 1 and m["lint_files"] == 5         # ruff: src + tests + the hidden hook
    assert m["targets"] == ["src"]


def test_measure_tree_with_a_dot_target_still_follows_mypy_rules_for_types(tree):
    m = size.measure_tree(tree, ["."])
    assert m["type_lines"] == 4 + 2 and m["lint_lines"] == 7             # mypy skips the hidden directory


def test_measure_tree_never_follows_a_link(tree, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("a = 1\n" * 50)
    (tree / "src" / "pkg" / "link.py").symlink_to(outside)
    (tree / "src" / "linkdir").symlink_to(tmp_path)
    assert size.measure_tree(tree, ["src"])["type_lines"] == 4


def test_measure_tree_missing_target_is_zero_lines(tmp_path):
    assert size.measure_tree(tmp_path, ["src"]) == {"lint_lines": 0, "lint_files": 0, "type_lines": 0,
                                                    "type_files": 0, "targets": ["src"]}


def test_parse_container_reads_the_last_json_line_and_refuses_a_failed_run():
    out = 'noise\n{"lint_lines": 10, "type_lines": 4, "lint_files": 2, "type_files": 1, "targets": ["src"]}\n'
    assert size.parse_container(0, out)["lint_lines"] == 10
    assert size.parse_container(3, out) is None                          # nonzero rc: a crash, never 0 lines
    assert size.parse_container(None, out) is None
    assert size.parse_container(0, "") is None
    assert size.parse_container(0, '{"lint_lines": 10}\n') is None
    assert size.parse_container(0, '{"lint_lines": true, "type_lines": 1}\n') is None


def test_record_keeps_a_failure_as_none_lines_with_why():
    r = size.record(None, how="h", source="quality", error="timed out")
    assert r["lint_lines"] is None and r["type_lines"] is None and r["error"] == "timed out"
    ok = size.record({"lint_lines": 3, "type_lines": 2}, how="h", source="quality", error="ignored")
    assert ok == {"lint_lines": 3, "type_lines": 2, "how": "h", "source": "quality"}


def test_container_cmd_uses_the_harness_interpreter_isolated():
    cmd = size.container_cmd(["src"])
    assert cmd[:3] == ["/opt/harness/bin/python", "-I", "-c"] and cmd[-1] == "src"
    assert set(json.loads(cmd[4])) == size.EXCLUDED_DIRS


# --- pass-1 backfill from the anonymised copies -------------------------------------------------------------------

def _pass(tmp_state, *, key_in_state: bool):
    pass_ = "p"
    for arm, label in (("alpha", "Arm A"), ("control", "Arm B")):
        q = paths.RESULTS / pass_ / arm / "01" / "quality"
        q.mkdir(parents=True)
        (q / "summary.json").write_text(json.dumps({"targets": ["src"]}))
        repo = paths.scoring_out(pass_) / "anon" / label / "01" / "repo"
        _w(repo, "src/m.py", "a = 1\n" * (3 if arm == "alpha" else 5))
        _w(repo, "tests/test_m.py", "b = 2\n")
    key = (paths.STATE / f"{pass_}-scoring" if key_in_state else paths.scoring_out(pass_)) / anonymise.KEY
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps({"salt": "s", "labels": {"Arm A": "alpha", "Arm B": "control"}}))
    return pass_


@pytest.mark.parametrize("key_in_state", [False, True])
def test_backfill_measures_each_arm_from_its_own_anonymised_tree(tmp_state, key_in_state):
    pass_ = _pass(tmp_state, key_in_state=key_in_state)
    written = size.backfill(pass_)
    assert len(written) == 2
    a = json.loads((paths.RESULTS / pass_ / "alpha" / "01" / "quality" / "size.json").read_text())
    c = json.loads((paths.RESULTS / pass_ / "control" / "01" / "quality" / "size.json").read_text())
    assert (a["type_lines"], a["lint_lines"], c["type_lines"], c["lint_lines"]) == (3, 4, 5, 6)
    assert a["source"] == "anon-backfill"
    assert "Arm" not in json.dumps(a)                                    # never writes the label next to the arm
    assert not (paths.scoring_out(pass_) / anonymise.KEY).exists() or not key_in_state   # never copied back


def test_backfill_never_overwrites_a_size_the_quality_stage_measured(tmp_state):
    pass_ = _pass(tmp_state, key_in_state=True)
    f = paths.RESULTS / pass_ / "alpha" / "01" / "quality" / "size.json"
    f.write_text(json.dumps({"lint_lines": 99, "type_lines": 9, "source": "quality"}))
    size.backfill(pass_)
    assert json.loads(f.read_text())["lint_lines"] == 99


def test_backfill_without_an_anonymised_tree_records_why_not_zero(tmp_state):
    pass_ = _pass(tmp_state, key_in_state=True)
    import shutil
    shutil.rmtree(paths.scoring_out(pass_) / "anon" / "Arm A")
    size.backfill(pass_)
    a = json.loads((paths.RESULTS / pass_ / "alpha" / "01" / "quality" / "size.json").read_text())
    assert a["lint_lines"] is None and "no anonymised tree" in a["error"]


def test_anon_key_is_read_from_state_when_moved_out_of_results(tmp_state):
    from runner.scoring import judge
    pass_ = _pass(tmp_state, key_in_state=True)
    assert anonymise.key_path(pass_) == paths.STATE / f"{pass_}-scoring" / anonymise.KEY
    assert judge.anon_key(pass_) == {"Arm A": "alpha", "Arm B": "control"}
    assert len(judge.key_digest(pass_)) == 64


def test_anon_key_under_results_wins_when_both_exist(tmp_state):
    pass_ = _pass(tmp_state, key_in_state=True)
    here = paths.scoring_out(pass_) / anonymise.KEY
    here.write_text(json.dumps({"salt": "t", "labels": {"Arm A": "control", "Arm B": "alpha"}}))
    assert anonymise.key_path(pass_) == here
