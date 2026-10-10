The spec for step 2 is written and committed on `feat/troupe-config-sync-files` (commit `2941e03`), and the quality checklist passes on the first try. It isn't on `main` yet. Delivery means merging that branch into `main` after implementation, the same way step 1 landed. Nothing pushed, no PR.

- **Mission:** `troupe-config-sync-files-01M3ZT6R` (id `01M3ZT6RJENXK1D5FZYETB4V72`)
- **Spec:** `kitty-specs/troupe-config-sync-files-01M3ZT6R/spec.md`
- **Checklist:** `kitty-specs/troupe-config-sync-files-01M3ZT6R/checklists/requirements.md`

**What the spec says:**
- **Change to step 1:** step 1 said hand edits never create history events (FR‑008/FR‑022 and its confirmed decision). That rule is replaced: reconcile now records hand edits as `set`/`remove` events. The files on disk are still the source of truth, and reconcile never writes to a file.
- **The rule that must always hold:** after any reconcile, the history matches the files on disk, and each difference is recorded exactly once. FR‑015 and FR‑016 apply this to a `set` while `watch` is running, so its write-back isn't recorded a second time.
- **Your answer on the open question (D‑1):** if a hand edit breaks the configuration while `watch` is running, `watch` keeps running. It writes one stderr line naming the file, records nothing, and reconciles once the files load again. Why: the contract says `watch` runs until SIGINT/SIGTERM and then exits 0, and recording nothing loses no edits and can't corrupt the history.
- **Recorded choices D‑2 to D‑7:** the ones you accepted (stdout is only `watching <dir>`, import before the line, exit 4 at startup, `history` doesn't reconcile, event order). Plus one I made where the contract is silent: if a command reconciles and then fails with exit 3 or 5, the reconcile's events are kept.
- **Size:** 16 functional requirements, 7 non-functional ones (including the 2‑second reaction time and no missed changes after the `watching` line), and 5 constraints. One `watch` plus one other command at a time is supported; several `watch` processes on one theatre, or two `set` commands at once, are not.

`setup-plan` has already created an empty `plan.md`. `status.events.jsonl` has an uncommitted bookkeeping change from spec-kitty. How a `set`'s write-back is kept from being picked up again is deliberately left for the plan.

Next step: `/spec-kitty.plan`.