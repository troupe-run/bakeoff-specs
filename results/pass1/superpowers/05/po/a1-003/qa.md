Q1: CR-A is done and committed on `main` as `26aa408`, with no push and no PR. All 91 tests pass (79 existing plus 12 new in `tests/test_overrides.py`).

**What changed**
- **Mapping-form includes:** a mapping with a `$ref: file:...` key now works as an include. Its other keys are overrides, deep-merged into the included content: mappings merge key by key, and anything else in the override replaces the included value.
- **Shared files stay untouched:** adding a new key under content from an included file now writes it into the including file as an override. A scalar-form include is first rewritten in mapping form, exactly as in the contract's example: `coder: file:agents/coder.yaml  # c` becomes `coder:  # c` / `  $ref: file:agents/coder.yaml` / `  temperature: 0.3`. It uses the file's indentation and keeps the original quoting.
- **Existing values:** an overridden value is changed in the override; any other value is still changed in the file it comes from.
- **Lists:** appending an item, or adding a key inside a list item, still writes to the file that holds the list. An include that is itself a block list item becomes `- $ref: file:c.yml  # c`, with the new keys below it.
- **Errors:** a mapping-form include of a non-YAML file with other keys exits 4. So does a `$ref` whose value isn't a `file:` string.

**One existing behaviour changed:** `test_include_refused` used to expect a new key to be written into the included `coder.yaml`. The contract change reverses that, so the test now checks that `coder.yaml` is left alone.

**Choices where the contract was silent** (decisions 24–28 in `docs/decisions.md`):
- **Nested includes:** "the including file" means one level up. If `team.yml` includes `c.yml`, a new key under `c.yml` content goes into `team.yml`, even though `team.yml` is itself included by `troupe.yml`.
- **Section already in mapping form:** new keys go next to the overrides it already has.
- **Includes inside flow collections** become a flow mapping: `{coder: {$ref: file:c.yml, t: 1}}`.
- **A file that is only an include** (its whole content is `file:b.yml`) becomes `$ref: file:b.yml` plus the new keys.
- **`file:` string on a later line than its key:** rewriting it is refused with exit 3 rather than reflowing the lines.
- **Replacing a whole mapping-form include with `set`** still exits 3, as scalar-form includes already did.
- **Removing a key by setting its parent mapping** removes it both from the included file and from the overrides.

The code changes are in `src/troupe/config.py` (loading and merging) and `src/troupe/writer.py` (where new keys go, and the rewrite to mapping form). The README is updated too.
A1 (runner): /superpowers:finishing-a-development-branch

Q2: The work is already where it needs to be, so there's nothing left to do.

- **Tests:** all 91 pass on the committed tree.
- **Where it is:** a plain repository, not a worktree, on `main`. The working tree is clean and the latest commit is `26aa408` ("Write new keys under included sections as overrides in the including file").

The skill's usual options don't apply here:
1. **Merge back to main:** there's no feature branch, because the work was committed directly on `main`.
2. **Push and open a pull request:** your delivery instructions rule out both.
3. **Keep as-is:** this is the only option that fits. The work stays on `main` and there's no worktree or branch to clean up.
A2 (runner): A second change request has arrived while you work on the first one:

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.

---

## In-include (from step 5, change request B)

- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.
