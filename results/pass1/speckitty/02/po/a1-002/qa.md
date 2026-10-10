Q1: **Discovery question 1: what should `watch` do when a hand edit breaks the configuration?**

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
A1 (po+fallback): On “When `troupe config watch` is running and a hand edit leaves the configuration unloadable (bad YAML, missing include target, include cycle, or both troupe.yml and troupe.yaml present), should watch keep watching and report the file on stderr, or exit 4?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Do you object to the listed default choices: watch's stdout carries only `watching <dir>`; watch imports a never-imported theatre first; watch exits 4 before printing `watching` if the configuration cannot load at startup; history imports but never reconciles; reconcile events use set/remove ops, with sets in document order and then removes?”: No objection. Using only `watching <dir>` on stdout is your choice, and the brief says this is out of contract (Escalated answers, watch stdout). Importing first follows from 'The first command run against a theatre imports it' (history). Exiting 4 at startup with nothing on stdout follows from the General exit codes and from 'the line is a promise'. History importing but never reconciling is stated in history and in Sync with files. Reconcile emitting set/remove events is stated in Sync with files (Reconcile). The contract does not state an order for events within one reconcile, so the order you proposed is acceptable. Record what you chose in the spec.