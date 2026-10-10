**Planning question 1: how should a `set`'s write-back be kept out of `watch`'s events, and each edit recorded exactly once?**

**What the code already gives us:**
- `set` writes files atomically (temp file plus rename), then records its events.
- The history is an eventsourcing aggregate in `.troupe/history.sqlite`. Its version check makes a second concurrent save fail instead of silently interleaving.
- `leaves.diff` already produces the ordering in D‑6.

**Options:**
- **(A) Theatre lock plus compare (recommended).** Every reconcile, and every `set` (from its reconcile through writing files and recording events), runs under an exclusive `flock` on `.troupe/lock`. A reconcile records only the leaves that differ from the recorded configuration, which is the history replayed into a path→value map kept on the aggregate.
  - A write-back is recorded by `set` before the lock is released, so when `watch` next reconciles it finds no difference and records nothing.
  - A hand edit is recorded by whichever reconcile takes the lock first. The next one finds it already recorded.
  - There is no bookkeeping that can drift: the "exactly once" rule follows directly from the invariant.
- **(B) Fingerprint ignore list.** `set` writes the hashes of the files it wrote, and `watch` skips matching bytes. This is fragile: a hand edit saved between the write and `watch`'s check is lost or double-counted, and a hand edit that happens to restore earlier bytes is suppressed.
- **(C) Something else.**

**Engineering Alignment (please confirm with your answer):**
1. **How `watch` observes files: stdlib polling, no new dependency.** About every 250 ms, `watch` reads the bytes of the watched files plus both root-file names. Any difference triggers a reconcile.
   - Comparing bytes rather than mtimes catches editors that save by renaming a new file over the old one, and same-second edits.
   - The baseline is taken before reconciling, and `watching <dir>` is printed afterwards. So any edit made after the line appears is detected within about 0.5 s, well under 2 s.
   - The alternative was adding `watchdog`, which brings a supply-chain dependency and platform-specific backends, so I rejected it.
2. **The watched set** is the set of files the loader actually read; the loader will report it. While the configuration can't load, `watch` retries loading every tick. It prints one `troupe: …` stderr line when it becomes unloadable, and another only if the error changes.
3. **Recorded configuration:** the `ConfigHistory` aggregate keeps a `leaves` map that its import, set and remove events update. Existing step‑1 databases replay into it unchanged, so no migration is needed.
4. **Reconcile** is one function, `reconcile(theatre)`: lock, load, import if needed, diff against the recorded leaves, record. `show`, `set` and `watch` call it. `history` keeps its current path (it imports but never reconciles).
5. **Signals:** SIGINT/SIGTERM set a stop flag. The loop finishes any reconcile in progress (each one is a single atomic save), then exits 0.
6. **A contract-fidelity change to the spec:** `watching <dir>` will echo the theatre directory as you gave it, whether that came from `--theatre`, `$TROUPE_THEATRE` or the current directory. It will not print the resolved path. The contract writes `--theatre <dir>` → `watching <dir>`. Resolving would turn macOS `/var/…` into `/private/var/…` and break that match. I'd update FR‑009 to say this.

WAITING_FOR_PLANNING_INPUT