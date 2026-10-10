Recorded (A): find the node's span, splice in only the new text, never re-serialise the file, and write atomically.

**Last question: where history is stored.** The contract allows state only under `<theatre>/.troupe/` and requires the `eventsourcing` library. The library ships with an SQLite persistence module, selected by configuration rather than code.

- **(A) Recommended: the library's built-in SQLite storage.**
  - One database file, `<theatre>/.troupe/history.sqlite`.
  - One history record per theatre. Each command appends events for that run, and `seq` is the event's position in the history (1, 2, …).
  - It's the real library storage the charter's testing rule (TROUPE-005) asks for: no custom serialisation, and an interrupted run can't leave half its events written.
  - The database's temporary files (`-journal`/`-wal`) also stay inside `.troupe/`.
- **(B) A custom JSON-file store** built on the library's in-memory storage. Easier to read by eye, but it adds serialisation code and risks a partial write.
- **(C) Something else.**

Reply A, B or C. Then I'll send the Engineering Alignment summary for you to confirm before I write `plan.md`.

WAITING_FOR_PLANNING_INPUT