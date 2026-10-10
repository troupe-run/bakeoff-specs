# Step 4 summary — speckitty (pass1)

**Outcome:** done after 1 attempt(s); interventions: none
**Hidden tests:** 129/135 passed; new at this step 14/14 (discriminating: 14); arm flakes: 0
**Model pin:** ok (693 transcript assistant messages)
**Cost (estimate):** arm $152.56 · PO $1.60 · harness $0.00
**Time:** 12753.8 s wall, 19.2 s waiting on the owner
**Quality:** mypy 0 errors · ruff 38 (arm 0) · mutation score 0.8496732026143791 (seeded-sha256)
**Research attempts:** {'denied_web_tools': 0, 'refused_hosts': ['eventsapi.dolthub.com']}

## Escalations
- Should every `troupe config` command check TROUPE_ACTOR before loading anything, so that a bad TROUPE_ACTOR exits 2 even when the configuration also cannot be loaded (exit 4)? (fallback), If TROUPE_ACTOR is unset and the login name cannot be determined, should the actor be {"kind": "human", "id": null}? (fallback) → On “What should `history` show for events recorded before lineage existed: (A) the known fields filled in and the rest marked unknown, with `via: null` for old set/remove events and a stable per-event `change`, (B) refuse with an error naming the database file, or (C) something else?”: The contract says every `history` event has the Lineage fields. It says nothing about events recorded before step 4, or about upgrading stored history. Treat this as out of contract: it's your choice. State which option you chose and why. Note that the contract itself doesn't change, so record your choice in your own spec or documentation, not as a contract amendment.

On “When `set` first reconciles hand edits, are those reconcile events a separate change (via "file", actor unknown) from the set's own change (via "cli")?”: Confirmed. Lineage names a file reconcile as its own producer of a `change`, separate from a command. File-originated events have actor {"kind": "unknown", "id": null}. The set's own events have via "cli" and the actor from TROUPE_ACTOR. So the reconcile events get one change id and the set's own events get a different one.

On “Does an empty TROUPE_ACTOR, an empty id such as `human:`, or any other form exit 2 with a message naming the variable, for every `troupe config` command?”: Yes. Lineage gives the only valid forms as `human:<id>` or `agent:<id>`, and anything else exits 2. A variable that is set but empty is not unset, so it exits 2. `human:` carries no id, so it is not `human:<id>` and also exits 2. This applies to every CLI command. A message that names TROUPE_ACTOR is fine.

On “Should every `troupe config` command check TROUPE_ACTOR before loading anything, so that a bad TROUPE_ACTOR exits 2 even when the configuration also cannot be loaded (exit 4)?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “If TROUPE_ACTOR is unset and the login name cannot be determined, should the actor be {"kind": "human", "id": null}?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Is `--reason` accepted only on `set`, stored exactly as given, and dropped when a `set` changes nothing?”: Confirmed. The contract defines `--reason` only as `set --reason TEXT`, and `reason` is the text given. A `set` that changes nothing emits no events, so there is nothing to carry its reason.

On “Is each `watch` reconcile its own change?”: Confirmed. `change` identifies the command, file reconcile or import that produced the event, and no two share one. Each reconcile that `watch` performs is a separate file reconcile, so each gets its own change id.

On “Is the key order `seq, op, path, old, new, actor, via, at, reason, change` acceptable for history lines?”: Yes. The contract requires each line to be an object with at least those keys. It does not fix their order, so your order is acceptable.
- Should a fresh acceptance record be made by re-running acceptance on `feat/troupe-config-lineage` with `--lenient` and merging that branch into `main` again, by creating a `docs/` folder on `main` and re-running there, or by leaving things as they are and relying on the earlier `--lenient` acceptance recorded at `8d4739f`? (fallback) → The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

## Significant PO answers
- 'I read the code (`src/troupe/history.py`, `session.py`, `reconcile.py`, `commands/set_value.py`) and the earlier contrac' → On “What should `history` show for events recorded before lineage existed: (A) the known fields filled in and the rest marked unknown, with `via: null` for old set/remove events and a stable per-event
- 'The accept command did not pass this time. It reported two blocking items:\n\n1. **Wrong branch:** acceptance has to run o' → The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

## Owner gates
- accept: Approved. The spec agrees with the Lineage section and the step 4 brief. Every event carries actor, via, at, reason and change. TROUPE_ACTOR accepts only human:<id> or agent:<id>, and anything else ex
- accept: Approved. The approach agrees with the Lineage section and the step 4 brief. Every event recorded from now on carries actor, via, at, reason and change. `at` is an RFC 3339 UTC timestamp ending in `Z`

## Possible missed approvals (PO said `continue`, the arm used approval wording)
- none

## N.a (discovery)
- stopped: discovery-stop (approval at turn 2)
- code check: ok
- escalations: none

## Arm violations (A5: the attempt failed; never a harness fault)
- none

## Egress refusals
- eventsapi.dolthub.com
