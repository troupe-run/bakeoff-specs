Q1: I've written the step 4 lineage spec and committed it on `main` as `571afd7`. Nothing was pushed.

- **Feature directory:** `specs/004-config-lineage`
- **Spec:** `specs/004-config-lineage/spec.md`
- **Checklist:** `specs/004-config-lineage/checklists/requirements.md`. Every item passed on the first check, and there are no open clarification markers.
- `.specify/feature.json` now points at the new directory. Git ignores that file, so it isn't in the commit.
- **Hooks:** none are registered in `.specify/extensions.yml`, so none ran.

**What the spec covers**
- **New `history` fields:** every event gets `actor`, `via`, `at`, `reason` and `change` (FR-300 – FR-306). They are saved when the event is recorded and printed back exactly as saved.
- **`TROUPE_ACTOR`:** sets who made a command-line change. Any value other than `human:<id>` or `agent:<id>` makes the command exit 2 (FR-320 – FR-322).
- **`set --reason TEXT`:** the reason attaches only to that `set`'s own events (FR-330 – FR-332).
- **Grouping:** if one command also imports a new theatre or picks up hand edits first, those get their own change ids, separate from the command's own events (FR-340).

**Choices I made where the contract was silent** (recorded as D-30 – D-37):
- **Separate change ids:** a command's import and hand-edit pickup are not part of its change. They keep an unknown actor and never carry the command's reason (D-30).
- **Every command checks `TROUPE_ACTOR`:** this includes read-only ones (`get`, `show`, `history`), before anything else happens (D-31).
- **No login name:** if `TROUPE_ACTOR` is unset and the system reports no login name, the actor is recorded as unknown rather than failing or inventing a name (D-32).
- **Exact matching:** `HUMAN:x` or ` agent:x` exits 2, and an id can contain colons (D-33).
- **Empty reason:** `--reason ""` is recorded as an empty string; null means no reason was given (D-34).
- **Timestamps:** all events in one change share one timestamp (D-35).
- **Change id format:** the change id has no fixed format; it's only meant to be compared for equality (D-36).

**Decision for you:** history recorded before step 4 has no lineage, and I made it **out of contract** with no upgrade (D-37). The contract can't express an unknown timestamp, so I didn't invent one. Any existing theatre with older history isn't covered by this step. If you'd rather upgrade that history somehow, the spec needs changing before planning.

The spec is ready for `/speckit-clarify` or `/speckit-plan`.
A1 (owner): The contract says every `history` event has the Lineage fields. It doesn't say anything about events recorded before step 4, or about upgrading stored history. Treat that as out of contract: your choice — state which you chose and why.

Q2: I'm keeping it out of contract: history recorded before step 4 is not upgraded. troupe won't detect, convert or fill in lineage for events from steps 1–3, and what any command does with such a store is left undefined and untested.

**Why:**
1. **Any filled-in value would be a guess.** Those events never recorded who made them, how, when, or which change they belonged to. The contract has an "unknown" value for the actor, but none for the timestamp, `via` or `change`. Filling those in means inventing values, which is exactly what the step says not to do.
2. **Nothing needs upgrading.** I checked: there's no theatre with an older store anywhere in the repository. Steps 1–3 only ran against fresh theatres that the tests create.
3. **It would be work with no contract behind it.** The constitution says to build for the current stage only. A migration would be extra code with no defined behaviour to test it against.

Your configuration files aren't affected either way: lineage only changes troupe's own store under `.troupe/`.

I rewrote decision D-37 in `specs/004-config-lineage/spec.md` to state this choice and reasons, and updated the checklist note to match. It's committed on `main` as `1d2cb85`, not pushed. The spec is ready for `/speckit-plan`.
A2 (po): /speckit-plan

Q3: I've written the step 4 plan and design files and committed them on `main` as `f495760`. Nothing was pushed. The constitution check passes before and after design, with no violations to justify. No hooks are registered, so none ran.

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
A3 (po): /speckit-tasks