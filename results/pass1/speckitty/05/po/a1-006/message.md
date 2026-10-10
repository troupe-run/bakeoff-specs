I've read the loader, the tree model, path walking, placement, the write-back verifier, reconcile and the CLI. The code already has a single place that decides where a `set` writes: `writeback/placement.py`, whose docstring says the new-key rule "is expected to change at step 5". So this step fits the existing structure. Here's what I propose.

## Engineering Alignment (for your approval)

**1. Loading.** The loader treats a mapping with a `$ref` key as an include.
- **No other keys:** it loads exactly like the scalar form. The include remembers it was written as a mapping, so later overrides are added to that mapping instead of converting it again.
- **With other keys:** the include's target must be a YAML file whose content is a mapping, otherwise the load exits 4 (D-1, D-7, plus the non-YAML case from the contract).
  - The result is a *merged mapping*: a read-only combined view that keeps both sides, the included mapping and the override mapping.
  - Nested mappings merge the same way; anything else in the override replaces the included value.
  - Keys appear included-first, then override-only keys.
- **Why this shape:** the merged mapping behaves like an ordinary mapping to the rest of the code. So `get`, `show`, `show --sources` (every scalar keeps its own file), history and reconcile need almost no change. Reconcile also watches every file read on both sides.

**2. Where a `set` writes.** This stays decided in `placement.py`, the one place that already decides it.
- **Existing scalar:** written in the file that holds it. That's the override when one exists, so this needs no change.
- **List append:** written in the list's file.
- **New key (CR-A):** find the include reference nearest the key's deepest existing ancestor.
  - If a list lies between that reference and the ancestor, the key is inside a list item, so it goes to the file holding the list (step-1 rule).
  - Otherwise it's an override at that reference. If part of the path already exists as an override, the key is added there. If the include is still in scalar form, it is converted first (block, flow or list item; D-2…D-5).
- **`--in-include` (CR-B):** uses the step-1 rule, preferring the included side of a merged mapping.
- **Refusals:** a `$ref` segment in PATH exits 3 (D-6), and replacing a whole include of either form exits 3, as before.

**3. Safety net.** The existing check that re-loads the result in memory before writing stays in place, so a write that doesn't read back exactly as intended is refused with exit 3. It gets one allowance: along the path being set, a scalar-form include may turn into mapping form, as long as it still points at the same target.

**4. CLI.** `set` gains `--in-include`; other subcommands reject it with exit 2 (argparse already does this). History and lineage don't change.

**5. Three behaviours the code exposed that the spec doesn't cover.** All are out of contract, so they're my choices; I'll add them to the spec with reasons:
- **D-7 correction:** an empty included file stays an empty mapping, as in step 1. My spec wrongly said it exits 4, and that would break the existing step-1 test `test_new_key_into_empty_included_file`.
- **D-10:** replacing a whole mapping that is partly overridden (`set coder.tools '{x: 1}'` when `tools` comes from both files) exits 3 with no file changed. There's no way to write it without either editing the shared file or the old included keys coming back through the merge.
- **D-11:** converting an include whose `file:` string spans several lines (a block scalar or a wrapped quoted string) exits 3. It can't be moved verbatim to a `$ref:` line.

**6. Tests.** All tests run against real files, the real CLI and the real event store, with every file's bytes snapshotted. Two step-1 tests change their expected output because the contract changed: `test_new_key_goes_into_included_files_mapping` and `test_new_key_into_empty_included_file`. Under the new rule those keys become overrides. No new dependencies.

Do you approve this alignment, including the three spec additions?

WAITING_FOR_PLANNING_INPUT