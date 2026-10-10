I've read the loader, tree, placement, write-back and verification code, and I have a design for your approval before I write the plan files.

**Branch:** we're on `fix/troupe-config-anchor-aliases`, which is also the planning base. Spec Kitty also reports `fix/troupe-config-anchor-aliases` as its merge target, and the helper says the current branch matches it. Getting to `main` takes the local merge we agreed earlier.

**Key finding:** the YAML library (ruamel) returns the *same node object* for every alias, so the positions of `*d` in the text are lost. Separately, an anchored block mapping's position currently starts at `&d` rather than its first key, and the write-back code relies on the first-key position.

## Engineering Alignment (for confirmation)

1. **Parsing (`yamlcore`).** Build our own small composer from ruamel's parser events, still the only module that imports ruamel. It records:
   - each anchor `&name` with its span;
   - each alias occurrence `*name` with its own span and the node it refers to.

   Node positions start at the content, not at the anchor, so existing write-back code keeps working unchanged. Undefined or recursive aliases and any tag exit 4. Aliases and anchors in a `set` VALUE are still refused (exit 2).
2. **Tree.** A new `AliasNode` (alias span, name, the anchored node) is transparent to readers, like an include. `get`, `show`, `show --sources`, history leaves and reconcile then see resolved values with no other change. The anchored node is one shared object, so a write at the anchor shows up through every alias (FR-003).
3. **Merge keys.** A mapping holding `<<` becomes a read-only view over the mapping as written. Merged-in values arrive wrapped as aliases marked "via merge" and appear where the `<<` entry is written. Writers only ever see the mapping as written. The loader rejects (exit 4) a `<<` value that isn't mappings or aliases to mappings, and a `<<` beside `$ref`.
4. **Where the alias rule lives.** `placement` alone decides "reached through an alias". It looks for an alias on the route to PATH and on the side a new key would be written to; the second case covers aliases inside step-5 override mappings. Without the flag it exits 3, naming the path and the alias, with stderr mentioning `--expand-alias`. Through `<<` it exits 3 whether or not the flag is given.
5. **Expansion (new `writeback/aliases.py`).** One alias at a time, replaced in memory:
   - the key or dash line ends with `  # expanded from *d by troupe`;
   - the copy is written in block style at the file's indentation, from the anchored node's content;
   - anchors are left out of the copy and inner aliases stay aliases;
   - single-line scalars keep their written text.

   The tree is then reloaded in memory and placement runs again, until the path is free of aliases. The `set` is then written into the copy. The result is one verified write of one file.
6. **Verification.** Today's "nothing else changed" check gains three rules:
   - an alias stays equal if it still points at the same anchor (same name and same path), without descending into it;
   - on the route only, and only with the flag, an alias may become a copy of its anchored content;
   - anchor names outside PATH must not change.
7. **Writing next to an anchor.** Kind-changing replacement keeps `&name` on the key's line, so `set defaults '{model: x}'` keeps `&d` (C5).
8. **CLI.** Add `set --expand-alias` as a store-true flag. History, lineage and recording stay as they are (C11 follows from leaves being resolved).

**Two small spec additions I'd make in the plan commit:**
- `<<` beside `$ref` in a step-5 mapping-form include makes the file unloadable (exit 4). The merge of two merge mechanisms is undefined.
- `--expand-alias` exits 3 if the alias isn't on its key's or dash's line (`settings:` with `*d` on the next line). The contract puts the comment "on the key's line", and moving the alias would rewrite a line the user didn't ask to change.

**Known risks:**
- A file with many nested aliases expands exponentially in `show` and history. There are no performance targets, so I'm only noting it.
- Every `isinstance` dispatch over tree nodes needs an `AliasNode` branch. The plan will list all of them: leaves, `yamlout`, reconcile, values, placement, apply, merge and paths.

Do you approve this alignment, with or without changes?

WAITING_FOR_PLANNING_INPUT