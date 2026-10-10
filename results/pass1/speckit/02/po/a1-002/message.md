I've written the step 2 plan and design documents and committed them on `main` as `ebf44e2`. Every constitution check passes before and after design, with nothing needing justification. As before, there's still no code.

The setup script reported the branch as `002-config-file-sync`, but no branch was created; work stays on `main`. The plan is `specs/002-config-file-sync/plan.md`, and no hooks are registered for this step.

**Main design choices:**
- **Reconcile:** it compares the values loaded from the files with the recorded configuration, using step 1's existing comparison. So formatting-only or comment-only edits record nothing, and `1` → `"1"` counts as a change. Each reconcile's events are saved together in one go.
- **Who reconciles:** the one function that loads the configuration for every command gets a switch. `show`, `set` and `watch` turn it on; `history` turns it off.
- **Exactly once:** every command takes an exclusive lock on a new file, `.troupe/events.sqlite3.lock`, and holds it from loading the files until its events are recorded. Whichever process comes second finds nothing left to record. This is what stops `watch` re-recording a `set`'s own write-back, and stops `watch` and a command both recording the same hand edit.
- **Spotting changes:** `watch` re-reads every watched file five times a second and compares the bytes with the bytes it last read. File timestamps aren't used. That makes the `watching` line a real promise, catches editors that save by renaming, and needs no new dependency. Newly added includes start being watched after each reconcile.
- **Broken files:** if the configuration stops loading while `watch` runs, it retries on every check and prints each distinct error once. If it can't load at startup, it exits with code 4.
- **Signals:** SIGINT and SIGTERM only set a stop flag, so a reconcile that's under way finishes and `watch` exits 0.

**I changed the spec:** FR-114 now says a reconcile records removals in the order those values were first recorded, not "document order". Document order stops being well defined once `set` has added new values.

**Files added** in `specs/002-config-file-sync/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

Next is `/speckit-tasks`.