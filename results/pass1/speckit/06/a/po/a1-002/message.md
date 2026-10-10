I've recorded your answer and my three choices in the assessment and committed it to `main` (5863d66). Nothing is fixed yet. The decisions:

1. **Flow-style anchors (your answer):** `--expand-alias` always writes the copy in block style. The anchored node itself stays exactly as written. The copy keeps each value's original spelling, including quotes and number formats.
2. **Reading through merge keys: no change.** `get` and `show` keep showing `<<` as a plain key, so `get x.a` still fails (exit 5) when `a` only comes from `<<: *b`. Resolving merge keys on read would change what `get`, `show` and `history` print for files people already have. That's a new feature, not part of this bug. Writing stays safe because any path containing `<<` is refused with exit 3.
3. **`--expand-alias` when the path has no alias: run a plain set.** The result is byte-for-byte what you'd get without the flag. With no alias there's nothing to expand, and the write changes only that path. Refusing wouldn't protect anything, and scripts that always pass the flag would fail for no reason.
4. **A path through more than one alias: expand every alias on the path in one write,** starting with the outermost. Each expanded key gets its own `# expanded from *<name> by troupe` comment. Aliases that aren't on the path stay as they are. This changes my earlier recommendation to expand only the outermost alias. That would leave the value behind the inner alias, and setting it would change everything else using that inner anchor, which is exactly what this bug report objects to.

I also settled one detail I had left open. If the anchored node contains its own anchor (`&x`), that `&x` is left out of the copy. Otherwise, later `*x` aliases would silently start pointing at the copy.

I've added tests for each decision to the assessment's test list. The assessment has no open questions left.

Next step: `/speckit-bug-fix slug=alias-set-changes-anchor`