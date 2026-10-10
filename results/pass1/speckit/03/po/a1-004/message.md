Step 3 is built and committed on `main`, and the working tree is clean. Nothing was pushed and no pull request was opened. All 21 tasks are marked done. The pre-implementation requirements checklist had all 16 items checked, and no extension hooks are registered.

**Final checks:** 539 tests pass (442 before step 3), `mypy --strict` reports no issues across 63 files, and ruff check and format are clean.

**What changed:**
- **`get PATH`** (0c9e74b) prints a single value exactly as `show` did before. The step 1 `show` tests moved over to `get` unchanged. Asking `get` for a mapping or list exits 5 with: ``agents.coder: is a mapping, not a scalar; use `troupe config show agents.coder` to print it``.
- **`show [PATH]`** (5bcb6b7) still prints a single value like `get`. A section, or the whole configuration if PATH is left out, prints as YAML: 2-space indent, includes filled in, text includes as literal blocks. It uses the quoting rules `set` already had. The output reads back as the same configuration with the same types; a Windows line-ending text include is the one exception, as the spec records.
- **`show --sources`** (cc5775a) ends each value's line with `# from <file>`, relative to the theatre. This came from the same new `view.py` module, so this commit only added tests. They cover the main file, nested includes, text includes, files outside `.troupe/` or the theatre, single values, and a theatre reached through a symlink.
- **Docs** (adf65bb): the README, and notes in the step 1 and step 2 docs that `show PATH` is now `get PATH`.

**How the tests were checked:**
- For each story I broke the behaviour on purpose and confirmed a test failed, then restored the code. The breaks were: the `config show` hint, `get` not picking up hand edits, text includes not as literal blocks, list layout, quoting, the wrong source file, the symlink handling, and a comment on a section line.
- One of those first looked uncaught. It turned out my edit hadn't changed the code; with the edit applied, the tests catch it.
- One new test was wrong at first: I expected `show agents` to include the `agents:` key itself, but it correctly prints only what's inside it. I fixed the test, not the code.

I also ran the quickstart by hand. Every command printed what the spec shows, and no configuration file was modified.