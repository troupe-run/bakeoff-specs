#!/usr/bin/env bash
# checklists/verify/speckit.sh MODE — CANDIDATES §1.2 (arm image, cwd = repo, network none, mounts read-only).
# Every command here was run against the pinned specify-cli 1.0.12 in bakeoff-arm-speckit:1.
set -u; . /checks/lib.sh; MODE=${1:-setup}
common speckit ""
# `specify version` prints a banner and a boxed panel; the CLI's own version is the "CLI Version" row
v=$(specify version 2>&1 | sed -n 's/.*CLI Version[[:space:]]*\([^[:space:]]*\).*/\1/p' | head -1)
check speckit.version "$( [ "$v" = 1.0.12 ]; echo $?)" "$v"
[ "$MODE" = step ] && exit 0
# skills mode (`--integration claude`): the workflow stages of §1.2 as .claude/skills/speckit-<cmd>/SKILL.md
missing=""; for s in constitution specify clarify plan tasks analyze implement converge taskstoissues; do
  [ -f ".claude/skills/speckit-$s/SKILL.md" ] || missing="$missing $s"; done
check speckit.skills "$( [ -z "$missing" ]; echo $?)" "missing:${missing:- none}"
# `specify extension add bug`: the bug process's three skills, and the extension registered and enabled
missing=""; for s in assess fix test; do [ -f ".claude/skills/speckit-bug-$s/SKILL.md" ] || missing="$missing $s"; done
en=$(jq -r '.extensions.bug.enabled // "absent"' .specify/extensions/.registry 2>/dev/null)
check speckit.bug-skills "$( [ -z "$missing" ] && [ "$en" = true ]; echo $?)" "missing:${missing:- none}; bug extension enabled: ${en:-no registry}"
# /speckit-constitution replaces the template's [UPPER_CASE] placeholders (init writes the template itself)
c=.specify/memory/constitution.md
check speckit.constitution "$( [ -s $c ] && ! grep -qE '\[[A-Z][A-Z0-9_]{2,}\]' $c; echo $?)" \
      "$(wc -c < $c 2>/dev/null || echo no) bytes; placeholders: $(grep -oE '\[[A-Z][A-Z0-9_]{2,}\]' $c 2>/dev/null | sort -u | head -3 | tr '\n' ' ')"
