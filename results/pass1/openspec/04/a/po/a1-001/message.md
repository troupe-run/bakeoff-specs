I've written the plan for step 4 as the OpenSpec change `config-lineage` and committed it on `main` as `0ed9e55` (not pushed). It follows the same pattern as the earlier "Plan …" commits. `openspec validate --strict` passes. No code has been changed yet.

**What's in `openspec/changes/config-lineage/`:**
- **`proposal.md`**: why lineage is needed, what changes, and which specs are affected.
- **Specs:**
  - A new `config-lineage` spec. It covers the five new keys on each `history` line (`actor`, `via`, `at`, `reason`, `change`), how a command's actor is found, `--reason`, how change ids group events, and how events recorded before this step are shown.
  - Changes to `config-cli`: `set … [--reason TEXT]`, and every subcommand now reads `TROUPE_ACTOR`.
  - Changes to `config-history`: the exact keys and their order on each line.
- **`design.md`**: the decisions D1–D8.
- **`tasks.md`**: three groups. Group 1 adds lineage to the store, with a test against a real database made by the current code. Group 2 wires it through the commands, with tests and the README. Group 3 runs the full checks and commits.

**Choices I made where the request leaves room:**
- **A `set` that picks up a hand edit records two changes.** The hand edit gets its own change id, with an unknown actor and `via: "file"`. The `set`'s own edits get a separate change id, with the command's actor and reason. The import is always its own change.
- **`TROUPE_ACTOR` is checked on every subcommand.** That includes `history`, `get`, `show` and `watch`, even though only `set` records an actor. A bad value exits 2 before anything is loaded or created.
- **What counts as a bad `TROUPE_ACTOR`:** a value set but empty, an empty id, or a kind like `Human:` in other letter case. The id is everything after the first `:`, so `agent:team:coder` gives the id `team:coder`.
- **Login name:** when `TROUPE_ACTOR` is unset, the actor is the human with the current login name. If the name can't be found, the id is `null`.
- **`at`** is the time the event library already stores with each event, converted to UTC as `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
- **Change ids** are random UUIDs.
- **`--reason ""`** is recorded as `""`, not `null`.

**Decision for you:** theatres used before this step have events with no lineage saved. My plan keeps them as they are on disk and shows them with an unknown actor. Their `via`, `reason` and `change` show as `null`, except old imports, which show `via: "import"`. Their `at` comes from the stored time. This goes slightly beyond your contract, which allows only three values for `via`. I chose it because the request says to state what's unknown rather than guess. If you'd rather old events show a contract value anyway, the specs and design need a small change before implementation.

The plan is ready for review. When you want to go ahead, run `/opsx:apply`.