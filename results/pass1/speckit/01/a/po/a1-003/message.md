I've written the task list: 50 tasks in `specs/001-config-load-show-set/tasks.md`, committed on `main` (`e185b2f`). The template treats tests as optional, but the constitution makes them mandatory, so every behaviour has a test task written before its implementation. All 50 tasks follow the checklist format (checkbox, ID, optional `[P]`, story label in story phases, file path).

| Phase | Tasks | Count |
|---|---|---|
| 1. Setup (project file, package layout, test helpers, quality gates) | T001–T004 | 4 |
| 2. Foundational (errors, theatre lookup, paths, YAML reading, loader, values, event store, CLI skeleton) | T005–T019 | 15 |
| 3. US1 – Read a setting (P1, MVP) | T020–T025 | 6 |
| 4. US2 – Change a setting without disturbing the file (P1) | T026–T043 | 18 |
| 5. US3 – See what changed (P2) | T044–T046 | 3 |
| 6. Polish | T047–T050 | 4 |

**One change from the user-story split:** recording the initial import is in the Foundational phase, not in US3. The contract says every command imports the theatre on first use, so `show` and `set` need it too.

**How each story is tested on its own:**
- **US1:** build a theatre with YAML and text includes, run `show` on each kind of value, and check the exact output and exit codes.
- **US2:** for each write rule, copy every file's bytes, run `set`, and check that only the expected bytes changed and that `show` returns the new value.
- **US3:** on a fresh theatre, check the import events; after a few `set`s, check `history` and `history PATH` show the right events with `seq` running 1..n.

**Can run in parallel:**
- The five Foundational test tasks (T005–T009), then T010–T012.
- The US1 test tasks (T020–T022).
- The ten US2 test tasks (T026–T035), each in its own file; US2 implementation is sequential.
- The US3 test tasks (T044–T045).

**Suggested MVP:** Setup, Foundational and US1 — `show` with includes, plus importing on first use. After that, add `set` one group of rules at a time, committing as each goes green; then `history` and the polish tasks. The polish phase includes deliberately breaking key behaviours to confirm their tests fail.

No extension hooks are registered. The next step is `/speckit-implement`.