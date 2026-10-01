import dataclasses
import json
import os
import signal
import stat
import types

import pytest

from runner import config, quality
from runner.paths import Paths


def _pins(**limits_overrides):
    pins = config.load_pins()
    return dataclasses.replace(pins, limits=dataclasses.replace(pins.limits, **limits_overrides))


def _fake_run(responses):
    """responses: a list of quality.ToolRun to return in sequence, one per quality._run call."""
    it = iter(responses)
    def fake(p, copy, cmd, timeout, env=None):
        return next(it)
    return fake


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
    text = ("    troupe.cli.x__mutmut_1: killed\n    troupe.cli.x__mutmut_2: survived\n"
            "    troupe.cli.y__mutmut_1: no tests\n    troupe.cli.z__mutmut_1: caught by type check\n"
            "    troupe.cli.z__mutmut_2: check was interrupted by user\n    troupe.cli.z__mutmut_3: segfault\n")
    names, counts = quality.parse_results(text)
    assert names == ["troupe.cli.x__mutmut_1", "troupe.cli.x__mutmut_2", "troupe.cli.y__mutmut_1",
                     "troupe.cli.z__mutmut_1", "troupe.cli.z__mutmut_2", "troupe.cli.z__mutmut_3"]
    assert counts == {"killed": 1, "survived": 1, "timeout": 0, "suspicious": 0, "no_tests": 1, "skipped": 0,
                      "not_checked": 0, "caught_by_type_check": 1, "check_interrupted": 1, "segfault": 1,
                      "total": 6}


def test_an_unrecognised_status_is_recorded_as_not_checked_not_silently_dropped():
    names, counts = quality.parse_results("m.f__mutmut_1: something mutmut has never called this before\n")
    assert names == ["m.f__mutmut_1"] and counts["not_checked"] == 1 and counts["total"] == 1


def test_the_sample_is_deterministic_and_does_not_depend_on_order():         # OD15 B
    names = [f"m.f__mutmut_{i}" for i in range(500)]
    a = quality.sample(names, 200); b = quality.sample(list(reversed(names)), 200)
    assert a == b and len(a) == 200


def test_mutmut_table_replaces_any_arm_setting(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n\n[tool.mutmut]\npaths_to_mutate = ["other"]\nfoo = 1\n\n[tool.ruff]\nx = 1\n')
    quality.set_mutmut_paths(tmp_path, ["src"])
    t = (tmp_path / "pyproject.toml").read_text()
    assert 'paths_to_mutate = ["src"]' in t and "other" not in t and "foo" not in t and "[tool.ruff]" in t


def test_mutmut_table_replacement_handles_crlf_and_dotted_subtables(tmp_path):
    (tmp_path / "pyproject.toml").write_bytes(
        b'[project]\r\nname = "x"\r\n\r\n[tool.mutmut]  # arm comment\r\npaths_to_mutate = ["other"]\r\n'
        b'\r\n[tool.mutmut.ci]\r\nnope = true\r\n\r\n[tool.ruff]\r\nx = 1\r\n')
    quality.set_mutmut_paths(tmp_path, ["src"])
    t = (tmp_path / "pyproject.toml").read_text()
    assert 'paths_to_mutate = ["src"]' in t and "other" not in t and "nope" not in t and "[tool.ruff]" in t


def test_mutmut_as_an_inline_table_is_refused_not_guessed(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool]\nmutmut = { paths_to_mutate = ["other"] }\n')
    with pytest.raises(quality.UnsafeFile):
        quality.set_mutmut_paths(tmp_path, ["src"])


def test_unparsable_pyproject_is_refused(tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is not [ valid toml\n")
    with pytest.raises(quality.UnsafeFile):
        quality.set_mutmut_paths(tmp_path, ["src"])


# --- item 1: the host never opens an arm-written file through a link --------------------------------------

def test_a_symlinked_pyproject_toml_is_refused_not_followed(tmp_path):
    outside = tmp_path / "outside.toml"
    outside.write_text('[tool.mutmut]\npaths_to_mutate = ["evil"]\n')
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "pyproject.toml").symlink_to(outside)
    with pytest.raises(quality.UnsafeFile):
        quality._safe_read(copy / "pyproject.toml")
    with pytest.raises(quality.UnsafeFile):
        quality.set_mutmut_paths(copy, ["src"])
    # nothing outside the copy was written
    assert outside.read_text() == '[tool.mutmut]\npaths_to_mutate = ["evil"]\n'


def test_a_fifo_in_place_of_pyproject_toml_is_refused(tmp_path):
    copy = tmp_path / "copy"
    copy.mkdir()
    os.mkfifo(copy / "pyproject.toml")
    with pytest.raises(quality.UnsafeFile):
        quality._safe_read(copy / "pyproject.toml")


def test_an_oversized_pyproject_toml_is_refused(tmp_path):
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "pyproject.toml").write_text("x" * (quality.MAX_CONFIG_BYTES + 1))
    with pytest.raises(quality.UnsafeFile):
        quality._safe_read(copy / "pyproject.toml")


def test_targets_falls_back_safely_on_a_symlinked_pyproject_toml(tmp_path):
    outside = tmp_path / "outside.toml"
    outside.write_text('[project.scripts]\ntroupe = "evil.cli:main"\n')
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "pyproject.toml").symlink_to(outside)
    assert quality.targets(copy) == ["."]           # never followed the link to read "evil"


def test_writing_never_follows_a_symlink(tmp_path):
    outside = tmp_path / "outside.toml"
    outside.write_text("do not touch\n")
    link = tmp_path / "link.toml"
    link.symlink_to(outside)
    with pytest.raises(quality.UnsafeFile):
        quality._safe_write(link, "new content\n")
    assert outside.read_text() == "do not touch\n"


# --- additional tests: controller ruling — tool failures are recorded as such, never a silent 0/100 -----------

def test_mutation_summary_does_not_mutate_the_shared_zero_constant():
    before = dict(quality.ZERO_MUTATION)
    quality.mutation_summary(dict(quality.ZERO_MUTATION), partial=False, baseline_failed=True, crashed=True)
    assert quality.ZERO_MUTATION == before


def test_a_score_of_none_is_distinct_from_a_score_of_zero():
    """total == 0 (nothing measured) must never present as score 0 — that would look like every mutant survived."""
    s = quality.mutation_summary(dict(quality.ZERO_MUTATION), partial=False, baseline_failed=True)
    assert s["score"] is None


def test_a_crashed_mutation_run_withholds_the_score_even_with_nonzero_counts():
    """item 2: crashed forces score=None unconditionally, not just when the denominator collapses."""
    s = quality.mutation_summary({"killed": 5, "survived": 0, "timeout": 0, "suspicious": 0, "no_tests": 0,
                                  "skipped": 0, "total": 5}, partial=False, baseline_failed=False, crashed=True)
    assert s["score"] is None and s["crashed"] is True


def test_mypy_exit_0_and_1_are_real_results_but_2_is_a_tool_crash():
    assert quality.mypy_ok(0) is True
    assert quality.mypy_ok(1) is True
    assert quality.mypy_ok(2) is False


def test_mypy_result_rc0_is_always_zero_errors():
    assert quality.mypy_result(0, "Success: no issues found in 9 source files\n") == (0, False)
    assert quality.mypy_result(0, "") == (0, False)


def test_mypy_result_rc1_without_a_found_line_is_a_crash():
    """minor item: rc 1 must carry 'Found N errors'; its absence means something else went wrong."""
    assert quality.mypy_result(1, "Found 3 errors in 2 files (checked 5 source files)\n") == (3, False)
    assert quality.mypy_result(1, "internal error: traceback ...\n") == (None, True)


def test_mypy_result_any_other_rc_is_a_crash():
    assert quality.mypy_result(2, "Found 3 errors\n") == (None, True)


def test_ruff_parse_flags_a_crash_when_output_is_not_the_expected_json():
    findings, crashed = quality.ruff_parse(0, '[{"code": "F401"}]')
    assert findings == 1 and crashed is False
    findings, crashed = quality.ruff_parse(2, "ruff: error: invalid configuration\n")
    assert findings is None and crashed is True
    findings, crashed = quality.ruff_parse(0, "not json at all")
    assert findings is None and crashed is True


def test_ruff_parse_returns_none_whenever_rc_is_nonzero_even_with_parseable_output():
    """item 3: rc != 0 is always a crash — the findings count is never trusted, even if stdout happens to
    still be valid (possibly stale or coincidental) JSON."""
    findings, crashed = quality.ruff_parse(2, "")
    assert findings is None and crashed is True
    findings, crashed = quality.ruff_parse(1, "[]")
    assert findings is None and crashed is True


def test_tool_versions_match_the_pinned_tester_requirements_files():
    """Reproducibility (controller ruling): the pinned tool versions the tester image installs must be read
    from the same requirements files the image build itself uses, compared exactly, not just sanity-checked."""
    from runner.paths import REPO_ROOT
    text = ((REPO_ROOT / "runner/images/tester/requirements.txt").read_text() + "\n" +
            (REPO_ROOT / "runner/images/tester/mutmut-requirements.txt").read_text())
    v = quality.tool_versions()
    import re
    for name in ("mypy", "ruff", "mutmut", "pytest"):
        m = re.search(rf"(?m)^{name}==(\S+)", text)
        assert m is not None
        assert v[name] == m.group(1)
    assert v["tester_image"] == config.load_pins().images["tester"]


def test_mutation_summary_json_round_trips(tmp_path):
    s = quality.mutation_summary({"killed": 1, "survived": 0, "timeout": 0, "suspicious": 0, "no_tests": 0,
                                  "skipped": 0, "total": 1}, partial=False, baseline_failed=False,
                                 sampled=False, sample_size=0, sampling="all")
    (tmp_path / "mutation.json").write_text(json.dumps(s, indent=2))
    assert json.loads((tmp_path / "mutation.json").read_text())["score"] == 1.0


# --- binding isolation rule (coordinator, re-alignment to Task 18): mutation/mypy/ruff execute the arm's own
# code, so they must run the way prep and the hidden tests do -- uid 1001, no capabilities once the
# privilege-drop wrapper execs, no-new-privileges, the tester image (never tester-ref), network off ----------

def test_quality_specs_run_hardened_like_prep_and_hidden_tests(tmp_state, monkeypatch, tmp_path):
    from runner import docker, hidden

    accounts_dir = tmp_path / "accounts"
    accounts_dir.mkdir()
    passwd, group = accounts_dir / "passwd", accounts_dir / "group"
    passwd.write_text("actor:x:1000:1000::/home/actor:/bin/bash\n")
    group.write_text("actor:x:1000:\n")
    # avoid a real `docker run ... cat /etc/passwd` against the tester image: _accounts is the only side
    # effect _spec has for mode="script" that this test needs to avoid to stay pure.
    monkeypatch.setattr(hidden, "_accounts", lambda p, image: (passwd, group, "actor"))

    p = Paths("dryquality", "dryrun")
    copy = tmp_path / "work" / "bakeoff-specs-dryrun"
    copy.mkdir(parents=True)

    spec = quality._script_spec(p, copy, ["bash", "-c", "true"])

    pins = config.load_pins()
    assert spec.image == pins.images["tester"]
    assert spec.image != pins.images["tester_ref"]                 # never the harness's reference-only image
    assert spec.network == "none"                                  # never overridden by quality.py

    # docker's own --user starts the container as root only so setpriv (in spec.cmd) can drop it; the caps
    # granted are exactly the minimal set that privilege-drop needs, never the full set.
    assert set(spec.cap_add) == {"SETUID", "SETGID", "SETPCAP", "SYS_RESOURCE"}
    joined = " ".join(spec.cmd)
    assert f"--reuid={hidden.ARM_UID}" in joined and f"--regid={hidden.ARM_UID}" in joined
    assert "--bounding-set=-all" in joined and "--ambient-caps=-all" in joined and "--inh-caps=-all" in joined

    argv = docker.run_argv(spec)
    assert "--security-opt" in argv and "no-new-privileges" in argv     # applied to every RunSpec unconditionally
    assert "--cap-drop" in argv and "ALL" in argv


# --- item 6: offline tests for _mutation and run_all, monkeypatching quality._run --------------------------

def _paths():
    return Paths("dryquality", "dryrun")


def test_mutation_baseline_failed_only_on_pytest_rc_1(monkeypatch, tmp_path):
    monkeypatch.setattr(quality, "_run", _fake_run([quality.ToolRun(1, "1 failed\n", "", False)]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins())
    assert r["baseline_failed"] is True and r["crashed"] is False and r["score"] is None
    assert r["sampling"] == "n/a"


def test_mutation_no_tests_on_pytest_rc_5(monkeypatch, tmp_path):
    monkeypatch.setattr(quality, "_run", _fake_run([quality.ToolRun(5, "no tests ran\n", "", False)]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins())
    assert r["sampling"] == "no tests" and r["baseline_failed"] is False and r["crashed"] is False
    assert r["score"] is None


@pytest.mark.parametrize("rc", [2, 3, 4, 125, 126, 127, 137])
def test_mutation_baseline_harness_exit_codes_are_crashed_not_baseline_failed(monkeypatch, tmp_path, rc):
    monkeypatch.setattr(quality, "_run", _fake_run([quality.ToolRun(rc, "", "", False)]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins())
    assert r["crashed"] is True and r["baseline_failed"] is False and r["score"] is None


def test_mutation_baseline_timeout_is_crashed(monkeypatch, tmp_path):
    monkeypatch.setattr(quality, "_run", _fake_run([quality.ToolRun(None, "", "", True)]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins())
    assert r["crashed"] is True and r["timed_out"] is True and r["score"] is None


def test_mutation_partial_when_the_inner_timeout_fires_with_some_real_results(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=124\n", "", False)                    # container 1: just the marker
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\nm.f__mutmut_2: not checked\n"
                                        "__results_rc=0\n", "", False)                  # container 2: fresh
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["partial"] is True and r["crashed"] is False
    assert r["killed"] == 1 and r["score"] is not None


def test_mutation_crashed_when_mutmut_results_itself_fails(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "__results_rc=1\n", "", False)   # results crashed: no per-mutant lines
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["crashed"] is True and r["score"] is None
    assert r["sampling"] != "no mutants"


def test_mutation_crashed_when_every_sampled_mutant_is_not_checked_but_the_run_reports_success(monkeypatch, tmp_path):
    """The exact regression fix round 2 closed: mutmut results exits 0, the inner timeout marker never fired,
    but every sampled mutant still comes back "not checked" -- zero real signal must never read as a
    misleadingly precise 0.0."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n"
                                        "__results_rc=0\n", "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["crashed"] is True and r["score"] is None


def test_mutation_sampled_filter_only_counts_the_chosen_names(monkeypatch, tmp_path):
    """A results listing can include mutants outside the sample (mutmut lists everything it has ever seen);
    only the chosen names' statuses may contribute to the counts."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n"
                              "m.f__mutmut_3: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\nm.f__mutmut_2: survived\n"
                                        "m.f__mutmut_3: killed\n__results_rc=0\n", "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    monkeypatch.setattr(quality, "sample", lambda names, n: sorted(names)[:2])   # force a known 2-of-3 pick
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["total"] == 2 and r["killed"] == 1 and r["survived"] == 1


# --- fix round 3, item 1: status lines are parsed only from the fresh results container; forged lines printed
# during `mutmut run` never count, and a duplicate name is counted once, last status wins ----------------

def test_a_forged_status_line_printed_during_the_run_does_not_count(monkeypatch, tmp_path):
    """Arm test output printed while `mutmut run` executes must never be able to masquerade as a real status
    line -- it's redirected to a log file inside container 1 and never reaches the stream this function
    parses for statuses at all (container 2's clean stdout)."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    # container 1's own combined output (its "log tail") contains a forged status line for the one chosen
    # mutant, claiming it survived -- this must never be read, since only container 2's stdout is parsed.
    run_container = quality.ToolRun(0, "m.f__mutmut_1: survived\n__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["killed"] == 1 and r["survived"] == 0 and r["crashed"] is False


def test_parse_results_keeps_one_status_per_name_last_one_wins():
    text = "m.f__mutmut_1: survived\nm.f__mutmut_1: killed\nm.f__mutmut_2: killed\n"
    names, counts = quality.parse_results(text)
    assert names == ["m.f__mutmut_1", "m.f__mutmut_2"]
    assert counts["killed"] == 2 and counts["survived"] == 0 and counts["total"] == 2


def test_mutation_duplicate_status_lines_in_the_results_container_count_once(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    # the same mutant reported twice (a mutmut quirk, or a forged duplicate) -- the last one wins, never summed
    results_container = quality.ToolRun(0, "m.f__mutmut_1: survived\nm.f__mutmut_1: killed\n__results_rc=0\n",
                                        "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["total"] == 1 and r["killed"] == 1 and r["survived"] == 0


def test_run_all_produces_the_exact_keys_evidence_finalise_reads(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    b = tmp_path / "b"
    b.mkdir()
    (a / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (b / "pyproject.toml").write_text('[project]\nname = "x"\n')
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=b, prep={"quality": {"ok": True}})

    def fake_run(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "mypy" in text:
            return quality.ToolRun(0, "Success: no issues found in 1 source file\n", "", False)
        if "ruff" in text:
            return quality.ToolRun(0, "[]", "", False)
        if "pytest" in text:
            return quality.ToolRun(5, "no tests ran\n", "", False)
        return quality.ToolRun(0, "", "", False)

    monkeypatch.setattr(quality, "_run", fake_run)
    out = quality.run_all(_paths(), prep, tmp_path / "out")

    # evidence.finalise reads exactly these
    for key in ("mypy_errors", "ruff_findings", "ruff_arm_findings"):
        assert key in out
    for key in ("score", "sampling", "partial"):
        assert key in out["mutation"]
    assert out["mypy_errors"] == 0 and out["mutation"]["sampling"] == "no tests"


# --- fix round 2 -------------------------------------------------------------------------------------------

# item 1: check_interrupted is not a real outcome -- it sets partial; an all-interrupted run is crashed.

def test_mutation_all_check_interrupted_is_crashed_not_score_zero(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: check was interrupted by user\n"
                                        "m.f__mutmut_2: check was interrupted by user\n__results_rc=0\n", "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["crashed"] is True and r["score"] is None


def test_mutation_some_check_interrupted_sets_partial_not_crashed(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\n"
                                        "m.f__mutmut_2: check was interrupted by user\n__results_rc=0\n",
                                        "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["crashed"] is False and r["partial"] is True and r["killed"] == 1
    assert r["check_interrupted"] == 1


# item 5: fewer statuses than sampled sets partial and records the shortfall

def test_mutation_missing_results_sets_partial_and_records_the_shortfall(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n"
                              "m.f__mutmut_3: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    # only 2 of the 3 sampled names ever get a status line
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\nm.f__mutmut_2: survived\n__results_rc=0\n",
                                        "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=3))
    assert r["partial"] is True and r["missing_results"] == 1 and r["crashed"] is False


# item 4: markers are read from the last anchored line, never spoofable by earlier arm output

def test_last_marker_takes_the_last_anchored_occurrence_not_the_first():
    text = "some arm output\n__run_rc=0\nmore arm output\n__run_rc=124\n"
    assert quality._last_marker(text, "__run_rc") == 124


def test_last_marker_requires_its_own_line():
    text = "prefix__run_rc=0 suffix\n__run_rc=1 trailing junk\n__run_rc=7\n"
    assert quality._last_marker(text, "__run_rc") == 7


def test_last_marker_returns_none_when_absent():
    assert quality._last_marker("no markers here\n", "__run_rc") is None


def test_mutation_ignores_a_spoofed_early_marker_in_stdout(monkeypatch, tmp_path):
    """A hostile arm's own test output, tailed into container 1's stdout from the redirected mutmut-run.log,
    could contain a line that looks exactly like our success marker before the real one; only the last (our
    own echo, always printed after the tail) must be trusted."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    spoofed = ("some arm log content\n"
               "__run_rc=0\n"                                    # forged by arm test output, early in the stream
               "more arm output\n"
               "__run_rc=124\n")                                 # our own, always printed last
    run_container = quality.ToolRun(0, spoofed, "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["mutmut_run_rc"] == 124                              # not the spoofed 0
    assert r["partial"] is True and r["crashed"] is False         # 124 is the legitimate inner-timeout marker


# item 3: the run_rc crash path -- an rc outside {0, 124}, and a missing marker entirely

def test_mutation_crashed_when_run_rc_is_outside_zero_or_124(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=1\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["crashed"] is True and r["score"] is None


def test_mutation_crashed_when_a_marker_is_missing_entirely(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    run_container = quality.ToolRun(0, "__run_rc=0\n", "", False)
    results_container = quality.ToolRun(0, "m.f__mutmut_1: killed\n", "", False)   # __results_rc never printed
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, run_container, results_container]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["crashed"] is True and r["score"] is None and r["mutmut_results_rc"] is None


# item 3: ruff's stderr is kept out of the parse

def test_ruff_findings_ignore_stderr_content_even_when_it_looks_like_json(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})

    def fake_run(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "mypy" in text:
            return quality.ToolRun(0, "Success: no issues found in 1 source file\n", "", False)
        if "ruff" in text:
            # stderr looks like it could corrupt a naive combined parse; stdout alone is the real, valid array
            return quality.ToolRun(0, '[{"code": "F401"}]', "not json { garbage from the privilege-drop wrapper",
                                   False)
        return quality.ToolRun(0, "", "", False)

    monkeypatch.setattr(quality, "_run", fake_run)
    out = quality.run_all(_paths(), prep, tmp_path / "out")
    assert out["ruff_findings"] == 1 and out["ruff_crashed"] is False


# item 3 / item 2: _run converts TimeoutExpired; mypy/ruff timeouts propagate through run_all; run_all survives
# an exception raised by any phase, always writing summary.json with the full key set.

def test_run_converts_timeout_expired(monkeypatch, tmp_state, tmp_path):
    import subprocess as _subprocess
    from runner import hidden

    def raises_timeout(spec, timeout):
        raise _subprocess.TimeoutExpired(cmd="x", timeout=timeout)

    monkeypatch.setattr(hidden, "_run", raises_timeout)
    monkeypatch.setattr(hidden, "_spec", lambda *a, **k: object())
    result = quality._run(_paths(), tmp_path, ["bash", "-c", "true"], 5)
    assert result.timed_out is True and result.rc is None


def test_run_all_records_mypy_and_ruff_timeouts(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})

    def fake_run(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "mypy" in text:
            return quality.ToolRun(None, "", "", True)
        if "ruff" in text:
            return quality.ToolRun(None, "", "", True)
        return quality.ToolRun(0, "", "", False)

    monkeypatch.setattr(quality, "_run", fake_run)
    out = quality.run_all(_paths(), prep, tmp_path / "out")
    assert out["mypy_timed_out"] is True and out["mypy_crashed"] is True and out["mypy_errors"] is None
    assert out["ruff_timed_out"] is True and out["ruff_crashed"] is True and out["ruff_findings"] is None


# fix round 3, item 5: one test per run_all phase, precisely isolating which phase failed and confirming the
# others are unaffected -- a single blanket "everything blows up" test can't show that isolation.

def _ok_run(p_, copy, cmd, timeout, env=None):
    text = " ".join(cmd)
    if "mypy" in text:
        return quality.ToolRun(0, "Success: no issues found in 1 source file\n", "", False)
    if "ruff" in text:
        return quality.ToolRun(0, "[]", "", False)
    return quality.ToolRun(5, "no tests ran\n", "", False)


def test_run_all_survives_an_exception_from_targets(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})
    monkeypatch.setattr(quality, "targets", lambda copy: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(quality, "_run", _ok_run)
    out_dir = tmp_path / "out"
    out = quality.run_all(_paths(), prep, out_dir)
    assert out["targets_crashed"] is True and "RuntimeError" in (out["targets_error"] or "")
    assert out["targets"] == ["."]
    assert out["mypy_crashed"] is False                       # other phases unaffected
    assert (out_dir / "quality" / "summary.json").exists()


def test_run_all_survives_an_exception_from_mypy(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})

    def fake(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "mypy" in text:
            raise RuntimeError("simulated mypy crash")
        return _ok_run(p_, copy, cmd, timeout)

    monkeypatch.setattr(quality, "_run", fake)
    out_dir = tmp_path / "out"
    out = quality.run_all(_paths(), prep, out_dir)
    assert out["mypy_crashed"] is True and "RuntimeError" in (out["mypy_error"] or "")
    assert out["ruff_crashed"] is False and out["targets_crashed"] is False
    assert (out_dir / "quality" / "summary.json").exists()


def test_run_all_survives_an_exception_from_ruff(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})

    def fake(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "ruff" in text and "isolated" in text:
            raise RuntimeError("simulated ruff crash")
        return _ok_run(p_, copy, cmd, timeout)

    monkeypatch.setattr(quality, "_run", fake)
    out_dir = tmp_path / "out"
    out = quality.run_all(_paths(), prep, out_dir)
    assert out["ruff_crashed"] is True and "RuntimeError" in (out["ruff_error"] or "")
    assert out["mypy_crashed"] is False
    assert (out_dir / "quality" / "summary.json").exists()


def test_run_all_survives_an_exception_from_the_arm_ruff_pass(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    (a / "ruff.toml").write_text("")                    # gives the arm a config, so the arm pass is attempted
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})

    def fake(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "ruff" in text and "isolated" not in text:
            raise RuntimeError("simulated arm-ruff crash")
        return _ok_run(p_, copy, cmd, timeout)

    monkeypatch.setattr(quality, "_run", fake)
    out_dir = tmp_path / "out"
    out = quality.run_all(_paths(), prep, out_dir)
    assert out["ruff_arm_crashed"] is True and "RuntimeError" in (out["ruff_arm_error"] or "")
    assert out["ruff_crashed"] is False
    assert (out_dir / "quality" / "summary.json").exists()


def test_run_all_survives_an_exception_from_has_arm_ruff_config(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})
    monkeypatch.setattr(quality, "_has_arm_ruff_config",
                        lambda copy: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(quality, "_run", _ok_run)
    out_dir = tmp_path / "out"
    out = quality.run_all(_paths(), prep, out_dir)
    assert out["ruff_arm_crashed"] is True and "RuntimeError" in (out["ruff_arm_error"] or "")
    assert out["ruff_crashed"] is False
    assert (out_dir / "quality" / "summary.json").exists()


def test_run_all_survives_an_exception_from_tool_versions(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})
    monkeypatch.setattr(quality, "tool_versions", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(quality, "_run", _ok_run)
    out_dir = tmp_path / "out"
    out = quality.run_all(_paths(), prep, out_dir)
    assert out["tool_versions"] == {"error": "RuntimeError: boom"}
    assert out["mypy_crashed"] is False
    assert (out_dir / "quality" / "summary.json").exists()


def test_run_all_survives_an_exception_from_mutation_itself(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    b = tmp_path / "b"
    b.mkdir()
    (a / "pyproject.toml").write_text('[project]\nname = "x"\n')
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=b, prep={"quality": {"ok": True}})

    def fake_run(p_, copy, cmd, timeout, env=None):
        text = " ".join(cmd)
        if "mypy" in text:
            return quality.ToolRun(0, "Success: no issues found in 1 source file\n", "", False)
        if "ruff" in text:
            return quality.ToolRun(0, "[]", "", False)
        raise RuntimeError("simulated mutation crash")

    monkeypatch.setattr(quality, "_run", fake_run)
    out = quality.run_all(_paths(), prep, tmp_path / "out")
    assert out["mutation"]["crashed"] is True and out["mutation"]["score"] is None
    assert "RuntimeError" in out["mutation"]["sampling"]


def test_the_key_set_is_the_same_on_every_mutation_path(monkeypatch, tmp_path):
    """Extended (fix round 3, item 6): every early-return path, a real successful run, both container-timeout
    paths, a set_mutmut_paths refusal, and both _mutation_placeholder() paths must all carry the exact same
    keys -- a consumer never has to guess which fields a given outcome bothered to set."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')

    def via_mutation(responses):
        def call():
            monkeypatch.setattr(quality, "_run", _fake_run(responses))
            return quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
        return call

    def set_mutmut_paths_refused():
        monkeypatch.setattr(quality, "_run", _fake_run([quality.ToolRun(0, "5 passed\n", "", False)]))
        monkeypatch.setattr(quality, "set_mutmut_paths",
                            lambda copy, tg: (_ for _ in ()).throw(quality.UnsafeFile("refused")))
        return quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))

    scenarios = {
        "baseline_failed": via_mutation([quality.ToolRun(1, "1 failed\n", "", False)]),
        "no_tests": via_mutation([quality.ToolRun(5, "no tests\n", "", False)]),
        "harness_fault": via_mutation([quality.ToolRun(137, "", "", False)]),
        "baseline_timeout": via_mutation([quality.ToolRun(None, "", "", True)]),
        "crashed_results": via_mutation([quality.ToolRun(0, "5 passed\n", "", False),
                                        quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False),
                                        quality.ToolRun(0, "__run_rc=0\n", "", False),
                                        quality.ToolRun(0, "__results_rc=1\n", "", False)]),
        "success": via_mutation([quality.ToolRun(0, "5 passed\n", "", False),
                                quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False),
                                quality.ToolRun(0, "__run_rc=0\n", "", False),
                                quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)]),
        "run_timeout": via_mutation([quality.ToolRun(0, "5 passed\n", "", False),
                                    quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False),
                                    quality.ToolRun(None, "", "", True)]),
        "results_timeout": via_mutation([quality.ToolRun(0, "5 passed\n", "", False),
                                        quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False),
                                        quality.ToolRun(0, "__run_rc=0\n", "", False),
                                        quality.ToolRun(None, "", "", True)]),
        "set_mutmut_paths_refused": set_mutmut_paths_refused,
    }
    key_sets = {name: set(call().keys()) for name, call in scenarios.items()}
    key_sets["placeholder_install_failed"] = set(quality._mutation_placeholder("install failed").keys())
    key_sets["placeholder_error"] = set(quality._mutation_placeholder("error: RuntimeError: x").keys())
    unique = set(map(frozenset, key_sets.values()))
    assert len(unique) == 1, key_sets


# item 7: the entry-point module must be a safe dotted-identifier chain, never interpolated raw

def test_entry_point_must_be_a_dotted_identifier_chain(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project.scripts]\ntroupe = "evil; rm -rf ~:main"\n')
    with pytest.raises(quality.InvalidEntryPoint):
        quality.targets(tmp_path)


def test_entry_point_dotted_parts_must_each_be_identifiers(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project.scripts]\ntroupe = "a.b-c.d:main"\n')  # "b-c" not an identifier
    with pytest.raises(quality.InvalidEntryPoint):
        quality.targets(tmp_path)


def test_entry_point_valid_dotted_chain_is_accepted(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project.scripts]\ntroupe = "a.b.c:main"\n')
    (tmp_path / "a").mkdir()
    assert quality.targets(tmp_path) == ["a"]


def test_run_all_records_a_crashed_targets_phase(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "pyproject.toml").write_text('[project.scripts]\ntroupe = "evil; rm -rf:main"\n')
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})
    monkeypatch.setattr(quality, "_run", _fake_run([quality.ToolRun(0, "Success: no issues found\n", "", False),
                                                    quality.ToolRun(0, "[]", "", False)]))
    out = quality.run_all(_paths(), prep, tmp_path / "out")
    assert out["targets_crashed"] is True and out["targets"] == ["."]
    assert "InvalidEntryPoint" in (out["targets_error"] or "")


def test_mypy_command_quotes_targets_rather_than_interpolating_raw(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "weird target").mkdir()
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})
    captured = []

    def fake_run(p_, copy, cmd, timeout, env=None):
        captured.append(cmd)
        return quality.ToolRun(0, "Success: no issues found\n", "", False) if "mypy" in " ".join(cmd) else \
            quality.ToolRun(0, "[]", "", False)

    monkeypatch.setattr(quality, "targets", lambda copy: ["weird target"])
    monkeypatch.setattr(quality, "_run", fake_run)
    quality.run_all(_paths(), prep, tmp_path / "out")
    mypy_cmd = next(c for c in captured if "mypy" in " ".join(c))
    # the target must appear as a single shell-quoted token, not split by its embedded space
    script = mypy_cmd[-1]
    assert "'weird target'" in script or shlex_split_ok(script)


def shlex_split_ok(script: str) -> bool:
    import shlex as _shlex
    try:
        parts = _shlex.split(script)
    except ValueError:
        return False
    return "weird target" in parts


# item 6: _safe_write is atomic (temp file + os.replace) -- no stray temp file left behind either way

def test_safe_write_leaves_no_stray_temp_file_on_success(tmp_path):
    target = tmp_path / "pyproject.toml"
    quality._safe_write(target, "hello\n")
    assert target.read_text() == "hello\n"
    leftovers = [f for f in tmp_path.iterdir() if f.name != "pyproject.toml"]
    assert leftovers == []


def test_safe_write_replaces_an_existing_regular_file_atomically(tmp_path):
    target = tmp_path / "pyproject.toml"
    target.write_text("old\n")
    quality._safe_write(target, "new\n")
    assert target.read_text() == "new\n"
    leftovers = [f for f in tmp_path.iterdir() if f.name != "pyproject.toml"]
    assert leftovers == []


# --- fix round 3, item 4: tests that actually fail without the item-6 fixes ---------------------------------

def test_safe_write_cleans_up_its_temp_file_when_the_write_itself_fails(tmp_path, monkeypatch):
    """Without the try/except BaseException wrapping the write+replace, a write failure would leave the
    mkstemp-created temp file behind and the target untouched -- proves the cleanup path, not just the
    happy path."""
    target = tmp_path / "pyproject.toml"

    def raising_write(fd, data):
        raise OSError("simulated disk-full")

    monkeypatch.setattr(quality.os, "write", raising_write)
    with pytest.raises(OSError):
        quality._safe_write(target, "hello\n")
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []        # no stray temp file left behind


def test_safe_read_fstat_recheck_catches_a_fifo_even_when_lstat_is_fooled(tmp_path, monkeypatch):
    """Proves the fstat-after-open recheck matters on its own, not just the initial lstat: even if lstat
    reports a regular file (simulating a TOCTOU race, or a lstat implementation bug), the O_NONBLOCK open
    plus fstat on the real descriptor still catches the FIFO -- and, just as importantly, does not hang. A
    signal-based timeout guards the test itself: without O_NONBLOCK, opening a FIFO with no writer blocks
    forever, and this test would hang rather than fail."""
    fifo = tmp_path / "pyproject.toml"
    os.mkfifo(fifo)
    real_lstat = quality.os.lstat

    def fooled_lstat(path, *a, **k):
        st = real_lstat(path, *a, **k)
        if os.fspath(path) == os.fspath(fifo):
            fake = list(st)
            fake[0] = stat.S_IFREG | 0o644           # pretend it's a regular file
            return os.stat_result(fake)
        return st

    monkeypatch.setattr(quality.os, "lstat", fooled_lstat)

    def _on_alarm(signum, frame):
        raise TimeoutError("_safe_read hung on a FIFO -- the O_NONBLOCK/fstat recheck is missing or broken")

    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(5)
    try:
        with pytest.raises(quality.UnsafeFile):
            quality._safe_read(fifo)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# --- mutmut.log records the commands that really ran (the e2e copy-B test greps for the venv binary) --------

def _recording_run(responses, seen):
    it = iter(responses)
    def fake(p, copy, cmd, timeout, env=None):
        seen.append(list(cmd))
        return next(it)
    return fake


def _cmd_lines(log_text):
    return [ln for ln in log_text.splitlines() if ln.startswith("$ ")]


def test_mutmut_log_command_lines_are_what_the_baseline_run_and_results_containers_were_given(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    seen: list[list[str]] = []
    responses = [quality.ToolRun(0, "5 passed\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n", "", False),
                 quality.ToolRun(0, "__run_rc=0\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: killed\nm.f__mutmut_2: survived\n__results_rc=0\n", "", False)]
    monkeypatch.setattr(quality, "_run", _recording_run(responses, seen))
    quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2, mutation_seconds=600))
    baseline_cmd, _listing_cmd, run_cmd, results_cmd = seen      # the listing container is not logged
    lines = _cmd_lines((tmp_path / "out/quality/mutmut.log").read_text())
    assert len(lines) == 3, lines
    # baseline: the exact script bash was handed
    assert lines[0].startswith("$ " + baseline_cmd[2] + " ")
    # the mutation run: the mutmut argv exactly as passed (the `bash -c ... timeout N` wrapper is not spelled out;
    # the line names the cap instead), plus the sample count
    mutmut_argv = run_cmd[run_cmd.index(".venv/bin/mutmut"):]
    assert mutmut_argv[:4] == [".venv/bin/mutmut", "run", "--max-children", "4"]
    assert lines[1].startswith("$ " + " ".join(mutmut_argv) + " ")
    assert "(sampled 2" in lines[1] and "timeout 600s" in lines[1] and str(600) == run_cmd[4]
    # results: the command, without our own rc-marker echo
    assert lines[2].startswith("$ .venv/bin/mutmut results --all true ")
    assert results_cmd[2].startswith(".venv/bin/mutmut results --all true;")


def test_mutmut_log_shows_a_count_not_every_name_for_a_long_sample(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    names = [f"m.f__mutmut_{i}" for i in range(1, 21)]
    seen: list[list[str]] = []
    responses = [quality.ToolRun(0, "5 passed\n", "", False),
                 quality.ToolRun(0, "".join(f"{n}: not checked\n" for n in names), "", False),
                 quality.ToolRun(0, "__run_rc=0\n", "", False),
                 quality.ToolRun(0, "".join(f"{n}: killed\n" for n in names) + "__results_rc=0\n", "", False)]
    monkeypatch.setattr(quality, "_run", _recording_run(responses, seen))
    quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=20))
    run_line = _cmd_lines((tmp_path / "out/quality/mutmut.log").read_text())[1]
    assert run_line.startswith("$ .venv/bin/mutmut run --max-children 4 ")
    assert "(sampled 20" in run_line
    assert sum(n in run_line.split() for n in names) < 20           # not all twenty names spelled out
    assert len(seen[2]) - seen[2].index(".venv/bin/mutmut") == 4 + 20  # ...though all twenty were passed


def test_mutmut_log_unsampled_run_says_all(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    responses = [quality.ToolRun(0, "5 passed\n", "", False),
                 quality.ToolRun(0, "__run_rc=0\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)]
    monkeypatch.setattr(quality, "_run", _recording_run(responses, []))
    quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=0))
    run_line = _cmd_lines((tmp_path / "out/quality/mutmut.log").read_text())[1]
    assert run_line.startswith("$ .venv/bin/mutmut run --max-children 4 ") and "(all;" in run_line


# --- mutation containers: `uv run` from inside mutmut's `mutants/` must reuse the prepared venv ---------------
# mutmut 3 copies pyproject.toml/uv.lock into `mutants/` and runs the arm's tests from there, so an arm test that
# shells out to `uv run <script>` with cwd under `mutants/` makes uv treat `mutants/` as its own project and (with
# UV_NO_SYNC=1, offline) build an empty `mutants/.venv` -- `Failed to spawn`, the stats phase fails, and the run
# crashes. The listing, run and results containers carry UV_PROJECT_ENVIRONMENT=<copy>/.venv (in-container path);
# baseline, mypy and ruff do not.

def _env_recording_run(responses, seen):
    it = iter(responses)
    def fake(p, copy, cmd, timeout, env=None):
        seen.append((list(cmd), env))
        return next(it)
    return fake


def test_mutation_env_points_at_the_copys_venv_by_its_in_container_path(tmp_path):
    copy = tmp_path / "work" / "bakeoff-specs-dryrun"
    assert quality.mutation_env(copy) == {"UV_PROJECT_ENVIRONMENT": "/work/bakeoff-specs-dryrun/.venv"}


def test_script_spec_carries_uv_project_environment_only_when_given_the_mutation_env(tmp_state, monkeypatch, tmp_path):
    from runner import hidden
    accounts = tmp_path / "accounts"
    accounts.mkdir()
    (accounts / "passwd").write_text("actor:x:1000:1000::/home/actor:/bin/bash\n")
    (accounts / "group").write_text("actor:x:1000:\n")
    monkeypatch.setattr(hidden, "_accounts", lambda p, image: (accounts / "passwd", accounts / "group", "actor"))
    copy = tmp_path / "work" / "bakeoff-specs-dryrun"
    copy.mkdir(parents=True)

    plain = quality._script_spec(_paths(), copy, ["bash", "-c", "true"])
    mut = quality._script_spec(_paths(), copy, ["bash", "-c", "true"], env=quality.mutation_env(copy))

    assert "UV_PROJECT_ENVIRONMENT" not in plain.env
    assert mut.env["UV_PROJECT_ENVIRONMENT"] == mut.workdir + "/.venv"       # the copy as mounted, + /.venv
    assert any(m.host == copy.parent and m.ctr == "/work" for m in mut.mounts)
    assert {k: v for k, v in mut.env.items() if k != "UV_PROJECT_ENVIRONMENT"} == plain.env   # nothing else moves


def test_listing_run_and_results_containers_get_the_mutation_env_and_the_baseline_does_not(monkeypatch, tmp_path):
    copy = tmp_path / "bakeoff-specs-dryrun"
    copy.mkdir()
    (copy / "pyproject.toml").write_text('[project]\nname = "x"\n')
    seen: list = []
    responses = [quality.ToolRun(0, "5 passed\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False),
                 quality.ToolRun(0, "__run_rc=0\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)]
    monkeypatch.setattr(quality, "_run", _env_recording_run(responses, seen))
    quality._mutation(_paths(), copy, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    (baseline_cmd, baseline_env), (list_cmd, list_env), (run_cmd, run_env), (res_cmd, res_env) = seen
    assert "pytest" in baseline_cmd[2] and baseline_env is None
    want = {"UV_PROJECT_ENVIRONMENT": "/work/bakeoff-specs-dryrun/.venv"}
    assert "__bk_list_only__" in list_cmd[2] and list_env == want
    assert ".venv/bin/mutmut" in run_cmd and run_env == want
    assert "mutmut results" in res_cmd[2] and res_env == want


def test_mypy_and_ruff_containers_get_no_extra_env(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    (a / "src").mkdir(parents=True)
    (a / "pyproject.toml").write_text('[project]\nname = "x"\n[tool.ruff]\n')
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=None, prep={})
    seen: list = []
    def fake(p_, copy, cmd, timeout, **kw):
        seen.append((" ".join(cmd), kw.get("env")))
        return _ok_run(p_, copy, cmd, timeout)
    monkeypatch.setattr(quality, "_run", fake)
    quality.run_all(_paths(), prep, tmp_path / "out")
    tools = [t for t, _ in seen]
    assert sum("mypy" in t for t in tools) == 1 and sum("ruff" in t for t in tools) == 2
    assert all(env is None for _, env in seen)


def test_mutmut_log_notes_the_uv_project_environment_the_mutation_containers_got(monkeypatch, tmp_path):
    copy = tmp_path / "bakeoff-specs-dryrun"
    copy.mkdir()
    (copy / "pyproject.toml").write_text('[project]\nname = "x"\n')
    responses = [quality.ToolRun(0, "5 passed\n", "", False),
                 quality.ToolRun(0, "__run_rc=0\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: killed\n__results_rc=0\n", "", False)]
    monkeypatch.setattr(quality, "_run", _env_recording_run(responses, []))
    quality._mutation(_paths(), copy, ["src"], tmp_path / "out", _pins(mutation_sample=0))
    text = (tmp_path / "out/quality/mutmut.log").read_text()
    notes = [ln for ln in text.splitlines() if ln.startswith("# ") and
             "UV_PROJECT_ENVIRONMENT=/work/bakeoff-specs-dryrun/.venv" in ln]
    assert len(notes) == 1
    # the note precedes the mutation run's `$ ` line and follows the baseline's, which ran without it
    lines = text.splitlines()
    i_note = lines.index(notes[0])
    assert lines[i_note + 1].startswith("$ .venv/bin/mutmut run ")
    assert any(ln.startswith("$ ") and "(baseline)" in ln for ln in lines[:i_note])


def test_every_mutant_no_tests_is_an_unmeasurable_null_score_not_a_crash(monkeypatch, tmp_path):
    # an arm whose tests all reach the code through the CLI subprocess: mutmut runs cleanly and reports every
    # mutant "no tests" -- a real (if empty) verdict, so the score is withheld without calling the run a crash
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    responses = [quality.ToolRun(0, "5 passed\n", "", False),
                 quality.ToolRun(0, "__run_rc=0\n", "", False),
                 quality.ToolRun(0, "m.f__mutmut_1: no tests\nm.f__mutmut_2: no tests\n__results_rc=0\n", "", False)]
    monkeypatch.setattr(quality, "_run", _fake_run(responses))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=0))
    assert r["crashed"] is False and r["partial"] is False
    assert r["no_tests"] == 2 and r["total"] == 2 and r["score"] is None
