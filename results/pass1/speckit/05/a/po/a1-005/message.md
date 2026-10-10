I've written two task lists, one for each change request, and committed them on `main` as `e1813f2`. Nothing was pushed. No code has changed yet. No extension hooks are registered, so none ran. All 38 tasks follow the required checklist format (checkbox, ID, labels where needed, file paths), checked with a grep.

The active feature is CR-B, but its code sits inside CR-A's, which had no task list yet. So I wrote both, and CR-A's runs first.

**`specs/005-include-overrides/tasks.md` (CR-A): 23 tasks**

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | 2 (T001–T002) | Quality checks pass on today's code; the loader's `overrides` parameter is renamed |
| Foundational | 5 (T003–T007) | Includes written with `$ref` load and merge correctly; malformed ones exit 4 |
| US1 – new key becomes an override (P1) 🎯 MVP | 6 (T008–T013) | `set agents.coder.temperature 0.3` leaves the shared file byte-identical |
| US2 – existing values (P1) | 2 (T014–T015) | Overridden → override; not overridden → shared file; a merged section set to a mapping → exit 3 |
| US3 – read and audit (P1) | 3 (T016–T018) | `show --sources` names each value's file; converting by hand records nothing |
| US4 – lists (P2) | 2 (T019–T020) | Appends and keys inside list items stay in the file that holds the list |
| Polish | 3 (T021–T023) | README, notes in the earlier specs, quality checks |

**`specs/006-set-in-include/tasks.md` (CR-B): 15 tasks.** It waits for CR-A's T001–T013.

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | 2 | CR-A's prerequisite tasks done and checks pass; the `set` test helpers can pass options |
| Foundational | 3 | The merged tree keeps the shared file's side; the placement value reaches the planner; the CLI flag exists |
| US1 – shared file on purpose (P1) 🎯 MVP | 4 | `set --in-include` changes only the shared file; with or without the flag, other cases give identical files |
| US2 – recorded and validated (P2) | 3 | History records actor and reason; the flag on other commands exits 2 |
| Polish | 3 | README, keep both specs in agreement, quality checks |

**Parallel work:**
- **CR-A:** after the foundational phase, the four story test files (T014, T016, T017, T019) can be written in parallel. T003 and T004 can run together, as can T008 and T010.
- **CR-B:** its tests mostly share one file, so they run in sequence. Only T011 (`test_usage.py`) can run alongside them.

**Suggested MVP:** CR-A phases 1–3, which stop new keys from changing shared files, then CR-B phases 1–3.

Every behaviour is written as a failing test first, as the constitution requires. One existing test asserts the rule CR-A replaces: `test_set_new_key.py::test_new_key_in_an_included_file`. T009 rewrites it.

Next is `/speckit-implement`. Start with `specs/005-include-overrides`, then switch `.specify/feature.json` to `specs/006-set-in-include`.