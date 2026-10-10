I've planned the change `config-include-overrides` in `openspec/changes/config-include-overrides/`. It passes `openspec validate --strict`. The plan is committed on `main` as `deee957`, following the repo's "Plan …" commit pattern. No project code has changed yet; the request is done only once the implementation is committed on `main`.

**Artifacts:**
- **`proposal.md`**: why shared includes must stay shared. It marks the new-key target change as **BREAKING**.
- **`specs/`** (changes to four existing specs):
  - `config-loading`: a new "Mapping-form includes and overrides" requirement covering `$ref`, the deep-merge rules, key order and the exit 4 cases.
  - `config-set`: a new "New keys under includes are written as overrides" requirement, with exact before/after file contents for each case. It also updates the rules for existing values, refusing to replace an include, setting a collection, creating new keys and appending to lists.
  - `config-show`: `--sources` names the file that holds the override.
  - `config-sync`: hand-added overrides are recorded, a conversion with no overrides records nothing, and files reached through `$ref` are watched.
- **`design.md`**: a new `overrides.py` module holds the merge rule. Merged mappings keep a record of the files they were built from, so every edit lands in a real file. One function, `new_key_target`, decides where a new key goes. Existing checks that re-read the result before writing still refuse anything wrong with exit 3.
- **`tasks.md`**: five groups. Each group brings its own tests (exact file contents through the real CLI), and README updates come before the final integration and commit steps.

**Choices I made where the contract is silent (please confirm or overrule):**
1. **Nested includes**: a new key goes into the *nearest* file holding the include reference, because that is what the contract says. For example, `agents/coder.yaml` including `limits.yaml` means the override goes into `agents/coder.yaml`. The alternative is always writing into `troupe.yml`, which is never shared; that would be a one-place change.
2. **Exit 4 for overrides on non-mapping content**: an include with overrides whose content is a list, a scalar or an empty file fails to load. The contract doesn't define merging in that case.
3. **`$ref` with a non-include value** (e.g. `$ref: hello`) stays an ordinary key.
4. **Deleting an overridden key** removes it from the override *and* from the included file, because overrides can't delete. An override mapping left empty is removed too.
5. **`set coder file:agents/coder.yaml` when overrides exist** is refused with exit 3, so overrides are never dropped silently.
6. **A list item that is an include** converts to the compact form: `- $ref: file:x.yaml` followed by the override entries.

The artifacts are ready for review. When you are ready, run `/opsx:apply`.