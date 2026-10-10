I've written task lists for both change requests and committed them on `main` as `283ad8f`. You asked for CR-B's tasks; I also wrote CR-A's, because CR-B is built on CR-A's code and CR-A had no task list yet. There were no extension hooks to run. Tests are included throughout, since the constitution requires a test for every behaviour.

**CR-A: `specs/005-include-overrides/tasks.md`, 24 tasks**

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | T001–T002 (baseline checks; let the test helpers pass extra `set` options) | — |
| Foundational | T003–T006 (new tree fields, recognising and merging `$ref` mappings in the loader, merge unit tests) | — |
| US2: read overrides (P1) | T007–T010 | `get`, `show`, `--sources`, history and `watch` on hand-written `$ref` fixtures |
| US1: new key becomes an override (P1) 🎯 | T011–T017 | byte-for-byte comparison; only the including file changes |
| US3: existing values (P2) | T018–T019 | override vs shared file; whole-section replacement refused (exit 3) |
| US4: lists (P2) | T020–T021 | appends and keys inside list items stay in the list's file |
| Polish | T022–T024 | README, note in the step 1 spec, final checks |

- **Order:** reading (US2) comes before writing (US1). Every new-key write is checked by reloading the result, so the reading code must be proven first.
- **Existing test:** T012 changes the one existing test that encodes the old rule (new key written into the shared file), rather than deleting it.

**CR-B: `specs/006-set-in-include/tasks.md`, 10 tasks**

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | T001 (confirm CR-A is done and green) | — |
| Foundational | T002–T004 (flag parsing and errors, passing it down to placement, merged sections remember their shared-file part) | — |
| US1: key into the shared file (P1) 🎯 | T005–T006 | with the flag, only the included file changes, including the file-included-twice case |
| US2: flag changes nothing else (P2) | T007–T008 | each `set` runs with and without the flag on two fresh theatres; files and history must match |
| Polish | T009–T010 | README, final checks |

**Parallel work:** in CR-A, the merge tests (T003) can run alongside the tree change (T004), and the three US2 test files (T007–T009) can be written together. US3 and US4 can be done in either order, and T022/T023 together. In CR-B, T002 and T004 can run in parallel.

**MVP:** CR-A phases 1–4 deliver CR-A's main promise (shared files untouched). CR-B phases 1–3 add the flag.

**Format check:** all 34 tasks use the `- [ ] T### [P?] [US?] description` form with file paths; none are malformed.

Next step is `/speckit-implement`, starting with CR-A. `.specify/feature.json` points at 006, so switch it to `specs/005-include-overrides` first.