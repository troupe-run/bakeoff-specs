# Consistency check — pass1 step 6: confirmed

## Questions answered by the fallback in step 5's scored run (informational)

- openspec: Should the change's spec deltas be synced into openspec/specs/ before archiving (the recommended option), or should the change be archived without syncing?
- control: When the same file is included in two places in one theatre, should `set --in-include` keep refusing with exit 3 because the new key would appear under both, or skip that check because writing to the shared file is deliberate?

## Round 1 (2026-10-06T03:17:32+00:00)

### Q1

Question: Should reading (get/show) resolve merge keys, so that `get x.a` succeeds when `a` comes from `<<: *b`?
  speckit (step 6): The contract's Aliases section (from step 6) covers writing only: setting a value defined at an anchor changes it at the anchor; setting a path reached through an alias -> exit 3 with stderr mentioning `--expand-alias`; `set --expand-alias PATH VALUE` "replaces that alias with a block-style copy of the anchored node, puts the end-of-line comment `# expanded from *<name> by troupe` on the key's line ... and then sets the value in the copy. Nothing else changes; other aliases still refer to the anchor." Merge keys (`<<`) are never written. Flow-style anchor: the copy is block-style, as the contract says; the anchor itself does not change ("Nothing else changes"), so neither converting the anchor nor refusing is what the contract describes. Reading through merge keys, `--expand-alias` when the path has no alias, and paths through more than one alias: the contract does not define these. They are out of contract: your choice - state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q2

Question: What should `set --expand-alias` do when the path does not pass through any alias?
  speckit (step 6): The contract's Aliases section (from step 6) covers writing only: setting a value defined at an anchor changes it at the anchor; setting a path reached through an alias -> exit 3 with stderr mentioning `--expand-alias`; `set --expand-alias PATH VALUE` "replaces that alias with a block-style copy of the anchored node, puts the end-of-line comment `# expanded from *<name> by troupe` on the key's line ... and then sets the value in the copy. Nothing else changes; other aliases still refer to the anchor." Merge keys (`<<`) are never written. Flow-style anchor: the copy is block-style, as the contract says; the anchor itself does not change ("Nothing else changes"), so neither converting the anchor nor refusing is what the contract describes. Reading through merge keys, `--expand-alias` when the path has no alias, and paths through more than one alias: the contract does not define these. They are out of contract: your choice - state which you chose and why.
  OVERLAPS Q3 (a similar question this step)
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q3

Question: What should `set --expand-alias` do when the path passes through more than one alias?
  speckit (step 6): The contract's Aliases section (from step 6) covers writing only: setting a value defined at an anchor changes it at the anchor; setting a path reached through an alias -> exit 3 with stderr mentioning `--expand-alias`; `set --expand-alias PATH VALUE` "replaces that alias with a block-style copy of the anchored node, puts the end-of-line comment `# expanded from *<name> by troupe` on the key's line ... and then sets the value in the copy. Nothing else changes; other aliases still refer to the anchor." Merge keys (`<<`) are never written. Flow-style anchor: the copy is block-style, as the contract says; the anchor itself does not change ("Nothing else changes"), so neither converting the anchor nor refusing is what the contract describes. Reading through merge keys, `--expand-alias` when the path has no alias, and paths through more than one alias: the contract does not define these. They are out of contract: your choice - state which you chose and why.
  OVERLAPS Q2 (a similar question this step)
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

Owner: {"Q1": {"ok": true, "note": "", "seconds": 1004.500013249999}, "Q2": {"ok": true, "note": "", "seconds": 17.999864875004278}, "Q3": {"ok": true, "note": "", "seconds": 9.090175625009579}}
