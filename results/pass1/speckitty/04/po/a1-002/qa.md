Q1: I read the code (`src/troupe/history.py`, `session.py`, `reconcile.py`, `commands/set_value.py`) and the earlier contracts. The step-4 contract doesn't settle one thing, so I need your call on it.

**Question: what should `history` show for events recorded before lineage existed?**

A theatre imported or changed under steps 1–3 already has events in `history.sqlite`, and those events carry no actor, reason or change id. Two facts matter:
- The event store already records a UTC timestamp on every event, so `at` can be filled in truthfully.
- `via` can also be filled in for old `import` events. It can't for old `set`/`remove` events: the stored data doesn't say whether a CLI `set` or a file reconcile produced them.

Options:
- **(A) Recommended: report what is known and mark the rest unknown.** Old events get their real `at`, actor `{"kind":"unknown","id":null}`, `reason: null`, and `via: "import"` for old imports. That leaves two gaps:
  - `via` for old `set`/`remove` events has no truthful value in the contract's three-value list. I'd add `null` for these events only, and say so in the contract.
  - `change` would be a stable id for each old event, because which events came from the same command was never recorded.
- **(B) Refuse:** `history` fails on a pre-lineage history with an error naming the database file.
- **(C) Something else.**

Along with your answer, please confirm or correct the defaults I plan to use for the other open points:
1. When `set` first reconciles hand edits, those events are a separate change (`via: "file"`, actor unknown) from the `set`'s own change (`via: "cli"`).
2. Every `troupe config` command checks `TROUPE_ACTOR` before loading anything. An empty id (`human:`), an empty variable, or any other form exits 2 with a message naming the variable.
3. If `TROUPE_ACTOR` is unset and the login name can't be found, the actor is `{"kind":"human","id":null}`.
4. `--reason` exists only on `set` and is stored as given. A `set` that changes nothing records nothing, so its reason is dropped.
5. Each `watch` reconcile is its own change.
6. The history line keys run in this order: `seq, op, path, old, new, actor, via, at, reason, change`.

WAITING_FOR_DISCOVERY_INPUT
A1 (po+fallback): On “What should `history` show for events recorded before lineage existed: (A) the known fields filled in and the rest marked unknown, with `via: null` for old set/remove events and a stable per-event `change`, (B) refuse with an error naming the database file, or (C) something else?”: The contract says every `history` event has the Lineage fields. It says nothing about events recorded before step 4, or about upgrading stored history. Treat this as out of contract: it's your choice. State which option you chose and why. Note that the contract itself doesn't change, so record your choice in your own spec or documentation, not as a contract amendment.

On “When `set` first reconciles hand edits, are those reconcile events a separate change (via "file", actor unknown) from the set's own change (via "cli")?”: Confirmed. Lineage names a file reconcile as its own producer of a `change`, separate from a command. File-originated events have actor {"kind": "unknown", "id": null}. The set's own events have via "cli" and the actor from TROUPE_ACTOR. So the reconcile events get one change id and the set's own events get a different one.

On “Does an empty TROUPE_ACTOR, an empty id such as `human:`, or any other form exit 2 with a message naming the variable, for every `troupe config` command?”: Yes. Lineage gives the only valid forms as `human:<id>` or `agent:<id>`, and anything else exits 2. A variable that is set but empty is not unset, so it exits 2. `human:` carries no id, so it is not `human:<id>` and also exits 2. This applies to every CLI command. A message that names TROUPE_ACTOR is fine.

On “Should every `troupe config` command check TROUPE_ACTOR before loading anything, so that a bad TROUPE_ACTOR exits 2 even when the configuration also cannot be loaded (exit 4)?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “If TROUPE_ACTOR is unset and the login name cannot be determined, should the actor be {"kind": "human", "id": null}?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Is `--reason` accepted only on `set`, stored exactly as given, and dropped when a `set` changes nothing?”: Confirmed. The contract defines `--reason` only as `set --reason TEXT`, and `reason` is the text given. A `set` that changes nothing emits no events, so there is nothing to carry its reason.

On “Is each `watch` reconcile its own change?”: Confirmed. `change` identifies the command, file reconcile or import that produced the event, and no two share one. Each reconcile that `watch` performs is a separate file reconcile, so each gets its own change id.

On “Is the key order `seq, op, path, old, new, actor, via, at, reason, change` acceptable for history lines?”: Yes. The contract requires each line to be an object with at least those keys. It does not fix their order, so your order is acceptable.