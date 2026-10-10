I stopped before generating tasks: the design is not approved yet.

`.kiro/specs/config-file-sync/spec.json` shows `approvals.design.approved: false`, and no `-y` was passed. The project rules ask for a human review at each phase, so I didn't treat running this step as approval. The working tree is clean, and `design.md` is as committed in `161879d`.

These are the design decisions most worth checking before you approve:
- **Reconcile inside the shared opening step:** `open_theatre` reconciles by default for every command and every `watch` check. Only `history` turns it off.
- **Lock on `.troupe/`:** every command, `history` included, holds a lock on the `.troupe/` directory itself from just after the config file is found until it ends. It creates no file and waits as long as needed.
- **Polling:** `watch` checks the files every 0.2 seconds and uses no file-watching library. Failures are retried on every check, and each distinct error message is printed once.
- **Signals:** SIGINT and SIGTERM only set a flag. A reconcile in progress always finishes, then `watch` exits 0.
- **Order of `remove` events:** within one reconcile, `remove` events follow the order in which those leaves were created in the history.
- **Small changes to step-1 files:** `scalar_equal` moves into `troupe.config.scalars`. The shell keeps the raw `--theatre` text so `watch` can print `<dir>` as given. `run()` gets a streaming path so `watch` can print its line and keep running.

To approve the design and generate tasks, run:
```
/kiro-spec-tasks config-file-sync -y
```
Or reply "approved" and I'll mark the design approved and generate the tasks; you'll still approve the task list separately. If you want changes, tell me which and I'll revise `design.md`.