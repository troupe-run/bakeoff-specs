I've finished discovery and committed it on `main` (`8f58c05`). This covers planning only: no code for `watch` or reconcile has been written yet. If the step is tested as delivered behaviour, those tests will fail until the spec is implemented.

**Path: mixed.** Step 2 needs one new spec, `config-file-sync`. It also reverses a step-1 rule in both existing specs: edits made by hand used to add no history events ("importing is not reconciling"), and now every command except `history` must record them. The rule that `show` and `set` read the files on disk stays as it is.

**Chosen approach** (recorded in `.kiro/specs/config-file-sync/brief.md`):
- **Reconcile** compares the leaves in the files with the configuration as recorded, which is worked out by replaying the history. It records a `set` or `remove` event for each leaf that differs, all in one transaction. Edits that only change formatting or comments produce no events.
- **A `set`'s own write-back is never recorded twice.** The `set` has already recorded those values, so the next reconcile finds nothing to add.
- **`set` and `watch` take turns through a lock** held on `.troupe/`, so no extra file is left behind. Without it, `watch` could reconcile between a `set` writing the file and recording its events, which would duplicate them.
- **`watch` checks file contents every few hundred milliseconds**, using only the standard library. It watches the config file and every included file, and re-reads the list after each load so a newly added include is followed. It takes its first snapshot before printing `watching <dir>`, so the line is true when it appears.
- **I didn't use a file-watching library** (watchfiles or watchdog). It would add a dependency and make the "only print once watching" promise harder to keep.

**Open choices**, listed in the brief for the requirements step:
- If the files can't be loaded during `watch` (for example, a half-saved file), it records nothing and keeps watching. It never treats that as every leaf being removed.
- `<dir>` in the `watching` line is printed exactly as it was given.
- `watch` on a theatre that has never been imported imports it first.
- `watch` prints only the `watching` line to stdout; everything else goes to stderr.

**Roadmap** (`.kiro/steering/roadmap.md`): I kept all the step-1 content and added a step-2 section. It lists `config-file-sync` as a new spec, plus requirement changes to `config-foundation` (6.9 and 7.3) and `config-set-writeback` (the 15.1 example). The step-1 tests that assert hand edits add no events will be updated within the new spec's tasks, in the same change as the new behaviour.

**Next steps:**
- `/kiro-spec-init config-file-sync`, or `/kiro-spec-quick config-file-sync` to go straight through to tasks.
- `/kiro-spec-requirements config-foundation` and `/kiro-spec-requirements config-set-writeback` to update the step-1 requirements this reverses.