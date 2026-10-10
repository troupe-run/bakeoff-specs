Q1: I've written the plan for step 4 as the OpenSpec change `config-lineage` in `openspec/changes/config-lineage/`. It passes `openspec validate --strict` and is committed on `main` (`21a9bf9`), not pushed. No project code has changed yet.

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
A1 (po): /opsx:apply

Q2: ## Implementation Complete

Lineage is in: every `history` event now carries `actor`, `via`, `at`, `reason` and `change`. All 16 tasks of `config-lineage` (spec-driven) are done and committed on `main` in four commits after the plan, `afedc8a` to `0dac4a5`. Nothing was pushed and the working tree is clean.

**Checks:** `uv run pytest` passes 515 tests, and the same suite still passes with `TROUPE_ACTOR=robot:x` in the shell, so a developer's own setting can't leak into the tests. `mypy --strict`, `ruff check`, `ruff format --check` and `openspec validate config-lineage --strict` are all clean.

**What changed:**
- **`src/troupe/lineage.py`** (new) holds every lineage rule: reading `TROUPE_ACTOR`, falling back to the login name, the UTC timestamp format and the change ids. Each import, reconcile or `set` creates one lineage and saves all its events with it, so events from one command can't end up with different change ids.
- **`store.py`**: the event types now carry lineage and keep their old names, so databases written before step 4 still load. Their events are filled in when read and nothing on disk is rewritten.
- **`cli.py` / `commands.py` / `sync.py`**: `set --reason TEXT` is recorded with the change. Every command rejects an invalid `TROUPE_ACTOR` with exit 2 before storing anything. `history` prints the five new fields.
- **Tests**: every spec scenario runs through the real CLI, including a live `watch` process and separate `uv run` processes. To check that older stores still load, the tests use a real `events.sqlite` written by the step-3 code (commit `4ef5d76`); how it was made is in `tests/fixtures/step3/README.md`. I also broke the code on purpose in a few places (accepting an empty id, local-time timestamps, labelling hand edits as `cli`, removing the old-event conversion) and the tests caught each one.
- **README**: a new Lineage section, `set --reason` in the commands table, decisions 19–25, and a note on rolling back. I ran every README command as written.

**One change from the plan:** old events from before step 4 now get change ids numbered by the `seq` that `history` shows (`legacy-2` for seq 2), not by the internal event version, which would have shown `legacy-3` for seq 2. I updated `design.md` and `tasks.md` to match.

The decisions listed for your review at the end of `design.md` still stand. The one most worth checking is that old `set` events are labelled `via: "file"`, because step 3 never recorded whether they came from the command line or a hand edit.

All tasks are complete. You can archive this change with `/opsx:archive`.
A2 (po): /opsx:archive