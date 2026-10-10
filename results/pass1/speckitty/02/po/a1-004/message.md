The plan for step 2 is written and committed on `feat/troupe-config-sync-files` (commits `c340ce1` and `be613e5`), and `setup-plan` reports the plan phase complete. Nothing is implemented yet.

**Branch:** current, planning base and merge target are all `feat/troupe-config-sync-files`, and `branch_matches_target` is true. That branch goes into `main` at delivery. No push, no PR.

**Design, as you confirmed it:**
- **No double recording:** every reconcile and every `set` (from its reconcile through writing files and recording events) runs under one exclusive lock on the `.troupe` directory. A reconcile records only what differs from the recorded configuration. A write-back is already recorded before `watch` can see it, so `watch` finds no difference and records nothing.
- **No new file in the theatre:** the lock is taken on the `.troupe` directory itself, so the existing test that commands create only history files (`test_history.py:154`) still holds.
- **Recorded configuration:** a path→value map on the history aggregate, rebuilt by replaying events. Existing step‑1 histories need no migration and print exactly as before.
- **`watch`:**
  - It compares the bytes of the watched files and both root-file names every 0.25 s, with no new dependency.
  - The baseline is taken before `watching <dir>` is printed, so an edit made after the line is never missed.
  - While the configuration can't load, it retries every tick and prints one stderr line per distinct error.
  - SIGINT/SIGTERM let any reconcile in progress finish, then it exits 0.
- **One place for reconcile:** `open_session(theatre_dir, reconcile=…)` does lock → locate → load → import or reconcile. `show` and `set` pass `True`, `history` passes `False`.
- **Spec change:** FR‑009 now says `watching <dir>` echoes the directory as given (new decision D‑8).
- **Step‑1 tests to rewrite:** two of them encode the old "hand edits never produce events" rule. They'll be rewritten alongside the reconcile code, not deleted.

**One risk the plan leaves alone:** a hand edit saved during a `set`'s locked section is two writers on the same file at once. That is out of contract (C‑003), so it's documented rather than handled.

All 9 charter rules pass, the dependency checks (directive 051) had nothing to review, and the decision check is clean. `status.events.jsonl` has an uncommitted bookkeeping change from spec-kitty.

Files are in `kitty-specs/troupe-config-sync-files-01M3ZT6R/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli-watch.md`
- `quickstart.md`

Next step: `/spec-kitty.tasks`.