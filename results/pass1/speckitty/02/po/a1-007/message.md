`spec-kitty agent mission accept` did **not** pass. (The bare command errors with `--mission <slug> is required`, so I ran it with `--mission troupe-config-sync-files-01M3ZT6R`.) All four WPs show `done`, but it reports two blockers:

1. **Wrong branch.** Acceptance must run on `feat/troupe-config-sync-files` or `kitty/mission-troupe-config-sync-files-01M3ZT6R`, not `main`. The checkout is on `main` because I fast-forwarded it for delivery. `feat/troupe-config-sync-files` points at the same commit (`3aed8a0`).
2. **No `docs/` directory.** Spec-kitty's path convention expects one. This is the same check I downgraded to a warning with `--lenient` for the earlier acceptance (`81555f2`); the project has no `docs/` and the charter doesn't ask for one.

The run wrote nothing: `git status` is clean and `main` is still at `3aed8a0`.

To make it pass, I'd run it on `feat/troupe-config-sync-files` with `--lenient`. That adds acceptance-record commits to that branch, and I'd then fast-forward `main` to them, since `main` is what gets tested. The other way is to create a real `docs/` (git won't track an empty directory, so it would need content), but I don't recommend it. Should I go ahead with the `feat` + `--lenient` run?