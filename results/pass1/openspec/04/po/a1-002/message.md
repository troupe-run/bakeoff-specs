## Implementation Complete

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