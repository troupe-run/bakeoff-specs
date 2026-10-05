import gzip
import json
import os
import re
import shutil
from pathlib import Path
import pytest
from runner import docker, gitops, paths
from runner.scoring import anonymise as an

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
    for arm in ("ccsdd", "superpowers", "speckit", "speckitty", "openspec", "control"):
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
def test_copy_scrubs_text_renames_paths_copies_binaries_and_never_follows_links(tmp_path):
    src, dest, secret = tmp_path / "src", tmp_path / "dest", tmp_path / "secret.txt"
    secret.write_text("speckit private")
    (src / ".specify" / "memory").mkdir(parents=True)
    (src / ".specify" / "memory" / "constitution.md").write_text("speckit rules")
    (src / "blob.bin").write_bytes(b"\xff\xfespeckit\x00")
    (src / "big.txt").write_text("speckit " * 200_000)                # > 1 MB: copied as is
    os.symlink(secret, src / "link-speckit")
    os.symlink(src, src / "loop")
    an.copy_scrubbed(src, dest, an.scrub_terms("speckit"))
    got = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
    assert got == {"spec/memory/constitution.md", "blob.bin", "big.txt", "link-method.symlink", "loop.symlink"}
    assert (dest / "spec/memory/constitution.md").read_text() == "method rules"
    assert (dest / "blob.bin").read_bytes() == b"\xff\xfespeckit\x00"
    assert (dest / "big.txt").stat().st_size == (src / "big.txt").stat().st_size
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
    monkeypatch.setattr(gitops, "diff_text", lambda p, a, b: (
        "diff --git a/.specify/notes.md b/.specify/notes.md\n+Claude-Session: https://x\n+speckit /opsx:apply\n"))
    return pd


def _all_text(anon: Path) -> str:
    return "\n".join(f.relative_to(anon).as_posix() + "\n" + f.read_text(errors="replace")
                     for f in sorted(anon.rglob("*")) if f.is_file())


def test_run_writes_labelled_dirs_with_every_artefact_and_the_key_last(world):
    anon = an.run("p1")
    out = paths.scoring_out("p1")
    key = json.loads((out / "anon-key.json").read_text())
    assert sorted(key.values()) == ["control", "speckit"] and sorted(key) == ["Arm A", "Arm B"]
    assert sorted(p.name for p in anon.iterdir()) == ["Arm A", "Arm B"]          # only labelled dirs under anon/
    assert not (anon / "anon-key.json").exists() and not (out / "anon-tmp").exists()
    lab = {v: k for k, v in key.items()}["speckit"]
    step = anon / lab / "01"
    assert sorted(p.name for p in step.iterdir()) == [
        "diff.patch", "gates.md", "others-questions.md", "questions.md", "repo", "transcript.md"]
    assert (step / "repo" / "spec" / "notes.md").read_text().startswith("speckit".replace("speckit", "method") + " method")


def test_leak_check_no_arm_tool_or_folder_name_survives_anywhere_under_anon(world):
    anon = an.run("p1")
    text = _all_text(anon)
    banned = ["speckit", "spec-kit", "specify", "openspec", "opsx", "ccsdd", "kiro", "superpowers", "speckitty",
              "kittify", "kitty-specs", "bakeoff-specs-", "Co-Authored-By", "Claude-Session", "github/"]
    low = text.lower()
    assert [b for b in banned if b.lower() in low] == []
    assert not re.search(r"\bspecs/", text)                                   # the folder name, renamed to spec/
    assert "control group" in text                                            # the English word is left alone
    assert not any(p.is_symlink() for p in anon.rglob("*"))


def test_transcript_is_the_final_attempts_assistant_text_and_tool_calls_one_line_each(world):
    d = world / "speckit" / "01"
    _stream(d / "turns" / "arm-a1-001.stream.jsonl.gz", ["OLD ATTEMPT"], [])
    anon = an.run("p1")
    key = json.loads((paths.scoring_out("p1") / "anon-key.json").read_text())
    lab = {v: k for k, v in key.items()}["speckit"]
    tr = (anon / lab / "01" / "transcript.md").read_text()
    assert "OLD ATTEMPT" not in tr
    assert "assistant: Using method; marker qs1" in tr
    assert any(l.startswith("tool: Write ") and "spec/x.md" in l for l in tr.splitlines())


def test_others_questions_lists_only_the_other_arms_under_their_anonymous_label(world):
    anon = an.run("p1")
    key = json.loads((paths.scoring_out("p1") / "anon-key.json").read_text())
    lab = {v: k for k, v in key.items()}
    mine = (anon / lab["speckit"] / "01" / "others-questions.md").read_text()
    assert f"## {lab['control']}" in mine and "unique-qc1-question" in mine
    assert "unique-qs1-question" not in mine and f"## {lab['speckit']}" not in mine
    theirs = (anon / lab["control"] / "01" / "others-questions.md").read_text()
    assert "unique-qs1-question" in theirs and "unique-qc1-question" not in theirs


def test_the_other_arms_questions_are_scrubbed_too(world):
    anon = an.run("p1")
    key = json.loads((paths.scoring_out("p1") / "anon-key.json").read_text())
    lab = {v: k for k, v in key.items()}
    theirs = (anon / lab["control"] / "01" / "others-questions.md").read_text()
    assert ".specify" not in theirs and "which spec/ file" in theirs


def test_a_step_without_shas_gets_a_placeholder_not_a_crash_and_no_repo(world):
    (world / "control" / "01" / "git.json").write_text(json.dumps({"head": "0" * 40}))
    anon = an.run("p1")
    key = json.loads((paths.scoring_out("p1") / "anon-key.json").read_text())
    lab = {v: k for k, v in key.items()}["control"]
    assert (anon / lab / "01" / "diff.patch").read_text().startswith("(no commit recorded")
    assert not (anon / lab / "01" / "repo").exists()


def test_a_failed_export_is_reported_and_the_run_still_finishes(world, monkeypatch, capsys):
    def boom(p, sha, dest):
        raise docker.ContainerError("export failed in container: /work/bakeoff-specs-control")
    monkeypatch.setattr(gitops, "export_tree", boom)
    an.run("p1")
    assert "export failed" in capsys.readouterr().err
    assert (paths.scoring_out("p1") / "anon-key.json").exists()


def test_a_rerun_is_byte_identical(world):
    def snap():
        out = paths.scoring_out("p1")
        return {f.relative_to(out).as_posix(): f.read_bytes() for f in sorted(out.rglob("*")) if f.is_file()}
    an.run("p1")
    first = snap()
    an.run("p1")
    assert snap() == first
