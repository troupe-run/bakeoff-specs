Q1: I've built the configuration subsystem and committed it to `main` (commit `10edbac`). `uv run troupe config show|set|history --theatre DIR …` works from the repo root, and all 39 tests in `tests/test_config.py` pass. I also ran about 4,500 random `set` commands against varied files (CRLF, flow style, block scalars, includes). None crashed or was refused; one bug they turned up is fixed (last point below).

**How it works**
- **Loading:** PyYAML reads each file and gives the exact position of every value. I decide whether a plain value is a number, boolean, null or string myself, using YAML 1.2 rules, because PyYAML follows the older 1.1 rules. Includes are followed recursively, and a missing target or a cycle exits with 4.
- **Writing (`set`):** every change is planned as a text replacement in the original file and applied all at once. Before any file is touched, the edited text is reloaded and the value at `PATH` is checked against `VALUE`. If they don't match, the command exits with 3 and nothing changes. So a formatting bug becomes a refused write, never a corrupted config.
- **History:** an `eventsourcing` aggregate stored in SQLite at `.troupe/troupe-state.sqlite`, with one event per leaf (`import`, `set`, `remove`). The first command against a theatre imports it. A `set`'s events come from comparing the configuration before and after the write, so removed leaves get `remove` events.

**Choices where the contract was silent or ambiguous**
- **What `show` reads:** it reads the files, not the stored history. If someone edits a file by hand, `show` reflects it but `history` does not ("importing is not reconciling").
- **Setting a mapping or list onto one of the same kind:** this merges rather than rewriting the block. Keys are compared one by one and only the differences are written, so unchanged entries and their comments keep their bytes.
- **Includes:** replacing a value whose whole value comes from a YAML include exits with 3 even when the new value is identical. Setting keys inside the include writes into the included file.
- **Values on the command line:** a `VALUE` that YAML would read as a block mapping or list (for example the bare text `a: b`) is a usage error (exit 2). To pass a string like that, quote it: `'"a: b"'`.
- **Empty values:** setting a mapping or list to empty writes `{}` or `[]`, since block style can't show an empty collection. Writing a key into an empty or comment-only `troupe.yml` is supported.
- **Turning a list item into a collection:** the item is written in compact form (`- k: v`). If the item's line has an end-of-line comment, the comment stays on the dash line and the collection goes on the lines below, matching the rule for keys.
- **Literal blocks and trailing comments:** if a literal block would swallow comment lines indented below it, the value is written double-quoted instead. Otherwise those comments would silently become part of the value.
A1 (runner): /superpowers:finishing-a-development-branch