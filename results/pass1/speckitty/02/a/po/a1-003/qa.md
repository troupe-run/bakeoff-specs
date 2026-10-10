Q1: I've created the mission scaffold. Nothing in the spec is final yet.

**Branches**
- **Started on:** `main`, which is the primary branch, so spec-kitty recommends a separate feature branch.
- **Mission branch:** `feat/troupe-config-watch-sync` is where planning and building happen. spec-kitty's `merge_target_branch` is that branch too. I'll do the final merge into `main` myself, the same way step 1 was delivered. No push, no PR.
- **Handle:** `troupe-config-watch-sync-01M3YEQM`

**What I already take as settled from the contract:** step 1 decided that hand edits never produce history events. Step 2 reverses that: reconcile records each changed leaf as a `set` or `remove` event. The spec will say clearly that this replaces step 1's rule.

**Question 1: a hand edit that breaks the configuration while `watch` is running**

Editors save often, and people save in the middle of typing. That can leave a YAML syntax error, a missing include target, an include cycle, or both `troupe.yml` and `troupe.yaml` present. The contract doesn't say what `watch` should do then.

- **(A) Keep watching (my recommendation).** Print an error to stderr that names the file, record nothing, and reconcile normally once the files load again. Stopping on a half-saved file would make `watch` fragile. Recording nothing is the safe choice because no data can be lost.
- **(B) Stop.** Exit 4 with stderr naming the file, the same as other commands do on a load failure.
- **(C) Something else.**

For the record: if the configuration can't be loaded when `watch` starts, it would exit 4 without printing `watching <dir>`. Other commands that reconcile first would also exit 4 on a broken configuration, as they do today.

WAITING_FOR_DISCOVERY_INPUT
A1 (po): Option A: keep watching. The contract says `watch` runs in the foreground until SIGINT or SIGTERM and then exits 0, so a broken save must not make it exit. While the files can't be loaded, print an error to stderr that names the file involved and record no events. When the files load again, reconcile as usual against the recorded configuration.

Q2: I've recorded your answer: a broken save never stops `watch`. It prints an error to stderr naming the file, records nothing, and reconciles normally once the files load again.

**Question 2: what `watch` prints after `watching <dir>`**

The contract says `watch` emits `set`/`remove` events when it reconciles. It doesn't say whether those events also go to stdout, or only into the recorded history.

- **(A) Nothing else on stdout (my recommendation).** stdout carries only the `watching <dir>` line, and the events can be seen with `troupe config history`. This keeps the only stdout promise in the contract simple to check. It also leaves room to print events in a later step if that turns out to be wanted. Errors from a broken save still go to stderr, as you decided.
- **(B) Print each event as it is recorded,** as a JSON Lines record in the same shape `history` uses.
- **(C) Something else.**

WAITING_FOR_DISCOVERY_INPUT
A2 (owner): The contract's only stdout promise for watch is the single `watching <dir>` line (Sync with files). "Emit" under Reconcile means record the event, which `history` reports. Anything further on stdout is out of contract: your choice — state which you chose and why.