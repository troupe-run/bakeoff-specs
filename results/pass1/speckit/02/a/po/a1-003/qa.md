Q1: I've written the step 2 spec and committed it on `main` (`a149b58`). Nothing has been built yet: this step only produces the spec.

- **Feature directory:** `specs/002-config-file-sync`
- **Spec file:** `specs/002-config-file-sync/spec.md`
- **Checklist:** `specs/002-config-file-sync/checklists/requirements.md`. Every item passes on the first check and there are no open clarification questions.
- **Hooks:** none are registered in `.specify/extensions.yml`, so none ran.

**What the spec covers**
- **Four user stories:**
  1. Hand edits made while nothing is running are recorded by the next command.
  2. Live recording with `config watch`.
  3. A `set` made while `watch` runs is recorded once, not twice.
  4. An include added by hand is followed.
- **Requirements FR-050 to FR-066:**
  - `watch` prints `watching <dir>` only once every config file is being observed, and exits 0 on SIGINT or SIGTERM.
  - It reconciles within 2 seconds of a change, including saves where an editor renames a temporary file over the original.
  - The set of watched files changes as includes are added or removed.
  - Formatting-only and comment-only edits record nothing.
  - `history` never reconciles.
  - Event numbering stays correct when `watch` and other commands run at the same time.
- **Changes to step 1:** step 1 said hand edits are never recorded (D-1). The spec states which part of that this step overturns, and clarifies two related step 1 rules (FR-042, FR-043).

**Decisions I made where the contract leaves a choice open (D-10 to D-17), worth a look**
- **`<dir>` in the `watching` line:** the directory exactly as you gave it (from `--theatre` or `TROUPE_THEATRE`), or `.` if neither is set.
- **Broken file while `watch` runs:** nothing is recorded, an error naming the file goes to stderr, and `watch` keeps running. If the config can't be loaded when `watch` starts, it exits 4.
- **What counts as a change:** spelling differences don't count (`'x'` vs `"x"`, `0.20` vs `0.2`), but a change of type does (`1` vs `1.0` vs `"1"`).
- **Several saves within 2 seconds:** these may be recorded as a single net change, but the final state is always recorded.
- **Hand edits pending when you run `set`:** they are recorded first, and the `set`'s own events follow.

The next step is `/speckit-plan`, or `/speckit-clarify` if you want to revisit any of those decisions first.
A1 (po): /speckit-plan

Q2: I've written the design for step 2 and committed it on `main` (`3b9d9e8`). Nothing is built yet: the code and tests come at the tasks and implement steps. The plan passes the constitution check before and after design, and every technical question is settled in `research.md` (S-1 to S-10).

**Main design choices:**
- **Reconcile:** it records one event per leaf that differs between the files and the event store. It reuses step 1's comparison and event-ordering code unchanged, so `set` and reconcile can't disagree. `show`, `set` and `watch` reconcile first; `history` never does.
- **How `watch` sees changes:** it checks the files about five times a second, with no new dependency. It compares each file with the exact bytes the last load read, or with "absent" for a missing file or include target. Because of that, a change made right after the `watching` line still counts. Saving by renaming over the file, adding an include, and fixing a broken file are all picked up.
- **Partly written saves:** before reconciling, `watch` waits until a changed file reads the same twice, for at most 1 second. This stops an editor's brief empty file from being recorded as a burst of removes and re-sets, and stays inside the 2-second limit.
- **No double recording:** every command holds one lock across loading the files, reconciling, writing and recording. The lock file is `.troupe/events.sqlite3.lock`. Once a `set` releases it, the store already matches the files, so `watch` records nothing more. The lock also keeps event numbers contiguous when several processes run at once.
- **Signals:** SIGINT and SIGTERM only set a stop flag, so a store write is never cut off part-way, and the exit code is 0.

I also changed one wording in the spec. D-11 now says `remove` events come out "in the order each leaf was first recorded", because the recorded configuration has no file order of its own.

I checked two library facts in this repo. Recorded values keep their exact types after a store round trip (`1` vs `1.0`, `inf`). The lock also works on a read-only file, so the existing read-only-store test should still get exit 3.

There were no plan hooks to run. Next step: `/speckit-tasks`.

Files are in `specs/002-config-file-sync/`:
- plan.md
- research.md
- data-model.md
- contracts/cli.md
- quickstart.md
A2 (po): /speckit-tasks