I've written the step 2 task list and committed it on `main` as `34b2667`. It's in `specs/002-config-file-sync/tasks.md`, and no hooks are registered for this step.

There are 27 tasks, T001–T027:

| Phase | Tasks | Count |
|---|---|---|
| 1. Setup: confirm step 1 still passes all checks | T001 | 1 |
| 2. Foundational: reconcile, lock, reading the recorded configuration | T002–T007 | 6 |
| 3. US1: edits made while nothing was running are picked up (MVP) | T008–T012 | 5 |
| 4. US2: live sync with `watch` | T013–T019 | 7 |
| 5. US3: a `set`'s own write-back is recorded only once | T020–T023 | 4 |
| 6. Polish: README, step 1 spec pointer, quickstart, full checks | T024–T027 | 4 |

**How each story is tested on its own:**
- **US1:** edit files by hand between commands, then compare the exact `config history` output. This also checks that `history` never reconciles and that a reconcile still stands when the command after it fails.
- **US2:** start `watch` as a real process and read its `watching` line. Then edit the main file, an included file and a text include, both in place and by saving over the file with a rename. The edits must show up in `history` within 2 seconds, and SIGINT or SIGTERM must end it with exit code 0.
- **US3:** run 10 or more `set`s with `watch` running and the same `set`s without it, and the two histories must match. One test holds the lock itself to show the lock is what prevents duplicate events.

**Can run in parallel:**
- T002 with T003, and T004 with T005.
- T014 with T015, once the `watch` test fixture (T013) exists.
- T020 with T021.
- T024 with T025.

**Order of the stories:** US2 needs the reconcile switch added in US1 (T010). US3 tests how US1 and US2 work together, so it comes last.

**Suggested MVP:** Phases 1–3. With those, every command picks up edits made while nothing was running, without needing `watch`.

Every task follows the required format: checkbox, ID, story label in the story phases, and a file path. Tests are included even though the template calls them optional, because the constitution requires them. Each story ends with a step that breaks the behaviour on purpose to check the tests catch it.

Next is `/speckit-implement`.