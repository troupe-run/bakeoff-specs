Q1: I've written the step 3 spec and committed it on `main` (b4d3d3d). This step only covers the spec; there's no code or tests yet.

- **Feature directory:** `specs/003-config-get-show`
- **Spec file:** `specs/003-config-get-show/spec.md`
- **Checklist:** `specs/003-config-get-show/checklists/requirements.md`. Every item passed on the first check, and no questions were left open for you.
- **Hooks:** `.specify/extensions.yml` has none registered, so none ran.

**What the spec covers:**
- **`get PATH`** behaves as `show` did in step 1. Asking it for a mapping or list exits 5, and the error message names the path and mentions `config show`.
- **`show [PATH]`** prints a single value exactly as `get` does. A section, or the whole configuration when PATH is left out, is printed as YAML with includes filled in and text includes as literal blocks.
- **`show --sources`** adds ` # from <file>` to each line holding a value, with the file relative to the theatre directory. For a literal block, the comment goes on its first line (`prompt: | # from …`).
- Any `show` output can be read back as YAML and gives the same values.
- The new requirements are FR-200 to FR-240 and replace step 1's FR-015. Everything else from steps 1 and 2 still applies.

**Choices I made where the contract leaves room (recorded as D-20 to D-26):**
- **D-20:** `get` and `show` both first record any hand edits made since the last command. Step 2 says every command except `history` does this.
- **D-21:** YAML layout is 2-space indentation, lists indented under their key, quoting only where needed, and keys in file order. Empty sections print as `{}` or `[]`, because block style can't express them.
- **D-22:** A file outside the theatre directory is named with `..` segments. Symbolic links are not followed.
- **D-23:** `show <single value> --sources` prints that value as YAML with its comment, e.g. `0.2 # from .troupe/troupe.yml`. The contract doesn't say what happens here, so this is the least obvious choice; tell me if you want something else.
- **D-24:** A text include with Windows (CRLF) line endings still prints as a literal block, so in `show`'s YAML it reads back with plain `\n` line breaks. `get` still prints the text exactly.
- **D-25, D-26:** One space goes before the `#`. `--sources` is accepted only by `show`; on `get` it's a usage error (exit 2).

Existing step 1 tests that expect `show` to refuse a mapping or list will need to move to `get` when this is built. The spec says so.

The next step is `/speckit-plan`, or `/speckit-clarify` if you want to change D-23 or D-24 first.
A1 (po): /speckit-plan

Q2: The step 3 plan and design documents are written and committed on `main` (eadad43). No code has changed yet, and no extension hooks are registered, so none ran.

**Plan:** `specs/003-config-get-show/plan.md`. It passes the constitution check before and after design, with no exceptions to justify.

**The approach:**
- **`get`** is the current `show` renamed. The only change is the error for a mapping or list, which now says ``use `troupe config show PATH` to print it``.
- **`show`** prints a single value exactly as `get` does. Sections are printed by a new module, `src/troupe/config/view.py`. It works from the loaded configuration tree, which already records the file each value came from, so `--sources` gets its file names from there.
- **Reuse:** quoting rules and literal blocks (`|`, `|-`, `|+`, and an indentation number when the text starts with a space) come from the existing `edit/render.py`. The layout code that `set` uses for new values is not reused. Hooking `--sources` comments into it would tie a read-only view to the code that rewrites your files.
- **Behaviour shared with other commands:** both commands load the configuration and record pending hand edits first, then print. Neither writes any configuration file.
- **Tests:** the step 1 tests for `show` printing a value move to `get`, so they still prove that `get` behaves exactly as `show` did. New tests compare `show` output byte-for-byte, check that the YAML reads back as the same configuration, and check that no file changes.

**One spec change during planning:** I revised D-22 in `spec.md`. The file in `# from <file>` is now worked out from real locations, with symbolic links followed. The loader already identifies every file that way. It also means a theatre under a linked directory (like `/tmp` on macOS) still shows `.troupe/troupe.yml` rather than a path full of `..`.

I checked parsing against the installed YAML library. Comments after a value and on a literal-block header line are ignored, and indented literal blocks with an indentation number read back correctly, including at the top level.

**Other files in `specs/003-config-get-show/`:**
- `research.md`: technical decisions G-1 to G-7
- `data-model.md`
- `contracts/cli.md`: exact `get`/`show` output, layout and exit codes
- `quickstart.md`: the quality checks and a sample theatre to try the commands on

Next step: `/speckit-tasks`.
A2 (po): /speckit-tasks

Q3: The step 3 task list is at `specs/003-config-get-show/tasks.md` and is committed on `main` (a853539). It has 21 tasks, and all of them use the required format (checkbox, ID, story label where needed, file path). No extension hooks are registered, so none ran.

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
A3 (po): /speckit-implement