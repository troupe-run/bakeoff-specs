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

Q2: The spec for step 2 is written and committed on `feat/troupe-config-sync-files` (commit `2941e03`), and the quality checklist passes on the first try. It isn't on `main` yet. Delivery means merging that branch into `main` after implementation, the same way step 1 landed. Nothing pushed, no PR.

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
A2 (po): /spec-kitty.plan