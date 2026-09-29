#!/usr/bin/env bash
# checklists/verify/speckitty.sh MODE — CANDIDATES §1.4 + beads §2.1 (arm image, cwd = repo, network none, mounts
# read-only). Every command here was run against the pinned spec-kitty 3.2.7 / bd 1.3.0 in bakeoff-arm-speckitty:1.
set -u; . /checks/lib.sh; MODE=${1:-setup}
export SPEC_KITTY_NO_UPGRADE_CHECK=1                    # the check itself must not try PyPI (network none anyway)
common speckitty ""
# never a 4.0 RC: the whole version token (an rc suffix included) must be exactly 3.2.7
v=$(spec-kitty --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*' | head -1)
check speckitty.version "$( [ "$v" = 3.2.7 ]; echo $?)" "$v"
b=$(bd version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*' | head -1)
check beads.version "$( [ "$b" = 1.3.0 ]; echo $?)" "$b"
[ "$MODE" = step ] && exit 0
vs=$(spec-kitty verify-setup 2>&1); rc=$?
check speckitty.verify-setup "$rc" "exit $rc: $(printf '%s' "$vs" | grep -E '✓ Verification|✗|Error' | head -3 | tr '\n' ' ')"
# /spec-kitty.charter writes .kittify/charter/charter.md (narrative) and charter.yaml (authoritative) — its own command file
check speckitty.charter "$(ok_if bash -c 'test -s .kittify/charter/charter.md && test -s .kittify/charter/charter.yaml')" \
      "$(ls .kittify/charter 2>&1 | tr '\n' ' ')"
# `init --ai claude` installs the /spec-kitty.<cmd> commands user-scope ($CLAUDE_CONFIG_DIR/commands), not in the repo
missing=""; for c in charter specify plan tasks implement review accept merge; do
  [ -s "$CLAUDE_CONFIG_DIR/commands/spec-kitty.$c.md" ] || missing="$missing $c"; done
check speckitty.commands "$( [ -z "$missing" ]; echo $?)" "missing:${missing:- none}"
# settings (user and project): the hooks init installs and the one `bd setup claude` installs, both SessionStart
hooks() {  # hooks REGEX → how many SessionStart hook commands match
  cat "$CLAUDE_CONFIG_DIR/settings.json" .claude/settings.json .claude/settings.local.json 2>/dev/null | \
    jq -s --arg re "$1" '[.[] | .hooks.SessionStart // [] | .[] | .hooks[]? | .command // "" | select(test($re))] | length' 2>/dev/null
}
n=$(hooks '^spec-kitty session-start$')
check speckitty.session-hook "$( [ "${n:-0}" -ge 1 ]; echo $?)" "SessionStart hooks running spec-kitty session-start: ${n:-0}"
# the tracker group exists only with the SaaS-sync flag in 3.2.7 (ADR 2026-02-27). `status` opens (creating) its local
# cache under ~/.spec-kitty/trackers and the home is mounted read-only: it runs with a scratch copy of the home state
# it reads (in the container's own /tmp; the mounts are never written)
th=$(mktemp -d); for d in .spec-kitty .kittify .gitconfig; do [ -e "$HOME/$d" ] && cp -a "$HOME/$d" "$th/"; done
t=$(HOME=$th SPEC_KITTY_ENABLE_SAAS_SYNC=1 spec-kitty tracker status 2>/dev/null)
check speckitty.tracker-binding "$(printf '%s\n' "$t" | grep -qx -- '- provider: beads' && printf '%s\n' "$t" | grep -qx -- '- workspace: beads'; echo $?)" \
      "$(printf '%s' "$t" | grep -E '^- (provider|workspace):' | tr '\n' ' ')"
# the recorded egress decision (Channel 2) and the verdict spec-kitty's own gates enforce for a local subprocess (bd)
e=$(/opt/venvs/speckitty/bin/python - <<'PY' 2>&1
import sys
from pathlib import Path
from specify_cli.tracker.config import load_tracker_config
from specify_cli.tracker.egress_verdict import tracker_egress_verdict, EgressDestination
raw = load_tracker_config(Path(".")).egress
v = tracker_egress_verdict(Path("."), destination=EgressDestination.LOCAL_SUBPROCESS, identifiers="beads")
print(f"tracker.egress={raw!r}; local_subprocess {'REFUSED by ' + ','.join(sorted(v.refusing_channels)) if v.refused else 'permitted'}")
sys.exit(0 if raw == "permitted" and not v.refused else 1)
PY
); rc=$?
check speckitty.tracker-egress "$rc" "$e"
# embedded Dolt takes a lock file even for --readonly, and the repo is mounted read-only: list on a scratch copy of .beads
check beads.init "$(ok_if bash -c 'test -s .beads/config.yaml && b=$(mktemp -d) && cp -a .beads "$b/" && cd "$b" && bd --readonly --sandbox list --all --json')" \
      "$(ls .beads 2>/dev/null | tr '\n' ' ')"
n=$(hooks '^bd prime( |$)')
check beads.claude-hook "$( [ "${n:-0}" -ge 1 ]; echo $?)" "SessionStart hooks running bd prime: ${n:-0}"
m=$(bd metrics 2>&1 | grep -m1 -i 'usage metrics:')
check beads.metrics-off "$(printf '%s' "$m" | grep -q 'metrics: OFF'; echo $?)" "$m"
