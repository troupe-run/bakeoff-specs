## Archive Complete

**Change:** `config-sync-with-files`
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-03-config-sync-with-files/` (with its `.openspec.yaml`)
**Specs:** ✓ Synced to main specs

All artifacts complete. All tasks complete (21/21).

I synced without asking. That was the recommended option, and the same choice I made when archiving step 1: it keeps the main specs describing what the code and tests now do.

What changed in `openspec/specs/`:
- **`config-sync`:** new main spec, with 6 requirements and 23 scenarios.
- **`config-cli`:** `watch` is now a subcommand, and the rule that troupe only writes under `.troupe/` now covers `watch`.
- **`config-history`:** "Import on first command" is replaced by "Import on a theatre's first command". "Events recorded by set" is updated: a `set` after a hand edit records the hand edit's event first.

Two extra edits:
- I updated the `config-history` Purpose line so it mentions hand edits.
- I repointed the README's link from the change folder to the archived design doc.

All six main specs pass strict validation, and all 379 tests still pass. This is committed on `main` as `9143f74`, the working tree is clean, no changes are left open, and nothing was pushed.