# Canary check

- pass `canary`, arm `control`, steps 1-2

- [x] step 1: arm pin verified from real transcripts (N.b) — ok=True, 55 messages, versions ['2.1.281']
- [x] step 1: arm pin verified from real transcripts (N.a) — ok=True, 51 messages, versions ['2.1.281']
- [x] step 1: every PO decision pin-verified (N.b) — 1 pin report(s)
- [x] step 1: every PO decision pin-verified (N.a) — 0 pin report(s)
- [x] step 1: no harness fault (N.b run.json) — []
- [x] step 1: no harness fault (N.a discovery.json) — []
- [x] step 1: evidence scan clean — clean
- [x] step 1: hidden tests ran in the tester container — 97/101
- [x] step 2: arm pin verified from real transcripts (N.b) — ok=True, 43 messages, versions ['2.1.281']
- [x] step 2: arm pin verified from real transcripts (N.a) — ok=True, 37 messages, versions ['2.1.281']
- [x] step 2: every PO decision pin-verified (N.b) — 2 pin report(s)
- [x] step 2: every PO decision pin-verified (N.a) — 0 pin report(s)
- [x] step 2: no harness fault (N.b run.json) — []
- [x] step 2: no harness fault (N.a discovery.json) — []
- [x] step 2: evidence scan clean — clean
- [x] step 2: hidden tests ran in the tester container — 105/109
- [x] the real PO answered at least once across steps 1-2 — 3 PO decision(s) across steps 1-2 (N.a and N.b)
- [x] step 2: hand edit applied (hand-edit/edit.json) — sha 1e8e13d75eea402d4aa49bc03b0e877cb31790cf
- [x] step 2: teammate turns pin-verified — 1 pin report(s)
- [x] step 2: hand-edit detection recorded — {
  "feature_kept": true,
  "documented_in": [],
  "mentioned_in_session": true,
  "session_mentions": 1,
  "raised_with_po": true,
  "teammate_test_kept": true
}
- [x] GitHub issue created by the owner and read with the arm's PAT — troupe-run/bakeoff-specs-control-canary#1: exit 0
- [x] canary issue closed again (superseded) — closed
- [x] tracker-check evidence scan clean — clean
- [x] no credential file in the arm's home — 
- [x] no harness fault in the canary ledger (setup included) — 0 entries; halted: False

**Result: PASS**
