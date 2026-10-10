I re-ran acceptance on the branch it requires, and it passed. `main` now carries that acceptance record and the code is unchanged.

**What I did:**
- **Brought the feature branch up to date:** fast-forwarded `feat/troupe-config-lineage` to `main`, which only added the merge and retrospective commits.
- **Accepted there:** ran `spec-kitty agent mission accept --lenient` on that branch. It accepted all five work packages, which were already merged, and recorded acceptance commit `b5777a9`. `--lenient` downgraded only the missing-`docs/` check to a warning.
- **Updated `main`:** fast-forwarded it to that branch, so it gained only `kitty-specs/` bookkeeping commits: `b5777a9`, `8cba484` and `edb0ef3`. A diff of the code, tests and dependency files against the previously tested commit `3d51b78` is empty. So the earlier results still apply: 1652 tests passed, `mypy --strict` and `ruff` clean.

**Why this is the safest choice** (recorded as D-11 in the mission's `research.md`): it changes no code and no user files, and doesn't affect the contract. I ruled out three alternatives:
- creating an empty `docs/` folder, which would add structure nobody asked for;
- forcing past the check, which would hide the branch rule rather than satisfy it;
- rewriting `main`'s history, which would lose the record of what was merged.

Nothing has been pushed, and the working tree is clean on `main`.