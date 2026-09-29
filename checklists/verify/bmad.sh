#!/usr/bin/env bash
# checklists/verify/bmad.sh MODE — CANDIDATES §1.5 (arm image, cwd = repo, network none, mounts read-only).
# PARKED (preflight B2, arms/bmad.toml): written from the docs so it is ready when the arm is unparked.
set -u; . /checks/lib.sh; MODE=${1:-setup}
common bmad "bmad-core-tools bmad-method"
bad=""
for pl in bmad-method bmad-core-tools; do
  if [ "${PLUGIN_ROUTE:-plugin-dir}" = plugin-dir ]; then f=/opt/plugins/$pl/.claude-plugin/plugin.json
  else f=$(find "$CLAUDE_CONFIG_DIR/plugins" -path "*$pl*/.claude-plugin/plugin.json" 2>/dev/null | head -1); fi
  v=$(jq -r .version "$f" 2>/dev/null); case "$v" in 6.12.*) ;; *) bad="$bad $pl=${v:-none}";; esac
done
check bmad.plugin-version "$( [ -z "$bad" ]; echo $?)" "bad:${bad:- none}"
[ "$MODE" = step ] && exit 0
# `bmad setup` writes _bmad/ (team config _bmad/config.toml) and the output folder _bmad-output/ (§1.5 item 3)
check bmad.setup-done "$(ok_if bash -c 'test -f _bmad/config.toml && test -d _bmad-output')" "$(ls -A _bmad 2>&1 | tr '\n' ' ')"
# ticketing configured from the gh starter (§1.5 item 5): [tickets] store = "github"; a set repo must be this arm's
tk=$(python3 - <<'PY' 2>&1
import os, sys, tomllib
try:
    t = tomllib.load(open("_bmad/custom/ticketing-store-config.toml", "rb")).get("tickets", {})
except Exception as e:
    print(f"unreadable: {e}"); sys.exit(1)
store, repo, want = t.get("store"), t.get("repo", ""), os.environ.get("GH_REPO", "")
print(f"store={store!r} repo={repo!r} GH_REPO={want!r}")
sys.exit(0 if store == "github" and (repo == "" or repo == want) else 1)
PY
)
check bmad.ticketing-gh "$?" "$tk"
# PEP 723 scripts locked (review S-5): hub scripts and each module's scripts; at least one hub script must exist
unlocked=""; n=0
for f in _bmad/scripts/*.py _bmad/*/scripts/*.py; do [ -e "$f" ] || continue; n=$((n + 1))
  if grep -q '^# /// script' "$f" && [ ! -f "$f.lock" ]; then unlocked="$unlocked $f"; fi; done
hub=$(ls _bmad/scripts/*.py 2>/dev/null | wc -l | tr -d ' ')
check bmad.scripts-locked "$( [ -z "$unlocked" ] && [ "$hub" -ge 1 ]; echo $?)" "$n scripts ($hub hub); unlocked:${unlocked:- none}"
