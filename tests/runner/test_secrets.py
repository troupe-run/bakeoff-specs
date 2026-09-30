"""Task 21 (review S-2): secret scan of evidence, results, snapshots and everything publish pushes.

Every token here is FAKE and assembled at runtime, so this file itself never matches a pattern (the pre-commit
hook scans it too)."""
import ast, base64, bz2, gzip, hashlib, io, lzma, os, re, subprocess, threading, zipfile
from pathlib import Path

import pytest

from runner import cli, credentials, faults, gitops, paths, repo, secrets
from runner.paths import Paths

PAT = "github_pat_" + "A" * 22 + "_" + "b" * 59
GHO = "gh" + "o_" + "Z" * 36
ANT = "sk-ant-oat01-" + "x" * 40
KEY = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"
OAUTH = "fake-oauth-" + "q" * 30                      # the keychain token has no known shape: found as a literal
HOME_PAT = "fakepat" + "9" * 30                        # a PAT value with no known shape, only in the arm's hosts.yml
KC_PAT = "fakekeychainpat" + "4" * 30                  # the arm's keychain PAT item (`bakeoff-gh-<pass>-<arm>`)
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_real_keychain(monkeypatch):
    """No test reads the real keychain: every lookup fails unless a test installs a fake."""
    def absent(*a, **k):
        raise RuntimeError("no keychain in tests")
    monkeypatch.setattr(credentials, "from_keychain", absent)
    monkeypatch.setattr(credentials, "github_pat", absent)
    secrets.clear_keychain_cache()                     # the per-process cache must not leak between tests
    yield
    secrets.clear_keychain_cache()


# --- the brief's five ---------------------------------------------------------------------------------------

def test_a_pat_in_a_plain_file_is_found_by_path_and_kind_only(tmp_path):
    (tmp_path / "t.jsonl").write_text(f'{{"text": "token {PAT}"}}\n')
    [f] = secrets.scan_tree(tmp_path)
    assert f.path.endswith("t.jsonl") and f.kind == "github-pat" and f.line == 1 and PAT not in repr(f)


def test_a_token_inside_a_gz_is_found(tmp_path):
    with gzip.open(tmp_path / "s.stream.jsonl.gz", "wt") as fh:
        fh.write("ok\n" + ANT + "\n")
    assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["anthropic-token"]


def test_a_literal_value_is_found_even_without_a_known_shape(tmp_path):
    (tmp_path / "a.txt").write_text("hello dry-run-dummy-token\n")
    assert [f.kind for f in secrets.scan_tree(tmp_path, ["dry-run-dummy-token"])] == ["literal"]


def test_symlinks_are_not_followed(tmp_path):
    (tmp_path / "outside").mkdir(); (tmp_path / "outside" / "k").write_text(PAT)
    (tmp_path / "tree").mkdir(); os.symlink(tmp_path / "outside" / "k", tmp_path / "tree" / "k")
    assert secrets.scan_tree(tmp_path / "tree") == []


def test_a_clean_tree_has_no_findings(tmp_path):
    (tmp_path / "a.md").write_text("github_pat is a word here, and so is sk-ant.\n")
    assert secrets.scan_tree(tmp_path) == []


# --- every pattern, line numbers, names ----------------------------------------------------------------------

@pytest.mark.parametrize("text,kind", [(PAT, "github-pat"), (GHO, "github-token"), (ANT, "anthropic-token"),
                                       (KEY, "private-key")])
def test_every_pattern_kind_is_found(tmp_path, text, kind):
    (tmp_path / "x.log").write_text(f"a\nb\nsee {text} here\n")
    assert [(f.kind, f.line) for f in secrets.scan_tree(tmp_path)] == [(kind, 3)]


def test_a_token_split_across_read_chunks_is_found_with_its_true_line(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets, "CHUNK_BYTES", 64)
    body = "".join(f"line {i}\n" for i in range(1, 40)) + "x" * 50 + PAT + "\n"
    (tmp_path / "big.txt").write_text(body)
    assert [(f.kind, f.line) for f in secrets.scan_tree(tmp_path)] == [("github-pat", 40)]


def test_a_secret_in_a_file_name_is_found(tmp_path):
    (tmp_path / f"note-{GHO}.txt").write_text("nothing\n")
    [f] = secrets.scan_tree(tmp_path)
    assert f.kind == "github-token" and f.line == 0
    assert GHO not in f.path and f.path.endswith("note-<redacted>.txt")   # named, but never printed


def test_a_literal_in_a_history_path_is_redacted_too(tmp_path):
    h = tmp_path / "h.fe"
    h.write_bytes(b"blob\nmark :1\noriginal-oid abc\ndata 2\nx\n\ncommit refs/heads/main\nmark :2\n"
                  b"original-oid def\nauthor a <a> 1 +0000\ncommitter a <a> 1 +0000\ndata 2\nm\n"
                  + f"M 100644 :1 {OAUTH}.txt\n".encode())
    found = secrets.scan_history(h, "main", [OAUTH])
    assert [f.kind for f in found] == ["literal"] and all(OAUTH not in f.path for f in found)


def test_a_symlink_target_text_is_scanned_without_following_it(tmp_path):
    os.symlink(f"/nowhere/{PAT}", tmp_path / "link")         # a link is published as its target text
    assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["github-pat"]


def test_a_fifo_never_blocks_the_scan(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    (tmp_path / "ok.txt").write_text(PAT)
    got = []
    t = threading.Thread(target=lambda: got.append(secrets.scan_tree(tmp_path)), daemon=True)
    t.start(); t.join(10)
    assert not t.is_alive(), "scan_tree blocked on a FIFO"
    assert [f.kind for f in got[0]] == ["github-pat"]       # a FIFO holds no content: nothing to report


def test_a_hard_linked_file_is_still_scanned(tmp_path):
    (tmp_path / "a").write_text(PAT); os.link(tmp_path / "a", tmp_path / "b")
    assert sorted(Path(f.path).name for f in secrets.scan_tree(tmp_path)) == ["a", "b"]


def test_an_unreadable_directory_fails_closed(tmp_path):
    d = tmp_path / "locked"; d.mkdir(); (d / "x").write_text(PAT); d.chmod(0)
    try:
        assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["unscannable"]
    finally:
        d.chmod(0o700)


def test_a_corrupt_gz_fails_closed(tmp_path):
    (tmp_path / "s.jsonl.gz").write_bytes(gzip.compress(b"ok\n" * 1000)[:-30])
    assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["unscannable"]


def test_a_gz_bomb_is_capped_and_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets, "SCAN_MAX_BYTES", 10_000)
    (tmp_path / "b.gz").write_bytes(gzip.compress(b"\0" * 1_000_000))
    assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["unscannable"]


def test_a_concatenated_gz_is_read_to_the_end(tmp_path):
    (tmp_path / "c.gz").write_bytes(gzip.compress(b"a\n") + gzip.compress(f"{ANT}\n".encode()))
    assert [(f.kind, f.line) for f in secrets.scan_tree(tmp_path)] == [("anthropic-token", 2)]


def test_scan_files_scans_exactly_the_given_files(tmp_path):
    (tmp_path / "a").write_text(PAT); (tmp_path / "b").write_text(PAT)
    assert [Path(f.path).name for f in secrets.scan_files([tmp_path / "a"])] == ["a"]


def test_empty_and_short_literals_are_ignored(tmp_path):
    (tmp_path / "a").write_text("abc\n")
    assert secrets.scan_tree(tmp_path, ["", "a"]) == []


# --- faults name the file, never the secret ------------------------------------------------------------------

def test_require_clean_raises_a_named_harness_fault_without_the_secret(tmp_path):
    (tmp_path / "t.jsonl").write_text(f"{OAUTH}\n")
    found = secrets.scan_tree(tmp_path, [OAUTH])
    with pytest.raises(faults.HarnessFault) as e:
        secrets.require_clean(found, "secret-in-evidence")
    assert e.value.kind == "secret-in-evidence" and e.value.signature == "literal"
    assert "t.jsonl:1 literal" in e.value.detail
    assert OAUTH not in f"{e.value!s}{e.value!r}{e.value.detail}{e.value.findings!r}"
    secrets.require_clean([], "secret-in-evidence")         # clean: no fault


# --- the needles: keychain token (via raw_for_scanner) and the arm-home PAT files ------------------------------

def _home_with_pat(state: Path, pass_="pass1", arm="control") -> Path:
    home = state / pass_ / arm / "home"
    (home / ".config" / "gh").mkdir(parents=True)
    (home / ".config" / "gh" / "hosts.yml").write_text(f"github.com:\n    oauth_token: {HOME_PAT}\n")
    return home


def test_literals_hold_the_dummy_the_credential_and_every_arm_home_pat(tmp_state):
    _home_with_pat(paths.STATE)
    lits = secrets.literals(credentials.Credential(OAUTH))
    assert set(lits) == {"dry-run-dummy-token", OAUTH, HOME_PAT}


def test_a_home_pat_file_that_is_a_symlink_is_not_read(tmp_state):
    home = paths.STATE / "pass1" / "control" / "home"
    (home / ".config" / "gh").mkdir(parents=True)
    secret = paths.STATE.parent / "elsewhere.yml"; secret.write_text(f"oauth_token: {HOME_PAT}\n")
    os.symlink(secret, home / ".config" / "gh" / "hosts.yml")
    assert HOME_PAT not in secrets.home_pat_values(home)


def test_a_short_home_value_never_becomes_a_needle(tmp_state):
    home = paths.STATE / "pass1" / "control" / "home"
    (home / ".config" / "gh").mkdir(parents=True)
    (home / ".config" / "gh" / "hosts.yml").write_text("github.com:\n    oauth_token: e\n")
    assert secrets.home_pat_values(home) == []               # an arm cannot make every file match


def test_a_literal_without_a_credential_falls_back_to_the_keychain(tmp_state, monkeypatch):
    monkeypatch.setattr(credentials, "from_keychain", lambda: credentials.Credential(OAUTH))
    assert OAUTH in secrets.literals()
    secrets.clear_keychain_cache()                           # lookups are cached per process
    def missing():
        raise RuntimeError("no item")
    monkeypatch.setattr(credentials, "from_keychain", missing)
    assert secrets.literals() == ["dry-run-dummy-token"]


def test_only_runner_secrets_calls_raw_for_scanner():                        # controller ruling (S-2)
    """AST: no Python file of the harness (tests aside) reads `raw_for_scanner` except runner/secrets.py; its
    definition lives in runner/credentials.py. A text check catches getattr(cred, "raw_for_scanner") too."""
    skip = {".venv", "tests", "state", "results", ".git", "node_modules"}
    offenders = []
    for f in REPO_ROOT.rglob("*.py"):
        rel = f.relative_to(REPO_ROOT)
        if skip & set(rel.parts[:-1]) or rel.as_posix() == "runner/secrets.py":
            continue
        text = f.read_text(errors="replace")
        if "raw_for_scanner" not in text:
            continue
        tree = ast.parse(text)
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "raw_for_scanner"]
        strings = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value == "raw_for_scanner"]
        defined_here = rel.as_posix() == "runner/credentials.py"
        if uses or strings or (not defined_here and "raw_for_scanner" in text):
            offenders.append(rel.as_posix())
    assert offenders == []
    assert "raw_for_scanner" in (REPO_ROOT / "runner" / "secrets.py").read_text()


def test_session_credential_files_still_finds_the_token_via_secrets(tmp_path):
    from runner import session
    cred = credentials.Credential(OAUTH)
    (tmp_path / "log.txt").write_text(f"x {OAUTH}\n")
    assert session.credential_files(tmp_path, cred, 0.0) == ["log.txt"]


# --- full history (fast-export stream) -----------------------------------------------------------------------

def _host_git(repo_dir: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True,
                          env=env).stdout.decode()


def _export(repo_dir: Path, dest: Path) -> Path:
    dest.write_bytes(subprocess.run(["git", "-C", str(repo_dir), "fast-export", "--all", "--show-original-ids",
                                     "--reencode=yes", "--signed-tags=verbatim"],
                                    check=True, capture_output=True).stdout)
    return dest


def test_history_scan_finds_a_secret_that_the_tip_tree_no_longer_has(tmp_path):
    r = tmp_path / "r"; r.mkdir()
    _host_git(r, "init", "-q", "-b", "main")
    (r / "cfg.txt").write_text(f"a\n{PAT}\n"); _host_git(r, "add", "-A"); _host_git(r, "commit", "-qm", "add")
    blob = _host_git(r, "rev-parse", "HEAD:cfg.txt").strip()
    (r / "cfg.txt").write_text("a\n"); _host_git(r, "commit", "-qam", "scrub")
    _host_git(r, "commit", "-q", "--allow-empty", "-m", f"note {GHO}")
    msg_commit = _host_git(r, "rev-parse", "HEAD").strip()
    found = secrets.scan_history(_export(r, tmp_path / "h.fe"), "main")
    by_kind = {f.kind: f for f in found}
    assert set(by_kind) == {"github-pat", "github-token"}
    assert by_kind["github-pat"].path == f"main: blob {blob} (cfg.txt)" and by_kind["github-pat"].line == 2
    assert by_kind["github-token"].path == f"main: commit {msg_commit} message"
    assert all(PAT not in repr(f) and GHO not in repr(f) for f in found)


def test_history_scan_reads_data_by_length_so_content_cannot_forge_commands(tmp_path):
    r = tmp_path / "r"; r.mkdir()
    _host_git(r, "init", "-q", "-b", "main")
    (r / "a.txt").write_text(f"data 3\nblob\nmark :9\n{ANT}\n"); _host_git(r, "add", "-A")
    _host_git(r, "commit", "-qm", "x")
    [f] = secrets.scan_history(_export(r, tmp_path / "h.fe"), "main")
    assert f.kind == "anthropic-token" and f.path.endswith("(a.txt)") and f.line == 4


def test_history_scan_of_a_missing_export_fails_closed(tmp_path):
    assert [f.kind for f in secrets.scan_history(None, "main")] == ["unscannable"]
    (tmp_path / "bad.fe").write_bytes(b"blob\nmark :1\ndata notanumber\n")
    assert [f.kind for f in secrets.scan_history(tmp_path / "bad.fe", "main")] == ["unscannable"]


def test_scan_publish_covers_tree_and_history(tmp_path):
    t = tmp_path / "tree"; t.mkdir(); (t / "ok.txt").write_text("fine\n")
    h = tmp_path / "h.fe"; h.write_bytes(b"blob\nmark :1\noriginal-oid abc\ndata 5\nfine\n\n")
    assert secrets.scan_publish(t, h, []) == []
    assert [f.kind for f in secrets.scan_publish(t, None, [])] == ["unscannable"]


# --- publish refuses on any finding, with a fault ------------------------------------------------------------

def _fake_publish_chain(monkeypatch, calls):
    def fake_bundle(p_, dest, refs=()):
        dest.write_bytes(b"# v2 git bundle\n"); calls.append("bundle"); return dest
    monkeypatch.setattr(gitops, "bundle", fake_bundle)
    monkeypatch.setattr(gitops, "clone_bundle_bare", lambda b, d: (d.mkdir(), calls.append(("clone", d))))
    monkeypatch.setattr(gitops, "bare_tree", lambda p_, bare, ref, dest: (dest.mkdir(), calls.append(("tree", bare)))[0] or dest)
    def fake_fe(p_, root, git_dirs, dest, *, revs=()):
        calls.append(("history", root, tuple(revs))); dest.mkdir(parents=True, exist_ok=True)
        (dest / "1.fe").write_bytes(b""); return [dest / "1.fe"]
    monkeypatch.setattr(gitops, "fast_export", fake_fe)
    monkeypatch.setattr(gitops, "push_from_bare", lambda bare, url, ref="main": calls.append(("push", bare)))


def test_publish_scans_tree_and_full_history_of_the_clone_it_pushes(tmp_state, monkeypatch):
    p = Paths("pass1", "control"); p.scratch.mkdir(parents=True)
    calls = []
    _fake_publish_chain(monkeypatch, calls)
    assert repo.publish(p, "pass1", ask=lambda q: True, scan=lambda t, h: calls.append(("scan", h)) or [])
    kinds = [c if isinstance(c, str) else c[0] for c in calls]
    assert kinds == ["bundle", "clone", "tree", "history", "scan", "push"]
    clone = calls[1][1]
    assert calls[2][1] == clone and calls[3][1] == clone and calls[5][1] == clone
    assert calls[3][2] == ("refs/heads/main",)


def test_publish_raises_secret_in_publish_and_never_pushes(tmp_state, monkeypatch):
    p = Paths("pass1", "control"); p.scratch.mkdir(parents=True)
    calls = []
    _fake_publish_chain(monkeypatch, calls)
    hit = [secrets.Finding("main: blob abc (cfg.txt)", "github-pat", 2)]
    with pytest.raises(secrets.SecretFound) as e:
        repo.publish(p, "pass1", ask=lambda q: True, scan=lambda t, h: hit)
    assert e.value.kind == "secret-in-publish" and "cfg.txt" in e.value.detail
    assert not [c for c in calls if isinstance(c, tuple) and c[0] == "push"]


def test_cli_publish_is_wired_to_the_scanner_and_reports_the_fault(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(secrets, "literals", lambda cred=None, **k: ["dry-run-dummy-token"])
    seen = {}
    def fake_publish(p_, pass_, ask, scan):
        t = tmp_state / "t"; t.mkdir(); (t / "x").write_text(PAT)
        seen["found"] = scan(t, None)
        raise secrets.SecretFound("secret-in-publish", seen["found"])
    monkeypatch.setattr(repo, "publish", fake_publish)
    assert cli.main(["publish", "pass1", "control"]) == 1
    out = capsys.readouterr().out
    assert "secret-in-publish" in out and "x:1 github-pat" in out and PAT not in out
    assert {f.kind for f in seen["found"]} == {"github-pat", "unscannable"}


# --- CLI `runner scan` and the pre-commit hook ---------------------------------------------------------------

def test_cli_scan_paths_prints_path_line_kind_and_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(secrets, "literals", lambda cred=None, **k: ["dry-run-dummy-token"])
    (tmp_path / "a.txt").write_text(f"x\n{ANT}\n")
    assert cli.main(["scan", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert f"{tmp_path / 'a.txt'}:2 anthropic-token" in out and ANT not in out
    (tmp_path / "a.txt").write_text("clean\n")
    assert cli.main(["scan", str(tmp_path), str(tmp_path / "a.txt")]) == 0


def _staging_repo(tmp_path, monkeypatch) -> Path:
    r = tmp_path / "h"; r.mkdir()
    _host_git(r, "init", "-q", "-b", "main")
    monkeypatch.setattr(gitops, "REPO_ROOT", r)
    monkeypatch.setattr(paths, "RESULTS", r / "results")
    return r


def test_the_staged_scan_reads_the_index_not_the_working_tree(tmp_path, monkeypatch, capsys):   # fix round 1 (2)
    monkeypatch.setattr(secrets, "literals", lambda cred=None, **k: ["dry-run-dummy-token"])
    r = _staging_repo(tmp_path, monkeypatch)
    (r / "a.txt").write_text(f"x\n{ANT}\n"); _host_git(r, "add", "a.txt")
    (r / "a.txt").write_text("clean now\n")                              # the working copy no longer has it
    os.symlink(f"/x/{GHO}", r / "l"); _host_git(r, "add", "l")            # mode 120000: the link text
    assert cli.main(["scan", "--staged"]) == 1                             # what the hook execs
    out = capsys.readouterr().out
    assert "a.txt:2 anthropic-token" in out and "l:1 github-token" in out and ANT not in out and GHO not in out


def test_the_staged_scan_passes_a_clean_index_and_ignores_staged_deletions(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(secrets, "literals", lambda cred=None, **k: ["dry-run-dummy-token"])
    r = _staging_repo(tmp_path, monkeypatch)
    (r / "gone.txt").write_text(ANT); _host_git(r, "add", "gone.txt"); _host_git(r, "commit", "-qm", "x")
    _host_git(r, "rm", "-q", "gone.txt")
    (r / "ok.txt").write_text("fine\n"); _host_git(r, "add", "ok.txt")
    assert cli.main(["scan", "--staged"]) == 0
    assert [p for p, _, _ in gitops.staged_blobs()] == ["ok.txt"]


def test_the_staged_scan_treats_results_as_evidence_and_the_dummy_counts_there(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(secrets, "literals", lambda cred=None, **k: ["dry-run-dummy-token"])
    r = _staging_repo(tmp_path, monkeypatch)
    ev = r / "results" / "dry1" / "dryrun" / "01"; ev.mkdir(parents=True)
    (ev / "s.txt").write_text("dry-run-dummy-token\n")
    (r / "runner.py").write_text('Credential("dry-run-dummy-token")\n')   # the runner's own source
    _host_git(r, "add", "-A")
    assert cli.main(["scan", "--staged"]) == 1
    out = capsys.readouterr().out
    assert "results/dry1/dryrun/01/s.txt:1 literal" in out and "runner.py" not in out


def test_cli_scan_needs_something_to_scan(capsys):
    with pytest.raises(SystemExit):
        cli.main(["scan"])


def test_staged_files_asks_the_harness_repo_for_staged_non_deleted_paths(monkeypatch):
    seen = []
    def fake_run(argv, **kw):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"a.txt\0dir/b c.txt\0", b"")
    monkeypatch.setattr(gitops.subprocess, "run", fake_run)
    assert gitops.staged_files() == [paths.REPO_ROOT / "a.txt", paths.REPO_ROOT / "dir/b c.txt"]
    assert seen == [["git", "-C", str(paths.REPO_ROOT), "diff", "--cached", "--name-only", "-z",
                     "--diff-filter=d"]]


def test_the_pre_commit_hook_runs_the_staged_scan():
    hook = REPO_ROOT / ".githooks" / "pre-commit"
    assert os.access(hook, os.X_OK)
    assert re.search(r"^exec uv run --quiet python -m runner scan --staged$", hook.read_text(), re.M)


# --- the arm-level API orchestration calls (preflight row 36) --------------------------------------------------

def test_scan_arm_covers_results_and_every_snapshot(tmp_state, monkeypatch):
    p = Paths("pass1", "control")
    _home_with_pat(paths.STATE)
    (p.setup_results).mkdir(parents=True)
    (p.setup_results / "shell-history.txt").write_text(f"echo {HOME_PAT}\n")
    p.snapshots.mkdir(parents=True)
    (p.snapshots / "step-01.tar").write_bytes(b"t"); (p.snapshots / "step-02.tar").write_bytes(b"t")
    scanned = []
    monkeypatch.setattr(credentials, "github_pat", lambda pass_, arm: KC_PAT if (pass_, arm) == ("pass1", "control") else
                        (_ for _ in ()).throw(RuntimeError("absent")))
    monkeypatch.setattr(secrets, "scan_snapshot",
                        lambda p_, snap, lits, *, pat=None: scanned.append((snap.name, tuple(lits), pat)) or [])
    found = secrets.scan_arm(p, ["dry-run-dummy-token"])
    assert [(Path(f.path).name, f.kind) for f in found] == [("shell-history.txt", "literal")]
    assert [s for s, _, _ in scanned] == ["step-01.tar", "step-02.tar"]
    assert all(HOME_PAT in lits and KC_PAT in lits for _, lits, _ in scanned)   # home and keychain PATs are needles
    assert {pat for _, _, pat in scanned} == {KC_PAT}             # the exemption is the keychain PAT only (6)


def test_fast_export_runs_in_one_networkless_container_with_only_out_writable(tmp_state, monkeypatch):
    p = Paths("dry9", "dryrun")
    root, dest = tmp_state / "x", tmp_state / "fe"
    root.mkdir()
    specs = []
    def fake_run(s, input=None, timeout=None):
        specs.append(s); dest.joinpath("1.fe").write_bytes(b"")
        return subprocess.CompletedProcess(s.cmd, 0, b"", b"")
    monkeypatch.setattr(gitops.docker, "run", fake_run)
    got = gitops.fast_export(p, root, ["a/.git", "origin.git"], dest, revs=("refs/heads/main",))
    [s] = specs
    assert s.network == "none"
    assert {(str(m.host), m.ctr, m.ro) for m in s.mounts} == {(str(root), "/in", True), (str(dest), "/out", False)}
    assert "fast-export" in s.cmd[2] and s.cmd[3:] == ["fast-export", "1", "refs/heads/main", "a/.git", "origin.git"]
    assert got == [dest / "1.fe", None]                     # no export file for a git dir means unscannable




# --- fix round 1 (1): encoded and terminal-wrapped leaks of a known value ----------------------------------------

@pytest.mark.parametrize("prefix", ["", "x", "xy", "x-access-token:", "x:"])
def test_a_base64_encoded_literal_is_found_at_every_alignment(tmp_path, prefix):
    enc = base64.b64encode((prefix + OAUTH).encode()).decode()
    (tmp_path / "a.log").write_text(f"hdr\nAuthorization: Basic {enc}\n")
    assert [(f.kind, f.line) for f in secrets.scan_tree(tmp_path, [OAUTH])] == [("literal", 2)]


def test_a_urlsafe_base64_literal_is_found(tmp_path):
    val = "fake~oauth?" + "z" * 30 + ">>>"                                # bytes that encode to + and /
    enc = base64.urlsafe_b64encode(val.encode()).decode()
    assert enc != base64.b64encode(val.encode()).decode()
    (tmp_path / "a.log").write_text(enc)
    assert [f.kind for f in secrets.scan_tree(tmp_path, [val])] == ["literal"]


def test_a_mime_wrapped_base64_literal_is_found(tmp_path):
    enc = base64.encodebytes(os.urandom(100) + OAUTH.encode())            # 76-char lines
    (tmp_path / "m.txt").write_bytes(enc)
    assert [f.kind for f in secrets.scan_tree(tmp_path, [OAUTH])] == ["literal"]


def test_a_hex_encoded_literal_is_found(tmp_path):
    (tmp_path / "h.txt").write_text(f"dump: {OAUTH.encode().hex()}\n")
    assert [f.kind for f in secrets.scan_tree(tmp_path, [OAUTH])] == ["literal"]


def test_a_terminal_wrapped_literal_is_found_at_its_first_line(tmp_path):
    wrapped = OAUTH[:17] + "\r\n" + OAUTH[17:30] + "\n" + OAUTH[30:]
    (tmp_path / "t.txt").write_text(f"a\nb\ntoken: {wrapped}\nend\n")
    assert [(f.kind, f.line) for f in secrets.scan_tree(tmp_path, [OAUTH])] == [("literal", 3)]


def test_a_wrapped_literal_across_read_chunks_is_found(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets, "CHUNK_BYTES", 16)
    (tmp_path / "t.txt").write_text("x" * 40 + OAUTH[:20] + "\n" + OAUTH[20:] + "\n")
    assert [f.kind for f in secrets.scan_tree(tmp_path, [OAUTH])] == ["literal"]


# --- fix round 1 (3): the fake mark — tests/ only, recognisably fake or allowlisted, never a known value ----------

FAKE_SHAPED = "github_pat_FAKE_" + "0123456789abcdefghijklmnopqrstuvwxyzABCDEF"   # says FAKE in its body
REAL_SHAPED = "gh" + "p_" + "k3Jx9Qm2Lp7Vr8Tz1Wc4Yb6Nd0Hf5Gs3Ae8R"             # unknown, looks real


def _blob(path, text):
    return (path, "100644", text.encode())


def test_a_marked_recognisably_fake_token_under_tests_passes_the_staged_scan():
    items = [_blob("tests/runner/t.py", f'FAKE = "{FAKE_SHAPED}"   # secret-scan: fake\nOTHER = "{GHO}"\n')]
    got = secrets.scan_blobs(items, [], harness=True)
    assert [(f.kind, f.line) for f in got] == [("github-token", 2)]      # the unmarked line still fails


def test_the_mark_does_not_hide_an_unknown_real_shaped_token():
    items = [_blob("tests/runner/t.py", f'T = "{REAL_SHAPED}"   # secret-scan: fake\n')]
    assert [f.kind for f in secrets.scan_blobs(items, [], harness=True)] == ["github-token"]


def test_an_allowlisted_fixture_line_passes_but_only_that_line(monkeypatch):
    line = f'T = "{REAL_SHAPED}"   # secret-scan: fake'
    monkeypatch.setattr(secrets, "FAKE_FIXTURE_LINES",
                        frozenset({("tests/runner/t.py", hashlib.sha256(line.encode()).hexdigest())}))
    ok = [_blob("tests/runner/t.py", line + "\n")]
    assert secrets.scan_blobs(ok, [], harness=True) == []
    moved = [_blob("tests/runner/other.py", line + "\n")]
    assert [f.kind for f in secrets.scan_blobs(moved, [], harness=True)] == ["github-token"]


def test_the_mark_is_ignored_outside_tests():
    items = [_blob("runner/x.py", f'F = "{FAKE_SHAPED}"   # secret-scan: fake\n')]
    assert [f.kind for f in secrets.scan_blobs(items, [], harness=True)] == ["github-pat"]


def test_the_mark_never_hides_a_known_literal_nor_evidence_under_results(tmp_state, monkeypatch):
    monkeypatch.setattr(paths, "RESULTS", paths.REPO_ROOT / "results")
    lit = [_blob("tests/runner/t.py", f'X = "{OAUTH}"   # secret-scan: fake\n')]
    assert [f.kind for f in secrets.scan_blobs(lit, [OAUTH], harness=True)] == ["literal"]
    ev = [_blob("results/pass1/control/01/t.jsonl", f'{FAKE_SHAPED} secret-scan: fake\n')]
    assert [f.kind for f in secrets.scan_blobs(ev, [], harness=True)] == ["github-pat"]
    tree = tmp_state / "ev"; tree.mkdir(); (tree / "t.jsonl").write_text(f'{FAKE_SHAPED} secret-scan: fake\n')
    assert [f.kind for f in secrets.scan_tree(tree)] == ["github-pat"]    # evidence scans never honour it


def test_the_existing_repo_fixtures_pass_the_staged_rules():
    """The fixtures already in the repo are recognisably fake; with the mark they pass, without it they fail."""
    for tok in ("github_pat_FAKE_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJ",   # secret-scan: fake
                "sk-ant-oat01-FAKE-test-token-never-real-0123456789"):          # secret-scan: fake
        assert secrets.scan_blobs([_blob("tests/runner/f.py", f'T = "{tok}"   # secret-scan: fake\n')], [],
                                  harness=True) == []
        assert secrets.scan_blobs([_blob("tests/runner/f.py", f'T = "{tok}"\n')], [], harness=True) != []


def test_every_github_tracker_keychain_pat_is_a_needle(tmp_state, monkeypatch):
    monkeypatch.setattr(credentials, "github_pat", lambda pass_, arm: f"kcpat-{pass_}-{arm}-" + "7" * 20)
    lits = secrets.literals(credentials.Credential(OAUTH))
    for pass_ in ("pass1", "canary"):
        assert f"kcpat-{pass_}-control-" + "7" * 20 in lits
    assert not [l for l in lits if "-pass2-" in l]                       # m-5: pass 2 is retired
    assert not [l for l in lits if "-speckitty-" in l or "-dry" in l]     # beads/dry arms have no PAT item


def test_a_parked_arms_keychain_pat_is_never_queried(tmp_state, monkeypatch):     # Task 23: active arms only
    asked = []
    monkeypatch.setattr(credentials, "github_pat", lambda pass_, arm: asked.append(arm) or "")
    secrets.literals(credentials.Credential(OAUTH))
    assert "bmad" not in asked and "control" in asked


# --- fix round 1 (4): containers by magic bytes ------------------------------------------------------------------

def test_gzip_is_detected_by_magic_whatever_the_name(tmp_path):
    (tmp_path / "stream.bin").write_bytes(gzip.compress(f"ok\n{ANT}\n".encode()))
    assert [(f.kind, f.line) for f in secrets.scan_tree(tmp_path)] == [("anthropic-token", 2)]


def test_a_zip_is_read_in_memory_and_members_are_named(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("clean.txt", "fine\n")
        z.writestr("dir/leak.txt", f"a\n{PAT}\n")
        z.writestr(f"name-{GHO}.txt", "x")
    (tmp_path / "bundle.dat").write_bytes(buf.getvalue())
    got = sorted((f.path.split("!", 1)[1], f.kind, f.line) for f in secrets.scan_tree(tmp_path))
    assert got == [("dir/leak.txt", "github-pat", 2), ("name-<redacted>.txt", "github-token", 0)]
    assert not list(tmp_path.glob("**/leak.txt"))                            # nothing extracted to disk


def test_an_oversize_zip_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets, "ZIP_MAX_BYTES", 100)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("big.txt", "x" * 1000)
    (tmp_path / "z.zip").write_bytes(buf.getvalue())
    assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["unscannable"]


@pytest.mark.parametrize("data", [lzma.compress(b"hello"), bz2.compress(b"hello"),
                                  b"\x28\xb5\x2f\xfd" + b"\0" * 20], ids=["xz", "bz2", "zstd"])
def test_other_compressors_are_unscannable(tmp_path, data):
    (tmp_path / "blob").write_bytes(data)
    assert [f.kind for f in secrets.scan_tree(tmp_path)] == ["unscannable"]


def test_text_that_merely_starts_like_bz2_is_plain(tmp_path):
    (tmp_path / "t.txt").write_text("BZh is how this note starts\n")
    assert secrets.scan_tree(tmp_path) == []


def test_a_gzip_blob_in_history_is_decompressed(tmp_path):
    r = tmp_path / "r"; r.mkdir()
    _host_git(r, "init", "-q", "-b", "main")
    (r / "log.gz").write_bytes(gzip.compress(f"{ANT}\n".encode())); _host_git(r, "add", "-A")
    _host_git(r, "commit", "-qm", "x")
    [f] = secrets.scan_history(_export(r, tmp_path / "h.fe"), "main")
    assert f.kind == "anthropic-token" and f.path.endswith("(log.gz)")


# --- fix round 1 (5): publish fails closed without the keychain token; the hook may skip it ------------------------

def test_cli_publish_refuses_when_the_keychain_token_cannot_be_read(tmp_state, monkeypatch, capsys):
    monkeypatch.setattr(repo, "publish", lambda *a, **k: (_ for _ in ()).throw(AssertionError("published")))
    assert cli.main(["publish", "pass1", "control"]) == 1
    assert "keychain" in capsys.readouterr().out


def test_literals_strict_raises_but_default_skips_a_missing_keychain_token(tmp_state):
    assert secrets.literals() == ["dry-run-dummy-token"]
    with pytest.raises(RuntimeError):
        secrets.literals(require_oauth=True)


# --- fix round 1 (6): the PAT-file exemption covers only the keychain PAT value ------------------------------------

def _fake_extract(tree_files):
    def extract(p, snapshot, dest):
        for rel, text in tree_files.items():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_text(text)
        return dest
    return extract


def test_the_snapshot_pat_file_exemption_is_the_keychain_pat_only(tmp_state, monkeypatch):
    p = Paths("pass1", "control"); p.snapshots.mkdir(parents=True); (p.snapshots / "step-01.tar").write_bytes(b"t")
    hosts = f"github.com:\n    oauth_token: {PAT}\n    other: {GHO}\n    again: {HOME_PAT}\n"
    monkeypatch.setattr(repo, "extract_snapshot", _fake_extract({"home/.config/gh/hosts.yml": hosts}))
    lits = [HOME_PAT, PAT]
    exempt = secrets.scan_snapshot(p, p.snapshots / "step-01.tar", lits, pat=PAT)
    assert sorted((f.kind, f.line) for f in exempt) == [("github-token", 3), ("literal", 4)]
    none = secrets.scan_snapshot(p, p.snapshots / "step-01.tar", lits, pat=None)
    assert sorted((f.kind, f.line) for f in none) == [("github-pat", 2), ("github-token", 3), ("literal", 2),
                                                      ("literal", 4)]


# --- ruling on concern 2: the hook never touches the keychain; lookups are cached per process ---------------------

def _keychain_forbidden(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the keychain was queried")
    monkeypatch.setattr(credentials, "from_keychain", boom)
    monkeypatch.setattr(credentials, "github_pat", boom)


def test_the_staged_scan_never_queries_the_keychain_but_uses_arm_home_pats(tmp_path, monkeypatch, capsys, tmp_state):
    _keychain_forbidden(monkeypatch)
    _home_with_pat(paths.STATE)                                         # a PAT value available without keychain
    r = _staging_repo(tmp_path, monkeypatch)
    enc = base64.b64encode(("x:" + HOME_PAT).encode()).decode()
    (r / "a.txt").write_text(f"auth {enc}\n"); _host_git(r, "add", "a.txt")
    assert cli.main(["scan", "--staged"]) == 1                          # found via the derived needle
    assert "a.txt:1 literal" in capsys.readouterr().out
    (r / "a.txt").write_text("clean\n"); _host_git(r, "add", "a.txt")
    assert cli.main(["scan", "--staged"]) == 0


def test_literals_without_keychain_never_query_it(tmp_state, monkeypatch):
    _keychain_forbidden(monkeypatch)
    _home_with_pat(paths.STATE)
    assert set(secrets.literals(keychain=False)) == {"dry-run-dummy-token", HOME_PAT}
    with pytest.raises(ValueError):
        secrets.literals(keychain=False, require_oauth=True)          # publish can never skip the keychain


def test_evidence_scans_do_query_the_keychain(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(credentials, "from_keychain", lambda: calls.append("oauth") or credentials.Credential(OAUTH))
    (tmp_path / "t.jsonl").write_text(f"{OAUTH}\n")
    assert cli.main(["scan", str(tmp_path)]) == 1 and calls == ["oauth"]


def test_each_keychain_lookup_happens_at_most_once_per_process(tmp_state, monkeypatch):
    calls = []
    def oauth():
        calls.append("oauth"); return credentials.Credential(OAUTH)
    def pat(pass_, arm):
        calls.append((pass_, arm))
        if arm == "control":
            return f"kcpat-{pass_}-control-" + "7" * 20
        raise RuntimeError("absent")                                   # an absent item is cached too
    monkeypatch.setattr(credentials, "from_keychain", oauth)
    monkeypatch.setattr(credentials, "github_pat", pat)
    first = secrets.literals()
    n = len(calls)
    assert secrets.literals() == first and secrets.scan_arm(Paths("pass1", "control"), first) == []
    assert len(calls) == n and len(set(map(str, calls))) == n           # nothing looked up twice
    assert calls.count("oauth") == 1 and ("pass1", "control") in calls


def test_a_failed_oauth_lookup_is_cached_and_still_fails_publish(tmp_state, monkeypatch):
    calls = []
    def absent():
        calls.append(1); raise RuntimeError("no usable keychain item")
    monkeypatch.setattr(credentials, "from_keychain", absent)
    assert secrets.literals() == ["dry-run-dummy-token"]
    with pytest.raises(RuntimeError):
        secrets.literals(require_oauth=True)
    assert calls == [1]


# ---- Task 22 fix round 1 L-4: the harness-fault ledger is evidence too ---------------------------------------------

def test_ledger_files_are_the_shared_ledger_for_real_passes_and_the_namespaced_one_otherwise(tmp_state):
    assert secrets.ledger_files("pass1") == [paths.FAULTS, paths.HALTED,
                                             paths.RESULTS / "pass1" / "resource-exhaustion.jsonl"]
    assert secrets.ledger_files("dry3") == [paths.RESULTS / "dry3" / "faults.jsonl", paths.RESULTS / "dry3" / "HALTED",
                                            paths.RESULTS / "dry3" / "resource-exhaustion.jsonl"]


def test_a_secret_in_the_fault_ledger_is_found_by_the_close_out_arm_scan(tmp_state):
    faults.record(faults.HarnessFault("infra-is_error", "x", f"arm said {ANT}"), "pass1", "control", 2, 1)
    [f] = secrets.scan_arm(Paths("pass1", "control"), snapshots=False)
    assert f.kind == "anthropic-token" and "faults.jsonl" in f.path


def test_a_secret_in_a_dry_pass_ledger_is_found_by_the_per_step_scan(tmp_state):
    p = Paths("dry3", "control")
    p.step(2).mkdir(parents=True)
    faults.record(faults.HarnessFault("infra-is_error", "x", f"arm said {ANT}"), "dry3", "control", 2, 1)
    assert [f.kind for f in secrets.scan_step(p, 2)] == ["anthropic-token"]


def test_the_per_step_scan_covers_the_step_dir_too(tmp_state):
    p = Paths("dry3", "control")
    p.step(2).mkdir(parents=True); (p.step(2) / "run.json").write_text(ANT)
    assert [f.kind for f in secrets.scan_step(p, 2)] == ["anthropic-token"]


# ---- final fix batch A5: the arm printing its OWN GitHub token is redacted, not a harness fault -----------------------

OWN = "github_pat_" + "Q" * 60


def test_redact_removes_the_arms_own_token_and_its_encodings_from_plain_and_gzip_files(tmp_path):
    import base64
    (tmp_path / "turns").mkdir()
    (tmp_path / "questions.jsonl").write_text(f'{{"arm_message": "my token is {OWN}"}}\n')
    (tmp_path / "turns" / "arm-a1-001.stream.jsonl.gz").write_bytes(gzip.compress(f"x {OWN} y\n".encode()))
    (tmp_path / "b64.txt").write_text(base64.b64encode(f"x-access-token:{OWN}".encode()).decode())
    (tmp_path / "clean.txt").write_text("nothing here")
    changed = secrets.redact([tmp_path], [OWN])
    assert sorted(changed) == sorted(str(tmp_path / f) for f in ("questions.jsonl", "turns/arm-a1-001.stream.jsonl.gz",
                                                               "b64.txt"))
    assert secrets.scan_tree(tmp_path, [OWN]) == []
    assert secrets.REDACTION in gzip.decompress((tmp_path / "turns" / "arm-a1-001.stream.jsonl.gz").read_bytes()).decode()


def test_redact_never_follows_a_link(tmp_path):
    outside = tmp_path / "outside.txt"; outside.write_text(OWN)
    root = tmp_path / "root"; root.mkdir(); (root / "l").symlink_to(outside)
    assert secrets.redact([root], [OWN]) == [] and outside.read_text() == OWN


def test_a_real_arms_own_pat_values_are_its_keychain_items_not_its_home_files(tmp_state, monkeypatch):   # follow-up 2
    from runner import config
    from runner.paths import Paths
    p = Paths("pass1", "control")
    (p.home / ".config" / "gh").mkdir(parents=True)
    (p.home / ".config" / "gh" / "hosts.yml").write_text(f"github.com:\n    oauth_token: {OWN}\n")
    monkeypatch.setattr(credentials, "github_pat", lambda pass_, arm: "kc-" + "1" * 30)
    monkeypatch.setattr(credentials, "github_disc_pat", lambda pass_, arm: "kd-" + "2" * 30)
    secrets.clear_keychain_cache()
    got = secrets.own_pat_values(p, config.load_arm("control"))
    secrets.clear_keychain_cache()
    assert set(got) == {"kc-" + "1" * 30, "kd-" + "2" * 30}
    monkeypatch.setattr(credentials, "github_pat", lambda *a: pytest.fail("keychain read for a dry arm"))
    assert secrets.own_pat_values(Paths("dry1", "dryrun"), config.load_arm("dryrun")) == []


# ---- follow-up 2: the arm's "own" token is what it was given, never a harness literal ---------------------------------

OAUTH_FU = "sk-ant-oat01-" + "Z" * 60


def _home(p, text):
    (p.home / ".config" / "gh").mkdir(parents=True)
    (p.home / ".config" / "gh" / "hosts.yml").write_text(text)


def test_a_real_arms_own_tokens_are_only_its_keychain_and_discovery_pats(tmp_state, monkeypatch):
    from runner import config
    from runner.paths import Paths
    p = Paths("pass1", "control")
    _home(p, f"github.com:\n    oauth_token: {OWN}\n")                   # an arm-written home value: not "given"
    monkeypatch.setattr(credentials, "github_pat", lambda pass_, arm: "github_pat_" + "K" * 50)
    monkeypatch.setattr(credentials, "github_disc_pat", lambda pass_, arm: "github_pat_" + "D" * 50)
    secrets.clear_keychain_cache()
    got = secrets.own_pat_values(p, config.load_arm("control"), credentials.Credential(OAUTH_FU))
    secrets.clear_keychain_cache()
    assert set(got) == {"github_pat_" + "K" * 50, "github_pat_" + "D" * 50}


def test_a_dry_arms_home_values_count_only_in_github_token_shapes(tmp_state):
    from runner import config
    from runner.paths import Paths
    p = Paths("dry1", "dryrun")
    _home(p, f"github.com:\n    oauth_token: {OWN}\nother:\n    oauth_token: {'n' * 40}\n")
    assert secrets.own_pat_values(p, config.load_arm("dryrun"), credentials.dummy()) == [OWN]


def test_the_oauth_token_in_hosts_yml_is_never_the_arms_own(tmp_state):
    from runner import config
    from runner.paths import Paths
    p = Paths("dry1", "dryrun")
    tok = "gho_" + "O" * 40                                                  # GitHub-shaped, but it is the harness's
    _home(p, f"github.com:\n    oauth_token: {tok}\n    x: {secrets.DRY_RUN_TOKEN}\n")
    assert secrets.own_pat_values(p, config.load_arm("dryrun"), credentials.Credential(tok)) == []
