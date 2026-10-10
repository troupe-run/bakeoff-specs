Discovery is finished and committed on `main` (`7455822`), but **the `troupe config` CLI itself is not built yet**. This skill only plans the work; it doesn't write specs or code. Nothing in the repo can run `uv run troupe config …` yet, so testing `main` now would find no CLI.

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