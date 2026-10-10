I've written the plan for issue #2 as the change `config-anchors-and-aliases` in `openspec/changes/config-anchors-and-aliases/`. `openspec validate --strict` passes. I haven't changed any code, and nothing is committed yet.

**The bug on `main` today:** the reported behaviour can't happen on `main` as it stands. Anchors and aliases aren't supported, so the reporter's file fails to load with exit 4. To fix the issue, this change has to add anchor support with the contract's rules from the start.

**Artifacts:**
- **`proposal.md`**: the issue and what changes:
  - anchors, aliases and `<<` merge keys load;
  - setting a value at the anchor changes it for everyone;
  - setting a path reached through an alias exits 3 and mentions `--expand-alias`;
  - the new `set --expand-alias` flag gives that path its own copy;
  - merge keys are never written.
- **`specs/`**:
  - `config-loading`: a new requirement for anchors, aliases and merge keys.
  - `config-set`: four new requirements. One scenario is the issue's exact file and command.
  - `config-cli`: `set` now lists `--expand-alias`.
- **`design.md`**: how it's built. An alias is the same node as its anchor, so `get`, `show` and history need no changes. Two checks in the planner catch writes through an alias or a merge key. Expansion replaces one alias, reloads and plans again, which handles nested aliases. The copy is the anchored node as written.
- **`tasks.md`**: 6 groups. Each feature group includes its own tests and README updates, ending with a full test run, validation and commits.

**Choices I made where the contract is silent** (recorded in design.md D8; tell me if any should change):
- **Merge keys:** `<<` is applied when reading. Setting a value that a merge key supplies exits 3, even with `--expand-alias`. Writing a local key instead would quietly shadow or drop other merged values.
- **Anything holding `<<`:** deleting or replacing a mapping that contains a `<<` entry also exits 3.
- **What the copy contains:** the node exactly as the user wrote it. Quoting and number formats are kept, nested aliases stay aliases, and include strings stay include strings.
- **When the flag expands:** it expands every alias the set would otherwise be refused for, including nested ones. With no alias involved it does nothing, so re-running a command is safe.
- **Existing comments:** if the alias's line already has a comment, it stays and the `# expanded from …` comment goes after it.
- **Aliases inside `{…}` or `[…]`:** these can't be expanded and exit 3.
- **Includes:** a path through an alias in an included file is refused, even when the write would go into an override.

To start implementing, run `/opsx:apply`.