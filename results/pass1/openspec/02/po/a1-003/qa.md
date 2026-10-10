Q1: I've written the plan for step 2 as the OpenSpec change `config-sync-with-files` in `openspec/changes/config-sync-with-files/`. It passes `openspec validate --strict`. I committed it on `main` as `20902ac` (not pushed), the same way step 1's plan was committed. No project code has changed yet.

**What's in it**
- **`proposal.md`**: why hand edits now have to be recorded, what changes, and which specs are affected. One behaviour changes from step 1: a hand edit now produces `set`/`remove` events. A `set` after a hand edit records the hand edit's event first, then its own.
- **`specs/config-sync/spec.md`** (new capability): reconcile, `show`/`set`/`watch` reconciling first while `history` never does, the `watch` command, broken files while watching, `set` while `watch` runs, and includes added by hand. Each rule has testable scenarios.
- **`specs/config-cli/spec.md`**: adds `watch` to the subcommands and to the rule that troupe only writes under `.troupe/`.
- **`specs/config-history/spec.md`**: the step-1 import rule said hand edits never create events, so I replaced it with one that keeps the same import rules without that sentence. The `set` scenario that starts from a hand edit now expects two events.
- **`design.md`**: how it works, with the alternatives I rejected:
  - Reconcile uses the same comparison `set` already uses, so a hand edit and a `set` with the same effect record the same events.
  - Every command takes a lock on the `.troupe/` folder. A `set` releases it only after its events are saved, so `watch` finds nothing left to record from the write-back. Locking the folder creates no file, so a theatre that fails to load still gets no state.
  - `watch` re-reads the files every 0.2 s and acts only once a change has stayed the same for two reads. That way it doesn't record a file an editor has emptied halfway through saving. This adds no dependency and works the same on Linux and macOS.
- **`tasks.md`**: 4 groups, 21 tasks, each with its own tests and README updates.

**Choices I made where the contract was silent** (listed in `design.md` for review):
1. If the config can't be loaded when `watch` starts, it exits 4 and doesn't print the line.
2. If the files become unloadable while `watch` is running, it keeps running, reports the error once on stderr, and catches up when the files load again.
3. `watch` prints nothing to stdout except the `watching <dir>` line.
4. `<dir>` is printed exactly as given, not expanded to a full path. Expanding it would turn `/var/…` into `/private/var/…` on macOS and the line wouldn't match what was passed. With no theatre given, it's the current directory.
5. `history` still imports on a theatre's first run. Importing isn't reconciling.
6. Events from a reconcile are kept even if the command then fails with exit 3 or 5, as the import already is.
7. A second command on the same theatre waits for the first to finish rather than failing.

**Two risks:**
- One test checks that `uv run` passes Ctrl-C and SIGTERM on to `watch`.
- Locking a folder works on Linux, and I tested that here. I couldn't test it on macOS.

The artifacts are ready for review. When you are ready, run `/opsx:apply`.
A1 (po): /opsx:apply

Q2: ## Implementation Complete

**Change:** `config-sync-with-files` (spec-driven), **21/21 tasks complete**. The work is committed on `main` and not pushed. All 379 tests pass, `mypy --strict` and ruff are clean, and `openspec validate --strict` passes. I ran the timing-sensitive tests (`watch`, the lock and the `uv run` smoke tests) three more times and they passed each time.

### What it does now
- **Hand edits are recorded:** `show`, `set` and `watch` first compare the files with what has been recorded and add a `set` or `remove` event for each value that differs. Formatting-only and comment-only edits add nothing. `history` never does this check; it only reports what has been recorded. This uses the same comparison `set` already used, now in `src/troupe/leaves.py`, and the new `src/troupe/sync.py`.
- **Commands take turns:** each command locks the `.troupe/` folder itself, so no lock file is created. `set` keeps the lock until its events are saved, so `watch` never records troupe's own write-back. A test holds the lock and checks that both `set` and `watch` wait for it. I also disabled the lock briefly and confirmed those tests then fail.
- **`troupe config watch`:** it prints `watching <dir>` only once it is ready. It records an edit in well under 2 seconds, including edits to included files, saves that replace the file, and includes added by hand. If the files stop loading, it reports this once on stderr, keeps running, and catches up when they load again. Ctrl-C and SIGTERM exit 0 with nothing on stderr. A smoke test confirms this works through `uv run`.

### Changes from what you might expect
- **Tests:** `test_hand_edits_are_not_reconciled` became `test_hand_edits_are_not_imported`. `test_set_records_old_value_from_the_files` now expects the hand edit's event before the `set`'s own. The new tests are in `test_reconcile.py`, `test_watch.py` and `test_lock.py`, plus one each in `test_loading.py` and `test_smoke.py`.
- **README:** it now covers reconciling and `watch`, and lists decisions 11–14. I also fixed a stale link to the step-1 design, which had moved to the archive folder.
- **Design doc:** I updated it to match the code. The session function takes the command name (checked against one list of commands that reconcile) and an optional store, instead of a true/false flag.

The specs aren't merged into `openspec/specs/` yet; that happens when you archive the change with `/opsx:archive`.
A2 (po): /opsx:archive