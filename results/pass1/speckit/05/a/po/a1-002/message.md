The step 5 plan and design docs are written and committed on `main` as `0987e10`. Nothing was pushed. No code has changed yet, and no extension hooks are registered, so none ran. Every principle passes the constitution check before and after design, with no exceptions to justify.

**Artifacts** (all in `specs/005-include-overrides/`):
- `plan.md`: technical context, constitution check, files to change, design overview
- `research.md`: ten technical decisions, O-1 to O-10
- `data-model.md`: the changes to the in-memory configuration tree, the merge rule, and a table of where `set` writes
- `contracts/cli.md`: the `$ref` file format, the new write rules, and the new exit 3 and exit 4 cases
- `quickstart.md`: the quality checks plus a manual walk-through you can run

**The approach:**
- **Loading:** a `$ref` include is loaded into a merged tree built from the original nodes. Each value keeps the file it came from, so `get`, `show --sources`, history, reconcile, `watch` and changing an existing value all work without changes.
- **New keys:** while walking the path, `set` tracks the nearest include. A new key goes into that include's overrides, or converts a one-line include to the `$ref` form first, keeping the comment and the exact include text. Passing through a list switches back to the old rule of writing in the file that holds the list.
- **Refusing bad writes:** the existing reload-and-verify check already produces exit 3 when merging wouldn't give the value that was set, so that needs no special code. It does need one change: it must expect an override to show up only where its include appears, not everywhere the shared file is included.
- **Rename:** the loader parameter `overrides`, which means something else today, becomes `texts` so the word has one meaning.

One existing test asserts the rule being replaced: `test_set_new_key.py::test_new_key_in_an_included_file`. It will be rewritten to expect the override in `troupe.yml`.

Next is `/speckit-tasks`.