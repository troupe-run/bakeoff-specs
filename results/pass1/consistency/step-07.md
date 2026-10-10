# Consistency check — pass1 step 7: confirmed

## Round 1 (2026-10-07T08:39:42+00:00)

### Q1

Question: When a remote include's content changes on the server, should the change be recorded in history like a hand edit at the next reconcile, with watch polling only local files (A), should watch also poll the URLs on a slower interval (B), should remote leaves be kept out of history (C), or something else?
  speckitty (step 7): The contract says a remote include "is fetched when the configuration loads" (Remote includes and schema). Reconcile compares "the files with the configuration and emit[s] a set/remove event for each leaf that differs"; every command except `history` reconciles first; `watch` reconciles "within 2 seconds of any change to the config file or an included file" (Sync with files); file-originated events have actor {"kind": "unknown", "id": null} (Lineage). The contract does not say whether content that changes on the server counts as a change for reconcile or for `watch`. Treat that as out of contract: your choice - state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q2

Question: Is a 10-second fetch timeout acceptable?
  speckitty (step 7): The contract says "A failed fetch → exit 4" (Remote includes and schema). It doesn't define a timeout or what counts as failing. Out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q3

Question: Should a relative `file:` include inside a remotely fetched file resolve against the URL's directory and be fetched, never reading the local disk?
  speckitty (step 7): The contract defines remote includes as strings starting `https://` or `http://`, "fetched when the configuration loads" (Remote includes and schema). It doesn't say how a relative include inside fetched content resolves. Out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q4

Question: Should `!literal` on a value that is not a string exit 4?
  speckitty (step 7): The contract says "A string tagged `!literal` is a literal" (Remote includes and schema). It doesn't define `!literal` on a non-string. Out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q5

Question: Should every YAML tag other than `!literal` still exit 4, as in step 6?
  speckitty (step 7): The contract mentions only `!literal` ("A string tagged `!literal` is a literal", Remote includes and schema). It does not define other tags. Out of contract: your choice - state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

Owner: {"Q1": {"ok": true, "note": "", "seconds": 398.39513449999504}, "Q2": {"ok": true, "note": "", "seconds": 9.181666040996788}, "Q3": {"ok": true, "note": "", "seconds": 9.188678874983452}, "Q4": {"ok": true, "note": "", "seconds": 9.19875433400739}, "Q5": {"ok": true, "note": "", "seconds": 9.180242790986085}}
