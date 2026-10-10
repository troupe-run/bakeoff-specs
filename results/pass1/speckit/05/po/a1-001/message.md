I've written the step 5 spec and committed it on `main` as `0aaad5a`. Nothing is implemented yet: this is the spec only, so CR-A is not delivered until the plan, tasks and implementation are done.

- **Feature directory:** `specs/005-include-overrides`
- **Spec file:** `specs/005-include-overrides/spec.md`
- **Checklist:** `specs/005-include-overrides/checklists/requirements.md`. Every item passes; one wording fix was needed so the contract's example comes out as exactly `coder:  # c`.

**What the spec covers:**
- **Stories:** four of them: adding a new key without touching the shared file, reading includes that carry overrides (`get`, `show`, `show --sources`, history), changing existing values where they live, and keeping list changes in the file that holds the list.
- **Requirements:** numbered FR-400 to FR-450. They replace step 1's rule for where a new key is written (FR-022) and refine its rule for existing values (FR-020); everything else from steps 1–4 still applies.
- **Clarification questions:** none. Where the contract leaves a choice open, I made it and recorded it as D-40 to D-46.

**Decisions you may want to check:**
- **D-40, nested includes:** if `troupe.yml` includes `coder.yaml`, which includes `model.yaml`, a new key under `model` is written as an override in `coder.yaml`. That is the literal reading of "the file that contains the include reference", but `coder.yaml` may itself be shared. If you want overrides always written in the main file, say so; it's a one-place change.
- **D-41:** a list item that is itself an include can carry overrides. It is converted to mapping form inside the list.
- **D-42:** a `$ref` whose value isn't a `file:` string is just an ordinary mapping key.
- **D-43:** overrides on a YAML include whose content is a list or scalar → exit 4, because merging keys into it would discard the included content.
- **D-44:** replacing a whole mapping that mixes override keys with keys from the included file → exit 3, because an override can't remove the included keys.
- **D-45 and D-46:** when an include is converted, its string keeps its original quoting. Merged keys keep the included file's order, with override-only keys after it.

There are no extension hooks to run. `.specify/feature.json` now points at the new directory, but it is gitignored, so it isn't in the commit.

Next step is `/speckit-plan`, or `/speckit-clarify` first if you want to change D-40.