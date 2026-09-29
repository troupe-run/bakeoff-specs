#!/usr/bin/env bash
# checklists/verify/openspec.sh MODE — CANDIDATES §1.3 (arm image, cwd = repo, network none, mounts read-only)
set -u; . /checks/lib.sh; MODE=${1:-setup}
common openspec ""
v=$(openspec --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
check openspec.version "$( [ "$v" = 1.13.2 ]; echo $?)" "$v"
[ "$MODE" = step ] && exit 0
# the default `core` profile's six workflows (§1.3 item 3), as skills and as /opsx:<id> commands (§1.3 item 7)
missing=""; for s in propose explore apply-change update-change sync-specs archive-change; do
  [ -f ".claude/skills/openspec-$s/SKILL.md" ] || missing="$missing $s"; done
check openspec.skills "$( [ -z "$missing" ]; echo $?)" "missing:${missing:- none}"
missing=""; for c in propose apply archive update sync explore; do [ -f ".claude/commands/opsx/$c.md" ] || missing="$missing $c"; done
check openspec.commands "$( [ -z "$missing" ]; echo $?)" "missing:${missing:- none}"
check openspec.tree "$(ok_if bash -c 'test -d openspec/specs && test -d openspec/changes && grep -q "^schema: spec-driven" openspec/config.yaml')" \
      "$(ls -A openspec 2>&1 | tr '\n' ' ')"
t=$(openspec config get telemetry.enabled 2>&1 | tail -1)
check openspec.telemetry-off "$( [ "$t" = false ] && [ "${OPENSPEC_TELEMETRY:-}" = 0 ]; echo $?)" "config: $t; env: ${OPENSPEC_TELEMETRY:-unset}"
# config.yaml's `context`, parsed by OpenSpec's own YAML library, is exactly project-principles.md (§1.3 item 5; OD22)
ctx=$(node -e '
const fs = require("fs"), Y = require("/opt/openspec/node_modules/yaml");
const c = Y.parse(fs.readFileSync("openspec/config.yaml", "utf8")) || {};
const want = fs.readFileSync("/setup/project-principles.md", "utf8").replace(/\n+$/, "");
const got = typeof c.context === "string" ? c.context.replace(/\n+$/, "") : null;
if (got === null) { console.log("no context"); process.exit(1); }
if (got !== want) { console.log("context differs from project-principles.md"); process.exit(1); }
console.log("context is project-principles.md (" + got.split("\n").length + " lines)");' 2>&1)
check openspec.context "$?" "$ctx"
