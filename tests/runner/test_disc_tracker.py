"""Final fix batch A3 (owner): N.a uses a separate discovery tracker. A GitHub-tracker arm's N.a points at its own
private repo `troupe-run/bakeoff-specs-<arm>-<pass>-disc` (GH_REPO and the PAT keychain item
`bakeoff-gh-<pass>-disc-<arm>` in its home); the local origin is untouched; N.b uses the normal repo from a clean
tracker (the home, and so the normal PAT, comes back with the pre-step snapshot). No real GitHub: fakes only."""
import json
import os
import pytest
from runner import checklist, cli, config, credentials, drive, repo, secrets, tracker
from runner.paths import Paths

GITHUB_ARMS = [a for a in config.active_arms() if config.load_arm(a).tracker == "github"]


def test_the_discovery_repo_exists_only_for_github_tracker_arms_on_passes_with_a_repo():
    assert config.github_disc_slug("pass1", "control") == "troupe-run/bakeoff-specs-control-pass1-disc"
    assert config.github_disc_slug("canary", "control") == "troupe-run/bakeoff-specs-control-canary-disc"
    assert config.github_disc_slug("pass1", "speckitty") is None                # beads lives in git
    assert config.github_disc_slug("dry1", "dryrun") is None


def test_an_na_arm_session_points_gh_at_the_discovery_repo_and_nb_at_the_normal_one():
    pins, arm = config.load_pins(), config.load_arm("control")
    a = credentials.session_env(pins, arm, role="arm", isolated=False, pass_="pass1", disc=True)
    b = credentials.session_env(pins, arm, role="arm", isolated=False, pass_="pass1")
    assert a["GH_REPO"] == "troupe-run/bakeoff-specs-control-pass1-disc"
    assert b["GH_REPO"] == "troupe-run/bakeoff-specs-control-pass1"


def test_the_discovery_pat_comes_from_its_own_keychain_item(monkeypatch):
    asked = []

    class R:
        returncode, stdout = 0, "github_pat_" + "D" * 40 + "\n"
    monkeypatch.setattr(credentials.subprocess, "run", lambda argv, **k: asked.append(argv) or R())
    assert credentials.github_disc_pat("pass1", "control") == "github_pat_" + "D" * 40
    assert asked[0][asked[0].index("-s") + 1] == "bakeoff-gh-pass1-disc-control"


def _home_with_pat(tmp_state, arm="control"):
    p = Paths("pass1", arm)
    gh = p.home / ".config" / "gh"
    gh.mkdir(parents=True)
    (gh / "hosts.yml").write_text(checklist.gh_hosts_yml("github_pat_" + "N" * 40))
    return p


def test_the_discovery_pat_replaces_the_normal_one_in_the_arm_home(tmp_state, monkeypatch):
    p = _home_with_pat(tmp_state)
    monkeypatch.setattr(credentials, "github_disc_pat", lambda pass_, arm: "github_pat_" + "D" * 40)
    assert checklist.install_disc_pat(p, config.load_arm("control"), "pass1") is True
    f = p.home / ".config" / "gh" / "hosts.yml"
    assert "D" * 40 in f.read_text() and "N" * 40 not in f.read_text()
    assert oct(f.stat().st_mode & 0o777) == "0o600"


def test_the_discovery_pat_refuses_a_link_the_arm_left_in_its_home(tmp_state, monkeypatch, tmp_path):
    p = _home_with_pat(tmp_state)
    f = p.home / ".config" / "gh" / "hosts.yml"
    f.unlink(); target = tmp_path / "elsewhere"; target.write_text("x"); f.symlink_to(target)
    monkeypatch.setattr(credentials, "github_disc_pat", lambda pass_, arm: "github_pat_" + "D" * 40)
    with pytest.raises(checklist.NotReady, match="link"):
        checklist.install_disc_pat(p, config.load_arm("control"), "pass1")
    assert target.read_text() == "x"


def test_no_discovery_pat_for_a_beads_or_dry_arm(tmp_state, monkeypatch):
    monkeypatch.setattr(credentials, "github_disc_pat", lambda *a: pytest.fail("keychain read"))
    assert checklist.install_disc_pat(Paths("pass1", "speckitty"), config.load_arm("speckitty"), "pass1") is False
    assert checklist.install_disc_pat(Paths("dry1", "dryrun"), config.load_arm("dryrun"), "dry1") is False


def test_github_plan_pat_instructions_and_verify_include_the_discovery_repos_for_github_arms_only(monkeypatch):
    plan = repo.github_plan("pass1")
    disc = [c for c in plan if c.split()[3].endswith("-disc")]
    assert sorted(c.split()[3] for c in disc) == sorted(f"troupe-run/bakeoff-specs-{a}-pass1-disc" for a in GITHUB_ARMS)
    assert all("--private" in c for c in disc) and not any("speckitty-pass1-disc" in c for c in plan)
    pats = "\n".join(repo.pat_instructions("pass1"))
    assert all(f"bakeoff-gh-pass1-disc-{a}" in pats and f"bakeoff-specs-{a}-pass1-disc" in pats for a in GITHUB_ARMS)
    assert "bakeoff-gh-pass1-disc-bmad" not in pats and "disc-speckitty" not in pats
    seen = []

    def fake(argv, **k):
        seen.append(argv)
        out = "[]" if argv[:3] == ["gh", "repo", "list"] else \
            '{"visibility": "PRIVATE", "hasIssuesEnabled": true, "isEmpty": true}'
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()
    monkeypatch.setattr(repo.subprocess, "run", fake)
    res = repo.github_verify("pass1")
    assert {f"{a}-disc" for a in GITHUB_ARMS} <= set(res) and "speckitty-disc" not in res and repo.verify_ok(res)


def test_the_discovery_pats_are_secret_scan_needles(tmp_state, monkeypatch):
    monkeypatch.setattr(credentials, "github_pat", lambda pass_, arm: "")
    monkeypatch.setattr(credentials, "github_disc_pat", lambda pass_, arm: f"kcdisc-{pass_}-{arm}-" + "7" * 20)
    secrets.clear_keychain_cache()
    lits = secrets.literals(credentials.Credential("sk-ant-oat01-" + "x" * 40))
    secrets.clear_keychain_cache()
    assert "kcdisc-pass1-control-" + "7" * 20 in lits and not [l for l in lits if "speckitty" in l]


def test_tracker_calls_in_na_go_to_the_discovery_repo(tmp_state, monkeypatch):
    from tests.runner.conftest import make_test_ctx
    import dataclasses
    ctx = dataclasses.replace(make_test_ctx(tmp_state, arm="control", step=6), pass_="pass1",
                              paths=Paths("pass1", "control"), run="a")
    assert tracker._slug(ctx) == "troupe-run/bakeoff-specs-control-pass1-disc"
    assert tracker._slug(dataclasses.replace(ctx, run="b")) == "troupe-run/bakeoff-specs-control-pass1"


# ---- follow-up 6: a missing or timed-out discovery keychain item is NotReady, found at run start ----------------------

@pytest.mark.parametrize("why", ["no usable keychain item 'bakeoff-gh-pass1-disc-control' (exit 44)",
                                 "keychain lookup for 'bakeoff-gh-pass1-disc-control' timed out after 20s"])
def test_install_disc_pat_turns_a_keychain_failure_into_not_ready(tmp_state, monkeypatch, why):
    p = _home_with_pat(tmp_state)

    def boom(pass_, arm):
        raise RuntimeError(why)
    monkeypatch.setattr(credentials, "github_disc_pat", boom)
    with pytest.raises(checklist.NotReady, match="disc"):
        checklist.install_disc_pat(p, config.load_arm("control"), "pass1")
    assert "N" * 40 in (p.home / ".config" / "gh" / "hosts.yml").read_text()     # the normal PAT is untouched


def test_a_run_with_a_missing_discovery_pat_is_refused_before_any_step(fake_orch, monkeypatch):
    from runner import orchestrate
    from tests.runner.test_orchestrate import real

    def boom(pass_, arm):
        raise RuntimeError(f"no usable keychain item 'bakeoff-gh-{pass_}-disc-{arm}' (exit 44)")
    monkeypatch.setattr(credentials, "github_disc_pat", boom)
    with pytest.raises(orchestrate.NotReady, match="bakeoff-gh-pass1-disc-"):
        real(fake_orch)
    assert fake_orch.runs() == []
