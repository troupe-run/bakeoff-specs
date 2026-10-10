Both specs are complete and committed on `main` (`5e1501e`), but **the `troupe config` CLI is still not built**. These are planning documents only; testing `main` now would find no CLI.

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