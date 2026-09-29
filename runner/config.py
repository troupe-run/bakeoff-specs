"""Pins and per-arm configuration. Everything that differs between arms lives in config/arms/<arm>.toml."""
from __future__ import annotations
import re, tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent / "config"
ARMS_DIR = CONFIG_DIR / "arms"
REAL_ARMS = ("bmad", "ccsdd", "control", "openspec", "speckit", "speckitty", "superpowers")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    turn_seconds: int
    exchanges_per_attempt: int
    owner_reclassifies_first_breach: bool
    attempts_no_progress: int
    mutation_seconds: int
    mutation_sample: int
    load_factor: float
    cpus: str
    memory: str
    pids: int
    transient_backoff: list[int]


@dataclass(frozen=True)
class Pins:
    claude_version: str
    model: str
    accepted_models: list[str]
    synthetic_models: list[str]
    max_retries: int
    permission_mode: str
    disallowed_tools: list[str]
    binary_sha256: str
    bd_sha256: str        # @beads/bd's native binary hash (fix-round-1 item 1); written by `runner images pin`
    images: dict[str, str]
    digests: dict[str, str]
    limits: Limits
    pass2_order: str
    plugin_route: str
    egress_setup_common: list[str]
    egress_run_common: list[str]
    egress_po: list[str]
    egress_tester_prep: list[str]


@dataclass(frozen=True)
class Plugin:
    name: str             # plugin name as installed, e.g. "superpowers"
    marketplace: str      # e.g. "anthropics/claude-plugins-official" ("" = already added by an earlier entry)
    install: str          # e.g. "superpowers@claude-plugins-official"
    version: str          # pinned; verified by the checklist
    repo: str             # GitHub repo holding the plugin source, e.g. "obra/superpowers" (OD9 B)
    tag: str              # e.g. "v6.4.2"
    sha: str = ""         # the tag's commit, written by `runner images pin`
    subdir: str = ""      # plugin root inside the repo ("" = repo root)


VOLATILE_KINDS = ("install-stamp", "model-written")


@dataclass(frozen=True)
class Volatile:
    """A manifest entry (a file, or a directory prefix) the pass-2 comparison leaves out (Task 11 FR1 item 6).
    `install-stamp`: the tool writes a timestamp or per-run id there — a test proves it differs between two identical
    offline setups. `model-written`: the setup agent turn writes it — the checklist names it and the owner reads it."""
    path: str
    kind: str
    why: str


@dataclass(frozen=True)
class Smoke:
    prompt: str
    expect_skill: str


@dataclass(frozen=True)
class Arm:
    name: str
    tool: str
    version: str
    citation: str
    image: str
    tracker: str
    repo_name: str
    env: dict[str, str]
    egress_setup: list[str]
    egress_run: list[str]
    setup_shell: list[str]
    setup_agent: list[str]
    setup_post_shell: list[str]                  # shell steps after the agent turns (e.g. BMAD script locks)
    plugins: list[Plugin]
    smoke: Smoke | None
    manifest_paths: list[str]
    entry: str
    bug_entry: str
    must_run: list[str]
    must_run_source: str
    fresh_session_before: list[dict[str, str]]    # [{command, source}] (OD19 B)
    export_after: str                              # speckit only (OD24 B): the command after which export runs
    dry: bool = False
    volatile_paths: list[Volatile] = field(default_factory=list)   # excluded from the pass-2 manifest comparison


_ANCHORED = re.compile(r"^\^.+\$$")
TOP = {"name", "tool", "version", "citation", "image", "tracker", "repo_name", "env", "egress", "setup", "drive", "dry"}
SETUP = {"shell", "agent", "post_shell", "plugins", "smoke", "manifest_paths", "volatile_paths"}
DRIVE = {"entry", "bug_entry", "must_run", "must_run_source", "fresh_session_before", "export_after"}


def _check_hosts(patterns: list[str], where: str) -> list[str]:
    for p in patterns:
        if not _ANCHORED.match(p):
            raise ConfigError(f"{where}: host pattern {p!r} must be anchored (^…$), spike B Q3")
    return list(patterns)


def _only(d: dict, allowed: set[str], where: str) -> dict:
    extra = set(d) - allowed
    if extra:
        raise ConfigError(f"{where}: unknown key(s) {sorted(extra)}")
    return d


def load_pins() -> Pins:
    raw = tomllib.loads((CONFIG_DIR / "pins.toml").read_text())
    c, e, im = raw["claude"], raw["egress"], dict(raw["images"])
    digests = im.pop("digests")
    if raw["order"]["pass2_order"] not in ("same", "reverse"):
        raise ConfigError("pins.order.pass2_order must be same|reverse")
    if raw["plugins"]["route"] not in ("marketplace", "plugin-dir"):
        raise ConfigError("pins.plugins.route must be marketplace|plugin-dir")
    return Pins(
        claude_version=c["version"], model=c["model"], accepted_models=list(c["accepted_models"]),
        synthetic_models=list(c["synthetic_models"]), max_retries=int(c["max_retries"]),
        permission_mode=c["permission_mode"], disallowed_tools=list(c["disallowed_tools"]),
        binary_sha256=c["binary_sha256"], bd_sha256=raw["beads"]["sha256"], images=im, digests=dict(digests),
        limits=Limits(**raw["limits"]), pass2_order=raw["order"]["pass2_order"],
        plugin_route=raw["plugins"]["route"],
        egress_setup_common=_check_hosts(e["setup_common"], "pins.egress.setup_common"),
        egress_run_common=_check_hosts(e["run_common"], "pins.egress.run_common"),
        egress_po=_check_hosts(e["po"], "pins.egress.po"),
        egress_tester_prep=_check_hosts(e["tester_prep"], "pins.egress.tester_prep"),
    )


def load_arm(name: str) -> Arm:
    where = f"arms/{name}.toml"
    raw = _only(tomllib.loads((ARMS_DIR / f"{name}.toml").read_text()), TOP, where)
    eg = _only(raw.get("egress", {}), {"setup", "run"}, where + " [egress]")
    su = _only(raw.get("setup", {}), SETUP, where + " [setup]")
    dr = _only(raw.get("drive", {}), DRIVE, where + " [drive]")
    if raw.get("tracker") not in ("github", "beads", "dry"):
        raise ConfigError(f"{where}: tracker must be github|beads|dry")
    if "{handoff}" not in dr.get("entry", "") or "{handoff}" not in dr.get("bug_entry", ""):
        raise ConfigError(f"{where}: entry and bug_entry must contain {{handoff}}")
    must_run = list(dr.get("must_run", []))
    if must_run and not dr.get("must_run_source"):
        raise ConfigError(f"{where}: must_run needs must_run_source (a CANDIDATES citation, review F-5)")
    fresh = [dict(x) for x in dr.get("fresh_session_before", [])]
    if any(not x.get("source") for x in fresh):
        raise ConfigError(f"{where}: every fresh_session_before entry needs a source (OD19)")
    sm = su.get("smoke")
    manifest_paths = list(su.get("manifest_paths", [".claude"]))
    return Arm(
        name=raw["name"], tool=raw["tool"], version=raw["version"], citation=raw.get("citation", ""),
        image=raw["image"], tracker=raw["tracker"], repo_name=raw["repo_name"], env=dict(raw.get("env", {})),
        egress_setup=_check_hosts(eg.get("setup", []), where), egress_run=_check_hosts(eg.get("run", []), where),
        setup_shell=list(su.get("shell", [])), setup_agent=list(su.get("agent", [])),
        setup_post_shell=list(su.get("post_shell", [])),
        plugins=[Plugin(**p) for p in su.get("plugins", [])],
        smoke=Smoke(sm["prompt"], sm["expect_skill"]) if sm else None,
        manifest_paths=manifest_paths, volatile_paths=_volatile(su.get("volatile_paths", []), manifest_paths, where),
        entry=dr["entry"], bug_entry=dr["bug_entry"], must_run=must_run,
        must_run_source=dr.get("must_run_source", ""), fresh_session_before=fresh,
        export_after=dr.get("export_after", ""), dry=bool(raw.get("dry", False)),
    )


def _volatile(raw: list, manifest_paths: list[str], where: str) -> list[Volatile]:
    out = []
    for v in raw:
        v = _only(dict(v), {"path", "kind", "why"}, where + " volatile_paths")
        if not str(v.get("why", "")).strip():
            raise ConfigError(f"{where}: volatile path {v.get('path')!r} needs a why (the reason it may differ)")
        if v.get("kind") not in VOLATILE_KINDS:
            raise ConfigError(f"{where}: volatile path {v.get('path')!r}: kind must be one of {VOLATILE_KINDS}")
        path = str(v.get("path", "")).rstrip("/")
        if not any(path == m.rstrip("/") or path.startswith(m.rstrip("/") + "/") for m in manifest_paths):
            raise ConfigError(f"{where}: volatile path {path!r} is under no manifest path (it would hide nothing)")
        out.append(Volatile(path, v["kind"], v["why"]))
    return out


GITHUB_ORG = "troupe-run"


def github_slug(pass_: str, arm: str) -> str | None:
    """The arm's GitHub repo for a pass; None on dry/probe passes. Single source for repo naming: Task 8's
    `repo.github_slug` re-exports this, and `credentials.session_env` uses it for GH_REPO (preflight M4).
    With the owner's local bare origin (B4), `gh` can no longer infer the repo from origin, hence GH_REPO."""
    if pass_ == "pass1":
        return f"{GITHUB_ORG}/bakeoff-specs-{arm}-pass1"
    if pass_ == "pass2":
        return f"{GITHUB_ORG}/bakeoff-specs-{arm}"
    if pass_ == "canary":
        return f"{GITHUB_ORG}/bakeoff-specs-{arm}-canary"
    return None


def all_arms() -> list[str]:
    return list(REAL_ARMS)
