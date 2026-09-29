#!/usr/bin/env bash
# checklists/verify/control.sh MODE — arm image, cwd = repo, network none, mounts read-only (design §2 control arm)
set -u; . /checks/lib.sh; MODE=${1:-setup}
common control ""
[ "$MODE" = step ] && exit 0
# no methodology anywhere Claude Code reads one from: project scope (repo) and user scope (the arm's home)
found=""
for f in .claude CLAUDE.md CLAUDE.local.md AGENTS.md .mcp.json \
         "$HOME/.claude/CLAUDE.md" "$HOME/.claude/skills" "$HOME/.claude/commands" "$HOME/.claude/agents"; do
  [ -e "$f" ] && found="$found $f"
done
check control.no-method "$( [ -z "$found" ]; echo $?)" "found:${found:- none}"
# setup adds nothing: the repo is repo.init's one empty commit, with nothing tracked, untracked or ignored
n=$(rgit rev-list --count HEAD 2>&1)
t=$(rgit ls-tree -r --name-only HEAD 2>/dev/null | wc -l | tr -d ' ')
s=$(rgit --no-optional-locks status --porcelain --ignored 2>/dev/null | wc -l | tr -d ' ')
check control.empty-repo "$( [ "$n" = 1 ] && [ "$t" = 0 ] && [ "$s" = 0 ]; echo $?)" "commits: $n; tracked files: $t; untracked or ignored: $s"
