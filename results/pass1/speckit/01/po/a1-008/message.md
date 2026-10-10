I fixed T054 and committed it on `main` as `46421cc`. Every task in `tasks.md` is now marked done. No extension hooks are registered.

`troupe config set p file:o.md` now works. It writes the `file:` string into the file, and after that `p` reads as the included file:
- `show p` prints the content of `o.md`.
- History records the change with `new` set to that content.

If the include can't load (the target is missing, or it would include itself in a cycle), it still refuses with exit 3 and names the target. Nothing is changed in that case.

Before writing, the check now also accepts a value that matches what is written, meaning the `file:` string itself. Text-include writes are still checked against the loaded text. The decision is recorded as B-17 in `research.md`.

**Tests:** I added five end-to-end tests: a text target, a YAML target, an include inside a new mapping, a missing target, and a cycle. The three success cases failed before the fix; the two refusal cases already passed. Removing the new check made those three fail again, so the tests do catch the problem. The full suite (363 tests) passes, and mypy and ruff are clean.

A fresh `/speckit-converge` should now come back clean.