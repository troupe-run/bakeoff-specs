# Consistency check — pass1 step 1: confirmed

## Round 1 (2026-10-01T12:40:29+00:00)

### Q1

Question: After the initial import, if a file is hand-edited, are the files on disk or the stored event-sourced projection the source of truth for show and set?
  speckitty (step 1): A
   The files are the truth.** `show` and `set` always read the files as they are on disk. The stored projection is only the change history, so a hand edit appears in `show` but produces no history event. A later `set` records its `old` value as what was in the file.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

Owner: {"Q1": {"ok": true, "note": "", "seconds": 2133.012895792024}}
