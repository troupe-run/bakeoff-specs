Step 2 is built and committed on `main`, and all 27 tasks are marked done. Nothing was pushed. The full suite passes (437 tests), and `mypy --strict`, `ruff check` and `ruff format --check` are clean. The `watch` tests passed 5 runs in a row, and I walked through the quickstart by hand with every output as expected.

**What changed:**
- **Hand edits between commands:** `show` and `set` first record, as `set`/`remove` events, anything edited in the files since the last command. `history` never does this, so it still reports only what has been recorded. Formatting-only and comment-only edits record nothing.
- **`troupe config watch`:**
  - It records each edit within 2 seconds, including edits to included files, newly added includes, and editors that save by renaming.
  - It prints only the `watching <dir>` line, and exits 0 on SIGINT or SIGTERM.
  - If a file becomes invalid while it runs, it prints the error once and keeps going.
- **No double recording:** every command takes a lock (`.troupe/events.sqlite3.lock`) from loading the files until its events are saved. So a `set` made while `watch` runs is recorded once, and a hand edit is never recorded by two processes. A test running more than 10 `set`s with and without `watch` produces identical histories.

**Things that behave differently from before:**
- I updated a step 1 test (`test_history.py`) that asserted hand edits are never recorded. Step 2 replaces that rule, and I marked the old decision as superseded in the step 1 spec.
- If the theatre has no `.troupe/` directory, the error names the missing config file rather than the lock file, as it did before step 2.
- I committed the first change before running ruff. `a9a46ba` fixes the lint and formatting issues that slipped in.

**Checking that the tests catch real breakage:** for each story I deliberately broke the code and confirmed a test failed.
- **Weak plan entry:** one break the plan listed, never refreshing the list of watched files, isn't really a bug. `watch` just re-checks on every poll and still records correctly. I broke it a different way instead, by leaving included files unwatched, and 4 tests caught that.
- **Startup race (`watching` line):** an edit made between `watch` reading the files and printing its line could go unnoticed. End-to-end tests can't hit that timing reliably (the break passed 10 out of 10 runs), so I added `tests/unit/test_watch_snapshot.py`. It makes the edit at exactly that moment and fails if the edit is missed.
- **Recording outside the lock:** if a `set` saves its events after releasing the lock, the unit test fails. The end-to-end tests only catch it when the save is slowed by 0.3 s; with that delay they failed 20 out of 20 runs. Without it the window is too short for them to notice.

No extension hooks are registered for this step.