The plan is written and committed, so planning is done; no code has changed yet. The working tree is clean.

**Branch**
- We're on `fix/troupe-config-anchor-aliases`, which is also the planning base.
- Spec Kitty reports `fix/troupe-config-anchor-aliases` as its merge target, and the current branch matches it.
- Getting to `main` takes the local merge at the end, with no push and no PR.

**The approach**
- **Reading:** troupe will read the parser's events directly. The YAML library otherwise returns the shared anchored node for every alias, which loses where each `*d` is written. Anchored values keep the same positions as plain ones, so the existing writers don't change.
- **Show and history:** a new alias node is passed through by readers, so `get`, `show`, `show --sources`, history and reconcile all see resolved values. Merge keys (`<<`) become a read-only view over the mapping as written.
- **The refusal:** one function in `placement.py` decides "reached through an alias". It either refuses with exit 3, with `--expand-alias` in the message, or hands over to a new `writeback/aliases.py`. That module writes the block copy and the `  # expanded from *d by troupe` comment, then troupe reloads in memory and places the value again. The result is one verified write of one file.
- **Safety net:** the "nothing else changed" check gains three rules. An alias still pointing at the same anchor counts as unchanged. On the route, and only with the flag, an alias may become a copy. Anchor names can't change outside PATH.
- **Replacing an anchored value** keeps its anchor, so `set defaults '{...}'` keeps `&d`.

**Spec changes you approved, each recorded with its reason:**
- **C9:** `--expand-alias` exits 3 when the alias isn't on its key's or dash's line.
- **C13:** `<<` beside `$ref` makes the file unloadable (exit 4).
- **C14 / FR-010:** anchors and aliases in a `set` VALUE are refused (exit 2).

**Main risks**
- Every place that branches on tree-node types needs an alias case. Research R-3 lists all nine.
- A file with deeply nested aliases expands exponentially in `show` and history. There are no performance targets, so this is noted rather than guarded.
- The existing anchor and tag refusal tests from steps 1 and 5 will be updated to the new error messages; the exit code stays 4.

**Commits**
- `2a2999b` adds the plan.
- `34643be` adds the other planning files and the spec changes, with the decision record.

Next is `/spec-kitty.tasks`. Bug `bakeoff-specs-speckitty-qht` stays claimed and open until the fix reaches `main`.

Files are in `kitty-specs/troupe-config-anchor-aliases-01M48SQ8/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `quickstart.md`
- `contracts/cli.md`