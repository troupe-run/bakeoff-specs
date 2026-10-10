## Implementation complete

All 14 tasks of `config-get-and-show` are done and committed on `main`; nothing was pushed. The final run had 455 tests passing, and mypy, ruff check, ruff format and `openspec validate --strict` all clean.

**What it does now:**
- **`troupe config get PATH`** prints a single value, exactly as `show PATH` did before. On a mapping or list it exits 5, and the error names the path and says to use `troupe config show <path>`.
- **`troupe config show [PATH] [--sources]`**:
  - A single value prints the same as `get`.
  - A section, a list, or the whole configuration (no PATH) prints as YAML. Includes are resolved, and text includes appear as literal blocks (`|`).
  - With `--sources`, each line holding a value ends with `# from <file>`, e.g. `# from .troupe/agents/coder.yaml`. For a text include it names the included file.
- **`get` records hand edits before reading**, the same way `show` does.

**How it's built:** a new `src/troupe/render.py` writes the YAML. It reuses the quoting and literal-block code `set` already had, so both commands write values the same way.

**Tests:**
- The old scalar tests moved to `tests/test_get.py`.
- New exact-output tests are in `tests/test_show.py` and `tests/test_show_sources.py`.
- `tests/test_render.py` reads the output back and checks the values and their types match the configuration.
- There are new `get` cases for recording hand edits, and a `uv run` end-to-end test.

Three existing tests assumed the old behaviour and were updated:
- `show agents` exiting 5 is now `get agents` in the end-to-end tests.
- `show` with no PATH used to be a usage error and is now valid.
- The test that read commands leave your files untouched now also runs `get`, `show` and `show --sources`.

**What a deliberate breakage showed:** forcing strings to print unquoted makes the read-back tests fail, as intended. Turning off literal blocks does not: double-quoted strings still read back as the same data. The exact-output tests in `test_show.py` and `test_show_sources.py` are what pin the `|` layout.

**README:** it now documents `get`, `show --sources` and how to move scripts from `show` to `get`, and lists the choices I made where the contract was open. I put the new section after the `watch` example, because its demo overwrites `troupe.yml` and would otherwise break that example. I ran every README command in order against a fresh `/tmp/demo`, and they all work as written.

You can archive this change with `/opsx:archive`.