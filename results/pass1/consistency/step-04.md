# Consistency check — pass1 step 4: confirmed

## Round 1 (2026-10-04T05:08:53+00:00)

### Q1

Question: Should history events recorded before step 4, which have no lineage, be left out of contract without an upgrade, or should the spec upgrade that existing history somehow?
  speckit (step 4): The contract says every `history` event has the Lineage fields. It doesn't say anything about events recorded before step 4, or about upgrading stored history. Treat that as out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

Owner: {"Q1": {"ok": true, "note": "", "seconds": 15422.973949208157}}
