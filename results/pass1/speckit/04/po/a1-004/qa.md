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

Q3: I've written the task list, `specs/004-config-lineage/tasks.md`, and committed it on `main` as `cb7367b`. Nothing was pushed. No extension hooks are registered, so none ran.

There are 25 tasks. Tests are included even though the template calls them optional, because the project constitution requires a test for every behaviour.

| Phase | Tasks | What it covers |
|---|---|---|
| Setup | 2 (T001–T002) | Confirm the current suite passes; stop tests inheriting your own `TROUPE_ACTOR`; fix the login name tests see |
| Foundational | 7 (T003–T009) | `lineage.py`, lineage saved with each event, the three places that record it, `history` output, existing tests kept working |
| US1 who and how (P1) | 5 (T010–T014) | Actor and `via`; an invalid `TROUPE_ACTOR` exits 2 on every command, including `watch` |
| US2 what changed together (P1) | 2 (T015–T016) | Change ids shared within a group and distinct between groups |
| US3 when and why (P2) | 3 (T017–T019) | `--reason` only on the `set`'s own events, `""` kept as given, timestamps in UTC and inside the command's run |
| US4 survives restarts (P1) | 2 (T020–T021) | History printed identically by new processes with a different actor |
| Polish | 4 (T022–T025) | README, notes in the step 1–2 docs, quickstart walk-through, final checks |

**How each story is tested:**
- **US1:** run an import, a `set` under each kind of `TROUPE_ACTOR`, a hand edit followed by `get`, and a hand edit under `watch`, then compare `actor` and `via` line by line. Every invalid actor value exits 2 with no files or history changed.
- **US2:** group history lines by change id and check each group is exactly one import, one pick-up of hand edits, or one `set`.
- **US3:** each timestamp falls between UTC times taken just before and after the command, and the reason text comes back exactly as given.
- **US4:** earlier `history` output is byte-for-byte unchanged when listed later by a different actor.

**Changes to the existing tests:** the test helper `theatre.history()` will keep returning only the original five fields, and a new `theatre.events()` returns the full lines with lineage. That keeps the step 1–3 tests unchanged and still testing what they did. Only the one test that compares a raw history line gets updated.

**One test may be skipped:** the end-to-end check for "no login name can be found" only runs if your user account has no system user entry, which is unusual. Otherwise it skips, and a unit test covers that case instead.

**Parallel work:** the three US1 test files can be written at the same time, as can the two foundation test files. Once the foundation is done, the US1, US2 and US3 tests are independent. US1 and US3 both edit `cli.py`, so their implementation tasks should run one after the other.

**Suggested MVP:** Setup, Foundational and US1, which answers who and how for every event.

All 25 tasks use the required checklist format: checkbox, ID, `[P]` where parallel, story label in story phases, and file paths.

Next step: `/speckit-implement`, optionally after `/speckit-analyze`.
A3 (po): /speckit-implement