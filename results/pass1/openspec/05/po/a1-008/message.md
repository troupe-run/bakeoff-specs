## Archive Complete

**Change:** config-set-in-include
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-05-config-set-in-include/`
**Specs:** ✓ Synced to main specs

All artifacts complete. All tasks complete (10/10).

**Decision: sync, then archive.** Following your earlier instruction to take the safest option where the brief is silent, I made the same choice as for CR-A. It's recorded under "Archive decision" in the archived `design.md`: without the sync, the main specs would lack `--in-include` while the code, tests and README have it.

**What changed in `openspec/specs/`:**
- **`config-cli`:** "Invocation and theatre selection" now lists `[--in-include]` (scenarios 17 → 18).
- **`config-set`:** gained "Writing new keys into the included file on request" (17 → 18 requirements, 63 → 74 scenarios).

I checked both against the change's spec deltas: every requirement matches exactly, no existing scenario was lost, and the Purpose sections are unchanged. All 8 specs pass strict validation.

**Also done:**
- The README link now points at the archived design.
- The suite still passes (582 tests).
- Everything is committed on `main` as `9c1dfbd`, nothing pushed, and the working tree is clean.
- No changes remain active.

Both change requests from step 5 are now delivered on `main`. CR-A keeps shared includes shared by writing new keys as overrides, and CR-B adds `set --in-include` for when a key belongs in the shared file.