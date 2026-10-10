I've planned step 2 as the OpenSpec change `config-watch-reconcile` and committed the plan on `main` (3df5b7a), not pushed. No code has changed yet, so the step isn't delivered until it's implemented and committed. `openspec validate --strict` passes.

**What's in `openspec/changes/config-watch-reconcile/`:**
- **`proposal.md`**: why and what. It adds `watch`, a reconcile step in `show`, `set` and `watch` (not `history`), and a lock that keeps a `set`'s write-back from being recorded again.
- **`specs/config-sync/spec.md`** (new): how reconcile compares files with the record, which commands reconcile, how `watch` behaves, how broken edits are handled while watching, and a scenario for each.
- **`specs/config-history/spec.md`**: step 1's rule that "hand edits generate no events" is reversed. OpenSpec can't drop a scenario from a modified requirement, so I removed "Import on first command" and re-added it as "Import once on first command", with everything else unchanged. "Events recorded by set" now says reconcile runs first, and a refused `set` keeps the reconciled events but records none of its own.
- **`specs/config-cli/spec.md`**: adds the `watch` subcommand. It also documents the `TROUPE_THEATRE` default, which commit 8f6131a added to the code but not to the spec.
- **`design.md`** and **`tasks.md`**: the approach below, and 10 tasks in 4 groups, each with its own tests.

**Main design choices:**
- **Shared rule:** reconcile compares leaves using the same function `set` already uses to work out its events, so formatting-only and comment-only edits record nothing.
- **Lock:** each command takes an exclusive `flock` on the `.troupe/` directory and holds it while it loads, reconciles, writes and records. When `watch` next looks, a `set`'s write-back already matches the record, so nothing new is recorded. Locking the directory means no new state file. I confirmed the lock is exclusive on this Linux machine; on macOS I'm relying on `flock` supporting directories, which still needs checking there.
- **Watching:** `watch` checks file contents every 0.2 s rather than using a file-watching library. That adds no dependency, works the same on Linux and macOS, catches editors that save by renaming, and picks up newly included files. `watching <dir>` is printed only after the starting state has been captured, so any later change is seen.

**Choices the contract left open (please confirm):**
1. `<dir>` in `watching <dir>` is the `--theatre` value exactly as given, else `TROUPE_THEATRE`, else the absolute current directory.
2. Apart from that line, `watch` prints nothing to stdout; it doesn't print the events it records.
3. If the configuration can't be loaded at startup, `watch` exits 4 without printing the line.
4. If a mid-edit save breaks the configuration while `watch` runs, it records nothing, reports the problem once on stderr naming the file, and keeps running. It never treats a broken configuration as empty, which would record a `remove` for every setting.
5. `history` still does the one-time import on a theatre nothing has run against; it just never reconciles.
6. **Not protected:** if someone saves a file in their editor at the same moment a `set` writes that file, the last write wins, as in step 1.

The artifacts are ready for review. When you're ready, run `/opsx:apply`.