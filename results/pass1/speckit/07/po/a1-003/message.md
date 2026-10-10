I've written the task list and committed it on `main` (`8392274`). It's at `specs/007-remote-includes-schema/tasks.md`. No code has changed yet. No task hooks are registered, so none ran.

**27 tasks:**

| Phase | Tasks | Count |
|---|---|---|
| Setup: confirm current tests pass, add `jsonschema` | T001–T002 | 2 |
| Foundation: groundwork that changes no behaviour, plus a real HTTP/HTTPS test server | T003–T006 | 4 |
| US1: include configuration from a URL (P1) | T007–T011 | 5 |
| US2: remote values are read-only (P1) | T012–T014 | 3 |
| US3: URL settings stay URLs, via `format: uri` and `!literal` (P1) | T015–T017 | 3 |
| US4: schema validation (P2) | T018–T019 | 2 |
| US5: `set` tags include-like strings, `--include` (P2) | T020–T024 | 5 |
| Polish: README, step 1 spec note, final checks | T025–T027 | 3 |

Every task uses the required format: checkbox, ID, `[P]` where it can run in parallel, a story label in the story phases, and exact file paths. The constitution requires tests, so each story starts with its end-to-end tests, to be written first and seen to fail.

**How each story is proven on its own:**
- **US1:** files served by the local test server load through `get`, `show`, `show --sources` and `history`. Each kind of fetch failure exits 4 and names the URL.
- **US2:** each kind of write into remote content exits 3, every file stays byte-for-byte the same, and stderr shows the include string as written plus its file and line. A new key becomes a local override.
- **US3:** literals found through `properties`, `additionalProperties` and `items`, and `!literal` values, print as plain strings. The server receives no requests for them.
- **US4:** an invalid configuration exits 4 for every command, a `set` that would make it invalid exits 3 with nothing written, and a broken schema file exits 4.
- **US5:** written bytes match exactly across every combination of schema marking and `--include`, including when an existing tag is kept or removed.

**Parallel work:**
- T003, T004 and T005 can run together.
- Each story's test task can be written while the previous story's code is being finished.
- T025 and T026 can run together.

**Order and MVP:** the MVP is Phases 1–3 (URL includes load). I'd do US2 straight after, because without it a `set` on remote content is still refused (mypy forces every write through the local-only check), but with a raw message that doesn't name the include line. US3 must follow US1, since its tests need real fetching to show that nothing is fetched. US4 and US5 need US3's schema loading.

The next step is `/speckit-implement`.