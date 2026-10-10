I've written the task list for step 1 and committed it to `main` as `08854fb`. No extension hooks are registered, before or after this step. Nothing has been implemented yet.

**File:** `specs/001-config-load-show-set/tasks.md`, with 50 tasks.

| Phase | Tasks | Count |
|---|---|---|
| 1 Setup | T001–T003 | 3 |
| 2 Foundational: errors, CLI, paths, value typing, file discovery and safe writes, loader with includes, leaves, event store with first-run import | T004–T020 | 17 |
| 3 US1 `show` (P1, MVP) | T021–T024 | 4 |
| 4 US2 `set` (P1) | T025–T043 | 19 |
| 5 US3 `history` (P2) | T044–T045 | 2 |
| 6 Polish | T046–T050 | 5 |

**Tests are included even though the template treats them as optional,** because the project constitution requires a test for every behaviour. Each test task is written first and should fail before the code exists. End-to-end tests run the real `troupe` command on real theatre folders and compare every file byte for byte. Once a test passes, the behaviour is broken on purpose to confirm the test catches it.

**Work that can run in parallel:** 31 tasks are marked `[P]`. The main groups:
- the seven foundational test files;
- the three US1 test files;
- the 13 US2 test files, one per group of write rules;
- the three US2 modules for formatting values, line layout and folded text.

**How to check each story on its own:**
- **US1:** in a theatre with nested and text includes, `show` prints the right value for paths in each file, and returns exit 5 for missing paths or lists/mappings.
- **US2:** for each write rule, every file in the theatre matches the expected bytes after `set`. Refused writes return exit 3 or 5 and leave all files unchanged.
- **US3:** `history` output (JSON Lines) is checked across first import, `set`s, removals, no-op sets, path filters, separate runs and hand edits, which are not recorded.

**Suggested MVP:** phases 1–3 (`show`). After that, `set` is built one rule group at a time, then `history`.

**Format check:** all 50 tasks follow the checklist format: checkbox, sequential ID, a `[USn]` label in story phases only, and a file path.

**Next step:** `/speckit-implement` (optionally `/speckit-analyze` first to cross-check the spec, plan and tasks).