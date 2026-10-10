## Status
The design is written to `.kiro/specs/config-file-sync/design.md` and committed on `main` (`161879d`), with the requirements recorded as approved. The design itself is not approved yet.

## Discovery Type
Light discovery, since this extends existing code and adds no new dependency.

## Key Findings
- **Reconcile goes inside the step that opens a theatre for every command.** It's on by default, only `history` turns it off, and every `watch` check goes through the same step. It compares the files with what the history has recorded, not with the previous file contents. That catches edits made while nothing was running, and a `set`'s write-back finds nothing new because the `set` already recorded it.
- **A lock is required.** I confirmed that two processes adding to the history at once collide. The design uses a lock on the `.troupe/` directory itself, which creates no file. It's held from just after the config file is found until the command ends. That closes the gap between a `set` writing its files and recording its events, during which `watch` could otherwise record the write-back again.
- **`watch` checks files every 0.2 seconds.** It snapshots the watched files *before* each load and re-reads them by name, which makes the `watching` line a true promise and handles editors that save by renaming. Any failure is retried on the next check, with each distinct error message printed once. Signals only set a flag, so a reconcile in progress always finishes, and `watch` exits 0.

## Review Gate
The design passed. All 44 requirement IDs are traced, every component has a file, and the boundary sections are filled in. One pass removed a stray component name, `StopFlag`, from the traceability table.

## Research Log
`research.md` now also records the design decisions, the alternatives considered, the synthesis notes and the risks.

## Next Action
Review the design, then:
```
/kiro-spec-tasks config-file-sync
```
Optionally run `/kiro-validate-design config-file-sync` first. `-y` approves the design and goes straight to tasks.