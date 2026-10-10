Q1: Setup is done. Here's where things stand.

**Branch contract.** You started on `main`, which is the primary branch. You said no PR, but Spec Kitty won't commit planning files directly to a protected primary branch. So I did what the last three troupe missions did and created the mission on a feature branch, which gets merged into `main` at the end.
- Current branch: `feat/troupe-config-lineage`
- Planning/base branch and the branch completed work merges into: `feat/troupe-config-lineage`
- Delivery: merge into `main` locally, no push, no PR (same as `Merge feat/troupe-config-get-show`)

**Mission:** `troupe-config-lineage-01M425S3` (`kitty-specs/troupe-config-lineage-01M425S3/`)

**Relevant code:**
- `src/troupe/history.py` stores three event types (`LeafImported`, `LeafSet`, `LeafRemoved`) holding only path, old and new.
- `troupe config history` prints `seq, op, path, old, new`.
- `get`, `show`, `set` and `watch` first record any hand edits, with no record of who made them. `set` then records its own events.
- The `eventsourcing` library already stores a timestamp on every event.

### Discovery question 1 of a few: history recorded before this step

Any theatre that already has a `history.sqlite` holds events with no actor, `via` or change id. Under the contract, `via` is always `import`, `cli` or `file`. For an old `set` event, there's no way to tell whether it came from `troupe config set` (cli) or a hand edit (file).

Options:
- **(A) Recommended:** report what is known and mark the rest as unknown.
  - Actor is `{"kind":"unknown","id":null}`.
  - `at` comes from the time already stored on the event.
  - `reason` is `null`.
  - `via` is `"import"` for old import events and `null` for old set/remove events. This is a small, documented exception to the three values.
  - All old import events share one `change`, because the import was one unit. Each old set/remove event gets its own `change`, so events are never wrongly grouped.
- **(B)** Same as A, but `via` is `null` for every old event, imports included.
- **(C)** Refuse to read an old history (error naming `history.sqlite`), so the user has to start a fresh one. This is safe but throws away audit history.
- **(D)** Something else.

I recommend A. It follows your rule to "say so explicitly rather than guessing" and keeps the full audit trail. The contract only allows three `via` values, so A needs your sign-off.

WAITING_FOR_DISCOVERY_INPUT
A1 (po): The contract says every `history` event has the Lineage fields. It says nothing about events recorded before step 4, or about upgrading stored history. Treat that as out of contract. It is your choice: say which option you chose and why.