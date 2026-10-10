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

Q2: I've changed the plan so `via` is never `null`, and committed it on `main` as `bf996c1`.

For history saved before step 4:
- **Import events** get `"via": "import"`.
- **`set` and `remove` events** get `"via": "cli"`. The old history can't tell a `set` apart from a hand edit picked up from the files, so this is a best guess, not a recorded fact. I chose `"cli"` because `set` existed in every earlier step, while picking up hand edits only started in step 2. `"file"` would be just as much a guess, and wrong for every step 1 event.
- **The other fields** say plainly what isn't known. The actor stays `{"kind":"unknown","id":null}`, the reason is `null`, and `at` comes from the time the event was originally saved. `change` is `"legacy:<seq>"`, one per event, because how those events were grouped was never stored.

The brief (open choice 1) records this as your decision and flags the best-guess `via` as a known limitation. It also says when to revisit it: if old hand-edit events turn out to be distinguishable from `set` events after all. The roadmap's open question is now a recorded decision.

Next step is still `/kiro-spec-init config-lineage`.
A2 (po): /kiro-spec-init config-lineage

Q3: ## Generated Feature Name
`config-lineage`: I kept the name from the discovery step. Its folder already held only `brief.md`, so there was no naming conflict.

## Project Summary
Step 4 adds who, how, when, why and a change id to every `troupe config history` event, so changes made by people and AI agents can be audited.

## Created Files
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-lineage/spec.json`: phase `initialized`, language `en`, nothing approved yet.
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-lineage/requirements.md`: the project description only, with no requirements yet. It contains:
  - the problem, the current state and the desired outcome, taken from the brief;
  - the step 4 Lineage contract, copied word for word;
  - your decision that `via` is never `null`, including for history saved before step 4.

This is committed on `main` as `f2d031f`.

## Next Step
```
/kiro-spec-requirements config-lineage
```
A3 (po): /kiro-spec-requirements config-lineage