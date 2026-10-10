I added the five tests from the convergence pass (T025–T029) and committed them on `main` as `62cb106`. Every task in CR-A's (005) and CR-B's (006) task lists is now checked off. There were no extension hooks to run, and CR-A's requirements checklist was fully checked.

**Added tests:**
- **T025:** a new key added to a one-line `{$ref: …}` mapping is appended in place: `{$ref: file:c.yaml, model: x, t: 1}`.
- **T026:** an include that is an item of a one-line list becomes `[{$ref: file:a.yaml, t: 1}]`.
- **T027:** `set` on a `{$ref: file:p.md}` text include writes `p.md` and leaves `troupe.yml` alone.
- **T028:** a multi-line string added as an override is written as a literal block (`p: |`).
- **T029:** the two refusal tests (D-44 and D-47) now also check that the error message names the path.

The implementation already handled all of these, so only tests changed. Because they passed on first run, I broke the code on purpose to check they can fail. Breaking the separator in the one-line conversion failed T026 and the existing flow-conversion test. Making new keys go into the shared file instead of the override failed T025. The code was restored after each break.

**Gates:** `uv run pytest` gives 782 passed, 1 skipped; `mypy --strict`, `ruff check` and `ruff format --check` are clean.

A second `/speckit-converge` on 005 should now come back clean; 006 had already converged. Nothing was pushed and no pull request was opened.