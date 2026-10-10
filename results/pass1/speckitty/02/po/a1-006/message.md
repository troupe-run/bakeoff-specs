Step 2 is done and committed on `main` (head `3aed8a0`, 23 commits on top of `bfcf6c7`). Nothing pushed, no PR. All four gates passed on the final code: 1275 tests, `mypy --strict`, ruff check and ruff format. That run was on `8e63090`; the code on `main` is identical, and the later commits only touch planning and status files.

**What it does now:**
- **`troupe config watch --theatre <dir>`** prints `watching <dir>` once it can see changes. It records any edit to the config file or an included file within 2 s, and follows includes added or removed by hand. If an edit breaks the configuration, it reports the file on stderr and keeps going. It exits 0 on SIGINT/SIGTERM.
- **`show` and `set`** record edits made while nothing was running before doing their own work. **`history`** never does.
- **Formatting-only or comment-only edits** record nothing.
- **A `set` while `watch` runs** records only its own events. That works because every command takes one shared lock on the `.troupe` directory, which also means each hand edit is recorded exactly once.

**Review:** each work package was reviewed independently. Only WP04 was sent back once, for a real gap: removing the lock left the whole suite green. It now has a test that fails when the lock is missing, both when it's removed from commands and when `flock` is disabled.

**Not covered by a test:** "a reconcile interrupted by a signal is all-or-nothing" relies on the history's single atomic save and isn't tested from outside. This is recorded in the acceptance matrix.

**Things that went off the standard path:**
- **`spec-kitty merge` failed at the last step, as it did in step 1.** I brought the code across in one commit (`8e63090`) after confirming it was identical to the reviewed code, and wrote it up as R‑11 in `research.md`.
- **I committed an empty `status.json` by mistake (`56a1700`).** `3aed8a0` fixes it with the full status history (all four WPs done), in the same shape as step 1's.
- **I used `spec-kitty accept --lenient`.** That turns the "no `docs/` directory" check into a warning; the project has no `docs/` and the charter doesn't ask for one.
- **I caused one approval block myself.** My analysis report wrote "test #13", which spec-kitty read as a GitHub issue reference; re-recording the report as "test 13" fixed it.
- **`quickstart.md` is rewritten to be portable** (`mktemp`, `perl -pi`, `kill -INT $!`), and I ran it end to end.
- **The helper scripts in `~/troupe-orch`** were hard-wired to the step‑1 mission. They now default to this mission and can be pointed at another one with environment variables.

**Left in place on purpose:** the lane worktrees and branches (`.worktrees/troupe-config-sync-files-01M3ZT6R-*`, `kitty/mission-troupe-config-sync-files-01M3ZT6R*`). I kept them in case the merge needed recovering. They can go whenever you like.

I haven't run the post-merge mission review or the retrospective; say if you want either.