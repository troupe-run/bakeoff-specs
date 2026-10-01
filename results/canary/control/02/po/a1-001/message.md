I've added `troupe config watch`, and every command except `history` now picks up hand edits before it runs. It's committed on `main` as `cd06893`, not pushed. All 31 tests pass: the 24 existing ones plus 7 new ones in `tests/test_sync.py`, which run a real `watch` process.

**How it works**
- **Reconcile:** it loads the files and compares their leaves with what's been recorded, then records a `set` or `remove` for each leaf that differs. Formatting and comment edits produce no events because only values are compared.
- **Every command but `history`** reconciles first, including commands that go on to fail (e.g. `show` of a missing path). `history` only reports what's recorded. The one exception is its very first run, when nothing has been recorded yet: it records the current config first, as in step 1.
- **`watch`** reconciles, then prints `watching <dir>`. From then on it checks every 0.2s whether any file the config was loaded from has changed, and reconciles if so. SIGINT or SIGTERM makes it exit 0.
  - If a hand edit breaks the config mid-edit, the error goes to stderr and it keeps watching.
  - If it can't load the config at startup, it exits with code 4 like the other commands.
- **Includes added by hand:** `watch` also tracks include targets that don't exist yet. So an include added before its file is created is picked up once the file appears, and its leaves are recorded as `set` events.
- **`set` while `watch` runs:** every command, including `watch`, holds a new lock file (`.troupe/state.lock`) while it reads the files, writes them back and records events. By the time `watch` reads a `set`'s write-back, the `set`'s events are already recorded, so nothing extra is logged. In a test with 30 `set`s at once against a running `watch`, the log had exactly 30 set events.

**Decision for you:** `watch` prints the directory exactly as it was given (`watching <dir>`), not the resolved absolute path.

The main changes are in `cli.py`, `store.py` and `model.py`, and the README documents `watch`.