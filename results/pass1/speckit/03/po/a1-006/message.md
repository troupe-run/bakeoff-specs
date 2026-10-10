I've fixed both convergence tasks, T022 and T023, and committed the work on `main` (9699529). All 23 tasks in `tasks.md` are now marked done. The working tree is clean, and nothing was pushed or opened as a pull request.

- **T022:** a text whose first line contains only spaces (e.g. `"    \nabc\n"`) made `show` print YAML that wouldn't parse, and made `set` refuse the value with exit 3. The fix is in `needs_indent_indicator` in `src/troupe/config/edit/render.py`. Such text now gets an indentation number (`|2`) and reads back exactly.
  - New tests cover a text include, a value inside a list item, and a top-level value with `--sources`. A new `set` test checks it now writes `k: |2` followed by the indented lines.
  - All four tests failed before the fix and pass after it, which also served as the deliberate-break check.
- **T023:** added a test that a file included under two keys is shown in full under both, each line marked `# from .troupe/s.yaml`. That behaviour was already correct, so I didn't do a deliberate break for this one.

Final checks: 544 tests pass, `mypy --strict` reports no issues across 63 files, and ruff check and format are clean. No extension hooks are registered.

Running `/speckit-converge` again should now report nothing left to do.