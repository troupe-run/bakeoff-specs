#!/bin/bash
# runner/tester_entry.sh — mounted read-only at /harness/entry.sh in the tester (runner/hidden.py, fix round 1).
# Runs as the HARNESS uid (1000) with ambient SETUID/SETGID/KILL/DAC_OVERRIDE; the arm's CLI runs as uid 1001
# (pytest's --cmd-prefix) with no capabilities, so it can neither signal pytest nor write this results dir.
# Usage: entry.sh <timeout-seconds> <pytest argv...>
# Output: ONLY a tar of the results dir on stdout (exit, pytest.log, junit.xml if written, timed_out if so).
set -u
umask 077
R=/tmp/results
mkdir -m 700 "$R" || exit 90            # created before any arm code runs; nobody else can enter it
T="$1"; shift
start=$SECONDS
timeout --signal=TERM --kill-after=30 "$T" "$@" >"$R/pytest.log" 2>&1 </dev/null
rc=$?
if [ $((SECONDS - start)) -ge "$T" ]; then : >"$R/timed_out"; fi
echo "$rc" >"$R/exit"
pkill -KILL -U 1001 2>/dev/null         # no arm process outlives pytest into the copy-out
if [ "$(stat -c %s "$R/pytest.log")" -gt 8000000 ]; then
  tail -c 8000000 "$R/pytest.log" >"$R/log.tail" && mv -f "$R/log.tail" "$R/pytest.log"
fi
cd "$R" && exec tar -cf - $(ls -A)
