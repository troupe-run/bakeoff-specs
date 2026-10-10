The step 3 task list is at `specs/003-config-get-show/tasks.md` and is committed on `main` (a853539). It has 21 tasks, and all of them use the required format (checkbox, ID, story label where needed, file path). No extension hooks are registered, so none ran.

| Phase | Tasks | What it covers |
|---|---|---|
| Setup | T001 | Run the tests, `mypy --strict` and ruff on the current code first |
| Foundational | — | Nothing needed; both commands reuse existing code |
| US1 `get` (P1, MVP) | T002–T008 (7) | Rename the code and step 1 tests to `get`, add the "use `config show`" hint and tests that `get` picks up hand edits, update usage tests |
| US2 `show` YAML (P1) | T009–T014 (6) | Unit tests for the layout, exact-output tests, read-back tests, the new `view.py`, the new `show` command |
| US3 `--sources` (P2) | T015–T017 (3) | Comment tests: main file, nested and text includes, files outside `.troupe/`, a single value, a symlinked theatre |
| Polish | T018–T021 (4) | README, notes in the step 1 and 2 docs that `show PATH` is now `get`, quickstart walk-through, final checks |

**Order matters:** the stories have to run in sequence. US1 first moves the old `show` tests and code to `get`, so the `show` name is free before US2 replaces it. US3 adds the comments to the output that US2's `view.py` produces. Keeping this order means the full test suite passes at every commit.

**Running work in parallel:** within US1, T002, T003 and T004 touch different files and can run together. Within US2, T009, T010 and T011 can run together. In Polish, T018 and T019 can run together.

**How each story is tested:**
- **US1:** `get` gives the same output, errors and exit codes as step 1's `show`. A mapping or list exits 5 and the error mentions `config show`.
- **US2:** `show` output matches the expected YAML byte for byte, and parsing it back gives the same configuration with the same types.
- **US3:** every line holding a value ends with the correct `# from <file>`, and no other line has one.

**Existing tests:** most step 1 and 2 tests call `show` on a single value. They stay as they are, because `show` still prints single values exactly like `get`. Only three need changing, and T005 covers them: the "collection exits 5" cases, the usage test expecting `config show` with no PATH to exit 2, and `test_error_messages.py`.

**Suggested first slice:** Setup plus US1 gives a working `get` that behaves exactly like the old `show`.

Every story ends with a step that deliberately breaks the behaviour, confirms a test fails, then restores it, as Principle II of the constitution requires.

Next step: `/speckit-implement`.