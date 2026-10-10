The four convergence tasks (T028–T031) are done and committed on `main` as `aacd93a`, and every task in `tasks.md` is now checked off. They added only tests; no source code changed. The full suite passes (442 tests), and `mypy --strict`, `ruff check` and `ruff format --check` are clean.

| Task | New test | What it checks | Fails when I break it by… |
|---|---|---|---|
| T028 | `test_main_file_deleted_then_recreated` | Deleting the main file while `watch` runs prints one error naming it, records nothing and `watch` keeps running; recreating it records the change within 2 s | making `watch` give up on a load error |
| T029 | `test_signal_during_a_reconcile_lets_it_finish` | SIGTERM while `watch` waits on the lock with an edit pending: it finishes the reconcile, records exactly one event, exits 0, and stdout is just the `watching` line | making the signal end the process immediately |
| T030 | `test_scalar_replaced_by_collections_by_hand` and `test_collection_replaced_by_a_scalar_by_hand` | Hand edits that change a value's kind record the new values first, then the removed ones, in that order | recording removals before new values |
| T031 | `test_edit_in_an_include_of_an_include_is_recorded` | `watch` picks up an edit in an include two levels deep within 2 s | not watching files below the first include level |

T029's wording was ambiguous ("one event or none", then "exactly one"); the test checks for exactly one event.

The `requirements.md` checklist passed 16/16 before I started, and no extension hooks are registered. Another `/speckit-converge` run should now come back clean.