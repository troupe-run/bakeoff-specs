I've written the step 4 plan and design files and committed them on `main` as `f495760`. Nothing was pushed. The constitution check passes before and after design, with no violations to justify. No hooks are registered, so none ran.

The plan is at `specs/004-config-lineage/plan.md`. Alongside it are `research.md` (decisions L-1 to L-8), `data-model.md`, `contracts/cli.md` and `quickstart.md`.

**The design**
- **New module:** `config/lineage.py` holds every lineage rule in one place. That covers the actor format, the "unknown" actor, the `via` values, the timestamp format and the change id.
- **One change id per change:** each change gets exactly one id and one timestamp, so the events of one change always share them. The three kinds of change are import, reconcile (including `watch`), and a `set`'s own events.
- **Storage:** the lineage is saved on each existing stored event, in the same write as the event. `history` prints what was saved and recomputes nothing.
- **Values:**
  - `at` is UTC with microseconds, like `2026-10-03T14:05:09.123456Z`.
  - `change` is a random UUID, so it stays unique across processes, including `watch` running alongside a command.
- **CLI:** `TROUPE_ACTOR` is checked for every subcommand before anything is loaded. `--reason` exists only on `set`.

**What I checked against the installed libraries**
- The event store saves and reads back string and null fields unchanged, including multi-line non-ASCII text.
- argparse silently keeps the last of two `--reason` values. The plan adds a small check so a repeated `--reason` exits 2 instead of dropping one reason.
- `getpass.getuser()` reads `LOGNAME`/`USER`/`LNAME`/`USERNAME` before the account name. I updated the spec's D-32 wording to say so, and tests can set the login name through `LOGNAME`.

**Worth knowing before implementation**
- **Older stores:** an event store written before step 4 should fail with exit 4 naming `events.sqlite3`, writing nothing. That's the intended result, but I haven't confirmed the library error is actually caught that way. Research L-8 flags it as a check to do during implementation.
- **Existing tests:** current history tests compare whole lines, so they'll need updating to include the new fields.
- **Test environment:** the test helper will drop any inherited `TROUPE_ACTOR` so the tests don't depend on the environment they run in.

Next step is `/speckit-tasks`.