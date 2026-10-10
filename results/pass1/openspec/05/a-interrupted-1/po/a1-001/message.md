I've read the set planner, loader, tree model and the existing specs. Before I create the change, there's one point where the contract's wording and the CR's stated purpose disagree.

**Nested includes: which "including file" gets the override?**

Take `troupe.yml` → `agents.coder: file:agents/coder.yaml`, where `coder.yaml` has `params: file:params.yaml`. Then `set agents.coder.params.seed 1` runs. The deepest existing ancestor, `params`, comes from `params.yaml`.

- **A. Literal reading:** the file that holds the reference to `params.yaml` is `coder.yaml`. So `coder.yaml` becomes `params:` / `  $ref: file:params.yaml` / `  seed: 1`. But `coder.yaml` is itself a shared, included file, so this breaks CR-A's goal: "adding a new setting under an included section must no longer modify the shared file."
- **B. Outermost reference:** keep moving up while the reference sits in an included file. The override lands in `troupe.yml` as `coder:` / `  $ref: file:agents/coder.yaml` / `  params:` / `    seed: 1`. Deep merge makes this give the same value, and no shared file changes. The list rule still holds: if a list is in the way, the key is written in the file that holds the list.

**I recommend B**, because it's the only option that meets CR-A's purpose. A follows the contract's wording more closely.

These are the other choices I'd make and record unless you say otherwise:
1. **`$ref` that isn't an include string** (for example `$ref: 5` or a typo like `flie:x.yaml`): exit 4, naming the file. I won't silently treat it as an ordinary key.
2. **Deep merge when the included content isn't a mapping** (a scalar, or an empty file): the overrides replace it. This is the contract's merge rule applied literally, so an empty shared file plus local overrides works.
3. **Key order in the merged value:** the included content's keys first, then keys that exist only in the overrides.
4. **Deleting a key** with a collection `set`: the key is removed wherever it is, from the override and/or the included file. This follows "existing settings still change where they live".
5. **Replacing a whole include** (either form) with a different value: still refused with exit 3, as now.
6. **A mapping `VALUE` with `$ref`:** it is written as given and becomes a mapping-form include, just as a `file:` string becomes an include.
7. **Converting a scalar-form include:**
   - In flow style: `{coder: file:x.yaml}` → `{coder: {$ref: file:x.yaml, temperature: 0.3}}`.
   - A list item: becomes compact `- $ref: file:x.yaml` with the overrides below it.
   - An include string not on its key's line: refused with exit 3.

Should I go with **B**, and are the other seven choices acceptable?