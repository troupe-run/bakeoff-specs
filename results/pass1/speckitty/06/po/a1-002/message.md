I've recorded the decision. **I chose (A):**
- **Reading:** `<<` follows standard YAML merge rules. Keys written in the mapping itself win, and in `<<: [*a, *b]` the earlier source wins. This is the meaning every YAML reader gives the file, so `get` and `show` agree with what the user expects.
- **Writing:** a value that arrives through `<<` counts as reached through an alias, so `set` exits 3 and the error mentions `--expand-alias`. `set --expand-alias` on that path also exits 3, and the error says expanding would mean writing a merge key. Refusing can't lose data, troupe never writes `<<`, and nobody else's value changes without the explicit opt-in the reporter asked for. Option B would quietly override a shared value. Adding a key that doesn't exist yet straight into the mapping that holds `<<` is an ordinary write.

## Intent Summary (please confirm)

**Who and when:** a theatre owner who shares settings between agents with `&anchor` / `*alias` runs `troupe config set PATH VALUE`.

**Contract rules (step 6, Aliases):**
1. `set` on a path whose value is defined at an anchor changes it at the anchor, so every alias sees the new value.
2. `set` on a path reached through an alias exits 3, changes no file, and the error mentions `--expand-alias`. With the reporter's file, `set coder.settings.model sonnet` is refused and `defaults` and `reviewer` stay unchanged.
3. `set --expand-alias PATH VALUE` replaces that alias with a block-style copy of the anchored node and puts `  # expanded from *d by troupe` on the key's line. It then sets the value in the copy. Nothing else changes, and other aliases still point at the anchor.
4. Troupe never writes `<<`.

**Rule that must always hold:** without `--expand-alias`, a `set` never changes a value that any other path shares through an alias. With it, the only bytes that change are the alias, which becomes the copy plus the comment, and the value being set.

**Choices the contract leaves open (my recommendation, each to be recorded with its reason):**

**Reading files**
- **C1 Reading:** anchors and aliases now load. `get` and `show` print resolved values, with no `&`, `*` or `<<` in the output. `show --sources` attributes an aliased value to the file that holds the anchor.
- **C2 Tags** (`!foo`) still exit 4. Step 6 only adds anchors and aliases.
- **C3 Includes:** a file can't load (exit 4) if it puts an anchor on an include reference (`$ref` or `file:`), on a node that contains one, or on a mapping key, or if it aliases such a node or uses an alias as a key. This keeps the step 5 rule and avoids include and alias semantics that the contract doesn't define.

**`set` without the flag**
- **C4 A value that is just an alias** (`model: *m`) counts as reached through an alias, so `set` exits 3. With `--expand-alias` it becomes `model: <new>  # expanded from *m by troupe`.
- **C5 A whole anchored collection:** replacing it (`set defaults '{model: x}'`) keeps its anchor, so aliases follow. That's contract rule 1 applied to collections.
- **C6 New keys** under a path reached through an alias (`set coder.settings.temperature 0.2`) exit 3. With `--expand-alias` the key is added to the copy. A new key under the anchored node itself appears everywhere.

**How `--expand-alias` builds the copy**
- **C7 Nested aliases:** `--expand-alias` expands every alias the path goes through, outermost first, and each one gets its own comment. Aliases inside the copy that aren't on the path stay as aliases.
- **C8 What goes into the copy:** anchors inside the copied node are left out of the copy. Keeping them would redefine the anchor name and repoint later aliases. Comments inside the anchored node aren't copied. Scalars keep their written form.
- **C9 Where the comment goes:**
  - For an alias that is a list item (`- *d`), the comment goes on the dash line.
  - For an alias inside a flow collection (`{settings: *d}`), the command exits 3, because a block copy can't go there.
  - If the alias's line already has a user comment, the command exits 3 rather than drop that comment.

**Flag and history**
- **C10 Flag scope:** `--expand-alias` is accepted only by `set`, like `--reason` and `--in-include`. Other subcommands exit 2. On a path that doesn't go through an alias it has no effect.
- **C11 History, watch and reconcile** record a change for every path whose resolved value changed. A change at an anchor therefore records `defaults.model`, `coder.settings.model` and `reviewer.settings.model` in one batch. An expand-and-set records only the path that was set.
- **C12 Earlier behaviour:** step 1–5 behaviour for files without anchors stays exactly as it is.

Reply **"confirmed"** or correct any item, and I'll write and commit `spec.md` plus the quality checklist.

WAITING_FOR_DISCOVERY_INPUT