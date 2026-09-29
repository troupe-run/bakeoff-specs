"""Installed commands, skills and model settings of an arm, listed INSIDE the arm's container (review F-6).

The host never walks an arm-controlled tree: `LIST_PY` runs in the arm image with `--network none` and every
mount read-only, and prints one JSON object. It lists project commands/skills/agents, plugins under
`CLAUDE_CONFIG_DIR/plugins` (route A) and `/opt/plugins` (route B), and every `model:` in agent/skill/command
frontmatter. `invocation()` turns a named command or skill into the method's own invocation form (review F-2).
"""
from __future__ import annotations
import json, re, uuid
from dataclasses import dataclass, field
from runner import config, docker, gitops, repo
from runner.docker import Mount, RunSpec
from runner.paths import Paths

LIST_PY = r'''
import json, os, re, sys
from pathlib import Path
repo, cfg = Path(sys.argv[1]), Path(sys.argv[2])
roots = [Path(x) for x in sys.argv[3:]]
names, models = set(), []
def model_of(f, shown):
    try:
        t = f.read_text(errors="replace")
    except OSError:
        return
    if t.startswith("---"):
        end = t.find("\n---", 3)
        m = re.search(r"(?m)^model:\s*['\"]?([^'\"\n#]+)", t[: end if end > 0 else 0])
        if m:
            models.append({"file": shown, "model": m.group(1).strip()})
def scan(root, plugin, shown_base):
    for f in sorted((root / "commands").rglob("*.md")) if (root / "commands").is_dir() else []:
        if f.is_symlink(): continue
        n = ":".join(f.relative_to(root / "commands").with_suffix("").parts)
        names.add(f"{plugin}:{n}" if plugin else n); names.add(n) if plugin else None
        model_of(f, f"{shown_base}commands/{f.relative_to(root / 'commands')}")
    for f in sorted((root / "skills").glob("*/SKILL.md")) if (root / "skills").is_dir() else []:
        if f.is_symlink(): continue
        n = f.parent.name
        names.add(f"{plugin}:{n}" if plugin else n); names.add(n)
        model_of(f, f"{shown_base}skills/{n}/SKILL.md")
    for f in sorted((root / "agents").glob("*.md")) if (root / "agents").is_dir() else []:
        if not f.is_symlink(): model_of(f, f"{shown_base}agents/{f.name}")
def load(f):
    if not f.is_file() or f.is_symlink():
        return None
    try:
        return json.loads(f.read_text(errors="replace"))
    except Exception:
        return "<unparseable>"
settings = [(repo / ".claude" / "settings.json", ".claude/settings.json"),
            (repo / ".claude" / "settings.local.json", ".claude/settings.local.json"),
            (cfg / "settings.json", "~/.claude/settings.json"), (cfg / "settings.local.json", "~/.claude/settings.local.json")]
enabled = {}
for f, shown in settings:                        # model choices in settings: `model` and every *MODEL* env value
    s = load(f)
    if s == "<unparseable>":
        models.append({"file": shown, "model": "<unparseable settings>"}); continue
    if not isinstance(s, dict):
        continue
    if isinstance(s.get("model"), str):
        models.append({"file": f"{shown}#model", "model": s["model"]})
    env = s.get("env")
    for k, v in sorted(env.items()) if isinstance(env, dict) else []:
        if "MODEL" in str(k).upper() and isinstance(v, str):
            models.append({"file": f"{shown}#env.{k}", "model": v})
    ep = s.get("enabledPlugins")
    for k, v in ep.items() if isinstance(ep, dict) else []:
        enabled[k] = enabled.get(k, True) and v is not False
scan(repo / ".claude", "", ".claude/")
scan(cfg, "", "~/.claude/")                       # user scope
# Route A: only plugins the installed-plugins record names (not every catalogue or stale cache copy), and not
# disabled in settings. Record shape: {"plugins": {"name@mkt": {installPath} | [{installPath}, ...]}}.
rec = load(cfg / "plugins" / "installed_plugins.json")
real_plugins = os.path.realpath(cfg / "plugins")
for key, entries in sorted(rec.get("plugins", {}).items()) if isinstance(rec, dict) and isinstance(rec.get("plugins"), dict) else []:
    if enabled.get(key) is False:
        continue
    for e in entries if isinstance(entries, list) else [entries]:
        ip = e.get("installPath") if isinstance(e, dict) else None
        if not isinstance(ip, str):
            continue
        root = Path(ip)
        if not root.is_dir() or not os.path.realpath(root).startswith(real_plugins + os.sep):
            continue
        m = load(root / ".claude-plugin" / "plugin.json")
        name = m.get("name") if isinstance(m, dict) and isinstance(m.get("name"), str) else str(key).split("@")[0]
        scan(root, name, f"{root}/")
for base in roots:                                # route B: plugins vendored into the image
    if not base.is_dir(): continue
    for man in sorted(base.rglob(".claude-plugin/plugin.json")):
        root = man.parent.parent
        try:
            name = json.loads(man.read_text())["name"]
        except Exception:
            continue
        scan(root, name, f"{root}/")
print(json.dumps({"names": sorted(names), "models": models}))
'''


@dataclass
class Listing:
    names: set[str]
    models: list[dict] = field(default_factory=list)


def parse_listing(text: str) -> Listing:
    o = json.loads(text)
    return Listing(set(o["names"]), list(o["models"]))


def listing(p: Paths, arm: config.Arm) -> Listing:
    repo.recover(p)                                          # never read a half-restored tree (Task 8 note)
    s = RunSpec(name=f"bk-list-{p.pass_}-{p.arm}-{uuid.uuid4().hex[:8]}",       # unique (preflight m13)
                image=gitops.image_for(arm.name), label=f"bakeoff.run={p.pass_}/{p.arm}",
                network="none", mounts=[Mount(p.work, "/work", True), Mount(p.home, p.container_home, True)],
                env={"HOME": p.container_home}, workdir="/work",
                cmd=["python3", "-c", LIST_PY, p.container_repo, f"{p.container_home}/.claude", "/opt/plugins"],
                stdin=False, limits=config.load_pins().limits, proxy=False)
    r = docker.run(s, timeout=120)
    if r.returncode != 0:
        raise docker.ContainerError(f"command listing failed: {r.stderr.decode(errors='replace')[:300]}")
    return parse_listing(r.stdout.decode())


def installed(p: Paths, arm: config.Arm) -> set[str]:
    return listing(p, arm).names


_LEAD = re.compile(r"^\s*(/[A-Za-z0-9][\w.:-]*)")


def leading(text: str) -> str | None:
    m = _LEAD.match(text)
    return m.group(1) if m else None


def invocation(name: str, arguments: str, installed_names: set[str]) -> str | None:
    """The method's own invocation form for a named command or skill (review F-2). Skills and commands are both
    invoked as /<name> in Claude Code (probe P6 confirms for skills)."""
    n = name.strip().split()[0].lstrip("/") if name.strip() else ""
    if n not in installed_names:
        return None
    return f"/{n}" + (f" {arguments.strip()}" if arguments and arguments.strip() else "")
