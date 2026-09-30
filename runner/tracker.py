"""Step 6's bug in each arm's own tracker (design §2, §4), tracker snapshots after every step, and the
round-trip facts of step 6 (facts only; Plan 3 scores them).

Backends, by `arm.tracker`:
- `github`: created from the HOST with the owner's own `gh` login, after `owner.confirm`. This is `gh` against
  the GitHub API, never git on an arm repo (review S-1 does not apply). The arm reads it with its Issues-only PAT.
- `beads`: created in the arm container (arm image, network none, home and work mounted).
- `dry`: a file `state/<pass>/<arm>/tracker/issue-<n>.md`, ref `dry#<n>`.

A substitute bug (ledger rulings B5a/B5b) goes through the same `create_bug` path with its own title and body.
"""
from __future__ import annotations
import json, os, re, subprocess, tempfile, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from runner import config, docker, faults, gitops, handoff
from runner.docker import Mount, RunSpec
from runner.paths import REPO_ROOT

BRIEF = REPO_ROOT / "scenario" / "steps" / "06-bug-alias.md"
SUPERSEDED = "Superseded by a harness re-run"

# Whether a backend's issues survive `repo.restore` (preflight M9). GitHub lives off-host; dry files live in the
# arm base beside (not inside) the snapshotted home/work trees; beads lives in the work tree, so a restore to a
# snapshot taken before the issue was filed removes it. N.a (final fix batch A3): a GitHub arm's discovery run uses
# its own discovery repo (`config.github_disc_slug`), so N.b starts from a clean tracker; beads (speckitty) lives in
# git, so the restore at the end of N.a already resets whatever N.a did to it.
SURVIVES_RESTORE = {"github": True, "dry": True, "beads": False}

# Who files the harness's issues (fix round 1): beads records the actor; GitHub records the owner's own login,
# labelled here without an extra API call; the dry file has no author.
REPORTER = {"beads": "bug-reporter", "github": "owner-gh", "dry": "harness"}
BD_WRITE = ["--sandbox", "--actor", REPORTER["beads"]]   # --sandbox: no Dolt auto-push
BD_READ = ["--readonly"]
NO_BEADS_DB = "no beads database found"
GH_ENV_STRIP = ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_REPO", "GH_ENTERPRISE_TOKEN")
_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")

# The live probe's write test (Task 25, owner): one plain issue per arm repo (pass-1 and N.a discovery), closed at
# once. Single source of its title and body; `snapshot` never lists an issue with exactly this title.
PROBE_ISSUE = {"title": "test issue - please ignore",
               "body": "Created by the bake-off harness to check that this repository's token can write issues. "
                       "It was closed at once. Please ignore it."}


def drop_probe_issues(issues: list) -> list:
    """The GitHub issue list without the live probe's write-test issues (exact title match only)."""
    return [i for i in issues if not (isinstance(i, dict) and i.get("title") == PROBE_ISSUE["title"])]


@dataclass(frozen=True)
class IssueRef:
    backend: str
    ref: str
    url: str | None
    id: str


# --- pure helpers -------------------------------------------------------------------------------------------

def gh_create_argv(slug: str, body_file: Path, title: str | None = None) -> list[str]:
    return ["gh", "issue", "create", "--repo", slug, "--title", title or handoff.STEP6["title"],
            "--body-file", str(body_file), "--type", "Bug"]


def gh_list_argv(slug: str) -> list[str]:
    return ["gh", "issue", "list", "--repo", slug, "--state", "all", "--limit", "200", "--json",
            "number,title,state,labels,createdAt,closedAt,comments,body,url"]


def gh_close_argv(slug: str, number: str, new_ref: str | None = None) -> list[str]:
    comment = SUPERSEDED + (f": {new_ref}" if new_ref else "")
    return ["gh", "issue", "close", number, "--repo", slug, "--comment", comment]


_GH_URL = re.compile(r"https://github\.com/([^/\s]+/[^/\s]+)/issues/(\d+)")


def parse_gh_url(text: str) -> IssueRef:
    m = _GH_URL.search(text)
    if not m:
        raise ValueError(f"no GitHub issue URL in gh output: {text[:200]!r}")
    return IssueRef("github", f"{m.group(1)}#{m.group(2)}", m.group(0), m.group(2))


def _json_in(text: str):
    """bd may print a warning line before its JSON: decode from the first bracket."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        if not starts:
            raise
        return json.JSONDecoder().raw_decode(text[min(starts):])[0]


def parse_bd(text: str) -> IssueRef:
    o = _json_in(text)
    o = o[0] if isinstance(o, list) else o
    return IssueRef("beads", f"beads {o['id']}", None, o["id"])


def commit_records(log: str) -> list[tuple[str, str]]:
    """(sha, message) pairs from gitops.commits_between's \\x1e/\\x1f-separated records."""
    out = []
    for rec in log.split("\x1e"):
        rec = rec.strip("\n")
        if "\x1f" in rec:
            sha, _, msg = rec.partition("\x1f")
            out.append((sha.strip(), msg))
    return out


def _ref_pattern(issue_id: str) -> re.Pattern:
    i = re.escape(issue_id)
    if issue_id.isdigit():
        # "#N" standing alone or as "owner/repo#N", or the issue URL; never "#N0" or "x-#N"
        return re.compile(rf"(?:^|[^\w-]|[\w.-]/[\w.-]+)#{i}(?!\d)|/issues/{i}(?!\d)")
    # a beads id standing alone: not "xr-fac", "r-fac0" or the child "r-fac.1"
    return re.compile(rf"(?<![\w-]){i}(?![\w-]|\.\w)")


def commits_referencing(log: str, issue_id: str) -> list[str]:
    pat = _ref_pattern(issue_id)
    return [sha for sha, msg in commit_records(log) if pat.search(msg)]


_TEXT_FIELDS = ("body", "description", "notes", "close_reason", "design", "text")


def _issue_text(issue: dict) -> str:
    parts = [str(issue.get(k) or "") for k in _TEXT_FIELDS]
    parts += [str(c.get("body") or c.get("text") or "") for c in issue.get("comments") or [] if isinstance(c, dict)]
    return "\n".join(parts)


def issue_links_commit(issue: dict, shas: list[str]) -> bool:
    text = _issue_text(issue)
    return any(len(s) >= 7 and s[:7] in text for s in shas)


# --- effectful ----------------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _summary(text: str) -> str:
    """First non-empty lines of a tool's stderr, with anything token-shaped removed."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return _TOKEN.sub("[redacted]", " | ".join(lines[:3]))[:300]


def _fault(verb: str, rc: int, stderr: str) -> faults.HarnessFault:
    return faults.HarnessFault("infra-tracker", verb, f"exit {rc}: {_summary(stderr)}")


def _verb(cmd: tuple[str, ...]) -> str:
    return next((c for c in cmd[1:] if not c.startswith("-") and c != REPORTER["beads"]), "bd")


def _bd(ctx, *cmd: str, extra: list[Mount] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """`bd` in the arm container: arm image, network none, the arm's home and work mounted."""
    p, arm = ctx.paths, ctx.arm
    gitops.check_trees(p)                      # never touch an arm mid-restore
    s = RunSpec(name=f"bk-bd-{p.pass_}-{p.arm}-{uuid.uuid4().hex[:8]}",       # unique (preflight m13)
                image=gitops.image_for(arm.name), label=f"bakeoff.run={p.pass_}/{p.arm}", network="none",
                mounts=[Mount(p.home, p.container_home, False), Mount(p.work, "/work", False), *(extra or [])],
                env={"HOME": p.container_home, "BD_NON_INTERACTIVE": "1"}, workdir=p.container_repo,
                cmd=list(cmd), stdin=False, limits=config.load_pins().limits, proxy=False)
    r = docker.run(s, timeout=120)
    r = subprocess.CompletedProcess(r.args, r.returncode, r.stdout.decode(errors="replace"),
                                    r.stderr.decode(errors="replace"))
    if check and r.returncode != 0:
        raise _fault(_verb(cmd), r.returncode, r.stderr)
    return r


def _gh(argv: list[str]) -> str:
    """`gh` on the host with the owner's own login: no token/host/repo overrides from the environment, and a
    neutral empty cwd so no local git repo can steer it."""
    env = {k: v for k, v in os.environ.items() if k not in GH_ENV_STRIP}
    with tempfile.TemporaryDirectory(prefix="bakeoff-gh-") as cwd:
        r = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=cwd)
    if r.returncode != 0:
        raise _fault(argv[2] if len(argv) > 2 else "gh", r.returncode, r.stderr)
    return r.stdout


def _slug(ctx) -> str:
    """The arm's repo; in N.a (`ctx.run == "a"`) its discovery repo (final fix batch A3)."""
    disc = getattr(ctx, "run", "b") == "a"
    slug = (config.github_disc_slug if disc else config.github_slug)(ctx.pass_, ctx.arm.name)
    if not slug:
        raise RuntimeError(f"no GitHub repo for {ctx.arm.name} on pass {ctx.pass_!r}; the github tracker needs one")
    return slug


def _dry_dir(ctx) -> Path:
    return ctx.paths.base / "tracker"


def create_bug(ctx, owner, *, title: str | None = None, body: str | None = None) -> IssueRef:
    """File the step-6 bug in the arm's tracker. With neither `title` nor `body`, the planted alias bug (title
    from scenario.toml [step6], body = the step-6 brief without its contract line). A substitute bug (B5) gives
    both. The body is written to `out/issue-body.md`; the ref and provenance to `out/issue.json`."""
    if (title is None) != (body is None):
        raise ValueError("a substitute bug needs both a title and a body")
    source = "planted" if title is None else "substitute"
    if source == "substitute" and (not title.strip() or not body.strip()):
        raise ValueError("a substitute bug needs a non-empty title and body")
    title = title if title is not None else handoff.STEP6["title"]
    text = body if body is not None else handoff.issue_body(BRIEF.read_text())
    ctx.out.mkdir(parents=True, exist_ok=True)
    body_file = ctx.out / "issue-body.md"
    body_file.write_text(text)
    backend = ctx.arm.tracker
    if backend == "dry":
        d = _dry_dir(ctx); d.mkdir(parents=True, exist_ok=True)
        n = 1 + max((int(f.stem.split("-")[1]) for f in d.glob("issue-*.md") if f.stem.split("-")[1].isdigit()),
                    default=0)
        (d / f"issue-{n}.md").write_text(f"# {title}\n\n{text}")
        ref = IssueRef("dry", f"dry#{n}", None, str(n))
    elif backend == "beads":
        r = _bd(ctx, "bd", *BD_WRITE, "create", "--title", title, "--type", "bug", "--body-file", "/setup/issue.md", "--json",
                extra=[Mount(body_file, "/setup/issue.md", True)])
        ref = parse_bd(r.stdout)
    elif backend == "github":
        slug = _slug(ctx)
        if not owner.confirm(f"Create the step-6 issue in {slug} with your own gh login? Title: {title}"):
            raise RuntimeError("owner declined the step-6 issue; step 6 cannot start")
        ref = parse_gh_url(_gh(gh_create_argv(slug, body_file, title)))
    else:
        raise ValueError(f"unknown tracker backend {backend!r}")
    (ctx.out / "issue.json").write_text(json.dumps(
        {**asdict(ref), "title": title, "source": source, "reporter": REPORTER[backend], "created_at": _now(),
         "survives_restore": SURVIVES_RESTORE[backend]}, indent=2))
    return ref


def _beads_list(ctx) -> list[dict] | None:
    """Every beads issue, or None when the arm has no beads database (never initialised, or removed by a
    harness restore)."""
    r = _bd(ctx, "bd", *BD_READ, "list", "--all", "--json", check=False)
    if r.returncode != 0:
        if NO_BEADS_DB in (r.stderr + r.stdout):
            return None
        raise _fault("list", r.returncode, r.stderr)
    return _json_in(r.stdout or "[]") or []


def supersede(ctx, old: IssueRef, owner, new: IssueRef | None = None) -> dict:
    """A harness re-run of step 6: close the old issue with "Superseded by a harness re-run" (naming the new one
    when known), after the owner confirms. An old issue a restore already removed (beads, preflight M9) is
    recorded as `absent` rather than crashing. Appends the record to `out/tracker-superseded.jsonl`."""
    rec = {"at": _now(), "backend": old.backend, "old": old.ref, "new": new.ref if new else None,
           "survives_restore": SURVIVES_RESTORE.get(old.backend)}
    reason = SUPERSEDED + (f": {new.ref}" if new else "")
    action = None
    if old.backend == "beads":
        match = next((i for i in _beads_list(ctx) or [] if i.get("id") == old.id), None)
        if match is None:
            action = "absent"
        elif match.get("status") == "closed":
            action = "already-closed"
    elif old.backend == "dry":
        if not (_dry_dir(ctx) / f"issue-{old.id}.md").is_file():
            action = "absent"
    if action is None:
        if not owner.confirm(f"Close {old.ref} as superseded by a harness re-run"
                             f"{f' (new issue {new.ref})' if new else ''}?"):
            action = "declined"
        elif old.backend == "github":
            _gh(gh_close_argv(old.ref.rsplit("#", 1)[0], old.id, new.ref if new else None))
            action = "closed"
        elif old.backend == "beads":
            _bd(ctx, "bd", *BD_WRITE, "close", old.id, "--reason", reason)
            action = "closed"
        elif old.backend == "dry":
            with open(_dry_dir(ctx) / f"issue-{old.id}.md", "a") as fh:
                fh.write(f"\n\n---\n{reason}\n")
            action = "closed"
        else:
            raise ValueError(f"unknown tracker backend {old.backend!r}")
    rec["action"] = action
    ctx.out.mkdir(parents=True, exist_ok=True)
    with open(ctx.out / "tracker-superseded.jsonl", "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def snapshot(ctx) -> dict:
    """Every issue in the arm's tracker now, written as `out/tracker.json` (after every step: design §2 records
    tracker quality separately)."""
    backend = ctx.arm.tracker
    initialised = True
    if backend == "dry":
        d = _dry_dir(ctx)
        files = sorted((f for f in d.glob("issue-*.md") if f.stem.split("-")[1].isdigit()),
                       key=lambda f: int(f.stem.split("-")[1])) if d.exists() else []
        issues = [{"ref": f"dry#{f.stem.split('-')[1]}", "id": f.stem.split("-")[1], "text": f.read_text()}
                  for f in files]
    elif backend == "beads":
        listed = _beads_list(ctx)
        initialised = listed is not None
        ids = [i["id"] for i in listed or []]
        issues = _json_in(_bd(ctx, "bd", *BD_READ, "show", *ids, "--json", "--include-comments").stdout) if ids else []
        issues = issues if isinstance(issues, list) else [issues]
    elif backend == "github":
        issues = drop_probe_issues(json.loads(_gh(gh_list_argv(_slug(ctx))) or "[]"))   # Task 25 write test
    else:
        raise ValueError(f"unknown tracker backend {backend!r}")
    snap = {"backend": backend, "survives_restore": SURVIVES_RESTORE[backend], "initialised": initialised,
            "at": _now(), "issues": issues}
    ctx.out.mkdir(parents=True, exist_ok=True)
    (ctx.out / "tracker.json").write_text(json.dumps(snap, indent=2))
    return snap


def round_trip_facts(ctx, issue: IssueRef, start_sha: str, end_sha: str, snap: dict) -> dict:
    """Step 6 facts (design §4): the issue's state and comment count; commits in start..end referencing it; whether
    the issue links any commit of the step; the non-.py files the step changed (a spec trace of the fix)."""
    p = ctx.paths if ctx is not None else None
    log = gitops.commits_between(p, start_sha, end_sha)
    shas = [sha for sha, _ in commit_records(log)]
    match = next((i for i in snap.get("issues", [])
                  if str(i.get("number", i.get("id", ""))) == issue.id or i.get("ref") == issue.ref), {})
    comments = match.get("comments")
    n_comments = len(comments) if isinstance(comments, list) else int(match.get("comment_count") or 0)
    return {"issue": issue.ref, "state": match.get("state", match.get("status")), "comments": n_comments,
            "commits_referencing": commits_referencing(log, issue.id),
            "issue_links_commit": issue_links_commit(match, shas),
            "non_py_files_changed": sorted(f for _, _, f in gitops.numstat(p, start_sha, end_sha)
                                           if not f.endswith(".py"))}
