## Scored run

### Question 1 (step_done, answered by po)

Arm asked: I've added `troupe config watch`, and every command except `history` now picks up hand edits before it runs. It's committed on `main` as `1f533bf`. All 21 tests pass: the 18 existing ones plus 3 new ones covering the sync behaviour.

**How it works**
- **Catching up on edits:** before doing anything else, each command compares the files with what's been recorded. It records a `set` or `remove` event for each value that differs. Edits that only change formatting or comments compare equal, so they record nothing. `history` never does this check and only reports what's already recorded.
- **`config watch`:** it catches up first, then prints `watching <dir>`, so any edit after that line is noticed. It checks the config file and every included file about every 0.1s and catches up when one changes. Edits are usually recorded within about 0.2s.
  - When a hand edit adds a new include, that file's values are recorded as `set` events and the file is watched from then on. If an edit points at an include that doesn't exist yet, creating that file also triggers a catch-up.
  - If a file has broken YAML part-way through an edit, `watch` prints the error to stderr and keeps going.
  - SIGINT or SIGTERM makes it exit 0.
- **`set` while `watch` runs:** all commands take turns via a lock file, `.troupe/events.lock`. A `set` holds it while it catches up, writes the files and records its events. By the time `watch` sees the changed file, the change is already recorded, so it adds nothing. I ran 15 `set`s in a row against a running `watch` and got exactly 2 import events and 14 set events (one `set` didn't change the value), with no duplicates.

**Behaviour you might not expect**
- The lock file `.troupe/events.lock` is new and sits in each project's `.troupe/` folder, next to `events.sqlite`.
- If `history` runs before anything has been recorded, it still records the starting values as `import` events, as it did before. It doesn't catch up on edits when it does this.
- `watch` exits with code 4 if there's no config file when it starts. It doesn't wait for one to appear.

The new code is in `src/troupe/sync.py`, with small changes in `cli.py`, `store.py` and `editor.py`. I've also updated the README.

Reply: 
