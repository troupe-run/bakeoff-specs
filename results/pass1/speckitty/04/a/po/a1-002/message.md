I chose **option A**. Pre-step-4 events are reported with what is known, and every unknown is marked explicitly. Here is why:
- **Nothing is lost or changed.** Stored history is never rewritten. The missing lineage fields are filled in only when `history` reads the events. This is the data-safe choice the charter's TROUPE-002 asks for.
- **Unknowns are marked, not guessed.**
  - The actor is `{"kind":"unknown","id":null}`.
  - `via` is `null` for old set/remove events, because nothing records whether they came from the CLI or a hand edit. Old import events can only have come from the import, so they keep `"import"`.
  - `at` comes from the time the `eventsourcing` library already stored on each event, so it is real.
- **Old events are never wrongly grouped.** All old import events share one `change`, because the import was a single unit by construction. Each old set/remove event gets its own `change`.
- **Option C was rejected.** Refusing to read old history would make an upgraded theatre unusable until the user deleted their audit trail.

I recorded this as decision `01M425SBQPM5X49KSAEKDT331V` in the mission folder.

## Intent Summary — please confirm

**Who and when:** a person or an AI agent changes configuration with `troupe config set`, or by editing a file. Later, an auditor runs `troupe config history [PATH]` and sees who, how, when, why and what-else for every event. Lineage is stored in the history database, so it survives restarts.

**What each `history` line gains**, after the existing `seq, op, path, old, new`:
- `actor`
- `via`
- `at`
- `reason`
- `change`

**Rules that always hold:**
1. **One command, one change.** All events one command or one reconcile produces share one `change`. No two commands share one.
   - A `set` that first records hand edits produces two changes: the hand edits (`via: file`, actor unknown) and its own value change (`via: cli`, the CLI actor).
   - The first import of a theatre is its own change (`via: import`, actor unknown), even when a CLI command triggered it.
   - Each pass of `watch` that records something is one change.
2. **Actor comes from `TROUPE_ACTOR`.**
   - `human:<id>` gives a human actor and `agent:<id>` gives an agent actor.
   - If it is unset, the actor is `{"kind":"human","id":<login name>}`.
   - Any other value exits 2, with stderr naming `TROUPE_ACTOR`. This includes an empty `<id>`, an unknown kind, or a set but empty variable.
3. **`reason` is only on `set`'s own events.** It holds the `--reason TEXT` value verbatim, or `null` if none was given. Reconcile and import events always have `reason: null`.

**Choices I made where the contract is silent** (each will be recorded in the spec):
- **Where `TROUPE_ACTOR` is checked:** every `troupe config` command checks it before loading anything, including commands that never record a CLI actor (`get`, `show`, `history`, `watch`). One rule everywhere, and a bad value is caught early.
- **Login name:** the "login name" is the operating system's login name. If it can't be determined, the id is `null` rather than a guess.
- **Timestamps:** all events of one change share one `at`, in whole seconds, UTC, ending in `Z` (for example `2026-10-04T00:42:17Z`).
- **`--reason` scope:** only `set` accepts `--reason`. A `set` that changes nothing records nothing, so its reason is dropped.
- **Change id format:** each `change` is an opaque, unique string, and nothing should depend on its format.
- **Unchanged:** the order of existing fields, exit codes, and the files touched are all as before.

Does this match what you want, or should I correct anything before I write the spec?

WAITING_FOR_DISCOVERY_INPUT