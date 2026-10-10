Q1: I've assessed issue #2 and committed the assessment to `main` (3ff1a93). No source files are changed yet, so the bug itself is still unfixed.

Slug: alias-set-changes-anchor (I generated it; no slug was given)

- **Assessment:** `.specify/bugs/alias-set-changes-anchor/assessment.md`
- **Source:** fetched from GitHub with `gh`.
- **Verdict:** valid. I reproduced it on `main`.
- **Severity:** high. It silently changes other agents' settings with exit 0.

**What I reproduced**
- **The report:** `set coder.settings.model sonnet` exits 0 and rewrites `defaults: &d`, so `reviewer` changes too.
- **`--expand-alias`:** the option doesn't exist yet; `set` rejects it with exit 2.
- **New keys through an alias:** `set coder.settings.new 1` silently writes the key under `defaults`.
- **Anchored scalars:** with `v: &v 1` and `w: *v`, `set v 2` deletes the `&v`. The write is then refused (exit 3) only because the file would no longer load. This breaks the contract's first rule.
- **Merge keys:** `set 'x.<<' 7` writes a merge key, and `set 'x.<<.a' 7` changes the anchor. Both break "merge keys are never written".

**Root cause:** the YAML parser hands back an alias as the very same object as its anchor, and the loader never records which nodes were reached through an alias. So the edit lands on the anchor's text. The check run before writing was built for a file included twice, and it accepts the extra changes as intended. Also, an anchored node's text starts at the `&name` token, so replacing the whole node drops the anchor.

**Proposed fix:**
- Record in the loader when a node is reached through an alias, separately for each YAML file so a file included twice isn't mistaken for one.
- Refuse paths through an alias with exit 3 and a message naming `--expand-alias`; refuse any path containing `<<` the same way.
- Keep the `&name` when replacing an anchored value.
- Add `set --expand-alias`, which expands the alias in place and then makes the change as an ordinary set.

**Four questions for you, in the assessment:**
- Should reading resolve merge keys? Today `get x.a` fails when `a` comes from `<<: *b`.
- Should expanding a flow-style anchor like `&d {model: opus}` convert it to block style, or refuse?
- What should `--expand-alias` do when there's no alias on the path? I recommend running it as a plain set.
- What if a path passes through more than one alias? I recommend expanding only the outermost one.

Next step: `/speckit-bug-fix slug=alias-set-changes-anchor`
A1 (po+owner): On “Should reading (get/show) resolve merge keys, so that `get x.a` succeeds when `a` comes from `<<: *b`?”: The contract's Aliases section (from step 6) covers writing only: setting a value defined at an anchor changes it at the anchor; setting a path reached through an alias -> exit 3 with stderr mentioning `--expand-alias`; `set --expand-alias PATH VALUE` "replaces that alias with a block-style copy of the anchored node, puts the end-of-line comment `# expanded from *<name> by troupe` on the key's line ... and then sets the value in the copy. Nothing else changes; other aliases still refer to the anchor." Merge keys (`<<`) are never written. Flow-style anchor: the copy is block-style, as the contract says; the anchor itself does not change ("Nothing else changes"), so neither converting the anchor nor refusing is what the contract describes. Reading through merge keys, `--expand-alias` when the path has no alias, and paths through more than one alias: the contract does not define these. They are out of contract: your choice - state which you chose and why.

On “Should `--expand-alias` on an alias whose anchor is flow-style (e.g. `&d {model: opus}`) convert the copy to block style, or refuse?”: Convert it. The contract says `set --expand-alias PATH VALUE` replaces the alias with a block-style copy of the anchored node, so the copy is written in block style whatever style the anchor uses. Nothing else changes, so the anchored node itself stays as it is.

On “What should `set --expand-alias` do when the path does not pass through any alias?”: The contract's Aliases section (from step 6) covers writing only: setting a value defined at an anchor changes it at the anchor; setting a path reached through an alias -> exit 3 with stderr mentioning `--expand-alias`; `set --expand-alias PATH VALUE` "replaces that alias with a block-style copy of the anchored node, puts the end-of-line comment `# expanded from *<name> by troupe` on the key's line ... and then sets the value in the copy. Nothing else changes; other aliases still refer to the anchor." Merge keys (`<<`) are never written. Flow-style anchor: the copy is block-style, as the contract says; the anchor itself does not change ("Nothing else changes"), so neither converting the anchor nor refusing is what the contract describes. Reading through merge keys, `--expand-alias` when the path has no alias, and paths through more than one alias: the contract does not define these. They are out of contract: your choice - state which you chose and why.

On “What should `set --expand-alias` do when the path passes through more than one alias?”: The contract's Aliases section (from step 6) covers writing only: setting a value defined at an anchor changes it at the anchor; setting a path reached through an alias -> exit 3 with stderr mentioning `--expand-alias`; `set --expand-alias PATH VALUE` "replaces that alias with a block-style copy of the anchored node, puts the end-of-line comment `# expanded from *<name> by troupe` on the key's line ... and then sets the value in the copy. Nothing else changes; other aliases still refer to the anchor." Merge keys (`<<`) are never written. Flow-style anchor: the copy is block-style, as the contract says; the anchor itself does not change ("Nothing else changes"), so neither converting the anchor nor refusing is what the contract describes. Reading through merge keys, `--expand-alias` when the path has no alias, and paths through more than one alias: the contract does not define these. They are out of contract: your choice - state which you chose and why.