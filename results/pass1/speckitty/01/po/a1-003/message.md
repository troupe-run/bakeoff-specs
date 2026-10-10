I've loaded the charter's plan context. The riskiest scenario is User Story 2: after `set`, the only bytes that change are the ones the contract requires (FR-014 to FR-020). How we write back decides almost everything else, so I'm asking this first.

**What I found:** the charter (TROUPE-001) mentions "format-preserving YAML round-tripping". But a ruamel.yaml load-modify-dump is only *mostly* format-preserving. It normalises indentation, can re-flow long lines and folded scalars, and rewrites quoting, spacing in flow collections and comment spacing. Several contract rules can't be met that way: folded paragraphs keeping their bytes, comments moved back to their previous column, and new entries placed below trailing comments.

**Options:**
- **(A) Recommended: find the node, then replace only its text.**
  - A parser locates the exact character span of the target node (start/end marks, block or flow, quoting style, indicator, end-of-line comment column).
  - A small set of edit rules builds only the replacement text: one rule each for quoting, block/flow collections, literal/folded blocks, entry placement and comment columns.
  - That text is spliced into the original file text, and the file is written atomically (temp file + rename).
  - The document is never re-serialised, so untouched bytes are identical by construction.
  - This still meets TROUPE-001's intent, and I'd record the reasoning in `research.md`.
- **(B) ruamel.yaml round-trip dump.** Less code, but it predictably breaks NFR-001 on real files and would need fix-ups that amount to (A) anyway.
- **(C) Something else.**

Reply A, B or C. After that I have one more question, about how history is stored under `.troupe/`, then I'll give you an Engineering Alignment summary to confirm.

WAITING_FOR_PLANNING_INPUT