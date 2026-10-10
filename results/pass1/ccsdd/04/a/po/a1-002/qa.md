Q1: I've planned step 4 and committed it on `main` as `eb52c82`. This was only the planning step: none of the lineage behaviour is built yet, and nothing was pushed.

**What I found:** the request needs one new spec, `config-lineage`, plus small updates to three existing specs. Today a history event records only what changed (the step, path, old and new values); nothing says who changed it, how, when, why, or which command it came from. Every change already comes from one of three places (the first import, the check that picks up hand edits, and `set`), and each one saves its events together in one database write. That makes it a natural place to attach lineage.

**Chosen approach:**
- **Stamp the lineage once per command.** Who, how, when, why and a change id are built once for each import, hand-edit check or `set`. They are added to every event that command saves. Because each command's events are already saved in one go, they always share one `change`, and the step numbers in `history` stay the same.
- **Check `TROUPE_ACTOR` before anything opens.** It is read and validated in the CLI part of the code, so a bad value exits with code 2 and creates nothing. The core code never reads the environment.
- **`set --reason TEXT`** is a new option on `set`.
- **Existing history stays readable.** History saved before step 4 is converted when it's read, not refused or rewritten.

**Choices I proposed (the requirements step settles them):**
- Every `troupe config` command checks `TROUPE_ACTOR`, not just `set`.
- A `TROUPE_ACTOR` that is set but empty, or written `human:` with no id, exits with code 2.
- If no login name can be found, the actor is `{"kind":"human","id":null}`.
- `at` has the fixed form `YYYY-MM-DDTHH:MM:SS.ffffffZ`, taken once per change.
- `change` is a random UUID.
- A `set` records two separate changes: first the hand edits it picked up (as a `file` change), then its own values (as a `cli` change).

**Decision for you:** history saved before step 4 has no record of where it came from. For those older `set`/`remove` events, `via` could be either `cli` or `file`, and there's no way to tell. I propose `"via": null` rather than guessing `"cli"`, which matches "say so explicitly rather than guessing" but is outside the three values in the contract. This only affects history saved before step 4.

Files written:
- `.kiro/specs/config-lineage/brief.md`
- `.kiro/steering/roadmap.md` (new "Step 4 — Lineage" section and a spec list entry)

**Next step:** `/kiro-spec-init config-lineage`, or `/kiro-spec-quick config-lineage` to go straight through. The updates to config-foundation, config-set-writeback and config-file-sync follow once the new spec's requirements are settled.
A1 (po): No. The Lineage section says every `history` event has `"via"` set to one of `"import"`, `"cli"` or `"file"`. That rule covers every event, including ones saved before step 4, so `null` is not allowed for `via`.