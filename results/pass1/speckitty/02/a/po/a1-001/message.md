I've created the mission scaffold. Nothing in the spec is final yet.

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