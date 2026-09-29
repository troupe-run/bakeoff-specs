#!/usr/bin/env bash
# checklists/verify/control.sh MODE — arm image, cwd = repo, network none, mounts read-only (design §2 control arm)
set -u; . /checks/lib.sh; MODE=${1:-setup}
common control ""
[ "$MODE" = step ] && exit 0
# no methodology anywhere Claude Code reads one from: the repo (project scope), every directory above it inside
# the container (CLAUDE.md files are read from ancestors too), and the arm's user scope (~/.claude)
found=""
for f in .claude CLAUDE.md CLAUDE.local.md AGENTS.md .mcp.json \
         "$HOME/.claude/CLAUDE.md" "$HOME/.claude/skills" "$HOME/.claude/commands" "$HOME/.claude/agents" \
         "$HOME/.claude/output-styles"; do
  [ -e "$f" ] && found="$found $f"
done
d=$(dirname "$PWD")
while :; do
  for f in "$d/CLAUDE.md" "$d/CLAUDE.local.md"; do [ -e "$f" ] && found="$found $f"; done
  [ "$d" = / ] && break; d=$(dirname "$d")
done
for s in "$HOME/.claude/settings.json" "$HOME/.claude/settings.local.json"; do
  [ -e "$s" ] || continue
  jq -e '((.hooks // {}) | length) == 0 and (has("outputStyle") | not)' "$s" >/dev/null 2>&1 \
    || found="$found $s(hooks/outputStyle)"
done
check control.no-method "$( [ -z "$found" ]; echo $?)" "found:${found:- none}"
# setup adds nothing: the repo is repo.init's one empty commit, with nothing tracked, untracked or ignored
n=$(rgit rev-list --count HEAD 2>&1)
t=$(rgit ls-tree -r --name-only HEAD 2>/dev/null | wc -l | tr -d ' ')
s=$(rgit --no-optional-locks status --porcelain --ignored 2>/dev/null | wc -l | tr -d ' ')
check control.empty-repo "$( [ "$n" = 1 ] && [ "$t" = 0 ] && [ "$s" = 0 ]; echo $?)" "commits: $n; tracked files: $t; untracked or ignored: $s"
