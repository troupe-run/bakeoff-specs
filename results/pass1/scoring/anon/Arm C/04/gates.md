### Gate 2 (attempt 1, approval)

Arm asked: The spec for step 4 (lineage) is written and committed on `feat/troupe-config-lineage`, and the next phase is `/method-command`. No code has changed yet, so nothing is on `main` so far. The plan is to merge this branch into `main` at the end, as the last mission did. Nothing has been pushed.

**Your three open choices, as I decided them.** Each is recorded in the spec and as a decision record, not as a contract change:
- **Events recorded before step 4:** `history` shows what is truly known and marks the rest unknown:
  - `at` is the time already stored with each event.
  - The actor is `{"kind":"unknown","id":null}` and `reason` is `null`.
  - `via` is `"import"` for old imports and `null` for old `set`/`remove` events, because a CLI `set` and a file reconcile can't be told apart.
  - `change` is a fixed id unique to each old event.
  
  Stored events are never rewritten. I chose this over refusing to read the history because refusing would hide a user's existing audit trail. Every event recorded from step 4 on has a `via` the contract allows.
- **When `TROUPE_ACTOR` is checked:** after argument parsing, before the theatre is located or loaded. A bad value exits 2 even if the config also can't be loaded, and the command records nothing, not even an import or reconcile.
- **Login name not found:** the actor is `{"kind":"human","id":null}` and the command still runs. The unknown id is stated rather than invented.

Your confirmed answers are in the spec as rules:
- The reconcile a command runs first is a separate change from the command's own events, and so is any import it triggers.
- Each `watch` reconcile is its own change.
- `--reason` exists only on `set`. It is stored as given, and dropped when the `set` records nothing.
- Every `troupe config` command checks `TROUPE_ACTOR`.
- The history line keys are in the order you approved.

The spec has 14 functional requirements, 5 non-functional requirements and 5 constraints. The quality checklist passes, `decision verify` is clean, and there are no open questions left in it.

**Three choices I made on my own while writing the spec.** They're listed as edge cases and assumptions; tell me if you want any changed:
- `--reason ""` is stored as `""`, not `null`.
- All events in one change share the same `at`.
- A `TROUPE_ACTOR` id is everything after the first `:`, so `human:alice:x` is accepted.

**Repository state:**
- **Commits:** the spec and checklist (`0d0105e`), then the decision records (`af3c6d6`, `a252fbb`).
- **Not committed:** `status.events.jsonl` changes after every method command. There is also an empty `plan.md` template, created when I ran the plan setup command to check readiness. I left both for the plan phase.

Files are in `spec/troupe-config-lineage-01M436R0/`:
- `spec.md`
- `checklists/requirements.md`

PO verdict: Approved. The spec agrees with the Lineage section and the step 4 brief. Every event carries actor, via, at, reason and change. TROUPE_ACTOR accepts only human:<id> or agent:<id>, and anything else exits 2. Imports and file-originated events have actor unknown/null. The reconcile a command runs first, each watch reconcile, and each import get their own change id. Lineage is persisted. The three things you chose yourself are acceptable and need no change. `--reason ""` stored as "" matches "the text given". A shared `at` within one change and an id taken as everything after the first `:` don't contradict the contract. Your choices for pre-step-4 events, the TROUPE_ACTOR check order and a missing login name are out of contract and recorded in your spec, as the brief requires.

Owner action: accept; approved: True

Final reply: Approved. The spec agrees with the Lineage section and the step 4 brief. Every event carries actor, via, at, reason and change. TROUPE_ACTOR accepts only human:<id> or agent:<id>, and anything else exits 2. Imports and file-originated events have actor unknown/null. The reconcile a command runs first, each watch reconcile, and each import get their own change id. Lineage is persisted. The three things you chose yourself are acceptable and need no change. `--reason ""` stored as "" matches "the text given". A shared `at` within one change and an id taken as everything after the first `:` don't contradict the contract. Your choices for pre-step-4 events, the TROUPE_ACTOR check order and a missing login name are out of contract and recorded in your spec, as the brief requires.

### Gate 4 (attempt 1, approval)

Arm asked: I checked how the event store reads old events, and that settles the riskiest part of the design. When it loads a stored event it passes the event's stored data through a version-upgrade hook first. That data already includes the event's position and its stored time, so old events can get their lineage when read, and nothing in the database has to change. No new dependencies are needed.

Branch contract for the plan: the current branch is `feat/troupe-config-lineage`, it is also the planning base and the merge target, and it is merged into `main` at the end.

## Proposed approach — please confirm or correct

1. **Lineage is stored on each event.** Every event recorded from now on carries six new fields: actor kind, actor id, via, at, reason and change.
   - The three event types get a version number of 2.
   - Old events go through a version-1-to-2 upgrade step whenever they're read. That step sets actor unknown/null and reason `null`. It sets `via` to `"import"` or `null`, `at` to the stored time converted to UTC, and `change` to `pre-lineage-<seq>`.
   - The database is never rewritten.
2. **One module owns all lineage decisions** (`src/troupe/lineage.py`):
   - reading and checking `TROUPE_ACTOR`;
   - the login-name fallback, using Python's standard lookup: `LOGNAME`/`USER`, then the system's account list. If that finds nothing or an empty name, the id is `null`;
   - reading the clock once per change, with microsecond precision, e.g. `2026-10-04T10:18:24.017202Z`;
   - creating change ids, which are random UUIDs and can never look like a `pre-lineage-…` id.
3. **How the actor reaches the commands:**
   - `cli.main` works out the actor after parsing arguments and before locating the theatre. A bad value exits 2 with a message naming `TROUPE_ACTOR`.
   - Commands receive the actor as an argument.
   - The session gives the import and the reconcile their own lineage (actor unknown).
   - `set` builds a CLI lineage that includes its `--reason`.
   - The history store's save methods take a lineage, so every event saved in one call shares it.
4. **History output** adds `actor, via, at, reason, change` after the existing keys. The `PATH` filter is unchanged.
5. **Tests** run against the real CLI and the real event store. Old-event behaviour is tested against a small database recorded by the step-3 code at `a589041`. It is committed as a test fixture, together with the script that recreates it.
6. **Mission contracts:**
   - `contracts/history-lineage.md`: the line format, a JSON schema, and the old-event rules marked as out of contract;
   - a CLI addition covering `set --reason` and `TROUPE_ACTOR`.

If this looks right, I'll write the plan, research notes, data model, contracts and quickstart, and commit them.

WAITING_FOR_PLANNING_INPUT

PO verdict: Approved. The approach agrees with the Lineage section and the step 4 brief. Every event recorded from now on carries actor, via, at, reason and change. `at` is an RFC 3339 UTC timestamp ending in `Z`, and microsecond precision is allowed. Change ids are random UUIDs, so every event from one command shares one id and no two commands share one. Imports and reconciles get their own lineage with actor unknown/null. `set` carries its `--reason`. A bad `TROUPE_ACTOR` exits 2 with a message naming the variable. When it is unset, the actor is `human` with the login name as id. Lineage is stored with the events, so it survives restarts and `history` reports it. Upgrading old events when they are read, without rewriting the database, carries out the out-of-contract choice already recorded in your spec. The `pre-lineage-<seq>` ids are unique per event and cannot collide with the UUIDs.

Owner action: accept; approved: True

Final reply: Approved. The approach agrees with the Lineage section and the step 4 brief. Every event recorded from now on carries actor, via, at, reason and change. `at` is an RFC 3339 UTC timestamp ending in `Z`, and microsecond precision is allowed. Change ids are random UUIDs, so every event from one command shares one id and no two commands share one. Imports and reconciles get their own lineage with actor unknown/null. `set` carries its `--reason`. A bad `TROUPE_ACTOR` exits 2 with a message naming the variable. When it is unset, the actor is `human` with the login name as id. Lineage is stored with the events, so it survives restarts and `history` reports it. Upgrading old events when they are read, without rewriting the database, carries out the out-of-contract choice already recorded in your spec. The `pre-lineage-<seq>` ids are unique per event and cannot collide with the UUIDs.
