Recorded: **nearest including file** (DM `01M43VTY80AXSM5W7X96WAHM8Z`). That was the only question I needed you to decide. Here is the Intent Summary for you to confirm before I write the spec.

## Intent Summary

**Who and when.** A theatre owner, or a harness acting for them, runs `troupe config set PATH VALUE` on a theatre whose config includes YAML files that are shared with other projects.

**Main scenario.** `troupe.yml` contains `coder: file:agents/coder.yaml  # c`, and `coder.yaml` has no `temperature` key. Running `set coder.temperature 0.3` leaves `agents/coder.yaml` byte-identical. `troupe.yml` becomes:

```yaml
coder:  # c
  $ref: file:agents/coder.yaml
  temperature: 0.3
```

`get coder.temperature` then prints `0.3`. History records exactly one `set` event for `coder.temperature`.

**Rules that must always hold**
- A new key whose deepest existing ancestor comes from an included file never modifies that included file. The key goes in as an override in the nearest including file (your decision above).
- Existing values are still changed where they live. An overridden value changes in its override. A value that is not overridden changes in the included file.
- List appends, and new keys inside list items, are written in the file that holds the list.
- All other bytes stay as they are (TROUPE-001). Writes are byte-surgical, as in step 1.

**Mapping form.** A mapping with `$ref: file:…` loads as the included content deep-merged with its other keys. Mappings merge recursively; scalars and lists in the override replace. `$ref` itself is never shown as a key. A mapping-form include of a non-YAML file that has sibling keys exits 4.

**Choices I'll make where the contract is silent** (each will be recorded in the spec with its reason):
1. **Ancestor already in an override.** If the deepest ancestor is already an override mapping, including one merged with included content, the new key is added to that override.
2. **`$ref` that isn't an include.** A `$ref` key whose value is not an include string is an ordinary key, not an include. This way existing configs that have a `$ref` key don't break.
3. **Overrides on a non-mapping target.** A mapping-form YAML include whose target is not a mapping (a list, scalar or empty file) exits 4 if it has override keys.
4. **Mismatched override types.** When an override and the included value aren't both mappings, the override replaces the included value.
5. **Flow-style includes.** An include inside a flow collection is converted to flow mapping form, `{$ref: file:…, temperature: 0.3}`. This matches step 1's flow-parent rule.
6. **Replacing whole values.**
   - Replacing a whole include (`set coder X`) still exits 3.
   - Replacing a mapping that is partly in the override and partly in the included file exits 3, because no single file can hold the result.
7. **`--sources`.** An overridden scalar's `# from` comment names the including file.
8. **History, reconcile and watch.** Paths and leaves refer to the merged configuration. Converting an include to mapping form records only the new key's event. A hand edit that converts an include to mapping form without adding keys records nothing.

**Out of scope:** removing keys through overrides, and overrides that address list items.

Is this right? Reply "confirmed" or send corrections.

WAITING_FOR_DISCOVERY_INPUT