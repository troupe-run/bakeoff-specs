## Archive complete

**Change:** config-get-and-show
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-03-config-get-and-show/`
**Specs:** ✓ Synced to main specs. All 7 main specs validate under `openspec validate --specs --strict`.

The workflow normally asks whether to sync the specs before archiving. I went ahead with the recommended option, as the two earlier changes did, so say if you'd rather have archived without the sync.

**What changed in the main specs:**
- **`config-get`** (new): the requirements for `get` printing one value and refusing mappings and lists.
- **`config-show`**:
  - Its purpose now covers reading any part of the configuration.
  - "Show a scalar value" was updated.
  - "Show collections as YAML" and "Show sources" were added.
  - "Show refuses collections and missing paths" was removed.
- **`config-cli`**: `get` is now in the subcommand list, and the "files untouched" scenario covers `get` and `show --sources`.
- **`config-sync`**: `get` is now one of the commands that record hand edits before running.

I also pointed the README's decisions list at the archived design path. Everything is committed on `main` (4ef5d76) and nothing was pushed. There are no other active changes. All artifacts complete. All tasks complete.