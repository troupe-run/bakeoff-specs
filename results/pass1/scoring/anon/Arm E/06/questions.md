## Scored run

### Question 1 (step_done, answered by po)

Arm asked: Issue #2 is fixed and committed on `main` as `1c6749d`. All 56 tests pass, including 3 new ones for aliases. I didn't push or open a PR.

**What was wrong:** On the current code, the reporter's `set coder.settings.model sonnet` was already refused (exit 3), but the message didn't mention `--expand-alias`. There were two real bugs:
- `set defaults.model …` was also refused, because the alias copies under `coder` and `reviewer` counted as other settings being changed. Changing the value at the anchor is supposed to change it everywhere.
- Replacing an anchored value such as `m: &m opus` would have dropped the `&m` and broken every alias that uses it.

**What it does now:**
- **Setting at an anchor** writes the value there and keeps `&name`. Every alias then sees the new value, and history records a change for each path that uses it.
- **Setting through an alias** (including adding a new key under one) exits 3. The message names the alias and suggests `--expand-alias`. The file isn't touched.
- **`set --expand-alias PATH VALUE`** replaces only that alias with a block-style copy, then sets the value in the copy. For the issue's example the file ends up as:
  ```yaml
  coder:
    settings:  # expanded from *d by troupe
      model: sonnet
  reviewer:
    settings: *d
  ```
  `defaults` and `reviewer` are unchanged.
- **Any path containing `<<`** exits 3, since merge keys are never written.

**Choices the contract didn't cover** (written up in `DECISIONS.md`):
- `<<` is read as an ordinary key, not merged. The config is read with the YAML 1.2 rules, which don't have merge keys, so `get coder.model` won't find values pulled in by `<<: *d`. Say if you want merging supported.
- Aliases nested inside the copied value are expanded in the copy too. Only the outer alias gets the comment.
- An alias inside a flow collection like `{x: *m}` can't be expanded (exit 3), because a block-style copy and a trailing comment don't fit there.
- For an alias that is a list item, the comment goes on the dash line and the copy goes below it.
- A comment the user already had after the alias stays, after troupe's comment.

The README documents the new behaviour and the `--expand-alias` flag. The code changes are in `yamldoc.py`, `editor.py` and `cli.py`.

Reply: 
