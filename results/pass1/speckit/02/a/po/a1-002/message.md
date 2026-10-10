I've written the design for step 2 and committed it on `main` (`3b9d9e8`). Nothing is built yet: the code and tests come at the tasks and implement steps. The plan passes the constitution check before and after design, and every technical question is settled in `research.md` (S-1 to S-10).

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