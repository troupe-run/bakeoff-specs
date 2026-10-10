## Generated Requirements Summary
The requirements for `config-lineage` are written and committed on `main` as `4f2187a`, but not yet approved. There are six requirement areas:
1. **Lineage on every `history` line**: the five members come after `seq, op, path, old, new`, in a fixed order and form. `at` is always `YYYY-MM-DDTHH:MM:SS.ffffffZ`, and filtering by PATH doesn't change any of them.
2. **Lineage of each producer**:
   - An import is `via: "import"` with an unknown actor.
   - Picking up hand edits from the files (before a command, or on each `watch` sync) is `via: "file"` with an unknown actor.
   - A `set` is `via: "cli"` with the declared actor and its reason.
   - Each of these is one change with one shared `at`, and change ids are never reused.
3. **`TROUPE_ACTOR`**:
   - It must be `human:<id>` or `agent:<id>`, with the id kept exactly as given.
   - If it is unset, the login name is used, or `{"kind":"human","id":null}` when no login name can be found.
   - Anything else, including an empty value, exits with code 2 on every subcommand, before anything is created.
   - `--help` still works.
4. **`set --reason TEXT`**: the text is stored exactly as given, and an empty TEXT gives `""`. It is never added to the hand-edit or import events the same command records. Giving it twice or without TEXT exits with code 2.
5. **Survives restarts**: lineage is stored with the events, and a later `history` prints the same lineage whatever its own environment is.
6. **History saved before step 4**:
   - The actor is unknown and the reason is `null`.
   - `at` is the time the event was saved.
   - `via` is `"import"` for imports and `"cli"` for `set`/`remove`.
   - The old imports share one change; every other old event gets its own change.
   - These old events are never rewritten.

The Boundary Context lists the notes to add to config-foundation, config-set-writeback and config-file-sync, and 10 choices I made where the contract says nothing.

## Document Status
- `.kiro/specs/config-lineage/requirements.md` now has the Introduction, Boundary Context and Requirements 1–6.
- `.kiro/specs/config-lineage/spec.json` is set to `requirements-generated`, with `requirements.generated: true` and `approved: false`.

## Review Gate
The review gate passed on its second pass. Every heading has a numeric ID and every criterion starts with an EARS keyword. In the first pass I made two fixes: 5.4 became an "If … then" error case, and I added 3.8 so `--help` works whatever `TROUPE_ACTOR` holds.

## Next Steps
Three choices are worth a look before you approve:
- **Every subcommand checks `TROUPE_ACTOR`**, including `get`, `show` and `history`, not just `set`.
- **A set but empty `TROUPE_ACTOR` exits with code 2** instead of being treated as unset.
- **Giving `--reason` twice exits with code 2** instead of the last one winning.

Then run:
```
/kiro-spec-design config-lineage
```
Or run `/kiro-validate-gap config-lineage` first to check the requirements against the existing code.