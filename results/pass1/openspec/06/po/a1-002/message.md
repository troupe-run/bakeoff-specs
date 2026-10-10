## Implementation complete

**Change:** `config-anchors-and-aliases` (spec-driven), 23/23 tasks done, now archived.

Issue #2 is fixed and committed on `main` in 8 small commits; nothing was pushed and no PR was opened. On the final commit all 668 tests pass, mypy, ruff and `ruff format --check` are clean, and all 8 main specs pass `openspec validate --strict`.

**What changed:**
- **Loading:** files with anchors, aliases and `<<` merge keys now load, where before they failed with exit 4. An alias reads exactly like the value at its anchor in `get`, `show` and history.
- **Setting at the anchor:** `set defaults.model sonnet` changes the value at the anchor and keeps `&d`, so every agent using `*d` sees the new value. History records one event per affected path, all in one change.
- **Setting through an alias** (the reported bug): `set coder.settings.model sonnet` now exits 3 and changes nothing. The message says where the anchor is, names `defaults.model` as the place to change it for everyone, and mentions `--expand-alias`.
- **`set --expand-alias`:** for the issue's file it writes exactly what the contract specifies: `settings:  # expanded from *d by troupe`, then the new value. `defaults` and `reviewer` stay as they were. An end-to-end test runs the issue's file through `uv run troupe config`.
- **Merge keys:** `set` never writes them. Any set that would change a `<<` entry, or a value one supplies, exits 3.

**Problems found and fixed along the way:**
- The check that re-reads files before writing expected only the set path to change. That refused every set at an anchor, because the aliases change too. It now follows aliases and merge keys.
- Edits measured an alias entry by the anchored value elsewhere in the file. Deleting `settings: *d` produced a duplicate key; it now measures the `*d` text itself.
- `set` could have written a new key named `<<` plain, which would turn it into a merge key. It is now quoted.

**Things to know:**
- I changed the wording of two tasks' "verify" steps because some of the tests they named don't depend on the code in question. The tests that do depend on it fail when that code is broken, which I checked.
- One commit failed `ruff check` (two lines too long); the next commit fixes it.
- Setting `coder.<<` on a mapping that holds a merge key is refused with a "duplicate key" message rather than the merge-key one. It's still exit 3 with no file changed.
- The choices I made where the contract is silent are listed as README decisions 39–47.
- Issue #2 on GitHub is still open. I didn't comment on it or close it; say if you want me to.