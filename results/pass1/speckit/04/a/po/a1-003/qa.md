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