I've written the CR-B spec and committed it on `main` as `2d319c9`. This is the spec only; neither CR-A nor CR-B is implemented yet.

- **Feature directory:** `specs/006-set-in-include`. It's a separate directory because each specify run makes one feature. It builds on CR-A (`005`) and continues its numbering: FR-460 to FR-466, decisions D-50 to D-52.
- **Spec file:** `specs/006-set-in-include/spec.md`
- **Checklist:** every item passes on the first try, and there are no clarification questions.

**What it says:** `set --in-include PATH VALUE` writes a new key under included content by the step 1 rule. The key goes into the file holding the deepest existing setting above it, and the including file is not touched or converted. Without the flag, CR-A's override behaviour stays the default.

**Decisions you may want to check:**
- **D-50:** the flag is accepted on any `set` but only changes where new keys go. Existing values, list appends and keys inside list items land exactly where they would without it. The alternative was to make it change an overridden value in the shared file. I rejected that because the override would still win, so the visible value wouldn't change.
- **D-51:** if the section above the new key mixes keys from the shared file and from an override, the key goes into the shared file's part. If that section exists only in an override, it stays in the file holding the override, rather than creating a new section in the shared file.
- **D-52:** `--in-include` is a flag of `set` only, like `--reason`. Any other subcommand rejects it with exit 2, and so does giving it a value.

**Workflow choice:** CR-A already has a plan but no tasks yet. I'd plan CR-B next (`/speckit-plan`, with `.specify/feature.json` now pointing at 006). It's a small change on top of CR-A's design: skip the override placement when the flag is set. Then generate tasks for both and implement them together.