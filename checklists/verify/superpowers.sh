#!/usr/bin/env bash
# checklists/verify/superpowers.sh MODE — CANDIDATES §1.1 (arm image, cwd = repo, network none, mounts read-only)
set -u; . /checks/lib.sh; MODE=${1:-setup}
common superpowers "superpowers"
if [ "${PLUGIN_ROUTE:-plugin-dir}" = plugin-dir ]; then root=/opt/plugins/superpowers
else root=$(dirname "$(dirname "$(find "$CLAUDE_CONFIG_DIR/plugins" -path '*superpowers*/.claude-plugin/plugin.json' 2>/dev/null | head -1)")"); fi
v=$(jq -r .version "$root/.claude-plugin/plugin.json" 2>/dev/null)
check superpowers.plugin-version "$( [ "$v" = 6.4.2 ]; echo $?)" "$root: $v"
[ "$MODE" = step ] && exit 0
# the workflow skills (§1.1 "Workflow stages") and using-superpowers, the bootstrap the SessionStart hook injects (§1.1 item 2)
missing=""; for s in using-superpowers brainstorming writing-plans subagent-driven-development test-driven-development \
                     finishing-a-development-branch; do
  [ -f "$root/skills/$s/SKILL.md" ] || missing="$missing $s"; done
check superpowers.skills "$( [ -z "$missing" ]; echo $?)" "missing:${missing:- none}"
h=$(jq -r '[.hooks.SessionStart[]?.hooks[]?.command] | join(" ")' "$root/hooks/hooks.json" 2>/dev/null)
hs=1; case "$h" in *session-start*) [ -f "$root/hooks/session-start" ] && hs=0;; esac
check superpowers.session-hook "$hs" "SessionStart: ${h:-none}"
