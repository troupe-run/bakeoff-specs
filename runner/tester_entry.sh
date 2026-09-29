# runner/tester_entry.sh — run as `bash -c "<this text>" entry <timeout> <pytest argv...>` inside the tester
# (runner/hidden.py). Runs as the HARNESS uid (1000) with ambient SETUID/SETGID/KILL/DAC_OVERRIDE/SETPCAP/
# SYS_RESOURCE; the arm's CLI runs as uid 1001 (pytest's --cmd-prefix) with no capabilities at all.
#
# Usage: bash -c "<this>" entry <unpacker source> <timeout> <pytest argv...>
# stdin: the hidden suite as length-framed records (`<path> <size>\n<bytes>`), unpacked by runner/bundle_unpack.py
#        into /harness — a tmpfs
#        owned by uid 1000, mode 0700 — BEFORE any arm code runs (fix round 2: bind mounts are readable by all).
# stdout: ONLY length-framed records for exit, timed_out, resources, junit.xml, pytest.log (each if present
#        and a regular file) from /results, another uid-1000 0700 tmpfs the arm cannot fill or enter.
set -u
umask 077
R=/results
U="$1"; T="$2"; shift 2                 # U: runner/bundle_unpack.py source; T: timeout seconds
/opt/harness/bin/python -c "$U" /harness || exit 92
cd /harness || exit 93
start=$SECONDS
timeout --signal=TERM --kill-after=30 "$T" "$@" >"$R/pytest.log" 2>&1 </dev/null
rc=$?
if { [ "$rc" = 124 ] || [ "$rc" = 137 ]; } && [ $((SECONDS - start)) -ge "$T" ]; then : >"$R/timed_out"; fi
echo "$rc" >"$R/exit"
{ cat /sys/fs/cgroup/memory.events 2>/dev/null; echo --pids; cat /sys/fs/cgroup/pids.events 2>/dev/null
  echo --tmp; df -P /tmp | tail -n 1; echo --results; df -P /results | tail -n 1; } >"$R/resources"
pkill -KILL -U 1001 2>/dev/null         # no arm process outlives pytest into the copy-out
if [ "$(stat -c %s "$R/pytest.log")" -gt 8000000 ]; then
  tail -c 8000000 "$R/pytest.log" >"$R/log.tail" && mv -f "$R/log.tail" "$R/pytest.log"
fi
cd "$R" || exit 91
for f in exit timed_out resources junit.xml pytest.log; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then
    printf '%s %s\n' "$f" "$(stat -c %s "$f")"
    cat "$f"
  fi
done
