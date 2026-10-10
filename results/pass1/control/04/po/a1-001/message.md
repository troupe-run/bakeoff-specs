Lineage is in and committed on `main` as `c3397d4`. All 29 tests pass. Every event in `troupe config history` now records who made the change, how, when, why, and which command it belongs to.

- **Who (`actor`):** for `set`, this comes from `TROUPE_ACTOR` (`human:<id>` or `agent:<id>`). If it's unset, the actor is the human with your login name. Anything else (empty, `bogus`, `human:`, `robot:x`) exits with code 2 before anything is read or written. Imports and hand edits to files are recorded as `{"kind": "unknown", "id": null}` rather than guessed.
- **How (`via`):** `import` for the first import, `cli` for `troupe config set`, and `file` for hand edits that are picked up before a command runs or by `watch`.
- **When (`at`):** a UTC timestamp ending in `Z`, with microseconds.
- **Why (`reason`):** the text from the new `set --reason TEXT` option, otherwise `null`.
- **What else (`change`):** a fresh id per command, shared by all of that command's events. A `set` that first picks up hand edits produces two changes: one for the file edits and one for the set itself.

Lineage is stored in the events themselves, so it survives restarts. The helpers are in a new `src/troupe/lineage.py`. I also updated the README.

**Older history databases:** I checked that a `.troupe/events.sqlite` written by the previous commit still loads. Its events show an unknown actor and the timestamp the event store saved. Old imports share the change id `unrecorded-import`, and each old set/remove gets its own id. Two parts of that fall outside the contract:
- **`via` is `null` for old set/remove events.** It was never recorded whether they came from the CLI or a file edit, and the allowed values have no "unknown", so `null` was the only way to avoid guessing.
- **Old change ids aren't UUIDs.** They're labels like `unrecorded-4`.

There's no automated test for this case because building an old-format database needs the previous commit's code.

**Decision for you:** only `set` checks `TROUPE_ACTOR`. Other commands (`get`, `show`, `history`, `watch`) record no CLI changes, so they ignore it, even when it's malformed. The spec could be read as wanting every command to reject a bad value with exit 2. That's a one-line change if you'd prefer it.