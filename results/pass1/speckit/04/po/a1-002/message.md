I've written the step 4 plan and design documents and committed them on `main` as `9a1001e`. Nothing was pushed. No extension hooks are registered, so none ran.

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