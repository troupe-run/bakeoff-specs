Q1: I've finished the discovery for issue #2 and committed it on `main` as `2627541` (not pushed). Nothing in the code has changed yet, so the alias behaviour itself still has to be built.

**What the issue really is.** I ran the reporter's file against current `main`. Both `set coder.settings.model sonnet` and `get` exit 4 with "anchor '&d' is not supported", and the file is left untouched. So the corruption they describe can't happen here, because anchors are still refused (decision H, which held them back until step 6). The issue is really the step 6 "Aliases" contract: files with anchors should load, and `set` should follow the new rules.

**Path:** one new spec, `config-aliases`, plus short step-6 notes in the `config-foundation` and `config-set-writeback` specs. Your instructions said to proceed, so I chose this path myself instead of stopping to ask. It's easy to change if you'd rather go another way.

**Approach:** this follows the same pattern as step 5.
- When loading, every alias is replaced by the content of its anchor, and each node reached that way remembers which alias it came through.
- That means `get`, `show`, `history`, reconcile and `watch` need no changes.
- Before writing, `set` checks the path. If it passes through an alias, it refuses with exit 3 and mentions `--expand-alias`. A path that only touches the anchor is written at the anchor, so every alias sees the change.
- `--expand-alias` first swaps the alias for a block-style copy with the `# expanded from *<name> by troupe` comment, then does the normal `set` on the copy. Both changes are written together and checked once.

**Open choices for the requirements step.** The brief lists 12 with cautious defaults; these are the ones most worth your attention:
1. **Merge keys (`<<`):** still exit 4 when loading. The contract only says they're never written.
2. **Setting the alias's own key** (for example `set coder.settings {…}`): also exit 3 unless `--expand-alias` is given.
3. **Key line that already has a comment:** expansion is refused with exit 3, rather than replacing or editing the user's comment.
4. **Alias inside a flow collection:** expansion is refused with exit 3.
5. **Several aliases on one path:** each is expanded, outermost first, and the copies don't repeat `&name`.

**Files:**
- `.kiro/specs/config-aliases/brief.md` (new)
- `.kiro/steering/roadmap.md` (new "Step 6" section and spec list entry)

**Next step:** run `/kiro-spec-init config-aliases`, or `/kiro-spec-quick config-aliases` to go straight through requirements, design and tasks. The issue is fixed only once `/kiro-impl config-aliases` has been run and committed. Afterwards, `config-foundation` and `config-set-writeback` need their notes added with `/kiro-spec-requirements`.
A1 (po): /kiro-spec-init config-aliases

Q2: ## Generated Feature Name
`config-aliases`: I used the directory discovery had already created, since it held only `brief.md` and no `spec.json`. The name matches the step 6 contract section "Aliases".

## Project Summary
Step 6 lets anchors and aliases load and be read everywhere. `set` changes a value at its anchor, refuses a path reached through an alias with exit 3, and `set --expand-alias` makes a commented copy of the alias before setting the value in it (tracker issue #2).

## Created Files
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-aliases/spec.json`: language `en`, phase `initialized`, nothing approved yet.
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-aliases/requirements.md`: the project description is the brief, with its headings moved down one level. That gives problem, current state, desired outcome, approach, scope and the 12 open choices.

Both files are committed on `main` as `79cbad6` (not pushed).

## Next Step
```
/kiro-spec-requirements config-aliases
```
That step writes the requirements and settles the 12 open choices, using the cautious defaults proposed in the brief.
A2 (po): /kiro-spec-requirements config-aliases