I've changed the plan so `via` is never `null`, and committed it on `main` as `bf996c1`.

For history saved before step 4:
- **Import events** get `"via": "import"`.
- **`set` and `remove` events** get `"via": "cli"`. The old history can't tell a `set` apart from a hand edit picked up from the files, so this is a best guess, not a recorded fact. I chose `"cli"` because `set` existed in every earlier step, while picking up hand edits only started in step 2. `"file"` would be just as much a guess, and wrong for every step 1 event.
- **The other fields** say plainly what isn't known. The actor stays `{"kind":"unknown","id":null}`, the reason is `null`, and `at` comes from the time the event was originally saved. `change` is `"legacy:<seq>"`, one per event, because how those events were grouped was never stored.

The brief (open choice 1) records this as your decision and flags the best-guess `via` as a known limitation. It also says when to revisit it: if old hand-edit events turn out to be distinguishable from `set` events after all. The roadmap's open question is now a recorded decision.

Next step is still `/kiro-spec-init config-lineage`.