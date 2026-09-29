# checklists/verify/lib.sh — sourced by every verify script. Prints JSON lines; never modifies anything.
# Runs in the arm image, --network none, home and work mounted read-only (checklist.verify). The expected values
# come from the runner as env (single source: pins.toml and gitops): BK_EXPECT_CLAUDE_VERSION, BK_EXPECT_GIT_NAME,
# BK_EXPECT_ORIGIN. An unset expectation fails its check rather than passing.
check() {  # check ID STATUS(0=ok) DETAIL
  local ok=false; [ "$2" = 0 ] && ok=true
  jq -cn --arg id "$1" --argjson ok "$ok" --arg d "$3" '{id:$id, ok:$ok, detail:$d}'
}
ok_if() { if "$@" >/dev/null 2>&1; then echo 0; else echo 1; fi; }
rgit() { git -c safe.directory='*' -c core.hooksPath=/dev/null -c core.fsmonitor=false "$@"; }
common() {  # common ARM EXPECTED_PLUGINS(space-separated, sorted; "" for none)
  local v; v=$(claude --version 2>&1)
  check common.claude-version "$( [ -n "${BK_EXPECT_CLAUDE_VERSION:-}" ] && [ "$v" = "$BK_EXPECT_CLAUDE_VERSION" ]; echo $?)" "$v"
  check common.isolation-env "$( [ "${CLAUDE_CODE_DISABLE_AUTO_MEMORY:-}" = 1 ] && [ "${CLAUDE_CONFIG_DIR:-}" = /home/actor/.claude ]; echo $?)" ""
  local n; n=$(git -c safe.directory='*' config user.name)
  check common.git-identity "$( [ -n "${BK_EXPECT_GIT_NAME:-}" ] && [ "$n" = "$BK_EXPECT_GIT_NAME" ]; echo $?)" "$n"
  local installed; installed=$( { jq -r '.plugins // {} | keys[]' "$CLAUDE_CONFIG_DIR/plugins/installed_plugins.json" 2>/dev/null | sed 's/@.*//';
                                   ls /opt/plugins 2>/dev/null; } | sort -u | tr '\n' ' ' | sed 's/ $//')
  check common.no-foreign-plugins "$( [ "$installed" = "$2" ]; echo $?)" "installed: ${installed:-none}"
  # preflight B4 (owner answer): origin is the local bare repo in the arm's home and its main resolves
  local u; u=$(rgit remote get-url origin 2>&1)
  local o=1
  if [ -n "${BK_EXPECT_ORIGIN:-}" ] && [ "$u" = "$BK_EXPECT_ORIGIN" ] \
     && rgit ls-remote --exit-code origin refs/heads/main >/dev/null 2>&1; then o=0; fi
  check common.origin "$o" "origin: $u"
}
