Step 4 lineage is built and committed on `main`, and all 25 tasks are marked done. Nothing was pushed. No extension hooks are registered, so none ran.

**Final checks:** `uv run pytest` shows 689 passed and 1 skipped. `mypy --strict` reports no issues, and `ruff check` and `ruff format --check` are clean. Before any changes the suite had 544 passing tests and was clean.

**What changed:**
- **History output:** every `config history` line now ends with the five lineage fields: `actor`, `via`, `at`, `reason` and `change`.
- **Storage:** lineage is saved as part of each event, so it survives restarts and can't change after it's recorded. The new code is mostly in `src/troupe/config/lineage.py`.
- **Grouping:**
  - Each unit gets one change id and one UTC timestamp, shared by all its events. A unit is an import, a pick-up of hand edits, or a `set`'s own change.
  - A `set` that first picks up a hand edit records two units.
  - The hand edit is recorded with actor `unknown` and `via` `file`, never as the person or agent running the command.
- **`TROUPE_ACTOR`:** every command checks it before touching the configuration. An invalid value, including empty or `human:` with no id, exits 2 and records nothing.
- **`set --reason TEXT`:** the text is kept exactly, including `""`, and only on the `set`'s own events. `--reason` on any other command exits 2.
- **Tests:** the existing test helper `theatre.history()` still returns only the original five fields, so the step 1–3 tests are unchanged. A new `theatre.events()` returns full lines.
- **Test environment:** tests now ignore any `TROUPE_ACTOR` set in your shell and run with a fixed login name.

**Checks on the tests themselves:** for each story I broke the behaviour on purpose and confirmed a test failed, then restored it. The breaks included:
- checking the actor only in `set`;
- crediting hand edits to the command's actor;
- treating an empty `TROUPE_ACTOR` as unset;
- one shared change id per process, and a new id per event;
- local time instead of UTC;
- turning `""` into `null`;
- putting the reason on hand-edit events;
- printing the current actor instead of the stored one.

I also ran the quickstart walk-through by hand, and every output matched.

**Things to know:**
- **The 1 skipped test** checks the case where no login name can be found end to end. That can only happen on an account with no system user entry, so it skips here. A unit test covers that case instead.
- **Event stores from before step 4 aren't migrated.** Their events have no lineage. Running this build against one is untested and will probably fail when it reads the old events. That's intentional, per the spec's out-of-scope decision.
- **Commits:** foundation and US1 went in as one commit (`2d3ef22`) rather than the two the task list planned, because they share a function signature change in `cli.py`. The other commits are `d4c0a20`, `c13700c`, `5eabdfe` and `3344886`.
- **Docs:** the README now documents `TROUPE_ACTOR`, `--reason` and the new fields. The step 1 and step 2 docs carry notes saying where step 4 supersedes them.