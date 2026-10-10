`spec-kitty merge` failed, as it did before delivery. The mission's code is already on `main` and the failure didn't change it.

- **What it did:** it skipped all five lanes as already merged, then hit the same squash conflict as in D-10. The mission branch doesn't carry `meta.json` and `research.md`, so they conflict. It rolled the squash back.
- **Side effect:** it also reverted WP05's `done` status. I set it back to `done` with an override reason that goes into the event log, so all 5 work packages are done again. This matches how the same retry was handled in step 2.
- **State checked afterwards:**
  - `main` and `feat/troupe-config-lineage` were unchanged.
  - No git operation was left half-finished.
  - Every worktree was clean.
- **Not retried:** another retry can only fail the same way.

I recorded this as D-12 in the mission's `research.md` (`7fe7040`). `main` gained only that commit, and the code, tests and dependency files are identical to the tested state (1652 passed, `mypy`/`ruff` clean). Nothing has been pushed, and the working tree is clean on `main`.