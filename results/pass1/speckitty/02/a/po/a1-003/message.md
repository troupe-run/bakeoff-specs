I've recorded that choice: stdout carries only the `watching <dir>` line. The contract's only stdout promise is that one line, so keeping stdout quiet makes it unambiguous for anyone waiting on it. Printing events can be added later without breaking anything.

That's enough to write the spec. Here is my **Intent Summary**. Please confirm it or correct it.

**Who and why:** A theatre owner edits `.troupe/` files in their editor. Sometimes troupe is running at the time, sometimes nothing is. troupe should record those edits as changes so its history matches the files. It must never record its own write-backs a second time.

**Terms:**
- **Recorded configuration:** the leaves you get by replaying history.
- **Reconcile:** compare the leaves in the files with the recorded configuration and record one `set` or `remove` event per leaf that differs. It uses the same leaf comparison and the same event order as `set` already does.

**Main scenario:** The owner runs `troupe config watch --theatre <dir>`, sees `watching <dir>`, and changes `model.temperature` from 0.2 to 0.5 in their editor. Within 2 seconds, `history` shows `set model.temperature 0.2→0.5`.

**Rules that must always hold:**
1. Edits that change only formatting or comments record nothing.
2. A `set` made while `watch` is running records only the `set`'s own events. Its write-back never comes back as a second event.
3. `history` never reconciles.
4. After any command other than `history` has run, the recorded configuration matches the files.

**This replaces two step-1 rules:** FR-008 ("hand edits produce no event") and FR-022 ("importing never reconciles"). Hand edits are now recorded as `set`/`remove` events.

**Your two decisions:**
- **Broken saves:** a save that can't be loaded never stops `watch`. It prints an error to stderr naming the file, records nothing, and reconciles once the files load again.
- **stdout:** only the `watching <dir>` line.

**Choices I'll make where the contract is silent (I'll record each one in the spec):**
1. **First run:** a theatre that has never been imported is imported, as in step 1, and import counts as its first reconcile. `history` still imports a never-imported theatre, because importing is not reconciling.
2. **Start-up:** `watch` reconciles before it prints `watching <dir>`. It is already watching for changes by then, so an edit made in between isn't lost. If the configuration can't be loaded at start-up, `watch` exits 4 with an error naming the file and doesn't print the line, like every other command.
3. **Before other commands:**
   - `show` and `set` reconcile first. If loading fails they exit 4 and record nothing.
   - A `set` that is refused still keeps the events its reconcile recorded, the same way step 1 keeps an import when a command fails afterwards.
   - A `set` after an unrecorded hand edit records the hand edit's event first, then its own events. Its own `old` is the hand-edited value.
4. **Includes:**
   - An include added by a hand edit is watched from then on.
   - When an include is removed, its leaves get `remove` events and its file is no longer watched.
   - Edits to text-include targets are reconciled too.
5. **Rapid saves:** several saves inside the 2-second window may be recorded as one reconcile, from the recorded state to the final files. Intermediate states may not appear in history.
6. **Stopping:** SIGINT or SIGTERM exits 0 with no further output, even while the files are broken.
7. **Default theatre:** `watch` uses the same default as the other commands: `--theatre`, then `$TROUPE_THEATRE`, then the current directory.
8. **Out of contract:** a hand edit made at the same moment as a `set` writes the same file is a concurrent write, which step 1 already put out of contract.

Shall I write and commit the spec on this basis?

WAITING_FOR_DISCOVERY_INPUT