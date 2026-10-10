## Implementation Complete

**Change:** `config-sync-with-files` (spec-driven), **21/21 tasks complete**. The work is committed on `main` and not pushed. All 379 tests pass, `mypy --strict` and ruff are clean, and `openspec validate --strict` passes. I ran the timing-sensitive tests (`watch`, the lock and the `uv run` smoke tests) three more times and they passed each time.

### What it does now
- **Hand edits are recorded:** `show`, `set` and `watch` first compare the files with what has been recorded and add a `set` or `remove` event for each value that differs. Formatting-only and comment-only edits add nothing. `history` never does this check; it only reports what has been recorded. This uses the same comparison `set` already used, now in `src/troupe/leaves.py`, and the new `src/troupe/sync.py`.
- **Commands take turns:** each command locks the `.troupe/` folder itself, so no lock file is created. `set` keeps the lock until its events are saved, so `watch` never records troupe's own write-back. A test holds the lock and checks that both `set` and `watch` wait for it. I also disabled the lock briefly and confirmed those tests then fail.
- **`troupe config watch`:** it prints `watching <dir>` only once it is ready. It records an edit in well under 2 seconds, including edits to included files, saves that replace the file, and includes added by hand. If the files stop loading, it reports this once on stderr, keeps running, and catches up when they load again. Ctrl-C and SIGTERM exit 0 with nothing on stderr. A smoke test confirms this works through `uv run`.

### Changes from what you might expect
- **Tests:** `test_hand_edits_are_not_reconciled` became `test_hand_edits_are_not_imported`. `test_set_records_old_value_from_the_files` now expects the hand edit's event before the `set`'s own. The new tests are in `test_reconcile.py`, `test_watch.py` and `test_lock.py`, plus one each in `test_loading.py` and `test_smoke.py`.
- **README:** it now covers reconciling and `watch`, and lists decisions 11–14. I also fixed a stale link to the step-1 design, which had moved to the archive folder.
- **Design doc:** I updated it to match the code. The session function takes the command name (checked against one list of commands that reconcile) and an optional store, instead of a true/false flag.

The specs aren't merged into `openspec/specs/` yet; that happens when you archive the change with `/opsx:archive`.