I've written the task list for step 2 and committed it on `main` (`57ed6d4`). It's at `specs/002-config-file-sync/tasks.md` and has 27 tasks; nothing has been built yet.

| Phase | Tasks | What gets done |
|---|---|---|
| Setup | T001 | Run the test suite, `mypy --strict` and ruff on current `main` to confirm it's green before any change |
| Foundational | T002–T010 (9) | The shared store lock, recording the exact file bytes each load read, reconcile, one entry point for every command, and the CLI changes (`--theatre` kept as typed, one error-line format) |
| US1 Edits made between runs (P1) 🎯 MVP | T011–T012 (2) | `show` and `set` record hand edits first; `history` never does |
| US2 Live `watch` (P1) | T013–T017 (5) | A test helper that runs `watch` as a real process, the `watch` command itself, and signal handling |
| US3 No double recording (P1) | T018–T019 (2) | A `set` while `watch` runs adds exactly its own events, and event numbers stay contiguous with processes running at once |
| US4 Includes added by hand (P2) | T020–T022 (3) | Hand-added includes are followed, by one-off commands and by `watch` |
| Polish | T023–T027 (5) | README, a note in step 1's spec on what step 2 replaces, the quickstart run by hand, and the final test, type and lint run |

**How each story is tested on its own:**
- **US1:** run `show` once, edit the file by hand, run `show` again, then compare `history`. Running `history` alone must change nothing.
- **US2:** start `watch` and read its `watching <dir>` line. Edit a file in place, by renaming over it, or by deleting and re-creating it. The event must show up in `history` within 2 seconds, and SIGINT or SIGTERM must give exit 0.
- **US3:** run `set` while `watch` is running and wait 3 seconds. `history` must have gained exactly the `set`'s own events.
- **US4:** add a `file:` include by hand. Its leaves must appear as `set` events, and under `watch`, later edits to the new file must be picked up.

**Tests:** the constitution makes them mandatory, so every task that changes behaviour has its test written first. Four tasks also require breaking the code on purpose to show a test catches it:
- removing the lock;
- removing the reconcile step;
- printing the `watching` line too early;
- dropping the wait for a file to stop changing.

**Can run in parallel:** T002 with T003, and T004 with T005. After the foundational phase, the US1 tests, US2 tests and US4 one-off tests can be written in parallel, and T023–T025 can run in parallel. US3 has to wait for the US2 helper and the `watch` command.

**Suggested MVP:** the foundational phase plus US1, which makes every command pick up hand edits made between runs.

All 27 tasks use the required checklist format (checkbox, ID, `[P]` where it applies, story label in story phases, file paths). There were no task hooks to run. Next step: `/speckit-implement`.