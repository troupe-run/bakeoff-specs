Q1: I've written the step 7 spec and committed it on `main` (`3b4d346`). I didn't push or open a PR. This is only the spec; nothing is implemented yet, and no tests were run.

- **Feature directory:** `specs/007-remote-includes-schema`
- **Spec:** `specs/007-remote-includes-schema/spec.md`, with the contract section quoted word for word. It uses FR-600 onward, decisions D-60 to D-70 and success criteria SC-600 onward, following the numbering of the earlier steps.
- **Checklist:** `specs/007-remote-includes-schema/checklists/requirements.md`. Every item passed on the first check, and there are no open clarification questions.
- **Hooks:** none are registered, so none ran.

**Behaviour change for existing users:** any plain `https://` or `http://` string in a configuration now counts as an include and gets fetched. Teams have to mark URL settings in the schema or with `!literal`. The spec lists this under Assumptions so the README covers it.

**Decisions you should check.** The contract left these open, so I chose the cautious option each time and recorded why:
- **D-60:** If a remote include sits inside another remote include, adding a new key under it is refused (exit 3). Step 5 would put the override in the nearest including file, and that file is remote here.
- **D-61:** A `file:` include inside remote content stops the configuration loading (exit 4). Otherwise a remote document could pull files from the user's disk into the configuration.
- **D-63:** Fetching follows redirects, accepts only 2xx responses, gives up after 10 seconds, doesn't retry or cache, and sends no credentials.
- **D-64:** When deciding whether a string is a literal, the schema lookup only follows `properties`, `additionalProperties` and `items`, as the contract lists. `$ref`, `allOf` and the like are ignored for that, though validation still uses them. `format` is treated as a label, not a rule that values must pass. A schema `$ref` pointing outside the file stops loading (exit 4), so the schema never triggers a fetch.
- **D-65:** When remote content changes between commands, the next command records the difference as a file change. `watch` doesn't poll URLs.
- **D-68 / D-69:** `--include` on a path the schema marks `format: uri` is refused (exit 3). Include-like strings inside a mapping or list value also get the `!literal` tag.

If any of these is wrong, it's a change to one decision in the spec. Next step is `/speckit-plan`, or `/speckit-clarify` first if you want to revisit them.
A1 (po): /speckit-plan

Q2: The step 7 plan is written and committed on `main` (`c011391`). It's design only: no code has changed and no tests were run. It stays on `main` like the earlier steps; no branch was created. No plan hooks are registered, so none ran.

**Files written** (all in `specs/007-remote-includes-schema/`):
- `plan.md`: summary, technical context, a constitution check where every principle passes, the module layout and the design steps.
- `research.md`: technical decisions U-1 to U-12, each with the reason and what else was considered.
- `data-model.md`: how a source, a loaded configuration, the string classification and the schema rules fit together.
- `contracts/cli.md`: the `--include` option, the URL include forms, `!literal`, the schema file, and what happens for each refusal.
- `quickstart.md`: the checks to run (tests, mypy, ruff) and a manual walk-through using a local web server.

**Main design choices:**
- **Remote content can't be written, enforced by types.** A source's location becomes either a local path or a URL, and every write has to go through one helper that only accepts local paths. mypy then flags any write site that skips it. When a write is refused, the message names the remote include line on the route that PATH actually takes.
- **Literals are decided before anything is fetched.** The loader carries each node's part of the schema down as it builds the tree. A `format: uri` or `!literal` string is therefore never requested; the tests check this against the server's request log.
- **Validation happens when the configuration loads.** That gives exit 4 for every command, and `set`'s existing reload check turns a change that would break the schema into exit 3, with nothing written.
- **Tagging happens before `set` plans the edit.** Include-like values are marked first and the tag is written in one rendering spot, so none of the code that decides where values go changes. An existing `!literal` tag is kept unless `--include` is given.

**New dependency:** `jsonschema`, to validate against JSON Schema 2020-12. I checked that uv can install it. Fetching uses Python's standard library.

**Tests will use real HTTP and HTTPS:** a local server, with a self-signed certificate made by `openssl`, rather than a faked fetch. Proxy environment variables are cleared so they can't affect results. One test waits out the 10-second fetch limit, so it will be slow.

Next step is `/speckit-tasks`.
A2 (po): /speckit-tasks

Q3: I've written the task list and committed it on `main` (`8392274`). It's at `specs/007-remote-includes-schema/tasks.md`. No code has changed yet. No task hooks are registered, so none ran.

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
A3 (po): /speckit-implement