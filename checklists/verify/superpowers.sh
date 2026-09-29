#!/usr/bin/env bash
# checklists/verify/superpowers.sh MODE — CANDIDATES §1.1 (arm image, cwd = repo, network none, mounts read-only)
set -u; . /checks/lib.sh; MODE=${1:-setup}
common superpowers "superpowers"
# route B: the vendored copy. Route A: the installPath Claude Code recorded for the pinned install id
# (arms/superpowers.toml `install`) — exactly one entry, never a guess among cached versions or marketplaces.
if [ "${PLUGIN_ROUTE:-plugin-dir}" = plugin-dir ]; then root=/opt/plugins/superpowers
else root=$(jq -r '.plugins["superpowers@claude-plugins-official"] // [] | if length == 1 then .[0].installPath // empty else empty end' \
              "$CLAUDE_CONFIG_DIR/plugins/installed_plugins.json" 2>/dev/null)
     [ -n "$root" ] || root="<no installPath for superpowers@claude-plugins-official>"; fi
v=$(jq -r .version "$root/.claude-plugin/plugin.json" 2>/dev/null)
check superpowers.plugin-version "$( [ "$v" = 6.4.2 ]; echo $?)" "$root: $v"
[ "$MODE" = step ] && exit 0
# the eight workflow-stage skills (§1.1 "Workflow stages") and using-superpowers, the bootstrap the SessionStart
# hook injects (§1.1 item 2)
missing=""; for s in using-superpowers brainstorming using-git-worktrees writing-plans subagent-driven-development \
                     executing-plans test-driven-development requesting-code-review finishing-a-development-branch; do
  [ -f "$root/skills/$s/SKILL.md" ] || missing="$missing $s"; done
check superpowers.skills "$( [ -z "$missing" ]; echo $?)" "missing:${missing:- none}"
h=$(jq -r '[.hooks.SessionStart[]?.hooks[]?.command] | join(" ")' "$root/hooks/hooks.json" 2>/dev/null)
hs=1; case "$h" in *session-start*) [ -f "$root/hooks/session-start" ] && hs=0;; esac
check superpowers.session-hook "$hs" "SessionStart: ${h:-none}"
