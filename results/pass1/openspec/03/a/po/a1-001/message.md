I've planned the change `config-get-and-show` in `openspec/changes/config-get-and-show/` and committed the plan on `main` as `28a2740`. Nothing is pushed and no project code has changed. `openspec validate --strict` reports the change as valid, and all 4 artifacts are complete.

**What's in it:**
- **`proposal.md`**: why and what. `get PATH` takes over what `show` did. `show [PATH] [--sources]` prints a value, a section or the whole configuration as YAML, and `--sources` says which file each value comes from. It's marked **breaking** because `show agents` no longer exits 5.
- **Specs**:
  - **`config-get`** (new): prints a scalar. A mapping or list exits 5, and the error names the path and mentions `config show`.
  - **`config-show`**:
    - A scalar prints exactly as `get` prints it.
    - The YAML layout rules come with exact-output scenarios.
    - `--sources` comments.
    - Missing paths still exit 5.
    - The old "refuses collections" rule is removed, with a migration note pointing to `get`.
  - **`config-cli`**: `get` is a subcommand, `show`'s `PATH` is optional, and `--sources` is accepted only by `show`.
  - **`config-sync`**: `get` picks up hand edits before running, as `show` and `set` do.
- **`design.md`**: how to build it (D1–D8). A new module, `render.py`, prints the configuration as YAML, reusing the quoting rules `set` already uses. Each literal block is parsed back and checked before it's printed; if it doesn't read back exactly, the string is printed in double quotes instead.
- **`tasks.md`**: 4 groups, each carrying its own tests and README updates.

**Choices I made where the contract is silent** (all recorded in `design.md`; implementation will add them to the README's decisions list):
1. **`show PATH --sources` on a single value** prints it as a one-line YAML document, e.g. `m  # from .troupe/troupe.yml`. The plain `get` form has no safe place for a comment, since a value can contain `#` or end in blank lines.
2. **Which lines get a `# from` comment:** only lines holding a value. Key-only lines like `agents:` and empty `{}`/`[]` get none. For a multi-line text block, the comment goes on the `|` line, because a comment on a content line would become part of the text.
3. **Multi-line strings** written in the file, not only text includes, are also printed as `|` blocks. Text a `|` block can't hold exactly, such as CRLF line endings, is printed in double quotes.
4. **File names** are worked out from real paths with symlinks resolved, relative to the theatre. A file outside the theatre is named with `..`.
5. **Layout details:** two spaces before `#`, two-space indentation, and lists indented under their key.

Choice 1 changes what users see the most, so if you'd rather it print the plain value or refuse `--sources` for single values, it's a one-place change and better made before implementation.

The plan is ready for review. When you're ready, run `/opsx:apply`.