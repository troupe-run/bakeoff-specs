"""A fake `troupe` for the watcher selftest: on `config watch` it prints the readiness line, counts the
SIGTERMs it receives, and exits 0 shortly after the first — writing the count to $FAKE_SIGTERM_COUNT."""
import os, signal, sys, time

count = 0

def on_term(signum, frame):
    global count
    count += 1

assert sys.argv[1:3] == ["config", "watch"], sys.argv
signal.signal(signal.SIGTERM, on_term)
print("watching", flush=True)
while count == 0:
    time.sleep(0.05)
time.sleep(1.0)  # window in which a duplicate SIGTERM would land
with open(os.environ["FAKE_SIGTERM_COUNT"], "w") as f:
    f.write(str(count))
sys.exit(0)
