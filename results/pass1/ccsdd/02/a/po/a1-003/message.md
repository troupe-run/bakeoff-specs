## Requirements summary
I wrote 9 requirements (52 acceptance criteria) for `config-file-sync`:
- **Reconcile (Req 1):** when a hand edit changes, adds or removes a value, troupe records one `set` or `remove` event for it. Values must match in type, so `1`, `1.0`, `true` and `"1"` all count as different.
  - Edits that change only formatting or comments record nothing. Neither does moving a value into another file.
  - Each reconcile is recorded all-or-nothing, and never twice even when several troupe processes run at once.
- **When it runs (Req 2):** `show`, `set` and `watch` reconcile first. `history` never does, though it still does the first-run import. A `set` records its own events after the reconcile's, with `old` taken from the files.
- **`set` while watching (Req 3):** each `set` is recorded exactly once, including when it adds an include.
- **`watch` (Req 4–7):**
  - **Starting:** it prints `watching <dir>` only once it can see changes.
  - **Detecting changes:** it records each change within 2 seconds. Includes added by hand are followed, and removed ones are dropped.
  - **Errors:** a file it can't load is reported on stderr and skipped, and `watch` keeps running.
  - **Stopping:** SIGINT or SIGTERM ends it with exit 0, no leftover files and the store closed.
- **Shared rules and step 1 changes (Req 8–9):** `watch` uses the same exit codes and messages as the other commands. Req 9 lists the step 1 rules it replaces (decision A, 6.9, 7.3), and says the step 1 specs and tests are updated in the same change as the code.

I made five choices where the contract is silent, and listed them under "Boundary Context":
- Reconcile events stay recorded even if the command then fails.
- Usage errors (exit 2) record nothing.
- An unloadable file while watching is reported and skipped rather than ending `watch`.
- `<dir>` is printed exactly as given.
- Removed values are recorded in the order they were recorded.

## Document status
- `.kiro/specs/config-file-sync/requirements.md` is written.
- In `spec.json`, `phase` is `requirements-generated` and `approvals.requirements.generated` is `true`.
- Both are committed on `main` as `16bdc7f`.

## Review gate
It passed after one repair pass. The repairs:
- **5.5:** a "may" became a testable "net effect" rule.
- **1.10:** reworded to describe what you can observe, not how it's implemented.
- **2.1:** now covers every subcommand except `history`.
- **9.4:** now says which documents it applies to.

## Next steps
Please check the requirements, especially the five choices above. Then either:
```
/kiro-validate-gap config-file-sync     # optional: check what the code needs
/kiro-spec-design config-file-sync      # or add -y to approve and continue
```
To change anything, give feedback and re-run `/kiro-spec-requirements config-file-sync`.