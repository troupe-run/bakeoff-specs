I've written the step 3 implementation plan and committed it on `main` (commit `2941d0f`, not pushed). The Constitution Check passes before and after the design, nothing is left unresolved, and no hooks are configured.

**Location:** `specs/003-config-get-show/` (delivery stays on `main`; there is no feature branch)
- `plan.md`: summary, technical context, Constitution Check, file layout, design overview
- `research.md`: the technical choices, numbered G-1 to G-8
- `data-model.md`: one new field on an existing in-memory record, plus the shape of output lines
- `contracts/cli.md`: command forms, exact output shapes and errors. It replaces the `show PATH` rows of the step 1 contract.
- `quickstart.md`: the quality checks and commands to run by hand to see the feature work

**Design in brief:**
- **One renderer for both outputs.** The loaded configuration already records which file each value came from, including text includes. A new `config/view.py` walks it and pairs each output line with its source file. `--sources` then just adds ` # from <file>` to those lines, so stripping the comments always gives exactly the plain `show` output.
- **Quoting rules are shared, not copied.** The rules for how a value is written (plain, quoted, literal block) move out of `edit/render.py` into a new `config/spelling.py`, used by both `set` and `show`. This makes the printed YAML read back to the same values and types. The logic doesn't change, and the existing byte-exact `set` tests will confirm that.
- **File names are shown as the path was written.** Each loaded file gains a second path that doesn't follow symbolic links, so names come out like `.troupe/agents/coder.yaml` or `../shared/x.yaml`. One limitation: if the same file is included by two different routes, the first route's name is shown.
- **The commands:**
  - `get` keeps the old `show` code; asking it for a section exits 5 and points to `config show`.
  - `show` takes an optional path plus `--sources`.
  - The command-line parser already rejects `get --sources` with exit 2.

**Existing tests that will change:** the ones expecting `show` on a section to exit 5 move to `get`. Tests of `show` on a single value stay valid as they are.

I checked the YAML points the design relies on against the installed `ruamel.yaml`. A comment after a `|` header and a top-level literal block with an indentation digit both read back correctly. No code has been written yet; next is `/speckit-tasks`.