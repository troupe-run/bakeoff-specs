The convergence check found work left: I appended four test-only tasks as "Phase 7: Convergence" (T028–T031) at the end of `specs/002-config-file-sync/tasks.md` and committed it on `main` as `71138fb`. No other file changed. No code is missing; each task covers behaviour the code already handles but no test checks.

- **T028:** delete the main config file while `watch` runs, then recreate it. Expect one error line, nothing recorded meanwhile, and the new value recorded within 2 seconds.
- **T029:** send SIGTERM to `watch` while it is mid-reconcile, waiting on the lock the test holds. Expect the edit recorded whole, exit 0, and stdout still exactly the one `watching` line.
- **T030:** hand edits that turn a scalar into a mapping or list, and back. Expect the right `set`/`remove` events in the right order.
- **T031:** `watch` picks up an edit in an include of an include (SC-101 asks for a nested include).

T028–T030 are marked CRITICAL only because the constitution requires a test for every behaviour, and the spec names these three cases. T031 is low priority.

One wording problem in T029: it first says "one event or none", then says to check for exactly one. Exactly one is the correct expectation, because `watch` finishes its reconcile once the lock is released. I left the wording as is, because this step may only append to `tasks.md`.

Next, run `/speckit-implement` for T028–T031; another convergence check after that should come back clean.

No extension hooks are registered for this step.