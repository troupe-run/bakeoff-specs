## Archive Complete

**Change:** config-include-overrides
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-05-config-include-overrides/`
**Specs:** ✓ Synced to main specs

All artifacts complete. All tasks complete (17/17).

**Decision: sync, then archive.** I recorded it under "Archive decision" in the archived `design.md`. Archiving without syncing would leave the main specs saying new keys go into the shared file, while the code and tests do the opposite. That would break the rule that spec, code and tests agree. Syncing only touches spec files, keeps every existing scenario, and matches how earlier changes were archived.

**What changed in `openspec/specs/`:**
- **`config-loading`:** gained "Mapping-form includes and overrides" (3→4 requirements, 12→22 scenarios).
- **`config-set`:** gained "New keys under includes are written as overrides", and 5 requirements were replaced (16→17 requirements, 41→63 scenarios).
- **`config-show`:** "Show sources" was replaced, adding one scenario.
- **`config-sync`:** "Includes added by hand are followed" was replaced, adding three scenarios.

I checked each spec against its delta: every requirement matches exactly, no existing scenario was lost, and the Purpose sections are unchanged. All 8 specs pass strict validation; the only notes are informational ones about long requirement text.

The README link to this change's design now points into the archive. The test suite still passes (564 tests). Everything is committed on `main` as `ab49293`, nothing pushed, and the working tree is clean.

CR-B (`config-set-in-include`) is now the only active change, and it still validates. CR-B's request is done only once its implementation is committed on `main`. When you're ready, run `/opsx:apply config-set-in-include`.