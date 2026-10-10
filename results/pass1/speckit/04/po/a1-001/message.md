I've written the step 4 lineage spec and committed it on `main` as `dcc95db`. Nothing was pushed.

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