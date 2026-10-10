I've written the step 7 task list: 40 tasks, test-first and grouped by user story, committed on `main` as `901c713`. All 40 tasks use the checklist format (checkbox, ID, `[P]`/story labels where they apply, file paths).

**File:** `specs/007-remote-includes-schema/tasks.md`

| Phase | Tasks | Count | Independent test |
|---|---|---|---|
| Setup | T001–T003 | 3 | Run the checks, add `jsonschema`, add a real local HTTP server for tests |
| Foundational | T004–T008 | 5 | A source can be a local file or a URL; one rule decides what an include string is; the loader tracks where each value sits |
| US1: read remote includes 🎯 MVP | T009–T016 | 8 | Serve YAML and text locally; check `get`/`show`/`--sources`/`history`; failed fetches exit 4 |
| US2: refuse remote writes | T017–T022 | 6 | Every refused `set` exits 3, names the include string, file and line, and changes no file or event |
| US3: literals | T023–T028 | 6 | `format: uri` and `!literal` strings are never fetched, checked against the test server's request log |
| US4: schema validation | T029–T030 | 2 | An invalid configuration exits 4; a `set` that would make it invalid exits 3; both name the schema file and the setting |
| US5: `set` tagging, `--include` | T031–T036 | 6 | Exact file bytes for every row of the tagging table |
| Polish | T037–T040 | 4 | README, notes in earlier specs, a requirement-to-test audit, quickstart walk-through and checks shown |

**Order:**
- US2 comes after US1, because it refuses writes into fetched content.
- US4 and US5 come after US3, because both build on the schema code US3 adds.
- Once US3 is done, US4 and US5 can proceed in parallel.

**Parallel work** (different files, no unfinished dependencies): T004∥T005, T009∥T010∥T011∥T012, T017∥T018, T023∥T024, T031∥T032, T037∥T038.

**MVP:** US1 alone. Two things to know before stopping there:
- A `set` into remote content would only be refused with a generic message until US2 lands.
- Until US3 lands, any existing setting holding a URL would be fetched as an include.

So I'd treat US1–US3 as the minimum to deliver.

The test proxy settings follow research U-12: test runs drop the developer's proxy variables and set `NO_PROXY` for 127.0.0.1, so a local proxy can't change test results.

No extension hooks are registered, so none ran. The next step is `/speckit-implement`.