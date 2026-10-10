The tasks are written and finalized: 4 work packages with 22 subtasks, committed on `feat/troupe-config-sync-files` (finalize commit `4e9d42e`, data-model fix `5102e12`). Validation passed, all 16 functional requirements are mapped, and no two WPs own the same file. Nothing is implemented yet.

| WP | Goal | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | History keeps a path→value map of what it has recorded, plus the theatre lock | T001–T004 (4) | 213 lines | – |
| WP02 | `reconcile`; `show`/`set` reconcile first, `history` never; rewrite the step‑1 tests this supersedes | T005–T010 (6) | 267 lines | WP01 |
| WP03 | `troupe config watch` (CLI, polling, unloadable handling, signals, test harness, tests) | T011–T017 (7) | 290 lines | WP02 |
| WP04 | Tests for includes, write-backs not re-detected and exactly-once recording; fix anything they expose; quickstart and all gates | T018–T022 (5) | 179 lines | WP03 |

- **Size:** about 240 lines per WP on average. Every WP is within limits (≤7 subtasks, under 700 lines) and starts with the "Do This First" profile-load section.
- **Profiles:** all four use `python-pedro` as implementer, `agent: claude`.
- **Parallelism:** none between WPs, because the dependency chain is linear. `lanes.json` puts each WP in its own lane (`lane-a` to `lane-d`), but they still run one after another. Inside WP01 the history work and the lock work are independent.
- **MVP:** WP01 + WP02 already deliver "edits made while nothing was running are picked up".

Two things in the prompts are worth knowing about:
- **Old histories:** WP01's replay tolerates step‑1 histories that record a `remove` for a path that was never recorded, as found during tasks.
- **Superseded tests:** WP02 names the two step‑1 tests that change and says exactly how. They are rewritten, not deleted.

**Branch:** planning base and merge target are both `feat/troupe-config-sync-files`, and `branch_matches_target` is true. That branch then goes into `main` by local merge. No push, no PR.

`status.events.jsonl` (modified) and `status.json` (new) are uncommitted spec-kitty bookkeeping. I've deliberately not committed `status.json`, because a project memory notes that committing it trips spec-kitty's lane guards.

**Should I use the `/spec-kitty-implement-review` skill to fully implement all WPs until completion?** It dispatches implementing and reviewing agents for each WP, handles rejections, and merges the lanes when done. `/spec-kitty.analyze` must run first, because the implement step won't start until its `analysis-report.md` exists. I'd run it as the first step if you say yes.