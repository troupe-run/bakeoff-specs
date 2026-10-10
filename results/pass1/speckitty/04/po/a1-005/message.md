The plan phase is finished and committed. The setup check reports the plan phase complete, and `decision verify` is clean.

**Branch contract:** the current branch is `feat/troupe-config-lineage`, it is also the planning base and the merge target (`branch_matches_target: true`), and it gets merged into `main` at the end. Nothing has been pushed.

**What the plan contains:**
- **`plan.md`:** your approved approach and the charter check (no violations). It splits the work into five areas:
  - the lineage module;
  - the history store's new event version and the upgrade of old events;
  - passing the actor and lineage to imports, reconciles and `set`;
  - the history output;
  - tests, the old-history fixture and the contract files.
- **`research.md`:** nine recorded implementation choices, D-1 to D-9. Each has its reason and the alternatives I turned down.
- **`data-model.md`:** the actor and lineage values, the new event fields, how old events are upgraded, and six rules the code must keep. One of those rules is that a single command can produce up to three changes (import, reconcile, its own), each with its own id.
- **`contracts/cli.md` and `contracts/history-event.schema.json`:** the `TROUPE_ACTOR` rules, `set --reason`, and the history line format. The three out-of-contract choices are marked as such, not written in as contract changes.
- **`quickstart.md`:** a manual walkthrough.

One risk is now written into the plan as a hard rule: the event class names must not change. The event store finds stored events by name, so renaming a class would make existing histories unreadable. The test against the history recorded by the step-3 code guards this.

**Commits:** `ab29dce` (plan) and `cee0fda` (research, data model, contracts, quickstart). `status.events.jsonl` changes after every spec-kitty command, so it's still uncommitted.

All files are in `kitty-specs/troupe-config-lineage-01M436R0/`. The next step is `/spec-kitty.tasks`, which breaks the plan into work packages. Tell me when to run it.