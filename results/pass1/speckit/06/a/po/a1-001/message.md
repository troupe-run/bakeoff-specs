I've assessed issue #2 and committed the assessment to `main` (3ff1a93). No source files are changed yet, so the bug itself is still unfixed.

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