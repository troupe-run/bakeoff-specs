#!/usr/bin/env bash
# checklists/verify/ccsdd.sh MODE — CANDIDATES §1.7a (arm image, cwd = repo, network none, mounts read-only).
# Every command here was run against the pinned cc-sdd 3.1.0 in bakeoff-arm-ccsdd:1.
set -u; . /checks/lib.sh; MODE=${1:-setup}
common ccsdd ""
# the image links node_modules/.bin/cc-sdd onto PATH (no global npm package): ask the bin itself
v=$(cc-sdd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*' | head -1)
check ccsdd.version "$( [ "$v" = 3.1.0 ]; echo $?)" "$v"
[ "$MODE" = step ] && exit 0
# "It installs 17 skills" (§1.7a): exactly these, as 3.1.0 --claude-skills writes them — no more, no fewer
want="kiro-debug kiro-discovery kiro-impl kiro-review kiro-spec-batch kiro-spec-design kiro-spec-init kiro-spec-quick
kiro-spec-requirements kiro-spec-status kiro-spec-tasks kiro-steering kiro-steering-custom kiro-validate-design
kiro-validate-gap kiro-validate-impl kiro-verify-completion"
got=$(for f in .claude/skills/kiro-*/SKILL.md; do [ -f "$f" ] && basename "$(dirname "$f")"; done | sort | tr '\n' ' ' | sed 's/ $//')
w=$(echo $want | tr ' ' '\n' | sort | tr '\n' ' ' | sed 's/ $//')
check ccsdd.skills "$( [ "$got" = "$w" ]; echo $?)" "$(echo $got | wc -w) kiro skills; missing: $(comm -23 <(echo $w | tr ' ' '\n') <(echo $got | tr ' ' '\n') | tr '\n' ' ')extra: $(comm -13 <(echo $w | tr ' ' '\n') <(echo $got | tr ' ' '\n') | tr '\n' ' ')"
# the templates the spec skills fill ("Settings templates and rules → .kiro/settings/") and the project memory
check ccsdd.settings "$(ok_if bash -c 'for d in specs steering steering-custom; do ls .kiro/settings/templates/$d/*.md >/dev/null 2>&1 || exit 1; done')" \
      "$(ls .kiro/settings/templates 2>&1 | tr '\n' ' ')"
check ccsdd.project-memory "$(ok_if bash -c 'grep -q "\.kiro/steering/" CLAUDE.md && grep -q "\.kiro/specs/" CLAUDE.md')" \
      "$(head -1 CLAUDE.md 2>&1)"
n=$(ls .kiro/steering/*.md 2>/dev/null | wc -l | tr -d ' ')
check ccsdd.steering "$( [ "$n" -ge 1 ] && [ -z "$(find .kiro/steering -name '*.md' -empty 2>/dev/null)" ]; echo $?)" "$n steering files"
# skills only: the deprecated `--claude` command mode writes .claude/commands/kiro/ (§1.7a)
check ccsdd.no-legacy "$(ok_if bash -c '! test -e .claude/commands/kiro')" "$(ls -d .claude/commands/kiro 2>/dev/null || echo 'no .claude/commands/kiro')"
