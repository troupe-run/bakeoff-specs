Q1: I've added `troupe config watch`, and every command except `history` now picks up edits made while nothing was running. It's committed on `main` as `7708ad1`. All 54 tests pass, and I ran the new `watch` tests 5 more times with no failures.

**How it works**
- **Reconcile:** a command loads the files and compares their leaf values with the recorded configuration. It records a `set` or `remove` for each leaf that differs. The comparison checks types too, so `1` → `'1'` counts as a change. Formatting or comment edits produce no events.
- **`history`:** never reconciles. Once anything has been recorded, it works even if the files are currently broken.
- **`set`'s write-back isn't picked up again:** every load, reconcile and write holds an exclusive lock on the `.troupe/` folder. `set` writes its files and records its events before releasing the lock, so when `watch` next reconciles, files and records already match. I tested this with `set` run in-process and as separate processes while `watch` was running.
- **`watch`:**
  - It reconciles, then prints `watching <dir>` using the path as you passed it.
  - It then checks every 0.1s whether the config file or any included file differs from what it last loaded, well inside the 2-second limit.
  - It exits 0 on SIGINT or SIGTERM.
  - It checks file contents rather than using OS file-change notifications, which needs no new dependency and still covers includes outside `.troupe/` or not yet created.

**Choices the spec didn't settle** (all recorded in `docs/decisions.md`, items 11–15):
- If the config can't be loaded when `watch` starts, it exits 4 like the other commands and never prints the `watching` line.
- If a later edit breaks the config (a half-saved file, or an include whose file doesn't exist yet), `watch` prints the error to stderr once and keeps retrying until the files load again.
- Reconcile records `set`s in file order, then `remove`s, the same order `set` already uses.

I replaced the old test `test_import_is_not_reconciling`, because it checked the opposite of what the new spec requires. The new tests are in `tests/test_sync.py`, and the README is updated.
A1 (runner): /superpowers:finishing-a-development-branch