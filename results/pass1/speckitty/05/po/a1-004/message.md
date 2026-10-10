## Intent Summary: step 5 (CR-A and CR-B)

**Who and when:** a theatre owner (or a harness acting for them) runs `troupe config set PATH VALUE` on a theatre whose sections come from YAML includes that are shared with other projects.

**What happens:**

1. **Loading mapping-form includes.** A mapping whose `$ref` value is an include string is the included content deep-merged with its other keys, the overrides. Mappings merge recursively; scalars and lists in the override replace the included value. `get`, `show` and `show --sources` all see the merged value. Under `--sources`, overridden scalars are attributed to the including file. History and reconcile treat the merged leaves like any others.
2. **New key under an included section (CR-A).** The key is written as an override in the including file, meaning the file holding the include reference nearest the key's deepest existing ancestor (your answer to Question 1). A scalar-form include is first converted to mapping form, keeping its end-of-line comment on the key's line. Any missing intermediate mappings are created inside the override. The shared file's bytes don't change.
3. **`set --in-include PATH VALUE` (CR-B).** A new key goes into the included file instead (the step-1 rule, so the innermost file). When no include is involved, the result is the same as without the flag.
4. **Existing values.** An overridden value changes in its override. A value that isn't overridden changes in the file it comes from. `--in-include` has no effect on existing values.
5. **List items.** Appending a list item, or adding a key inside a list item, is written in the file that holds the list.

**Errors:**
- A mapping-form include of a non-YAML file that has sibling keys exits 4 (contract).
- A `$ref` whose value isn't an include string exits 4, naming the file and path (agent choice).
- Replacing a whole include still exits 3, as in step 1.

**Rule that must always hold:** without `--in-include`, adding a new key never changes a single byte of the included file that holds the key's ancestor. Every file changes only where the write-back rules require (step-1 byte preservation, TROUPE-001).

**Agent choices I'll record (contract is silent):**
- In mapping form, `$ref` is written first and overrides follow it.
- If the include sits under a flow-style parent, conversion is written in flow style (`{$ref: file:…, k: v}`), matching the step-1 rule for new collections under a flow parent.
- An include that is itself a list item (`- file:a.yaml`) is converted the same way, into `- $ref: file:a.yaml` with the override key on the next line at the item's indentation.

Does this match what you want? Reply yes, or tell me what to correct. Once you confirm, I'll write and commit the spec.

WAITING_FOR_DISCOVERY_INPUT