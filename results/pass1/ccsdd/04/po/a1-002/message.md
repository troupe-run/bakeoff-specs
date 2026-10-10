I've recorded that how pre-step-4 history is shown is our choice, not an open question for you. It's committed on `main` as `8d54867`.

**What I chose for events recorded before step 4:**
- **Same shape as new events:** they still get all five lineage fields, so every `history` line matches the contract and tools reading it need no special case.
- **`via`:** `"import"` for the first import, `"cli"` for `set`/`remove`. The stored data can't tell a CLI change from a file edit. `"cli"` stays within the three allowed values and matches where most of these events came from: every step-1 event, and every event a `set` recorded.
- **Unknown, not guessed:** the actor is `{"kind": "unknown", "id": null}` and `reason` is `null`, so nobody is credited with a change we can't attribute.
- **`at`:** the time each event was originally stored, which the event store already holds.
- **`change`:** the original import events share one id, since they were saved together. Every other old event gets its own id, because we can't prove which ones belonged together.

**Where it's written down:** the reasoning is Decision 5 in `.kiro/specs/config-lineage/research.md`. I also updated `requirements.md`, `design.md` (the trigger for revisiting it is now "a later contract step covers older history") and `brief.md` to match. No code changed.

Lineage is still not implemented. To build it, run:

```
/kiro-impl config-lineage
```