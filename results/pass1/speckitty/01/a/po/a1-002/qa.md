Q1: I've created the mission **`troupe-config-load-show-set-01M3VJ22`** (`kitty-specs/troupe-config-load-show-set-01M3VJ22/`).

**Branches:**
- We started on `chore/project-charter`, which isn't the primary branch.
- Planning and merging both target `chore/project-charter`, so they match.
- You asked for delivery on `main`. Spec Kitty won't commit to `main` unless it is checked out, and `main` is missing the last two commits on this branch. Since `main` is a direct ancestor of this branch, at the end I'll fast-forward `main` to the finished work, locally and without pushing.

Your contract is very detailed, so I'll only ask about the few choices it leaves open, one at a time.

**Question 1: is the config files or the stored history the source of truth?**

The contract says the first command imports the theatre and that "importing is not reconciling." It doesn't say what happens when someone edits a file by hand *after* that import, for example changing `model: a` to `model: b` directly in `troupe.yml`. Then:
- **(A) The files are the truth.** `show` and `set` always read the files as they are on disk. The stored projection is only the change history, so a hand edit appears in `show` but produces no history event. A later `set` records its `old` value as what was in the file.
- **(B) The stored projection is the truth.** `show` and `set` read the projection, so the hand edit is invisible until something reconciles the two.
- **(C)** Something else.

I recommend **(A)**. People edit and review these files directly, so the bytes on disk are what they expect to see. Writing back from a projection that has drifted from the files could silently overwrite their edits, which is the worst failure the charter names. "Importing is not reconciling" also suggests that hand edits are deliberately left out of history for now.

WAITING_FOR_DISCOVERY_INPUT
A1 (owner): A
 The files are the truth.** `show` and `set` always read the files as they are on disk. The stored projection is only the change history, so a hand edit appears in `show` but produces no history event. A later `set` records its `old` value as what was in the file.