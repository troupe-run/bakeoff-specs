Q1: I've fixed troupe-run/bakeoff-specs-speckit-pass1#2 and committed it to `main` as `8ec062d`. Nothing was pushed and no PR was opened.

Slug: `yaml-alias-set` (auto-generated)

**Assessment** (`.specify/bugs/yaml-alias-set/assessment.md`): valid, high severity. I reproduced it: `set coder.settings.model sonnet` exited 0 and rewrote the value under `defaults: &d`, which changed `defaults` and `reviewer` too. Adding a new key below the alias did the same. The cause is that the YAML library treats `*d` and `&d` as the same node, so troupe couldn't tell "reached through an alias" from "reached through the anchor". I also found that replacing any anchored value deleted the `&name`. That made the write fail its own check, so "change it at the anchor" never worked either.

**What changed now:**
- **Through an alias:** setting a path that goes through an alias is refused with exit 3, and the error mentions `--expand-alias`. Nothing is written.
- **At the anchor:** setting a value at the anchor keeps `&d` and changes every alias, so `set defaults.model sonnet` works as the issue expects.
- **`set --expand-alias PATH VALUE`:** replaces that one alias with a block-style copy, then sets the value in the copy. For the issue's example, other aliases still point to the anchor and history records only the one path that changed:
  ```yaml
  coder:
    settings:  # expanded from *d by troupe
      model: sonnet
  reviewer:
    settings: *d
  ```
- **Replacing the alias itself** (e.g. `set coder.settings none`) changes only that alias. The contract doesn't settle this case; I logged it as an open question in the assessment.
- **Merge keys:** any `set` whose path contains a `<<` segment is refused, so a merge key is never written.

**Choices the contract didn't cover:**
- `--expand-alias` refuses (exit 3) when the alias is inside a flow collection like `{settings: *d}`, because a block-style copy can't go there.
- It also refuses if, after expanding, the value would land in a different file.
- If the alias line already has a comment, the expansion comment goes in front of it: `k:  # expanded from *d by troupe  # mine`.

**Tests:** the full suite passes on the committed code (795 passed, 1 skipped), and ruff and mypy are clean. There are 13 new end-to-end tests in `tests/e2e/test_set_alias.py`; 12 of them fail on the old code. I also gave the stand-in planner in `tests/unit/test_verify.py` the new keyword, the same change the previous step made for `--in-include`. The README documents the flag, and the fix report is in `.specify/bugs/yaml-alias-set/fix.md`.

**Not fixed:** troupe still reads `<<` as an ordinary key instead of merging it. A self-referencing anchor (`a: &a [*a]`) would still hang the loader, which was already true before this change.

Next step: `/speckit-bug-test slug=yaml-alias-set`.
A1 (po): /speckit-bug-test slug=yaml-alias-set