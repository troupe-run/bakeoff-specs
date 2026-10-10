I've written the plan for step 4 as the OpenSpec change `config-lineage` in `openspec/changes/config-lineage/`. It passes `openspec validate --strict` and is committed on `main` (`21a9bf9`), not pushed. No project code has changed yet.

**Artifacts:**
- **`proposal.md`**: why lineage is needed and what changes. Every history event gains `actor`, `via`, `at`, `reason` and `change`, `set` gains `--reason TEXT`, and `TROUPE_ACTOR` decides the actor.
- **`specs/`**:
  - `config-lineage` (new): what each field means, where values come from, how events are grouped into one change, that lineage survives restarts, and how events stored before step 4 are reported.
  - `config-history` (modified): each history line carries the lineage fields.
  - `config-cli` (modified): `set PATH VALUE [--reason TEXT]`.
- **`design.md`**: one new module, `lineage.py`, holds every lineage rule. The three places that record events (import, reconcile, `set`) each get their lineage from one call, so a single save can't mix two changes. Events written before step 4 are still read without the database being rewritten.
- **`tasks.md`**: four groups, each landing its own tests. One task builds a real step-3 `events.sqlite` from commit `4ef5d76` as a test fixture.

**Choices the contract left open, for your review** (also listed at the end of `design.md`):
1. **Older event stores:** the step-3 data doesn't record whether a `set` came from the CLI or a hand edit, and `via` has no "unknown" value. I report these events with actor `unknown` and via `"file"`, the only value that fits an unknown actor, so some will be labelled `"file"` when they were really CLI sets. Their `at` is the time the event was stored. Old imports share `change` `legacy-import`, and every other old event gets its own `legacy-<n>`. If you'd rather report them another way, this is the one to change.
2. **`TROUPE_ACTOR` checks:** every subcommand rejects an invalid value with exit 2 before storing anything, not only `set`. An empty value counts as invalid, not as unset, which is the opposite of how an empty `TROUPE_THEATRE` behaves. Kinds must be lowercase, and the id is kept exactly as given, colons included.
3. **No login name:** if none can be found, the actor is `{"kind": "human", "id": null}`.
4. **Timestamps:** `at` has six fractional digits (`2026-10-04T09:15:02.481233Z`), and all events of one change share the same `at`.
5. **Change ids:** they are UUID4 strings. A `set` that first picks up hand edits makes two changes: the hand edits (`file`, unknown actor) and its own (`cli`).
6. **Reason:** `--reason` applies only to the `set`'s own events. An empty reason is stored as `""`, not `null`.
7. **Rollback:** step-3 code can't read the new events. Rolling back after step 4 means deleting `events.sqlite` and losing the history before that point. The README task notes this.

The artifacts are ready for review. When you are ready, run `/opsx:apply`.