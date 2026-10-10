Q1: I've written the step 5 spec and committed it on `main` as `0aaad5a`. Nothing is implemented yet: this is the spec only, so CR-A is not delivered until the plan, tasks and implementation are done.

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
A1 (po): /speckit-plan

Q2: I've written the step 5 plan and design documents and committed them on `main`. There were no extension hooks to run.

**Plan:** `specs/005-include-overrides/plan.md`
**Other documents:** `research.md` (technical choices O-1 to O-9), `data-model.md`, `contracts/cli.md`, `quickstart.md`.

**Design in brief:**
- **Reading:** the loader recognises a `$ref` mapping and builds the merged result directly. Each value still remembers the file it's written in, so `get`, `show`, `show --sources`, history, reconcile and `watch` need no changes.
- **Where a new key goes:** `set` tracks, for each file, the include reference it was reached through. A new module, `edit/override.py`, uses that to decide where the key is written. It also converts a one-line include into the `$ref` form, keeping the original include string and any end-of-line comment. The existing code still lays out the new lines, so quoting and comment handling stay as they were.
- **Checking a write:** before writing, the check that the change lands only where intended now identifies an include by where it is referenced. This matters when one file is included twice: an override at one key is shown to leave the other alone.
- **Existing test:** `test_new_key_in_an_included_file` encodes the old rule (new key written into the shared file). It will be changed to expect the override.

**Spec changes from planning** (committed separately as `75b0bb8`):
- **D-48:** a section that has keys from both a shared file and an override counts as coming from the override's file. So a new key there goes into that override, or one level further out if that file is itself included. No shared file gains it.
- **D-47:** if the place that should receive the override is itself an include (for example an override `limits: file:l.yaml`), `set` refuses with exit 3 and changes nothing.

Every principle in the constitution check passes, and no clarifications are open. Next step is `/speckit-tasks`.
A2 (runner): /speckit-specify A second change request has arrived while you work on the first one:

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.

---

## In-include (from step 5, change request B)

- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.
