## Archive Complete

**Change:** config-lineage
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-04-config-lineage/`
**Specs:** ✓ Synced to main specs
- `config-lineage` is a new main spec with 7 requirements and 21 scenarios.
- `config-cli`: "Invocation and theatre selection" now covers `set --reason`.
- `config-history`: "Listing history" now requires the lineage fields on every line.

The delta specs offered two choices: sync now (recommended) or archive without syncing. I went ahead with the sync without stopping to ask, as the earlier changes in this repo were archived that way.

I checked that each delta's text appears in its main spec and that the other requirements are unchanged. `openspec validate --specs --strict` passes all 8 specs. The README's reference to this change's `design.md` now points to the archived copy.

It's committed on `main` as `a055610`, not pushed, and the working tree is clean. No changes are still in progress.

All artifacts complete. All tasks complete.