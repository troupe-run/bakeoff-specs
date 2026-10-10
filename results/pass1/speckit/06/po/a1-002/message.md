The fix is **verified**: the reported bug no longer happens. The report is in `.specify/bugs/yaml-alias-set/test.md` and is committed to `main` as `32d38d2`. The working tree is clean, and nothing was pushed.

Slug: `yaml-alias-set` (you gave it explicitly)

**Re-running the bug through the real CLI on the committed code:**
- **The issue's exact case:** `set coder.settings.model sonnet` now exits 3, the error mentions `--expand-alias`, and the file is left untouched.
- **New key through an alias:** `set coder.settings.temperature 0.2` is refused the same way.
- **Anchored scalar:** setting `m` gives `m: &x 6`, so the anchor survives and `y` follows it. Setting `y` replaces only that alias.
- **`--expand-alias`:** gives `settings:  # expanded from *d by troupe` followed by `model: sonnet`. `reviewer.settings` still points to `*d`.
- **Setting at the anchor:** `set defaults.model sonnet` changes only the anchored line, and every alias follows it.

**Checks:**

| Check | Result |
|---|---|
| New tests (`tests/e2e/test_set_alias.py`) | 13 passed |
| Full suite | 795 passed, 1 skipped |
| `ruff check`, `ruff format --check`, `mypy --strict` | all clean |

These limits still apply and are listed in the report:
- Merge keys (`<<`) are read as ordinary keys rather than merged. Writes through them are refused, which meets the contract.
- `--expand-alias` refuses (exit 3) for an alias inside a flow collection like `{settings: *d}`, and when the change would land in a different file.
- Replacing the alias itself (e.g. `set coder.settings '{a: 1}'`) is allowed and changes only that alias. The contract doesn't say either way, so you may want to decide whether it should be refused instead.