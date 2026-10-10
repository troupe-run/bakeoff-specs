Q1: I've written the step 2 spec and committed it on `main` as `cd9b7dc`. Nothing was pushed. This step only produces the spec; there's no code yet.

- **Spec directory:** `specs/002-config-file-sync`
- **Spec file:** `specs/002-config-file-sync/spec.md`
- **Checklist:** `specs/002-config-file-sync/checklists/requirements.md`. All items pass on the first check, and there are no open clarification markers.
- **Hooks:** `.specify/extensions.yml` registers none, so none ran before or after.
- **Active feature:** `.specify/feature.json` now points at the new directory. That file is gitignored, so it is set locally but not in the commit.

**What the spec covers:**
- **Stories:**
  - Commands pick up edits made while nothing was running.
  - `watch` records edits within 2 seconds.
  - A `set` made while `watch` runs records only its own events.
- **Requirements FR-100 – FR-131:**
  - **`watch`:** the `watching <dir>` line is printed only once it can see changes; it follows includes added or removed by hand; SIGINT or SIGTERM exits 0.
  - **Reconcile:** a value counts as changed only if its type or value differs, so `1` → `"1"` is a change but formatting and comments are not. Events are ordered the same way as a `set`'s, and one reconcile is recorded entirely or not at all.
  - **Which commands:** `show`, `set` and `watch` reconcile first; `history` never does.
  - **Running alongside `watch`:** every change is recorded exactly once.
- **Change from step 1:** step 1 decided that hand edits between commands are not recorded (D-1). This spec replaces that decision; all other step 1 rules still apply.

**Decisions I made where the contract leaves a choice (D-10 – D-17):**
- "The configuration" that files are compared against means what the recorded events describe. That's why a `set`'s own write-back finds nothing new.
- `<dir>` in the `watching` line is the directory as you gave it. If none is given, it is the absolute path of the current directory.
- `watch` prints nothing to stdout except that one line. Load errors go to stderr.
- If a file becomes invalid while `watch` runs (say, a half-saved edit), `watch` reports it and keeps going. If the configuration can't load at startup, it exits with code 4 like the other commands.
- Several quick edits may be recorded together as their net change.
- Events from a reconcile stay recorded even if the command then fails with exit 3 or 5.
- `watch` running alongside one other command is supported. Two `set`s at once, and more than one `watch` on the same theatre, are left out.

Next is `/speckit-plan`. The main design question there is how one change gets recorded exactly once when `watch` and another command run at the same time.
A1 (po): /speckit-plan

Q2: I've written the step 2 plan and design documents and committed them on `main` as `ebf44e2`. Every constitution check passes before and after design, with nothing needing justification. As before, there's still no code.

The setup script reported the branch as `002-config-file-sync`, but no branch was created; work stays on `main`. The plan is `specs/002-config-file-sync/plan.md`, and no hooks are registered for this step.

**Main design choices:**
- **Reconcile:** it compares the values loaded from the files with the recorded configuration, using step 1's existing comparison. So formatting-only or comment-only edits record nothing, and `1` → `"1"` counts as a change. Each reconcile's events are saved together in one go.
- **Who reconciles:** the one function that loads the configuration for every command gets a switch. `show`, `set` and `watch` turn it on; `history` turns it off.
- **Exactly once:** every command takes an exclusive lock on a new file, `.troupe/events.sqlite3.lock`, and holds it from loading the files until its events are recorded. Whichever process comes second finds nothing left to record. This is what stops `watch` re-recording a `set`'s own write-back, and stops `watch` and a command both recording the same hand edit.
- **Spotting changes:** `watch` re-reads every watched file five times a second and compares the bytes with the bytes it last read. File timestamps aren't used. That makes the `watching` line a real promise, catches editors that save by renaming, and needs no new dependency. Newly added includes start being watched after each reconcile.
- **Broken files:** if the configuration stops loading while `watch` runs, it retries on every check and prints each distinct error once. If it can't load at startup, it exits with code 4.
- **Signals:** SIGINT and SIGTERM only set a stop flag, so a reconcile that's under way finishes and `watch` exits 0.

**I changed the spec:** FR-114 now says a reconcile records removals in the order those values were first recorded, not "document order". Document order stops being well defined once `set` has added new values.

**Files added** in `specs/002-config-file-sync/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

Next is `/speckit-tasks`.
A2 (po): /speckit-tasks

Q3: I've written the step 2 task list and committed it on `main` as `34b2667`. It's in `specs/002-config-file-sync/tasks.md`, and no hooks are registered for this step.

There are 27 tasks, T001–T027:

| Phase | Tasks | Count |
|---|---|---|
| 1. Setup: confirm step 1 still passes all checks | T001 | 1 |
| 2. Foundational: reconcile, lock, reading the recorded configuration | T002–T007 | 6 |
| 3. US1: edits made while nothing was running are picked up (MVP) | T008–T012 | 5 |
| 4. US2: live sync with `watch` | T013–T019 | 7 |
| 5. US3: a `set`'s own write-back is recorded only once | T020–T023 | 4 |
| 6. Polish: README, step 1 spec pointer, quickstart, full checks | T024–T027 | 4 |

**How each story is tested on its own:**
- **US1:** edit files by hand between commands, then compare the exact `config history` output. This also checks that `history` never reconciles and that a reconcile still stands when the command after it fails.
- **US2:** start `watch` as a real process and read its `watching` line. Then edit the main file, an included file and a text include, both in place and by saving over the file with a rename. The edits must show up in `history` within 2 seconds, and SIGINT or SIGTERM must end it with exit code 0.
- **US3:** run 10 or more `set`s with `watch` running and the same `set`s without it, and the two histories must match. One test holds the lock itself to show the lock is what prevents duplicate events.

**Can run in parallel:**
- T002 with T003, and T004 with T005.
- T014 with T015, once the `watch` test fixture (T013) exists.
- T020 with T021.
- T024 with T025.

**Order of the stories:** US2 needs the reconcile switch added in US1 (T010). US3 tests how US1 and US2 work together, so it comes last.

**Suggested MVP:** Phases 1–3. With those, every command picks up edits made while nothing was running, without needing `watch`.

Every task follows the required format: checkbox, ID, story label in the story phases, and a file path. Tests are included even though the template calls them optional, because the constitution requires them. Each story ends with a step that breaks the behaviour on purpose to check the tests catch it.

Next is `/speckit-implement`.
A3 (po): /speckit-implement