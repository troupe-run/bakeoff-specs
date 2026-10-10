I've written the task list, `specs/004-config-lineage/tasks.md`, and committed it on `main` as `cb7367b`. Nothing was pushed. No extension hooks are registered, so none ran.

There are 25 tasks. Tests are included even though the template calls them optional, because the project constitution requires a test for every behaviour.

| Phase | Tasks | What it covers |
|---|---|---|
| Setup | 2 (T001–T002) | Confirm the current suite passes; stop tests inheriting your own `TROUPE_ACTOR`; fix the login name tests see |
| Foundational | 7 (T003–T009) | `lineage.py`, lineage saved with each event, the three places that record it, `history` output, existing tests kept working |
| US1 who and how (P1) | 5 (T010–T014) | Actor and `via`; an invalid `TROUPE_ACTOR` exits 2 on every command, including `watch` |
| US2 what changed together (P1) | 2 (T015–T016) | Change ids shared within a group and distinct between groups |
| US3 when and why (P2) | 3 (T017–T019) | `--reason` only on the `set`'s own events, `""` kept as given, timestamps in UTC and inside the command's run |
| US4 survives restarts (P1) | 2 (T020–T021) | History printed identically by new processes with a different actor |
| Polish | 4 (T022–T025) | README, notes in the step 1–2 docs, quickstart walk-through, final checks |

**How each story is tested:**
- **US1:** run an import, a `set` under each kind of `TROUPE_ACTOR`, a hand edit followed by `get`, and a hand edit under `watch`, then compare `actor` and `via` line by line. Every invalid actor value exits 2 with no files or history changed.
- **US2:** group history lines by change id and check each group is exactly one import, one pick-up of hand edits, or one `set`.
- **US3:** each timestamp falls between UTC times taken just before and after the command, and the reason text comes back exactly as given.
- **US4:** earlier `history` output is byte-for-byte unchanged when listed later by a different actor.

**Changes to the existing tests:** the test helper `theatre.history()` will keep returning only the original five fields, and a new `theatre.events()` returns the full lines with lineage. That keeps the step 1–3 tests unchanged and still testing what they did. Only the one test that compares a raw history line gets updated.

**One test may be skipped:** the end-to-end check for "no login name can be found" only runs if your user account has no system user entry, which is unusual. Otherwise it skips, and a unit test covers that case instead.

**Parallel work:** the three US1 test files can be written at the same time, as can the two foundation test files. Once the foundation is done, the US1, US2 and US3 tests are independent. US1 and US3 both edit `cli.py`, so their implementation tasks should run one after the other.

**Suggested MVP:** Setup, Foundational and US1, which answers who and how for every event.

All 25 tasks use the required checklist format: checkbox, ID, `[P]` where parallel, story label in story phases, and file paths.

Next step: `/speckit-implement`, optionally after `/speckit-analyze`.