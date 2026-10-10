Q1: Discovery is finished and committed on `main` (`7455822`), but **the `troupe config` CLI itself is not built yet**. This skill only plans the work; it doesn't write specs or code. Nothing in the repo can run `uv run troupe config …` yet, so testing `main` now would find no CLI.

**Decision:** I split step 1 into two specs, built in this order, because the request is too large for one:
1. **`config-foundation`**: project setup, finding `troupe.yml`/`troupe.yaml`, loading with recursive `file:` includes, dotted paths, the `eventsourcing` event store with import on first command, `show`, `history`, and the exit-code and error rules. It records which file and position every value came from.
2. **`config-set-writeback`**: `set PATH VALUE` with byte-surgical write-back: choosing the target file, quoting, block and folded values, comment columns, line endings and appends. It also records `set`/`remove` events and writes files atomically. It depends on the first spec.

The write-back rules are the riskiest part, so they get their own spec and review.

**Approach chosen:** I made this choice myself rather than asking, since your brief was detailed. `ruamel.yaml` only parses the files; edits are applied as text patches at the recorded positions, and the whole file is never re-written from the parsed form. After each patch the file is re-parsed, and if the result isn't the intended config the write is refused with exit 3. I ruled out:
- **Re-writing the file with ruamel:** it reformats parts nobody asked to change.
- **PyYAML:** it reads values like `yes` as booleans (the wrong YAML version) and drops comments.
- **A hand-written YAML parser:** too much work for step 1.

**Check done:** `ruamel.yaml` 0.19.1 and `eventsourcing` 9.5.5 install together under Python 3.12. `ruamel` reports where each value sits in the file and how it's quoted, and reads `yes` as a string, as YAML 1.2 requires.

**One open question for the design:** after the first import, hand edits are not added to history. The design must decide whether `show` reads the files or the stored projection, and record why. I've noted this in the roadmap and the `config-foundation` brief.

Files:
- `.kiro/steering/roadmap.md`
- `.kiro/specs/config-foundation/brief.md`
- `.kiro/specs/config-set-writeback/brief.md`

**Next step:** run `/kiro-spec-batch` to write both specs. Then `/kiro-impl config-foundation`, then `/kiro-impl config-set-writeback`, committing each on `main`. That is when the CLI will actually exist.
A1 (po): /kiro-spec-batch

Q2: Both specs are complete and committed on `main` (`5e1501e`), but **the `troupe config` CLI is still not built**. These are planning documents only; testing `main` now would find no CLI.

| Spec | Requirements | Design | Tasks |
|---|---|---|---|
| config-foundation | 10 requirements, 62 acceptance criteria | 14 components | 6 groups, 20 sub-tasks |
| config-set-writeback | 16 requirements, 98 acceptance criteria | 14 components | 5 groups, 32 sub-tasks |

Both are at the `tasks-generated` stage with all three approvals recorded through the `-y` fast-track. Neither has had a human review, and the roadmap now marks both specs done.

**Problems along the way:**
- **Writeback task review:** it failed four times in total and was rewritten until a fresh run passed.
- **Cross-spec review:** it ran three rounds.
  - Round 1 found 12 issues.
  - Round 2 found 4 more introduced by those fixes, including a circular import between the two CLI modules. It's fixed by putting the shared CLI pieces in their own module, `troupe.cli.shell`.
  - Round 3 found only 3 minor wording issues, which I fixed directly.
- **Fold-marker bug:** `ruamel.yaml` adds stray U+0007 characters to folded (`>`) values. The loader now removes them.

**Choices I made where the contract is silent.** Each is the cautious option and recorded in the specs' `research.md`; please confirm or overrule:
- `show` reads the YAML files, not the stored history, so it never prints a stale value after a hand edit.
- A `set` that would have to change more than one file is refused with exit 3.
- After a write, the result is re-read in memory. If it isn't the intended configuration, the command exits 3 and no file changes.
- A `set` whose value starts with `file:` is written like any other string. If its target is missing or forms a cycle, it is refused with exit 3.
- File writes go through a hidden temporary file next to the target, then an atomic rename. A hard kill mid-write could leave that temporary file behind.
- Infinity and NaN appear in history as the JSON strings `".inf"`, `"-.inf"` and `".nan"`, so every line stays valid JSON.
- A malformed path such as `a..b` exits 2. Duplicate keys, explicit tags, anchors and files that aren't UTF-8 exit 4.

**One change from my own discovery plan:** the history is stored as SQLite at `.troupe/history.sqlite`, with its `-wal`/`-shm` side files also under `.troupe/`.

**Next:** run `/kiro-impl config-foundation`, then `/kiro-impl config-set-writeback`, committing each on `main`.
A2 (po+fallback): On “Should `show` read the YAML files on disk rather than the stored history, so a hand edit is never shown stale?”: Confirmed. The files are the truth. `show` and `set` always read the files as they are on disk. The stored projection is only the change history, so a hand edit shows up in `show` but produces no history event. A later `set` records its `old` value as what was in the file.

On “Should a `set` that would have to change more than one file be refused with exit 3?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Should a `set` whose re-read in-memory result is not the intended configuration exit 3 with no file changed?”: Confirmed. Exit 3 means the write was refused and no file changed, so refusing in that case and leaving every file untouched matches the contract.

On “Should a `set` whose value starts with `file:` be written as a plain string but refused with exit 3 if its target is missing or forms a cycle?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Is it acceptable to write files through a hidden temporary file next to the target and then atomically rename it, given that a hard kill mid-write could leave the temporary file behind?”: Acceptable, as long as no extra file is left behind once any command finishes, successfully or not. The implementation must not create or modify any file except as the write-back rules require. A crash mid-write is not something the contract defines.

On “Should Infinity and NaN appear in history as the JSON strings ".inf", "-.inf" and ".nan"?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Should a malformed path such as `a..b` exit 2?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Should YAML anchors in a configuration file cause exit 4?”: Your choice. Anchors, aliases and merge keys are out of contract for now, so you may decide how to handle them; just say what you chose (as you have).

On “Should duplicate keys, explicit tags and files that are not UTF-8 cause exit 4?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.