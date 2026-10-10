Both change requests are committed on `main` (merge commit `ded0223`). Nothing was pushed and no pull request was opened.

**What changed for users**
- **Includes can be written as a mapping.** A mapping with a `$ref` key is an include; its other keys are overrides, deep-merged over the included file. `get`, `show`, `show --sources` and history all read the merged values.
- **CR-A:** a new setting under a shared section becomes an override in the including file, and the shared file is untouched. A plain `file:` include is first converted to mapping form, keeping its end-of-line comment. Existing values still change where they live. List items stay in the file that holds the list.
- **CR-B:** `set --in-include PATH VALUE` writes a new key into the included file instead (the step-1 rule).
- **Refusals:**
  - exit 4: a `$ref` that isn't an include string, and overrides on a non-YAML include;
  - exit 3: a path containing `$ref`, replacing a whole include, replacing a mapping that is partly overridden, and converting an include whose `file:` string spans several lines.

**Verification**
- All four gates pass on `main`'s code: 1848 tests passed, mypy reports no issues, and ruff check and ruff format are clean.
- A CLI run on `main` gave the contract example byte for byte and left the shared file unchanged.
- The merged code is identical to the code that was reviewed.
- All 13 functional requirements are recorded as passing in the acceptance matrix, each with the tests that prove it.

**How it went**
- Five work packages, each reviewed independently.
- WP04 was rejected once for a real bug: `--in-include` was refused whenever the include already had override-only keys. The fix was approved on the second pass.
- A further gap with chained includes, found in that re-review, was fixed in WP05.

**Two places where I followed the last mission's precedent**
- **Acceptance ran with `--lenient`.** The only check it relaxed is the `docs/` folder convention; this repo has never had a `docs/` folder.
- **I re-recorded the analysis report twice.** The implement and accept gates saw my later spec edits as making it stale. Its findings never included anything critical or high.

**Left for later**
- **Bead `bakeoff-specs-speckitty-c22` (P3).** The pre-write safety check doesn't confirm which file a new key lands in. Today that file is decided correctly earlier, by the code that chooses where a `set` writes, so nothing goes wrong through the CLI. The check could still be stricter.
- **The mission's coordination worktree** at `.worktrees/troupe-config-include-overrides-01M46FY4-coord` was left in place. Spec-kitty couldn't delete its branch while that worktree had it checked out. Removing it is optional cleanup.
- **The suggested follow-up** is `/spec-kitty-mission-review` to audit the merged mission.