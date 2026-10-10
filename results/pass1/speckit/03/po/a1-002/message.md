The step 3 plan and design documents are written and committed on `main` (eadad43). No code has changed yet, and no extension hooks are registered, so none ran.

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