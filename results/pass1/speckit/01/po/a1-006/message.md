I fixed all three convergence tasks (T051–T053) and committed them on `main` as `330dc2f`. Every task in `tasks.md` is now marked done. No extension hooks are registered.

- **T051, store errors:** problems opening or using the event store now give exit 4 with a message naming `.troupe/events.sqlite3`, instead of a traceback with exit 1. If the store is readable but can't be written, `set` refuses with exit 3 before touching any file. That way a change is never written without its history events.
- **T052, read-only files:** `set` now checks that the target file and its folder are writable before writing. If not, it exits 3 with the file named, and the file and its permissions stay exactly as they were. Before, it overwrote a read-only file.
- **T053, `--theatre` before the subcommand:** I removed it rather than writing it into the spec. The contract fixes the placement after the subcommand, and the constitution says not to invent requirements. Its test is gone and `contracts/cli.md` is updated to match.

The decision behind the first two is recorded as B-16 in `research.md`.

**Verification:**
- **Tests:** I added four tests for read-only and unwritable cases, each checking the exact exit code. They failed before the fix and pass now. Removing the writability check made the read-only-file test fail again, so the test does catch the bug.
- **Full gates:** the suite (358 tests) passes, and mypy and ruff are clean.

The permission tests are skipped when run as root, because root ignores file permissions.

A fresh `/speckit-converge` should now come back clean.