**Discovery question 1: what should `watch` do when a hand edit breaks the configuration?**

**Scenario:** `troupe config watch` is running and someone saves a file that troupe can't load. It might be half-typed YAML, an include pointing at a file that doesn't exist yet, an include cycle, or both `troupe.yml` and `troupe.yaml` present. Editors often save in this kind of in-between state.

**What I found:**
- The contract only says `watch` stops on SIGINT/SIGTERM and exits 0.
- In step 1, every command exits 4 and names the file when the configuration can't be loaded. That still applies to the reconcile‑first step of `show`/`set`.
- `watch` is different because it runs for a long time. If it stops at the first broken save, it would stop during normal editing.

**Options:**
- **(A) Keep watching (recommended).** Write one stderr line that names the offending file and record nothing. When the files load again, reconcile against the last recorded configuration. The edits made in between then show up as normal `set`/`remove` events, and no data is lost or guessed.
- **(B) Stop.** Exit 4 and name the file, the same as other commands. The person has to restart `watch` after fixing it. Edits are still picked up later by the next command's reconcile.
- **(C) Something else.**

**Choices I'll make unless you object** (each one fills a gap in the contract, and I'll record why in the spec):
- `watch` writes nothing to stdout except `watching <dir>`.
- On a theatre that has never been imported, `watch` imports first, as every step‑1 command does.
- If the configuration can't load when `watch` starts, it exits 4 before printing `watching`.
- `history` still imports a never-imported theatre but never reconciles.
- Reconcile events use the existing `set`/`remove` ops. Sets come in document order, then removes, the same as a `set` command.

WAITING_FOR_DISCOVERY_INPUT