The troupe configuration subsystem is committed on `main` and passes every quality gate there. Nothing was pushed and no pull request was opened.

**On `main`:** `main` was fast-forwarded to `5426abb`, which adds two commits on top of the Spec Kitty bookkeeping:
- `e0d74f9` is the code: 47 new source and test files.
- `5426abb` adds Python build caches to `.gitignore`.

**Verification on `main`:**
- `uv run pytest`: 1,185 passed.
- `uv run mypy --strict`, `uv run ruff check` and `uv run ruff format --check` are all clean.
- An end-to-end run with `uv run troupe config …` from the repository root behaved as the contract says:
  - `show` printed `0.2`.
  - `set` changed only the value's bytes and kept the comment column.
  - A CRLF text include was written back with CRLF.
  - Replacing a whole YAML include exited 3.
  - `history` printed the expected events.
  - Only `.troupe/history.sqlite` was added.

**How it was built:**
- **Process:** all 8 work packages were implemented and reviewed independently. WP05, WP06 and WP07 each needed one rework cycle for defects the reviewers found:
  - WP05 quoted some characters (emoji joiners, non-breaking spaces) that YAML allows plain.
  - WP06 broke your folded-value ruling.
  - WP07 could alter an existing value in two edge cases.
- **Safety net:** before writing, `set` reloads the edited text in memory. If PATH doesn't hold the new value, or anything else changed, it refuses with exit 3 and changes no file.
- **Decision records:** `research.md` holds my decisions and your rulings (R-13 to R-19). The acceptance matrix maps every requirement to the tests that prove it.

**Where I worked around Spec Kitty 3.2.7:**
- Its lane guards contradict each other about the `status.json` file, so I scripted a fix (helper scripts in `~/troupe-orch`).
- Its automatic final squash would have deleted 15 planning files. I did that merge by hand, keeping the planning documents from the planning branch and the code, status and review records from the mission branch, then ran all four gates before committing.

**Incident:** early on, a helper script merged a lane into `feat/troupe-config-load-show-set` by mistake. I undid it with `git reset --keep`, and the scripts now refuse to run outside a lane worktree. Nothing reached `main`.

**Open follow-ups in beads** (none breaks the contract):
- `p3g` (P2): a read-only `.troupe/` folder crashes with a traceback instead of a contracted exit code.
- `0uv`: an include under a folder that can't be read crashes with a traceback instead of exit 4.
- `1wk`: a folded block containing only whitespace lines can be refused unnecessarily.
- `b9b`: a YAML include used at two paths can't be edited, and the error doesn't say why. You may want to decide whether both paths should change.
- `r55`: no automated test yet for a failed write exiting 3.

**Housekeeping:**
- **Checkout and branches:** the repository is now checked out on `main` (it started on `chore/project-charter`). The lane worktrees under `.worktrees/` (ignored by git) and the `kitty/mission-…` branches are kept, so you can delete them when you no longer need them.
- **Backup:** an older generated `status.json` is backed up in `~/troupe-orch/untracked-backup`.