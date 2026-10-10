Planning is finished and committed on `feat/troupe-config-include-overrides`. That branch is both the planning base and the mission's merge target (`branch_matches_target: true`), and it gets merged into `main` at the end. Nothing is on `main` yet and nothing has been pushed.

**How the design works**
- **Reading:** an include written as a mapping with `$ref` loads as one combined mapping. Every reader treats it like any other mapping, so `get`, `show`, `show --sources`, history and reconcile need almost no change. Each value still knows which file it came from, so `--sources` credits overrides to the including file.
- **Writing:** where a `set` writes is still decided in one place, `writeback/placement.py`. That's where the old new-key rule is replaced by the override rule, the `--in-include` rule and the refusals.
- **Safety net:** the existing in-memory reload check before any write stays. Its only new allowance is that, along the path being set, a plain include may become mapping form if it still points at the same file.
- **Dependencies:** none added.

**Spec changes from planning:** your three approved additions are now in the spec with their reasons:
- **D-7 correction:** an empty included file stays an empty mapping, as in step 1.
- **D-10:** replacing a mapping that is partly overridden exits 3.
- **D-11:** converting an include whose `file:` string spans several lines exits 3.

The quality checklist is updated and the decision check reports nothing outstanding.

**Expected test changes:** two step-1 tests in `tests/integration/test_set_new_entries.py` will get new expected output, because Overrides replaces rule 2. All other existing suites should pass unchanged.

**Commits:** `ccd2a6b` (plan), `ef7dc7b` (spec amendment), `186a484` (design files) and `59f0c72` (decision record).

Next step is `/spec-kitty.tasks`, which splits this into work packages.

Files are in `kitty-specs/troupe-config-include-overrides-01M46FY4/`:
- plan.md
- research.md
- data-model.md
- contracts/cli.md
- quickstart.md