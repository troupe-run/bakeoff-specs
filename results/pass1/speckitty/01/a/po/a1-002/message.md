I've recorded your answer. The contract and the charter (refuse rather than guess; name the file) cover everything else, so here is the **Intent Summary** for you to confirm before I write the spec.

**Who uses it and how:** a developer who maintains a troupe theatre runs `uv run troupe config show|set|history … [--theatre DIR]` from the repository root.

**Main scenario:**
1. The first command in a theatre loads `.troupe/troupe.yml` (or `.yaml`) and follows `file:` includes recursively.
   - Includes of `.yml`/`.yaml` files are embedded in place; any other file's text becomes a string value.
   - The first command also records one `import` event per leaf value in a persistent history under `.troupe/`.
2. `show PATH` prints a single value using the contract's formatting rules.
3. `set PATH VALUE` reads `VALUE` as a YAML flow node and writes the change into the file that owns that value. Only the bytes the contract requires are changed. It then records one `set` event per changed or new leaf and one `remove` event per leaf that no longer exists.
4. `history [PATH]` prints the events as JSON Lines, oldest first, optionally filtered by `PATH`.

**Rules that always hold:**
- The files on disk are the truth; the history only records changes. A hand edit shows up in `show` but creates no event, and the next `set` records the file's value as its `old` value.
- After a successful `set`, no byte changes anywhere except those the contract requires.
- Nothing outside `<dir>/.troupe/` is ever created.
- Any non-zero exit leaves stdout empty and puts the offending path or file on stderr.
- A refused write (exit 3) changes no file.

**Main exceptions and edge cases:**
- **Exit 4:** there are zero or two config files, an include is missing, includes form a cycle, or the YAML is invalid.
- **Exit 5:** the path is missing, `show` points at a mapping or list, or a list index is beyond the list's length.
- **Exit 3:** `set` would replace a value that comes entirely from an include, write a non-string into a text include, or add a more-indented line inside a folded (`>`) value.
- **Exit 2:** the command is malformed or `VALUE` isn't valid YAML.

**Scope:** the contract sections General, Includes, `show` (steps 1–2), `set`, and `history`.

**Not covered:**
- Anything the contract lists as out of contract: anchors and aliases, multi-document files, a TAB before a comment, and concurrent writers.
- Reconciling hand edits into the history.

**Assumptions:**
- A path that runs through a scalar, or uses a non-numeric key on a list, exits with 5.
- If `set` hits a case where it can't write the change safely and exactly, it refuses with exit 3 and changes no file. It never makes a best-effort write.

Does this match what you intend? Reply "yes", or correct anything above.

WAITING_FOR_DISCOVERY_INPUT