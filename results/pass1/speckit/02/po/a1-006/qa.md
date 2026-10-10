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

Q4: Step 2 is built and committed on `main`, and all 27 tasks are marked done. Nothing was pushed. The full suite passes (437 tests), and `mypy --strict`, `ruff check` and `ruff format --check` are clean. The `watch` tests passed 5 runs in a row, and I walked through the quickstart by hand with every output as expected.

**What changed:**
- **Hand edits between commands:** `show` and `set` first record, as `set`/`remove` events, anything edited in the files since the last command. `history` never does this, so it still reports only what has been recorded. Formatting-only and comment-only edits record nothing.
- **`troupe config watch`:**
  - It records each edit within 2 seconds, including edits to included files, newly added includes, and editors that save by renaming.
  - It prints only the `watching <dir>` line, and exits 0 on SIGINT or SIGTERM.
  - If a file becomes invalid while it runs, it prints the error once and keeps going.
- **No double recording:** every command takes a lock (`.troupe/events.sqlite3.lock`) from loading the files until its events are saved. So a `set` made while `watch` runs is recorded once, and a hand edit is never recorded by two processes. A test running more than 10 `set`s with and without `watch` produces identical histories.

**Things that behave differently from before:**
- I updated a step 1 test (`test_history.py`) that asserted hand edits are never recorded. Step 2 replaces that rule, and I marked the old decision as superseded in the step 1 spec.
- If the theatre has no `.troupe/` directory, the error names the missing config file rather than the lock file, as it did before step 2.
- I committed the first change before running ruff. `a9a46ba` fixes the lint and formatting issues that slipped in.

**Checking that the tests catch real breakage:** for each story I deliberately broke the code and confirmed a test failed.
- **Weak plan entry:** one break the plan listed, never refreshing the list of watched files, isn't really a bug. `watch` just re-checks on every poll and still records correctly. I broke it a different way instead, by leaving included files unwatched, and 4 tests caught that.
- **Startup race (`watching` line):** an edit made between `watch` reading the files and printing its line could go unnoticed. End-to-end tests can't hit that timing reliably (the break passed 10 out of 10 runs), so I added `tests/unit/test_watch_snapshot.py`. It makes the edit at exactly that moment and fails if the edit is missed.
- **Recording outside the lock:** if a `set` saves its events after releasing the lock, the unit test fails. The end-to-end tests only catch it when the save is slowed by 0.3 s; with that delay they failed 20 out of 20 runs. Without it the window is too short for them to notice.

No extension hooks are registered for this step.
A4 (runner): /speckit-converge

Q5: The convergence check found work left: I appended four test-only tasks as "Phase 7: Convergence" (T028–T031) at the end of `specs/002-config-file-sync/tasks.md` and committed it on `main` as `71138fb`. No other file changed. No code is missing; each task covers behaviour the code already handles but no test checks.

- **T028:** delete the main config file while `watch` runs, then recreate it. Expect one error line, nothing recorded meanwhile, and the new value recorded within 2 seconds.
- **T029:** send SIGTERM to `watch` while it is mid-reconcile, waiting on the lock the test holds. Expect the edit recorded whole, exit 0, and stdout still exactly the one `watching` line.
- **T030:** hand edits that turn a scalar into a mapping or list, and back. Expect the right `set`/`remove` events in the right order.
- **T031:** `watch` picks up an edit in an include of an include (SC-101 asks for a nested include).

T028–T030 are marked CRITICAL only because the constitution requires a test for every behaviour, and the spec names these three cases. T031 is low priority.

One wording problem in T029: it first says "one event or none", then says to check for exactly one. Exactly one is the correct expectation, because `watch` finishes its reconcile once the lock is released. I left the wording as is, because this step may only append to `tasks.md`.

Next, run `/speckit-implement` for T028–T031; another convergence check after that should come back clean.

No extension hooks are registered for this step.
A5 (po): /speckit-implement T028–T031