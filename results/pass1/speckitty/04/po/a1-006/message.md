The tasks phase is done. The plan is split into five work packages, finalized and committed on `feat/troupe-config-lineage`. That branch is also the planning base and the merge target, and it gets merged into `main` at the end. Nothing has been pushed, and no code has changed yet.

| WP | What it does | Subtasks | Prompt lines | Depends on |
|---|---|---|---|---|
| WP01 | `src/troupe/lineage.py`: actor rules, login fallback, `at` format, change ids, one lineage per producer | 5 | 232 | — |
| WP02 | A real old-history database recorded by the step-3 code (`a589041`), with its regeneration script and an independent expected output | 3 | 153 | — |
| WP03 | Recording: new event fields, old events upgraded on read, store saves take a lineage, import/reconcile/`set` lineages, `TROUPE_ACTOR` checked before locating, `set --reason` | 7 | 220 | WP01, WP02 |
| WP04 | `history` prints the ten keys in contract order; existing tests adapted without weakening them | 3 | 143 | WP03 |
| WP05 | End-to-end acceptance tests for every scenario and edge case, the quickstart, a requirement-to-test table, and all four quality gates | 5 | 146 | WP04 |

- **Size:** prompts are 143–232 lines (about 180 on average), so none is over 10 subtasks or 700 lines, and every one starts with the "Do This First" profile step.
- **Order:** WP01 and WP02 can run in parallel; after that the work is sequential.
- **Why recording and output are separate:** WP03 records lineage but leaves the `history` output unchanged, so the existing tests stay green. WP04 then changes the output and updates those tests.
- **Requirement mapping:** all 14 functional requirements are mapped to work packages, and the dependency and ownership checks pass.
- **File overlap:** no two work packages own the same file, with one deliberate exception. WP03 changes only the function signature in `commands/history.py`, a file WP04 owns, and the WP03 prompt says it must record this.
- **Agent profiles:** all five use `python-pedro` as implementer, with agent `claude`.
- **MVP:** WP01 to WP04 make lineage recorded and readable; WP05 completes the proof.

The commits are `f77b9e9` (requirement mapping) and `403bdfa` (tasks). The generated `status.json` and `status.events.jsonl` are not committed.

Should I use the `/spec-kitty-implement-review` skill to implement all five work packages through to completion? It dispatches implementing and reviewing agents, handles rejections, and merges the lanes. `/spec-kitty.analyze` has to run first, because the implement step won't start until its `analysis-report.md` exists; I'd run it as part of a yes. Afterwards I'd merge `feat/troupe-config-lineage` into `main` locally, with no push and no PR.