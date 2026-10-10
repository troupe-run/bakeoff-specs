There's nothing left to archive. `config-remote-includes-and-schema` was archived at the end of the apply run, and there are no other active changes.

## Archive Complete

**Change:** config-remote-includes-and-schema
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-08-config-remote-includes-and-schema/`
**Specs:** ✓ Synced to main specs
- New capability: `config-schema`.
- Updated: `config-loading`, `config-set`, `config-show`, `config-cli` and `config-sync`.
- Strict validation of all 9 main specs passes.

All 4 artifacts and all 30 tasks are complete. The archive is committed on `main` as `b813885`, and the working tree is clean. Nothing was pushed.

When syncing, the archive dropped the note explaining what `<base>` means in the scenarios, because it sat outside the requirement blocks. I added it back by hand to the Purpose sections of `config-loading` and `config-set`.