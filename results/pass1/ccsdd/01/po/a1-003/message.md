I recorded all nine answers in both specs and committed them on `main` (`8c0725b`). **The CLI is still not built.** I stopped before implementation because `kiro-impl` is set up so that only you can start it, not me.

**What changed in the specs:**
- **`show` and `set` read the files on disk (confirmed).** A hand edit shows up in `show` but records no history event. A later `set` records the value in the file as `old`. Tests for both are now in the task lists.
- **A `set` that touches several files now goes ahead instead of being refused.** This was your call to me, and I reversed my earlier choice. The contract's "only bytes that differ in any file" plus rule 1 means replacing a collection that contains a text include must legitimately change two files, so refusing would contradict it. To keep data safe:
  - Every file's patch is built and checked in memory before anything is written.
  - If a later write fails, the earlier files are restored to their original bytes and the command exits 3 with no history recorded.
  - A change that would alter the configuration anywhere other than at PATH, such as a file included in two places, is still refused.
- **A `file:` value is kept as a plain string.** If its target is missing or forms a cycle, the command exits 3 and no file changes. This never leaves you with a configuration that can't load.
- **No leftover files.** Tests now check that no extra file remains after success or after any failure. The history store is closed at the end of every command, and nothing may appear outside `.troupe/`.
- **Kept as before, with reasons recorded:**
  - Infinity and NaN in history are written as `".inf"`, `"-.inf"` and `".nan"`.
  - A malformed path such as `a..b` exits 2.
  - Anchors, aliases, merge keys, duplicate keys, explicit tags and files that aren't UTF-8 all exit 4.

**One trade-off to know about:** if restoring a file after a failed write itself fails, the command keeps its original exit code and names every file it couldn't restore. That breaks the usual meaning of exit 3 ("no file changed"), but only in a case the contract doesn't define.

Each decision is recorded with its reason in the specs' `research.md`, with a summary in `.kiro/steering/roadmap.md`.

**Next:** run `/kiro-impl config-foundation`, then `/kiro-impl config-set-writeback`. Each task gets an implementer and an independent reviewer, and is committed on `main`.