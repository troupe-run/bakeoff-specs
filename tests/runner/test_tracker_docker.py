"""Task 17: the dry and beads backends for real (GitHub is exercised by the canary, Task 26).

The ctx here is a minimal stand-in for `drive.StepCtx` (tracker reads only pass_, arm, paths, out): the plan's
`make_test_ctx` arrives with Task 15 and can replace `_ctx` then."""
import json, uuid
from types import SimpleNamespace

import pytest

from runner import config, docker, gitops, repo, tracker
from runner.docker import Mount, RunSpec
from runner.paths import Paths

pytestmark = pytest.mark.docker


class YesOwner:
    def confirm(self, text):
        return True


def _ctx(tmp_path, arm, pass_="dry9"):
    out = tmp_path / "out" / "06"
    out.mkdir(parents=True)
    return SimpleNamespace(pass_=pass_, arm=config.load_arm(arm), step=6, paths=Paths(pass_, arm), out=out,
                           owner=YesOwner())


def test_dry_backend_writes_the_issue_file(tmp_state, tmp_path):
    ctx = _ctx(tmp_path, "dryrun")
    repo.init(ctx.paths, "dryrun", "dry9")
    ref = tracker.create_bug(ctx, ctx.owner)
    assert ref.ref == "dry#1" and "anchor" in (ctx.paths.base / "tracker" / "issue-1.md").read_text()
    assert tracker.snapshot(ctx)["issues"][0]["ref"] == "dry#1"


def _bd_init(p: Paths) -> None:
    """`bd init` in the arm container, offline (bd 1.3.0 needs no network for it). The real arm gets this from
    its [setup] shell (P9 fixes those lines); this test needs only an initialised beads store."""
    s = RunSpec(name=f"bk-bdinit-{p.pass_}-{p.arm}-{uuid.uuid4().hex[:8]}", image=gitops.image_for(p.arm), label=f"bakeoff.run={p.pass_}/{p.arm}",
                network="none", mounts=[Mount(p.home, "/home/actor", False), Mount(p.work, "/work", False)],
                env={"HOME": "/home/actor"}, workdir=p.container_repo, cmd=["bd", "init", "--non-interactive"],
                stdin=False, limits=config.load_pins().limits, proxy=False)
    r = docker.run(s, timeout=120)
    assert r.returncode == 0, r.stderr.decode(errors="replace")


def test_beads_backend_creates_lists_and_supersedes_a_bug_in_the_container(tmp_state, tmp_path):
    ctx = _ctx(tmp_path, "speckitty")
    repo.init(ctx.paths, "speckitty", "dry9")
    _bd_init(ctx.paths)
    ref = tracker.create_bug(ctx, ctx.owner)
    assert ref.backend == "beads" and ref.ref == f"beads {ref.id}"
    snap = tracker.snapshot(ctx)
    (issue,) = [i for i in snap["issues"] if i.get("id") == ref.id]
    assert issue["title"] == "Setting one agent's model changed another agent's model"
    assert issue["issue_type"] == "bug" and issue["status"] == "open"
    assert issue["description"] == (ctx.out / "issue-body.md").read_text()      # verbatim, newlines kept
    assert json.loads((ctx.out / "tracker.json").read_text()) == snap
    new = tracker.create_bug(ctx, ctx.owner)
    assert tracker.supersede(ctx, ref, ctx.owner, new=new)["action"] == "closed"
    closed = next(i for i in tracker.snapshot(ctx)["issues"] if i["id"] == ref.id)
    assert closed["status"] == "closed" and closed["close_reason"].startswith("Superseded by a harness re-run")
    assert docker.running() == []


def test_beads_supersede_after_a_restore_removed_the_issue_does_not_crash(tmp_state, tmp_path):
    """Preflight M9, for real: the issue is created after the step-6 snapshot, the restore drops it with the
    work tree, and the re-run's supersede records that instead of letting `bd close` raise."""
    ctx = _ctx(tmp_path, "speckitty")
    repo.init(ctx.paths, "speckitty", "dry9")
    _bd_init(ctx.paths)
    repo.snapshot(ctx.paths, 6)
    ref = tracker.create_bug(ctx, ctx.owner)
    repo.restore(ctx.paths, 6)
    assert not any(i.get("id") == ref.id for i in tracker.snapshot(ctx)["issues"])
    rec = tracker.supersede(ctx, ref, ctx.owner)
    assert rec["action"] == "absent" and rec["survives_restore"] is False
