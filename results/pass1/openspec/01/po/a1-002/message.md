The `troupe config` subsystem is built and committed on `main`, and all 26 tasks are done. `show`, `set` and `history` work as the contract describes. On a fresh clone, `uv run troupe config …` runs from the repository root and all 340 tests pass. `mypy --strict` and ruff are clean.

**How it works:**
- **Reading:** ruamel.yaml is used only to find where each value sits in the text. Value types come from our own YAML 1.2 core-schema rules, because ruamel's own rules read `2001-01-01` as a date.
- **Writing:** `set` edits only the bytes the change needs. It reloads the result, and refuses with exit 3 unless it gives exactly the intended configuration, so a bad edit is never written.
- **History:** events are stored with eventsourcing in `.troupe/events.sqlite`. Nothing is stored if the config can't load or the command line is invalid.

**Testing:** about 150 of the tests compare whole files byte for byte, including CRLF files, includes, folded re-wrapping and comment columns. A smoke suite runs the real `uv run troupe` against a multi-file theatre. I also fuzzed 1,500 random `set` sequences on LF and CRLF configs with includes, checking that each set reads back as intended. There were no crashes, no wrong results and no LF line endings slipping into CRLF files; the only refusals were the include replacements the contract forbids.

**Bugs found and fixed:**
- New keys like `true` were written plain and would read back as booleans. They are now quoted.
- Filling an empty value such as `key:` was always refused (exit 3), because ruamel reports that empty value's position away from the key's line. It now writes right after the `:`.
- Deleting the first entry of a compact `- a: 1` list item was refused; it now works.

**Decisions to confirm:** the 8 points from the plan stand. Two more choices came up during implementation, and both are now in `design.md` and the README:
1. A TAB in a value goes into single quotes, because the contract's fallback order puts single before double quotes. So `'a<TAB>b'` with a literal TAB, not `"a\tb"`.
2. Line-length lint is switched off in `tests/` so each byte-exact before/after case stays on one line.

**Commits:** the work is in 7 commits after the plan commit. Two of them are fix-ups for lint and type errors in an earlier commit; I left them in rather than rewrite history. Nothing was pushed.

All tasks are complete. You can archive the change with `/opsx:archive`.