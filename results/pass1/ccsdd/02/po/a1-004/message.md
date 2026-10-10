## Analysis Summary
The requirements are generated but not approved yet; I ran the analysis anyway because it can still shape them.

- **Reconcile is small.** Most of it already exists: `open_theatre` is the one place every command passes through, `document.files` lists every included file, `flatten_leaves` and `scalar_equal` give the leaves and the typed comparison, and `record_changes` already saves a batch in one transaction. What's missing is a way to compute the configuration as recorded from the history. I checked that values like `inf`, `nan`, `1.0` and `true` read back from the history with the right types, so the comparison will work.
- **A lock is required.** I tested two processes adding to the history at once, and the second one fails with `IntegrityError` (it would exit 4). Nothing gets corrupted, but a `set` would fail spuriously while `watch` runs, and exactly-once recording breaks. A `set` also needs the lock across its file write and its event record, or `watch` could record its write-back as a hand edit.
- **`watch` is the biggest piece.** The CLI currently holds all output until a command finishes, which can't work for the `watching` line. SIGTERM currently kills the process and SIGINT prints a traceback. There is no file watching and no test helper for a background process.
- **Six existing tests assert the old "hand edits add no events" behaviour.** They're listed in `research.md` and must change together with the code.
- **Recommended approach (option C):** new modules for the recorded configuration, reconcile, the lock and the watch loop, plus a `watch` subcommand. `open_theatre` would take the lock and reconcile by default, and only `history` would opt out, so a future command can't silently skip reconciling. Effort is medium (3–7 days) and risk is medium (concurrency, signals and timing-based tests).
- **Questions carried to design:** which lock, how `watch` notices changes, and how signals are handled. Also: what to watch while the files can't be loaded, how to report errors without repeating them, printing `<dir>` exactly as given (`--theatre` is parsed as a `Path`, which rewrites `./t/` as `t`), the order of `remove` events, and how to keep timing tests reliable.

## Document Status
I wrote the analysis to `.kiro/specs/config-file-sync/research.md`, a new file. It covers what exists, a map from each requirement to what's missing, the three options with trade-offs, effort and risk, and the open questions for design. It's committed on `main` (`1ba03be`). No code changed.

## Next Steps
Once you approve the requirements, run:
```
/kiro-spec-design config-file-sync
```
Or `/kiro-spec-design config-file-sync -y` approves the requirements and goes straight to design.