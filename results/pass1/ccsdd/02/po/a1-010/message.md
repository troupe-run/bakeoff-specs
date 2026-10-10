Step 2 ("Sync with files") is built and committed on `main`, and the final check is **GO**. On the final commit (`c89fc30`), 2113 tests pass, mypy and ruff are clean, and the working tree is clean. Nothing was pushed and no pull request was opened.

## What changed
- **Every command except `history` reconciles first.** It compares the files with what the history has recorded, leaf by leaf, and records a `set` or `remove` for each difference. Edits that only change formatting or comments record nothing.
- **`history` never reconciles.** It still imports a theatre that has never been imported.
- **`troupe config watch`:**
  - prints `watching <dir>` only once it can already see changes;
  - records each edit within 2 seconds, including edits to includes and includes added or removed by hand;
  - reports a broken file once and recovers when it's fixed;
  - exits 0 on SIGINT or SIGTERM.
- **A per-theatre lock:** it uses the existing `.troupe/` directory, so no file is created. A `set` running alongside `watch` records exactly its own events and its write-back is never recorded again.

## How it was done
All 12 tasks went through implementation, an independent review, and a fresh test run before each commit. The reviews caught three real problems:
- **Task 2.3:** a removed leaf under an empty key would have made every later reconcile fail. Fixed, and the design updated.
- **Task 4.1:** a file read halfway through a save could leave false `remove` events in the history that were never corrected. Fixed by comparing against the bytes the load actually read, with a regression test.
- **Task 5.1:** the timing tests were too lenient to catch a readiness race or a too-slow polling interval. Strengthened, and shown to fail against both bugs.

## Final validation
- A real `watch` session in a temporary theatre covered a hand edit, a `set` alongside it, a hand-added include, a comment-only edit and SIGTERM. The history came out exactly as specified, stderr was empty, the exit code was 0, and `.troupe/` held only the config files and `history.sqlite`.
- An independent audit found the code consistent with the design and its boundaries. Every one of the 44 requirements is covered by a test.
- The step-1 specs and roadmap now say where step 2 replaces "hand edits add no events", and the six step-1 tests that asserted the old behaviour were rewritten in the same change as the new behaviour.
- After the audit I added two small tests: `watch` with an unknown option, and core code never importing the CLI.

## Known gaps
None of these blocks the feature:
- Under requirement 6.2, a `set` that *fails* (exit 4) while `watch` runs has no end-to-end test. Only the *refused* case (exit 3) is tested.
- If releasing the lock itself fails during an error, that release error would be reported instead of the original error. This is very unlikely.
- Pressing Ctrl-C while an ordinary command waits for the lock leaves the lock's file handle open until that process exits, which happens immediately. It's harmless.
- The full suite now takes about 3 minutes under `pytest -n auto`, mostly because of the timing-based `watch` tests.