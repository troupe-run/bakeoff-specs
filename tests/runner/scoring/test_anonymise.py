import gzip
import json
import os
import re
import shutil
from pathlib import Path
import pytest
from runner import config, docker, gitops, paths
from runner.scoring import anonymise as an, leakcheck

MINI = Path(__file__).parent / "fixtures" / "mini"


def test_labels_are_stable_for_a_seed_and_hide_the_order():
    a = an.labels(["ccsdd", "control", "openspec"], "pass1")
    assert a == an.labels(["openspec", "ccsdd", "control"], "pass1")
    assert sorted(a.values()) == ["Arm A", "Arm B", "Arm C"]


def test_scrub_removes_tool_names_folders_commands_and_trailers():
    terms = [("speckit", "the method"), (".specify/", "spec/"), ("/speckit-plan", "/method-command")]
    text = "Ran /speckit-plan in .specify/ for speckit\nCo-Authored-By: X <x@y>\nClaude-Session: https://z"
    out = an.scrub(text, terms)
    assert "speckit" not in out.lower() and ".specify" not in out and "Co-Authored-By" not in out
    assert "Claude-Session" not in out


def test_scrub_terms_cover_every_real_arm_repo_name():
    for arm in sorted(f.stem for f in config.ARMS_DIR.glob("*.toml")):
        assert any(f"bakeoff-specs-{arm}" in t[0] for t in an.scrub_terms(arm))


def test_control_the_word_survives_but_its_repo_name_does_not():
    t = an.scrub_terms("control")
    out = an.scrub("the control group lives in bakeoff-specs-control and docs/plan.md", t)
    assert out == "the control group lives in repo and docs/plan.md"


def test_real_arm_terms_scrub_names_folders_and_command_families_from_config():
    cases = {"speckit": ("/speckit-tasks in .specify/memory and specs/003 (github/spec-kit)", ["speckit", ".specify", "spec-kit"]),
             "ccsdd": ("/kiro-impl then .kiro/specs, by Kiro and gotalab", ["kiro", "gotalab"]),
             "openspec": ("/opsx:apply in openspec/changes; Fission-AI", ["opsx", "openspec", "fission"]),
             "speckitty": ("/spec-kitty.merge into kitty-specs/001 and .kittify/", ["kitty", "kittify"]),
             "superpowers": ("superpowers:brainstorming wrote docs/superpowers/specs/x.md", ["superpowers", "obra"])}
    for arm, (text, banned) in cases.items():
        out = an.scrub(text, an.scrub_terms(arm)).lower()
        assert not any(b in out for b in banned), (arm, out)


def test_command_slash_and_folder_get_the_neutral_words():
    t = an.scrub_terms("speckit")
    assert an.scrub("run /speckit-plan", t) == "run /method-command"
    assert an.scrub("see .claude/skills/speckit-plan/SKILL.md", t) == "see .claude/skills/method-command/SKILL.md"
    assert an.scrub("specs/003/spec.md", t) == "spec/003/spec.md"


def test_a_replacement_is_not_scrubbed_again():
    assert an.scrub("ab", [("a", "b"), ("b", "c")]) == "bc"


# --- copy_scrubbed -------------------------------------------------------------------------------------------------
def test_copy_scrubs_text_of_any_size_renames_paths_copies_binaries_and_never_follows_links(tmp_path):
    src, dest, secret = tmp_path / "src", tmp_path / "dest", tmp_path / "secret.txt"
    secret.write_text("speckit private")
    (src / ".specify" / "memory").mkdir(parents=True)
    (src / ".specify" / "memory" / "constitution.md").write_text("speckit rules")
    (src / "blob.bin").write_bytes(b"\xff\xfespeckit\x00")
    (src / "big.txt").write_text("speckit line\n" * 100_000)          # > 1 MB of text: scrubbed too (I2)
    (src / "big.bin").write_bytes(b"speckit\n" * 200_000 + b"\xff\xfe")   # > 1 MB, not UTF-8 at the end: raw, listed
    os.symlink(secret, src / "link-speckit")
    os.symlink(src, src / "loop")
    listed = an.copy_scrubbed(src, dest, an.scrub_terms("speckit"))
    got = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
    assert got == {"spec/memory/constitution.md", "blob.bin", "big.txt", "big.bin", "link-method.symlink",
                   "loop.symlink"}
    assert (dest / "spec/memory/constitution.md").read_text() == "method rules"
    assert (dest / "blob.bin").read_bytes() == b"\xff\xfespeckit\x00"
    assert listed == ["big.bin", "blob.bin"]
    assert (dest / "big.txt").read_text() == "method line\n" * 100_000
    assert (dest / "big.bin").read_bytes() == (src / "big.bin").read_bytes()
    assert not any(p.is_symlink() for p in dest.rglob("*"))
    assert "speckit private" not in "".join(p.read_text(errors="replace") for p in dest.rglob("*") if p.is_file())     # the target's content is never read


def test_two_files_whose_scrubbed_paths_collide_both_survive(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    for d in ("specs", ".specify"):
        (src / d).mkdir(parents=True)
        (src / d / "x.md").write_text("content of " + d.strip("."))
    an.copy_scrubbed(src, dest, an.scrub_terms("speckit"))
    assert sorted(p.name for p in (dest / "spec").iterdir()) == ["x.md", "x.md~2"]
    assert {p.read_text() for p in (dest / "spec").iterdir()} == {"content of specs", "content of specify"}


# --- run(): the whole pass over the mini fixture with a fake export tree --------------------------------------------
TOKEN = {"speckit": "qs1", "control": "qc1"}      # identity-free markers (an arm name would be scrubbed)
SHA = {"before": "b" * 40, "after": "a" * 40}


def _stream(path: Path, texts: list[str], tools: list[tuple[str, dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [{"type": "text", "text": t} for t in texts] + [{"type": "tool_use", "name": n, "input": i} for n, i in tools]
    with gzip.open(path, "wt") as g:
        g.write(json.dumps({"type": "assistant", "message": {"content": blocks}}) + "\n")
        g.write(json.dumps({"type": "result", "duration_ms": 1}) + "\n")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """results/p1 = the mini fixture with alpha renamed to the real arm `speckit` (control stays), a real config for
    speckit, git.json shas, owner gates, and gitops faked to write a tree full of identifying names."""
    root = tmp_path / "results"
    monkeypatch.setattr(paths, "RESULTS", root)
    pd = root / "p1"
    shutil.copytree(MINI, pd)
    (pd / "alpha").rename(pd / "speckit")
    for arm in ("speckit", "control"):
        for nn in ("01", "02"):
            d = pd / arm / nn
            if not d.is_dir():
                continue
            (d / "git.json").write_text(json.dumps({"sha_before": SHA["before"], "sha_after": SHA["after"]}))
            (d / "owner-gates.jsonl").write_text(json.dumps(
                {"attempt": 1, "n": 1, "kind": "approval", "arm_message": f"{arm} plan via /speckit-plan?",
                 "po_verdict": "ok, bakeoff-specs-speckit", "final_reply": "go", "owner_action": "accept",
                 "approved": True}) + "\n")
            (d / "questions.jsonl").write_text(json.dumps(
                {"n": 1, "kind": "clarify", "answered_by": "po", "arm_message": f"{arm}: which .specify/ file?",
                 "reply": f"unique-{TOKEN[arm]}-question reply"}) + "\n")
            _stream(d / "turns" / "arm-a9-001.stream.jsonl.gz", [f"Using speckit; marker {TOKEN[arm]}"],
                    [("Write", {"file_path": "/work/bakeoff-specs-speckit/.specify/x.md"})])

    def export(p, sha, dest):
        assert sha == SHA["after"]
        (dest / ".specify").mkdir(parents=True)
        (dest / ".specify" / "notes.md").write_text(f"{p.arm} speckit /speckit-plan bakeoff-specs-{p.arm}\n"
                                                    "Co-Authored-By: Bot <b@x>\n")
        (dest / "specs").mkdir()
        (dest / "specs" / "spec.md").write_text("openspec ccsdd superpowers speckitty github/spec-kit")
        (dest / "src").mkdir()
        (dest / "src" / "a.py").write_text("print('control group')\n")

    monkeypatch.setattr(gitops, "export_tree", export)
    monkeypatch.setattr(gitops, "commit_log", lambda p, a, b: [
        ("abc1234", "Plan lineage (OpenSpec change config-lineage) in bakeoff-specs-speckit-pass1#2",
         "Why: the /speckit-plan step via kitty/mission-x.\n\nCo-Authored-By: Claude <noreply@x>\n"
         "Claude-Session: https://claude.ai/code/session_1"),
        ("def5678", "Fix alias set", "")])
    monkeypatch.setattr(gitops, "diff_text", lambda p, a, b: (
        "diff --git a/.specify/notes.md b/.specify/notes.md\n+Claude-Session: https://x\n+speckit /opsx:apply\n"))
    return pd


def _all_text(anon: Path) -> str:
    return "\n".join(f.relative_to(anon).as_posix() + "\n" + f.read_text(errors="replace")
                     for f in sorted(anon.rglob("*")) if f.is_file())


def test_run_writes_labelled_dirs_with_every_artefact_and_the_key_after_the_export(world, monkeypatch):
    seen = []
    real = gitops.export_tree
    monkeypatch.setattr(gitops, "export_tree", lambda p, sha, dest: (seen.append((paths.scoring_out("p1") / "anon-key.json").exists()),
                                                                    real(p, sha, dest)))
    anon = an.run("p1")
    assert seen and not any(seen)                 # no key while any export is still to come
    out = paths.scoring_out("p1")
    key = an.read_key("p1")
    assert sorted(key.values()) == ["control", "speckit"] and sorted(key) == ["Arm A", "Arm B"]
    assert sorted(p.name for p in anon.iterdir()) == ["Arm A", "Arm B"]          # only labelled dirs under anon/
    assert not (anon / "anon-key.json").exists() and not (out / "anon-tmp").exists()
    lab = {v: k for k, v in key.items()}["speckit"]
    step = anon / lab / "01"
    assert sorted(p.name for p in step.iterdir()) == [
        "commits.md", "diff.patch", "gates.md", "others-questions.md", "questions.md", "repo", "transcript.md"]
    assert (step / "repo" / "spec" / "notes.md").read_text().startswith("speckit".replace("speckit", "method") + " method")


def test_fixture_leak_check_no_arm_tool_or_folder_name_survives_in_the_mini_fixture_run(world):
    anon = an.run("p1")
    text = _all_text(anon)
    banned = ["speckit", "spec-kit", "specify", "openspec", "opsx", "ccsdd", "kiro", "superpowers", "speckitty",
              "kittify", "kitty-specs", "bakeoff-specs-", "Co-Authored-By", "Claude-Session", "github/"]
    low = text.replace(".github/**", "").lower()        # the stale lists' generic legitimate path, not an owner/repo name
    assert [b for b in banned if b.lower() in low] == []
    assert not re.search(r"\bspecs/", text)                                   # the folder name, renamed to spec/
    assert "control group" in text                                            # the English word is left alone
    assert not any(p.is_symlink() for p in anon.rglob("*"))


def test_transcript_is_the_final_attempts_assistant_text_and_tool_calls_one_line_each(world):
    d = world / "speckit" / "01"
    _stream(d / "turns" / "arm-a1-001.stream.jsonl.gz", ["OLD ATTEMPT"], [])
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}["speckit"]
    tr = (anon / lab / "01" / "transcript.md").read_text()
    assert "OLD ATTEMPT" not in tr
    assert "assistant: Using method; marker qs1" in tr
    assert any(l.startswith("tool: Write ") and "spec/x.md" in l for l in tr.splitlines())


def test_others_questions_lists_only_the_other_arms_under_their_anonymous_label(world):
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}
    mine = (anon / lab["speckit"] / "01" / "others-questions.md").read_text()
    assert f"## {lab['control']}" in mine and "unique-qc1-question" in mine
    assert "unique-qs1-question" not in mine and f"## {lab['speckit']}" not in mine
    theirs = (anon / lab["control"] / "01" / "others-questions.md").read_text()
    assert "unique-qs1-question" in theirs and "unique-qc1-question" not in theirs


def test_the_other_arms_questions_are_scrubbed_too(world):
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}
    theirs = (anon / lab["control"] / "01" / "others-questions.md").read_text()
    assert ".specify" not in theirs and "which spec/ file" in theirs


def test_a_step_without_shas_gets_a_placeholder_not_a_crash_and_no_repo(world):
    (world / "control" / "01" / "git.json").write_text(json.dumps({"head": "0" * 40}))
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}["control"]
    step = anon / lab / "01"
    assert "no sha_before" in (step / "MISSING.md").read_text()
    assert not (step / "repo").exists() and not (step / "diff.patch").exists()
    assert json.loads((step / "MISSING.json").read_text()) == [
        {"files": ["repo/", "diff.patch", "commits.md"], "why": "git.json has no sha_before/sha_after for this step"}]


def test_a_failed_export_is_reported_and_the_run_still_finishes(world, monkeypatch, capsys):
    def boom(p, sha, dest):
        raise docker.ContainerError("export failed in container: /work/bakeoff-specs-control")
    monkeypatch.setattr(gitops, "export_tree", boom)
    anon = an.run("p1")
    assert "export failed" in capsys.readouterr().err
    steps = [d for d in anon.glob("Arm */0[12]")]
    assert steps and all((d / "MISSING.md").exists() and not (d / "diff.patch").exists() and not (d / "repo").exists()
                         for d in steps)
    assert not any("bakeoff-specs-control" in (d / "MISSING.md").read_text() for d in steps)
    assert not any("bakeoff-specs-control" in (d / "MISSING.json").read_text() for d in steps)   # scrubbed too
    assert all(json.loads((d / "MISSING.json").read_text())[0]["files"] == ["repo/", "diff.patch", "commits.md"]
               for d in steps)
    assert not any((d / "commits.md").exists() for d in steps)
    assert (paths.scoring_out("p1") / "anon-key.json").exists()


def test_a_rerun_is_byte_identical(world):
    def snap():
        out = paths.scoring_out("p1")
        return {f.relative_to(out).as_posix(): f.read_bytes() for f in sorted(out.rglob("*")) if f.is_file()}
    an.run("p1")
    first = snap()
    an.run("p1")
    assert snap() == first


def test_beads_folder_maps_to_tracker_and_the_name_is_gone():
    out = an.scrub("see .beads/issues.jsonl and .beads", an.scrub_terms("speckitty"))
    assert out == "see tracker/issues.jsonl and tracker"


def test_setup_records_are_anonymised_into_setup_and_unscrubbed_files_are_listed(world):
    for arm in ("speckit", "control"):
        s = world / arm / "00-setup"
        s.mkdir()
        (s / "versions.json").write_text('{"tool": "speckit 1.0"}')
    (world / "speckit" / "00-setup" / "blob.bin").write_bytes(b"\xff\xfe")
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}
    assert (anon / lab["speckit"] / "setup" / "versions.json").read_text() == '{"tool": "method 1.0"}'
    assert (anon / lab["speckit"] / "setup" / "UNSCRUBBED.txt").read_text().splitlines()[1:] == ["blob.bin"]
    assert not (anon / lab["control"] / "setup" / "UNSCRUBBED.txt").exists()
    assert not (anon / lab["speckit"] / "01" / "UNSCRUBBED.txt").exists()


def test_a_step_with_an_unscrubbed_file_lists_its_scrubbed_path(world, monkeypatch):
    def export(p, sha, dest):
        (dest / ".specify").mkdir(parents=True)
        (dest / ".specify" / "img.bin").write_bytes(b"\xff\xfe")
    monkeypatch.setattr(gitops, "export_tree", export)
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}["speckit"]
    assert "spec/img.bin" in (anon / lab / "01" / "UNSCRUBBED.txt").read_text()


# --- R-fix: real strings, aliases, word boundaries ----------------------------------------------------------------
REAL_STRINGS = [
    "Spec Kit", "Spec Kitty", "SPEC_KITTY", "spec-kitty", "kitty/mission-troupe-config-sync-files-01", "kitty-ops/x",
    "kitty-implement-review", "specify_cli", "Specify CLI", "beads", ".beads/issues.jsonl", "Beads",
    "bd create 'x'", "bd list --json", "bd close troupe-1", "bd show x", "bd ready", "bd update x", "bd dep add a b",
    "run `specify init .`", "OpenSpec", "Open Spec", "cc-sdd", "CC SDD", "obra/superpowers", "Obra", "Kiro",
    "bakeoff-specs-cc\u2026", "bakeoff-specs-speckitty/src", "bakeoff_specs_speckitty", "dolt sql-server", "Dolt", "a bead",
    # R26: after an escaped newline, tab, return or quote (JSON text and transcript lines)
    "x\\nKiro-style Spec-Driven Development", "x\\nbd create --title=x", "x\\nbd remember --key k", "x\\nbd ready",
    "x\\nbd show x", "x\\nbd update x", "x\\nbd close x", "x\\nbd dep add a b", "x\\nbeads here", "x\\nSpec Kit is",
    "x\\nCC-SDD", "x\\nObra wrote", "x\\nkitty/x", "x\\tkitty", "x\\rBeads", '{"a": "\\"Kiro\\""}', "x\\n/speckit-plan",
    "x\\nspeckit-plan", "x\\nspecify init .",
]


def test_real_name_variants_and_aliases_from_the_snapshot_are_scrubbed():
    t = an.pass_terms(["speckit", "speckitty", "ccsdd", "openspec", "superpowers", "control"])
    for s in REAL_STRINGS:
        out = an.scrub(s, t).lower()
        for banned in ("spec kit", "spec_kit", "kitty", "specify_cli", "specify cli", "beads", "bd ", "open spec",
                       "cc sdd", "cc-sdd", "obra", "kiro", "bakeoff-specs-", "bakeoff_specs", "dolt", "bead"):
            assert banned not in out, (s, out)
        assert not re.search(r"(?<![a-z0-9])(?:bd|speckit|openspec|spec-kitty)(?![a-z0-9])", out.replace("\\n", " ")), (s, out)


def test_short_aliases_match_on_word_boundaries_only():
    t = an.pass_terms(["superpowers", "speckitty"])
    assert an.scrub("a cobra and a bdelloid and Kittyhawk and abd", t) == "a cobra and a bdelloid and Kittyhawk and abd"
    assert an.scrub("Obra wrote it; the kitty/x branch; use bd now", t) == "method wrote it; the method/x branch; use tracker-cli now"



def test_the_tracker_cli_inside_shell_identifiers_is_scrubbed_as_the_leak_check_reads_it():   # pass 1 leak-check
    from runner.scoring import leakcheck
    t = an.pass_terms(["speckit", "speckitty", "ccsdd", "openspec", "superpowers", "control"])
    hook = ('export BD_GIT_HOOK=1\n_bd_timeout=${tracker_HOOK_TIMEOUT:-300}\ncase "$_bd_timeout" in\n'
            '# All settings can also be set via environment variables (BD_* prefix)\n')
    out = an.scrub(hook, t)
    assert not leakcheck.hits(out.lower(), "bd"), out
    assert an.scrub("a cobra and a bdelloid and abd and bd2", t) == "a cobra and a bdelloid and abd and bd2"

def test_english_specify_is_left_alone_but_the_cli_forms_go():
    t = an.pass_terms(["speckit"])
    assert an.scrub("specify it clearly", t) == "specify it clearly"
    assert "specify" not in an.scrub("run specify init and specify_cli", t)


def test_a_trailer_after_an_escaped_newline_is_removed_from_a_transcript(world):
    d = world / "speckit" / "01"
    _stream(d / "turns" / "arm-a9-001.stream.jsonl.gz", [],
            [("Bash", {"command": 'git commit -m "msg\n\nCo-Authored-By: Bot <b@x>\nClaude-Session: https://s/1"'})])
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}["speckit"]
    tr = (anon / lab / "01" / "transcript.md").read_text()
    assert "git commit -m" in tr and "Co-Authored-By" not in tr and "Claude-Session" not in tr


def test_scrubbing_precedes_truncation_so_a_repo_name_cannot_survive_cut_in_half(world):
    d = world / "speckit" / "01"
    cmd = "x" * 1990 + " /work/bakeoff-specs-speckitty/y"
    _stream(d / "turns" / "arm-a9-001.stream.jsonl.gz", [], [("Bash", {"command": cmd})])
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}["speckit"]
    assert "bakeoff-specs" not in (anon / lab / "01" / "transcript.md").read_text()


def test_a_truncated_repo_name_family_is_scrubbed():
    t = an.pass_terms(["control"])
    assert an.scrub("/work/bakeoff-specs-cc\u2026 and bakeoff-specs-x.", t) == "/work/repo and repo."


def test_setup_gz_streams_are_gunzipped_scrubbed_and_never_copied_raw(tmp_path):
    src, dest = tmp_path / "setup", tmp_path / "out"
    (src / "turns").mkdir(parents=True)
    with gzip.open(src / "turns" / "setup-a1-001.stream.jsonl.gz", "wt") as g:
        g.write('{"x": "speckit /speckit-plan\\n\\nCo-Authored-By: B <b@x>"}\n')
    (src / "turns" / "bad.gz").write_bytes(b"not gzip")
    listed = an.copy_scrubbed(src, dest, an.pass_terms(["speckit"]))
    assert not list(dest.rglob("*.gz"))
    text = (dest / "turns" / "setup-a1-001.stream.jsonl").read_text()
    assert "speckit" not in text and "Co-Authored" not in text and "method" in text
    assert listed == ["turns/bad.gz (left out: not readable as text)"]


# --- R25 -----------------------------------------------------------------------------------------------------------
def test_with_a_run_record_and_no_questions_file_the_arm_asked_no_questions(world):
    (world / "speckit" / "01" / "questions.jsonl").unlink()
    (world / "speckit" / "01" / "a" / "questions.jsonl").unlink()
    anon = an.run("p1")
    key = an.read_key("p1")
    lab = {v: k for k, v in key.items()}["speckit"]
    step = anon / lab / "01"
    assert "## Scored run" in (step / "questions.md").read_text()
    assert "The arm asked no questions at this step." in (step / "questions.md").read_text()
    assert not (step / "MISSING.md").exists()
    assert not (step / "MISSING.json").exists()


def test_without_a_run_record_questions_gates_and_transcript_are_listed_missing_not_written(world):
    d = world / "control" / "01"
    (d / "run.json").unlink()
    shutil.rmtree(d / "turns")
    anon = an.run("p1")
    key = an.read_key("p1")
    step = anon / {v: k for k, v in key.items()}["control"] / "01"
    assert not any((step / n).exists() for n in ("questions.md", "gates.md", "transcript.md"))
    miss = (step / "MISSING.md").read_text()
    assert "questions.md" in miss and "gates.md" in miss and "transcript.md" in miss
    listed = [f for e in json.loads((step / "MISSING.json").read_text()) for f in e["files"]]
    assert sorted(listed) == ["gates.md", "questions.md", "transcript.md"]


def test_each_step_with_a_stale_list_gets_it_as_stale_list_toml_and_step_1_does_not(world):
    anon = an.run("p1")
    for lab in ("Arm A", "Arm B"):
        assert not (anon / lab / "01" / "stale-list.toml").exists()
        got = anon / lab / "02" / "stale-list.toml"
        if (anon / lab / "02").is_dir():
            assert got.read_text() == (paths.SCORING_INPUTS / "stale" / "step-02.toml").read_text()
    assert any((anon / lab / "02").is_dir() for lab in ("Arm A", "Arm B"))


def test_only_a_discovery_file_still_gets_a_scored_run_heading_and_skipped_lines_show(world):
    d = world / "speckit" / "01"
    (d / "questions.jsonl").write_text("not json\n")
    anon = an.run("p1")
    key = an.read_key("p1")
    text = (anon / {v: k for k, v in key.items()}["speckit"] / "01" / "questions.md").read_text()
    assert "## Scored run" in text and "1 malformed line(s) skipped" in text and "## Discovery run" in text


def test_residual_vocabulary_is_listed_and_not_scrubbed():
    t = an.pass_terms(["ccsdd", "speckitty"])
    for w in ("steering", "mission", "claude-plugins-official"):
        assert w in an.RESIDUAL_VOCABULARY
        assert an.scrub(w, t) == w


# --- the general claim: the real pass-1 snapshot -------------------------------------------------------------------
def test_open_specification_in_plain_english_survives_but_the_tool_name_does_not():
    t = an.pass_terms(["openspec"])
    assert an.scrub("an open specification and open specs", t) == "an open specification and open specs"
    assert an.scrub("Open Spec and OpenSpec", t) == "method and method"


# --- the general claim, checked WITHOUT the implementation's regexes (runner/scoring/leakcheck.py) -----------------
_forms, _hits = leakcheck.forms, leakcheck.hits


def test_real_pass1_transcripts_questions_gates_and_setup_hold_no_name_alias_or_cli_in_any_form(tmp_path):
    """Scope: transcript.md text, questions, gates and the 00-setup copy of results/pass1. NOT repo trees or diffs:
    those are checked by the `leak-check` stage over the written anon/ tree after pass 1 (run book)."""
    pass_dir = paths.RESULTS / "pass1"
    if not pass_dir.is_dir():
        pytest.skip(f"{pass_dir} absent (results/pass1 snapshot not present)")
    from runner.scoring import collect
    arms = collect.arms(pass_dir)
    t = an.pass_terms(arms)
    words = leakcheck.words(arms)
    assert {"kitty", "beads", "obra", "ccsdd", "openspec", "kiro"} <= set(words)
    texts: list[tuple[str, str]] = []
    for arm in arms:
        for nn in an._step_dirs(pass_dir / arm):
            sd = pass_dir / arm / nn
            texts.append((f"{arm}/{nn}/transcript", an.transcript(sd, t) or ""))
            if an._ran(sd):
                texts += [(f"{arm}/{nn}/questions", an.scrub(an.questions_md(sd), t)),
                          (f"{arm}/{nn}/gates", an.scrub(an.gates_md(sd), t))]
        if (pass_dir / arm / "00-setup").is_dir():
            dest = tmp_path / arm
            an.copy_scrubbed(pass_dir / arm / "00-setup", dest, t)
            assert not list(dest.rglob("*.gz"))
            texts += [(f.relative_to(tmp_path).as_posix(), f.read_text(errors="replace"))
                      for f in dest.rglob("*") if f.is_file()]
    assert len(texts) > 20
    leaks = sorted({(where, w) for where, text in texts for w in words if _hits(text.lower(), w)})
    assert leaks == []


def test_an_unreadable_scored_questions_file_is_not_shown_as_asked_none(tmp_path):
    (tmp_path / "questions.jsonl").write_bytes(b'{"n": 1}\n\xff\n')
    text = an.questions_md(tmp_path)
    assert "could not be read" in text and "asked no questions" not in text


def test_anon_tmp_is_removed_even_when_the_run_fails_midway(world, monkeypatch):
    def boom(p, sha, dest):
        (dest / "half").mkdir(parents=True)
        (dest / "half" / "x.txt").write_text("speckit")
        raise RuntimeError("container went away")
    monkeypatch.setattr(gitops, "export_tree", boom)
    with pytest.raises(RuntimeError):
        an.run("p1")
    assert not (paths.scoring_out("p1") / "anon-tmp").exists()


# --- R37: a random salt, kept while a key exists -----------------------------------------------------------------------
def _raw_key():
    return json.loads((paths.scoring_out("p1") / "anon-key.json").read_text())


def test_the_key_stores_a_random_salt_and_labels_are_the_arms_shuffled_by_it(world, monkeypatch):
    monkeypatch.setattr(an.secrets, "token_hex", lambda n: "f" * (2 * n))
    an.run("p1")
    k = _raw_key()
    assert k["salt"] == "f" * 32
    assert {a: lab for lab, a in k["labels"].items()} == an.labels(["control", "speckit"], "f" * 32)


def test_a_rerun_reuses_the_keys_salt_and_a_missing_key_draws_a_new_one(world, monkeypatch):
    salts = iter(["a" * 32, "b" * 32])
    monkeypatch.setattr(an.secrets, "token_hex", lambda n: next(salts))
    an.run("p1")
    first = (paths.scoring_out("p1") / "anon-key.json").read_bytes()
    an.run("p1")
    assert (paths.scoring_out("p1") / "anon-key.json").read_bytes() == first          # same salt, same labels
    (paths.scoring_out("p1") / "anon-key.json").unlink()
    an.run("p1")
    assert _raw_key()["salt"] == "b" * 32


def test_a_rerun_that_crashes_keeps_the_salt_for_the_next_run(world, monkeypatch):
    monkeypatch.setattr(an.secrets, "token_hex", lambda n: "c" * (2 * n))
    an.run("p1")
    monkeypatch.setattr(an.secrets, "token_hex", lambda n: "d" * (2 * n))
    real = gitops.export_tree
    monkeypatch.setattr(gitops, "export_tree", lambda p, sha, dest: (_ for _ in ()).throw(RuntimeError("gone")))
    with pytest.raises(RuntimeError):
        an.run("p1")
    assert not (paths.scoring_out("p1") / "anon-key.json").exists()               # no key for a half-written tree
    monkeypatch.setattr(gitops, "export_tree", real)
    an.run("p1")
    assert _raw_key()["salt"] == "c" * 32 and not (paths.scoring_out("p1") / "anon-key.json.prev").exists()


def test_a_key_from_before_salts_keeps_its_pass_seeded_labels(world):
    out = paths.scoring_out("p1")
    out.mkdir(parents=True, exist_ok=True)
    legacy = {lab: a for a, lab in an.labels(["control", "speckit"], "p1").items()}
    (out / "anon-key.json").write_text(json.dumps(legacy))
    an.run("p1")
    assert _raw_key() == {"salt": "p1", "labels": legacy}


def test_rerunning_anonymise_deletes_a_stale_leak_check_json(world):
    """R39: leak-check.json describes the anon/ tree it was run over; a new anonymise makes a new tree, so the old
    verdict must not survive to show a stale 'clean' in the report."""
    lc = paths.scoring_out("p1") / "leak-check.json"
    lc.parent.mkdir(parents=True, exist_ok=True)
    lc.write_text('{"hits": [], "files": 3}')
    an.run("p1")
    assert not lc.exists()


def test_a_failed_anonymise_run_also_leaves_no_stale_leak_check_json(world, monkeypatch):
    lc = paths.scoring_out("p1") / "leak-check.json"
    lc.parent.mkdir(parents=True, exist_ok=True)
    lc.write_text('{"hits": [], "files": 3}')
    monkeypatch.setattr(an, "labels", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        an.run("p1")
    assert not lc.exists()


# --- commits.md (owner, 2026-10-10): the step's commit messages for change_reason and test_names --------------------
def test_commits_md_has_every_commit_subject_and_body_scrubbed_of_names_and_trailers(world):
    anon = an.run("p1")
    lab = {v: k for k, v in an.read_key("p1").items()}["speckit"]
    c = (anon / lab / "01" / "commits.md").read_text()
    assert "## abc1234 Plan lineage" in c and "## def5678 Fix alias set" in c and "Why: the" in c
    low = c.lower()
    assert not any(w in low for w in ("openspec", "speckit", "kitty", "bakeoff-specs", "co-authored-by",
                                       "claude-session"))
    assert leakcheck.check(anon, ["speckit", "control"]) == []


def test_commits_md_for_an_empty_range_says_so():
    assert "No commits in this step's range." in an.commits_md([])


def _tree_digest(anon: Path, skip: str = "commits.md") -> dict[str, str]:
    import hashlib
    return {f.relative_to(anon).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(anon.rglob("*")) if f.is_file() and f.name != skip}


def test_add_commits_writes_only_commits_md_under_the_existing_labels(world, monkeypatch):
    anon = an.run("p1")
    key_before = an.key_path("p1").read_bytes()
    for f in anon.rglob("commits.md"):
        f.unlink()
    before = _tree_digest(anon)
    (paths.scoring_out("p1") / "leak-check.json").write_text("{}")
    assert an.add_commits("p1") == []
    assert _tree_digest(anon) == before and an.key_path("p1").read_bytes() == key_before
    assert len(list(anon.rglob("commits.md"))) == len([d for d in anon.glob("Arm */0[0-9]")])
    assert not (paths.scoring_out("p1") / "leak-check.json").exists()       # R39: the tree changed


def test_add_commits_refuses_without_a_key_and_names_failed_steps(world, monkeypatch):
    with pytest.raises(FileNotFoundError):
        an.add_commits("p1")
    an.run("p1")
    monkeypatch.setattr(gitops, "commit_log", lambda p, a, b: (_ for _ in ()).throw(docker.ContainerError("boom")))
    fails = an.add_commits("p1")
    assert fails and all("boom" in f for f in fails)
