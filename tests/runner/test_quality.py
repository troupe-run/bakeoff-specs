import json

from runner import quality


def test_mypy_tail_is_parsed():
    assert quality.mypy_errors("x\nFound 12 errors in 3 files (checked 9 source files)\n") == 12
    assert quality.mypy_errors("Success: no issues found in 9 source files\n") == 0


def test_targets_prefer_src_then_entry_point_package(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project.scripts]\ntroupe = "troupe_cfg.cli:main"\n')
    (tmp_path / "troupe_cfg").mkdir()
    assert quality.targets(tmp_path) == ["troupe_cfg"]
    (tmp_path / "src").mkdir()
    assert quality.targets(tmp_path) == ["src"]


def test_mutation_score_excludes_untested_and_skipped():
    s = quality.mutation_summary({"killed": 60, "survived": 20, "timeout": 5, "suspicious": 0, "no_tests": 10,
                                  "skipped": 5, "total": 100}, partial=False, baseline_failed=False)
    assert s["score"] == 60 / 85


def test_ruff_findings_count_is_the_json_array_length():
    assert quality.ruff_count('[{"code": "F401"}, {"code": "E501"}]') == 2


def test_mutmut_results_are_parsed_into_counts():
    text = "    troupe.cli.x__mutmut_1: killed\n    troupe.cli.x__mutmut_2: survived\n    troupe.cli.y__mutmut_1: no tests\n"
    names, counts = quality.parse_results(text)
    assert names == ["troupe.cli.x__mutmut_1", "troupe.cli.x__mutmut_2", "troupe.cli.y__mutmut_1"]
    assert counts == {"killed": 1, "survived": 1, "timeout": 0, "suspicious": 0, "no_tests": 1, "skipped": 0,
                      "not_checked": 0, "total": 3}


def test_the_sample_is_deterministic_and_does_not_depend_on_order():         # OD15 B
    names = [f"m.f__mutmut_{i}" for i in range(500)]
    a = quality.sample(names, 200); b = quality.sample(list(reversed(names)), 200)
    assert a == b and len(a) == 200


def test_mutmut_table_replaces_any_arm_setting(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n\n[tool.mutmut]\npaths_to_mutate = ["other"]\nfoo = 1\n\n[tool.ruff]\nx = 1\n')
    quality.set_mutmut_paths(tmp_path, ["src"])
    t = (tmp_path / "pyproject.toml").read_text()
    assert 'paths_to_mutate = ["src"]' in t and "other" not in t and "foo" not in t and "[tool.ruff]" in t


# --- additional tests: controller ruling — tool failures are recorded as such, never a silent 0/100 -----------

def test_zero_mutation_summary_is_a_single_shared_constant():
    """m10 (preflight): the zero-summary dict literal must not be repeated 3x in quality.py — one constant."""
    assert quality.ZERO_MUTATION == {"killed": 0, "survived": 0, "timeout": 0, "suspicious": 0,
                                     "no_tests": 0, "skipped": 0, "total": 0}
    # mutation_summary must not mutate the shared constant when it merges extra keys in
    quality.mutation_summary(dict(quality.ZERO_MUTATION), partial=False, baseline_failed=True)
    assert quality.ZERO_MUTATION == {"killed": 0, "survived": 0, "timeout": 0, "suspicious": 0,
                                     "no_tests": 0, "skipped": 0, "total": 0}


def test_a_score_of_none_is_distinct_from_a_score_of_zero():
    """total == 0 (nothing measured) must never present as score 0 — that would look like every mutant survived."""
    s = quality.mutation_summary(dict(quality.ZERO_MUTATION), partial=False, baseline_failed=True)
    assert s["score"] is None


def test_mypy_exit_0_and_1_are_real_results_but_2_is_a_tool_crash():
    assert quality.mypy_ok(0) is True
    assert quality.mypy_ok(1) is True
    assert quality.mypy_ok(2) is False


def test_ruff_parse_flags_a_crash_when_output_is_not_the_expected_json():
    findings, crashed = quality.ruff_parse(0, '[{"code": "F401"}]')
    assert findings == 1 and crashed is False
    findings, crashed = quality.ruff_parse(2, "ruff: error: invalid configuration\n")
    assert findings is None and crashed is True
    findings, crashed = quality.ruff_parse(0, "not json at all")
    assert findings is None and crashed is True


def test_tool_versions_are_read_from_the_pinned_tester_requirements():
    """Reproducibility (controller ruling): the pinned tool versions the tester image installs must be
    recorded, sourced from the pins the image build itself uses — not re-derived or guessed."""
    v = quality.tool_versions()
    assert v["mypy"] and v["ruff"] and v["mutmut"]
    for value in v.values():
        assert value[0].isdigit()


def test_mutation_summary_json_round_trips(tmp_path):
    s = quality.mutation_summary({"killed": 1, "survived": 0, "timeout": 0, "suspicious": 0, "no_tests": 0,
                                  "skipped": 0, "total": 1}, partial=False, baseline_failed=False,
                                 sampled=False, sample_size=0, sampling="all")
    (tmp_path / "mutation.json").write_text(json.dumps(s, indent=2))
    assert json.loads((tmp_path / "mutation.json").read_text())["score"] == 1.0
