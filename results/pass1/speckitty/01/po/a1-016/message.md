All 8 WPs are now recorded as done, and `main` is at `b5c81f9`.

**Decision (recorded as R-20 in `research.md`):** I marked WP08 as done with an explicit override reason, and I'm not retrying `spec-kitty merge`. This was the safest option for these reasons:
- **The record is true:** every WP08 file on `main` is byte-identical to the reviewed, approved version, so `done` is accurate and `approved` was not.
- **A retry can only fail:** the merge would hit the same planning-file conflict and trigger more automatic status reverts.
- **Nothing else changes:** the status change touches only Spec Kitty's records, not code or user data, and it doesn't conflict with the contract.

Before recording it, I confirmed that all seven WP08 files on `main` are identical to the approved lane's, and that `main`'s code matches the mission branch exactly.

**What changed:**
- **WP08 status:** moved from `approved` to `done`, with the reason saved in Spec Kitty's event history. I ran this from `feat/troupe-config-load-show-set` because Spec Kitty refuses status changes on `main`.
- **`main`:** fast-forwarded to `b5c81f9`, which only adds the R-20 note. Code and tests are byte-identical to the version that passed all four quality gates (`5426abb`).

The checkout is back on `main`, the working tree is clean, and nothing was pushed. The five follow-up beads issues from earlier are still open.