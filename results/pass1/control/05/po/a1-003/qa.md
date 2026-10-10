Q1: CR-A is implemented and committed on `main` as `5acd7df`. All 51 tests pass, including 2 new ones for this change.

**What changed**
- **Mapping-form includes** (`yamldoc.py`): a mapping with a `$ref: file:…` key is now an include. Its other keys are overrides, deep-merged into the included content: mappings merge, scalars and lists replace. Overrides on a non-YAML include fail to load with exit 4. A `$ref` with no other keys pointing at a text file still works as a text include.
- **New keys under included content** (`editor.py`) are written as an override in the including file, and the shared file is left alone:
  - `coder: file:agents/coder.yaml  # c` becomes `coder:  # c` / `  $ref: file:agents/coder.yaml` / `  temperature: 0.3`, exactly as in the contract. Indentation follows the file's own step.
  - The same conversion also works for flow mappings (`{coder: {$ref: …, t: 1}}`) and list items (`- $ref: … # ic` / `  t: 2`).
  - If a key on the path already has an override mapping, the new key goes inside it. For example, `limits.time` lands under the existing `limits:` override.
- **Lists and existing values**: appending a list item, or adding a key inside a list item, still writes the file that holds the list. Setting a value that is overridden changes the override; a value that isn't is changed in the file it comes from.
- **Removals** (e.g. from `set a.sub '{…}'`) now handle mappings whose entries come from two files, including the `$ref` entry in flow form.
- I added a paragraph on mapping-form includes to the README.

**Choices you may want to check**
- **Nested includes:** the override goes next to the *nearest* include reference, as the contract says ("the file that contains the include reference"). So if `troupe.yml` includes `outer.yaml` and `outer.yaml` includes `coder.yaml`, a new key under the inner include is written into `outer.yaml`. That file is itself shared. If you'd rather always write to the top-level file, it's a small change.
- **Files included in several places:** changing an existing value in such a file is still refused with exit 3 ("write-back would disturb …"). The change would alter every place that includes the file, and this check was already there before CR-A. New keys aren't affected, since they now become overrides.
A1 (runner): A second change request has arrived while you work on the first one:

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.

---

## In-include (from step 5, change request B)

- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.


Q2: CR-B is implemented and committed on `main` as `3f073d6`. All 52 tests pass, including a new one for the flag.

`troupe config set --in-include PATH VALUE` writes a new key into the included file itself, following the step 1 rule, instead of adding it as an override:
- **Scalar-form include** (`coder: file:agents/coder.yaml`): the key goes into `coder.yaml`, and the reference in the including file is left unchanged.
- **Mapping-form include, or a mapping where an override merges into included content**: the key goes into the included file's mapping, not next to `$ref`. To make that possible, each merged node now keeps a link to the included mapping underneath it.
- **Existing values**: the flag makes no difference. An overridden value still changes the override, and one that isn't is changed in the file it comes from.

The README's usage line and include notes now mention the flag.

**Decision for you:** if the same file is included in two places in one theatre, `--in-include` is refused with exit 3 ("write-back would disturb …"), because the new key would show up under both. That's the same safety check that already blocks changing a shared file's existing values. I kept it, since the contract says to use the step 1 rule. If you'd rather `--in-include` skip the check, since writing to the shared file is then deliberate, it's a small change.
A2 (fallback): The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.