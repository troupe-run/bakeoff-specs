I checked how the event store reads old events, and that settles the riskiest part of the design. When it loads a stored event it passes the event's stored data through a version-upgrade hook first. That data already includes the event's position and its stored time, so old events can get their lineage when read, and nothing in the database has to change. No new dependencies are needed.

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