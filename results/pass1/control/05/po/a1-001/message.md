CR-A is implemented and committed on `main` as `5acd7df`. All 51 tests pass, including 2 new ones for this change.

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