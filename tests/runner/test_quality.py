import dataclasses
import json
import os
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
    def fake(p, copy, cmd, timeout):
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
    run_out = "m.f__mutmut_1: killed\nm.f__mutmut_2: not checked\n__run_rc=124\n__results_rc=0\n"
    main_run = quality.ToolRun(0, run_out, "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, main_run]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["partial"] is True and r["crashed"] is False
    assert r["killed"] == 1 and r["score"] is not None


def test_mutation_crashed_when_mutmut_results_itself_fails(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\n", "", False)
    main_run = quality.ToolRun(0, "__run_rc=0\n__results_rc=1\n", "", False)   # results crashed: no per-mutant lines
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, main_run]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=1))
    assert r["crashed"] is True and r["score"] is None
    assert r["sampling"] != "no mutants"


def test_mutation_crashed_when_every_sampled_mutant_is_not_checked_but_the_run_reports_success(monkeypatch, tmp_path):
    """The exact regression this fix round closes: mutmut results exits 0, the inner timeout marker never
    fired, but every sampled mutant still comes back "not checked" -- zero real signal must never read as a
    misleadingly precise 0.0."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n", "", False)
    run_out = "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n__run_rc=0\n__results_rc=0\n"
    main_run = quality.ToolRun(0, run_out, "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, main_run]))
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["crashed"] is True and r["score"] is None


def test_mutation_sampled_filter_only_counts_the_chosen_names(monkeypatch, tmp_path):
    """A results listing can include mutants outside the sample (mutmut lists everything it has ever seen);
    only the chosen names' statuses may contribute to the counts."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    baseline_ok = quality.ToolRun(0, "5 passed\n", "", False)
    listing = quality.ToolRun(0, "m.f__mutmut_1: not checked\nm.f__mutmut_2: not checked\n"
                              "m.f__mutmut_3: not checked\n", "", False)
    run_out = ("m.f__mutmut_1: killed\nm.f__mutmut_2: survived\nm.f__mutmut_3: killed\n"
               "__run_rc=0\n__results_rc=0\n")
    main_run = quality.ToolRun(0, run_out, "", False)
    monkeypatch.setattr(quality, "_run", _fake_run([baseline_ok, listing, main_run]))
    monkeypatch.setattr(quality, "sample", lambda names, n: sorted(names)[:2])   # force a known 2-of-3 pick
    r = quality._mutation(_paths(), tmp_path, ["src"], tmp_path / "out", _pins(mutation_sample=2))
    assert r["total"] == 2 and r["killed"] == 1 and r["survived"] == 1


def test_run_all_produces_the_exact_keys_evidence_finalise_reads(monkeypatch, tmp_state, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (a / "src").mkdir()
    b = tmp_path / "b"
    b.mkdir()
    (a / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (b / "pyproject.toml").write_text('[project]\nname = "x"\n')
    prep = types.SimpleNamespace(hidden_copy=a, quality_copy=b, prep={"quality": {"ok": True}})

    def fake_run(p_, copy, cmd, timeout):
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
