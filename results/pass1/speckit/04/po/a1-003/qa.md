Q1: I've written the step 4 lineage spec and committed it on `main` as `dcc95db`. Nothing was pushed.

- **Feature directory:** `specs/004-config-lineage`
- **Spec file:** `specs/004-config-lineage/spec.md`
- **Checklist:** `specs/004-config-lineage/checklists/requirements.md`. Every item passed on the first check, and the spec has no open clarification questions.
- **Extension hooks:** none are registered in `.specify/extensions.yml`, so none ran.

**What the spec covers:** four user stories: who and how; which settings changed together; when and why; and lineage surviving restarts. Requirements FR-300 – FR-332 cover the five new history fields, the actor rules, `TROUPE_ACTOR` checking and `set --reason`.

**Choices I made where the contract was silent** (recorded as D-30 – D-38). These are worth a look before planning:
- **Change groups (D-30):** one `set` command can record up to three groups, each with its own change id: the first import, the pick-up of hand edits, and the `set`'s own change. That way a hand edit is never credited to the person or agent running the command.
- **Who is checked (D-31):** every `config` command checks `TROUPE_ACTOR`, not just `set`. An invalid value exits 2 before anything is recorded.
- **Empty values (D-32):** an empty `TROUPE_ACTOR`, or `human:` / `agent:` with no id, exits 2 rather than falling back to the login name.
- **Unknown login name (D-34):** if the login name can't be found, the actor is a human with a null id, not a guessed name.
- **Empty reason (D-36):** `--reason ""` is recorded as `""`, not `null`.
- **Timestamps (D-35):** every event in one change has the same timestamp.

**Left out of scope:** event stores created before step 4. Their events carry no lineage, and filling in actor or via would mean guessing. If existing theatres need upgrading, that's a question for the product owner.

**Not committed:** `.specify/feature.json` (it now points to the new spec) is in `.gitignore`, so it's updated locally only.

Next step: `/speckit-plan`, or `/speckit-clarify` if you want to revisit D-30 or D-31 first.
A1 (po): /speckit-plan

Q2: I've written the step 4 plan and design documents and committed them on `main` as `9a1001e`. Nothing was pushed. No extension hooks are registered, so none ran.

The setup script reported the branch as `004-config-lineage`, but no branch was created; work stays on `main`, as in steps 1–3.

**How lineage is built:**
- **Storage:** lineage becomes six extra fields on the existing change event. The event library already saves and reloads those, so lineage survives restarts and needs no new storage.
- **Grouping:** a new module, `src/troupe/config/lineage.py`, creates one lineage value per group of changes: the import, a pick-up of hand edits, or a `set`'s own change. Every event in a group is stamped with that value, so they always share one change id and one timestamp.
- **Change id and timestamp:** the change id is a random UUID. The timestamp is in UTC with microseconds and ends in `Z`.
- **`TROUPE_ACTOR`:** checked in the CLI for every command, right after reading the arguments and before the configuration is loaded. An invalid value can't import, record or write anything.
- **Login name:** taken from the standard library's `getpass.getuser()`, or null if it can't be found. I didn't use `os.getlogin()` because it fails without a terminal, which is how agents and CI run.
- **`history`:** prints the five new fields after the existing ones.
- **Old event stores:** event stores from steps 1–3 get no migration and no default values. Replaying one may fail, and that's left undefined, matching the spec's out-of-scope decision.

The constitution check passes before and after the design, with no violations to justify.

Existing tests that compare whole history lines will need updating, because every line now has more fields. The test fixtures will also strip any `TROUPE_ACTOR` you have set, so your own environment can't make tests pass by accident.

Next step: `/speckit-tasks`.

Files are in `specs/004-config-lineage/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`
A2 (po): /speckit-tasks