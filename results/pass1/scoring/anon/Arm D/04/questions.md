## Scored run

### Question 1 (step_done, answered by runner)

Arm asked: Lineage is in and committed on `main` as `30b372a`. All 79 tests pass. Nothing was pushed.

Every event in `troupe config history` now has the five Lineage fields the contract asks for:

- **`actor`:**
  - For a `set`, it comes from `TROUPE_ACTOR` (`human:<id>` or `agent:<id>`).
  - If `TROUPE_ACTOR` is unset, it is `human` plus your login name.
  - Imports and hand edits get `{"kind": "unknown", "id": null}`.
- **`via`:** `import`, `cli` or `file`.
- **`at`:** a UTC timestamp ending in `Z`, with microseconds.
- **`reason`:** the text from the new `troupe config set --reason TEXT`, otherwise `null`.
- **`change`:** a random ID shared by all events from one command, reconcile or import. If a `set` first picks up hand edits, those edits are their own change, marked `unknown`/`file`. The reason and actor apply only to the `set`'s own events.

Choices where the contract was silent (recorded in `docs/decisions.md`, items 21–23):

- **Bad `TROUPE_ACTOR` exits 2 on every command**, including `get` and `history`, not just `set`. Nothing is read or recorded first.
- **An empty `TROUPE_ACTOR` counts as invalid, not unset.** This differs from how an empty `TROUPE_THEATRE` is treated. The reason: an agent with a misconfigured variable shouldn't be recorded as the logged-in person.
- **State files from before this change still load and show lineage.** I checked this against a database written by the previous commit, and a test covers it.
  - Their time is kept from the stored event and their actor is `unknown`.
  - An old import keeps `via: "import"` and gets the change ID `"import"`.
  - An old `set`/`remove` gets `via: null` and `change: null`, because whether it came from the CLI or a hand edit can't be known. That `null` falls outside the contract's three `via` values. I chose it over guessing, as the brief asks, but if your tests require one of the three values this is the place to change.

The changes are in `src/troupe/store.py` (lineage on each event, plus the upgrade path for older records) and `src/troupe/cli.py` (`TROUPE_ACTOR` parsing and `--reason`). The new tests are in `tests/test_lineage.py`, and the README documents the new fields.

Reply: /method-command

### Question 2 (step_done, answered by po)

Arm asked: The lineage work is already in place on `main`, so there's nothing left to merge, push or clean up.

- **Tests:** I just reran the full suite on the committed tree and all 79 pass.
- **Where it is:** this is the normal repository, not a separate worktree. The current branch is `main` and the working tree is clean. The commit is `30b372a Record lineage on every config history event`.
- **Why I skipped the menu:** this skill normally ends by offering three choices.
  - Merging into `main` doesn't apply, because the work was committed straight to `main`.
  - Pushing and opening a pull request is ruled out by your delivery instructions.
  - That leaves keeping things as they are, which is the current state.
- **Cleanup:** the temporary worktree I made at `/tmp/old` to test old state files was removed after that check. Nothing else was created.

Reply: 
