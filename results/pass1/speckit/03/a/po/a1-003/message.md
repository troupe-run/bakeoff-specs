I've written the step 3 task list to `specs/003-config-get-show/tasks.md` and committed it on `main` (commit `953343e`, not pushed). No hooks are configured.

**28 tasks in total**, every one in the checklist format with an ID and file path; tasks inside a user-story phase also carry a story label:

| Phase | Tasks | Count |
|---|---|---|
| 1. Setup: run the quality checks on the unchanged code | T001 | 1 |
| 2. Foundational: move the shared quoting rules into `config/spelling.py` (no behaviour change) | T002–T004 | 3 |
| 3. US1, `get` (P1), the first deliverable | T005–T010 | 6 |
| 4. US2, `show` for sections (P1) | T011–T019 | 9 |
| 5. US3, `show --sources` (P2) | T020–T024 | 5 |
| 6. Polish: README, mark the old step 1 rule as replaced, walk the quickstart, final checks | T025–T028 | 4 |

**How each story is tested on its own:**
- **US1:** `get` output is byte-identical to the old `show` for every existing single-value case. A section exits 5, and the error names the path and mentions `config show`.
- **US2:** exact expected YAML for each spec scenario. A separate test reads `show` output back with a YAML parser and checks it equals the configuration, with types kept.
- **US3:** exact `--sources` output; the text include is credited to its own file; files outside the theatre get `../` names. Removing the comments must give exactly the plain `show` output.

**What can run in parallel:**
- The Phase 2 move and US1 touch different files, so they can run side by side.
- Within the stories: T005 with T006, T011 with T013 and T014, T020 with T021.
- In the polish phase: T025 with T026.

**Existing tests that will change:** tests expecting `show` on a section to exit 5 move to `get` (T007). The test treating a bare `config show` as a usage error is turned into a success case (T015), since a missing path now means the whole configuration.

Tests are written before the code, as the project's rules require. Each story ends by deliberately breaking the behaviour once to confirm the tests catch it, then committing.

**Suggested first deliverable:** Phase 1 plus US1, which gives scripts a stable `get` straight away. Next is `/speckit-implement`.