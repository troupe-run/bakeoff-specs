I've written `specs/004-config-lineage/tasks.md` with 26 tasks and committed it on `main` as `ac459cc`. Nothing was pushed. No hooks are registered, so none ran.

**Tasks per phase**

| Phase | Tasks | How it's tested |
|---|---|---|
| 1. Setup | 1 (T001) | Run the test suite, `mypy` and `ruff` on the unchanged code first |
| 2. Foundational | 9 (T002–T010) | New lineage module, lineage saved on each event, `history` printing it, `TROUPE_ACTOR` checked by every command; unit tests plus the full suite |
| 3. US1 — who and how (P1) | 3 (T011–T013) | `actor` and `via` for each `TROUPE_ACTOR` form, the login-name fallback, hand edits and `watch`; invalid values exit 2 for all 5 subcommands |
| 4. US2 — which changes belong together (P1) | 2 (T014–T015) | Change ids are equal within a change and different between changes, including 10 commands in a row and `watch` running alongside `set` |
| 5. US3 — when and why (P2) | 4 (T016–T019) | `at` format and that it falls within the command; `--reason` placement, exact text and misuse |
| 6. US4 — survives restarts (P1) | 2 (T020–T021) | `history` output identical across processes, readers and `watch` restarts |
| 7. Polish | 5 (T022–T026) | README, a note in the step 2 spec, a manual check on older stores, quickstart walk-through, final checks |

Every story phase writes its tests first, then deliberately breaks the behaviour to confirm the tests catch it, as the constitution requires.

**Choices worth knowing about:**
- **Existing tests:** `theatre.history()` will keep returning only the original five fields, so the roughly 45 existing exact comparisons stay as they are. A new `theatre.lineage()` returns the full events for the new tests.
- **Test environment:** the test helper drops any inherited `TROUPE_ACTOR`, so results don't depend on the machine running them.
- **Older stores:** T024 checks by hand, not with a test, what happens with a store written before step 4. The expected result is exit 4 with no traceback.

**Parallel work:** after phase 2, the six new test files (T011, T012, T014, T016, T017, T020) are independent and can be written in parallel. So can T003 with T004, and T022 with T023.

**Suggested MVP:** phases 1–3, which make `history` answer who changed each setting and how.

Every task follows the checklist format (checkbox, ID, story label in the story phases, file paths). Next step is `/speckit-implement`.