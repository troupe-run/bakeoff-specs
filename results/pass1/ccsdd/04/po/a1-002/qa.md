Q1: I've finished discovery and the full spec for step 4, but I haven't written the implementation: the implementation skill (`/kiro-impl`) can only be started by you, and I'm not allowed to run its workflow by other means. So lineage is planned on `main` but not built — no code or tests have changed.

To finish it, run:

```
/kiro-impl config-lineage
```

**What's committed on `main`** (all in `.kiro/specs/config-lineage/` unless noted):
- **Discovery:** `brief.md`, plus a "Step 4 — Lineage" section in `.kiro/steering/roadmap.md`. Lineage gets a new spec, and three existing specs get step-4 notes: config-foundation, config-set-writeback and config-file-sync.
- **Requirements:** 7 requirements with 35 acceptance criteria.
- **Design:** `design.md` and `research.md`.
- **Tasks:** `tasks.md`, with 10 sub-tasks in three groups. An independent review passed it after one round of fixes.

**How the design works:**
- **One change, one id:** every batch the history records (one import, one file reconcile, or one `set`) is stamped with one change id and one UTC time. A `set` after a hand edit therefore records two changes: the file reconcile, then the CLI change.
- **Actor:** `TROUPE_ACTOR` is read once per command in the CLI layer. An invalid value gives exit 2 before any file or history is touched.
- **Older histories:** histories recorded before step 4 stay readable, with their lineage shown as unknown rather than guessed. I checked this against the event library with a small experiment.

**Choices I made where the contract is silent** (all recorded in `research.md`; tell me if you want any changed):
1. Every subcommand rejects an invalid `TROUPE_ACTOR`, not only `set`.
2. A set-but-empty `TROUPE_ACTOR` is invalid, not treated as unset. So is `human:` with no id.
3. If the login name can't be found, the actor is `{"kind": "human", "id": null}`.
4. `at` always has six fractional digits, e.g. `2026-10-04T09:30:00.123456Z`.
5. If `--reason` is given twice, the last one counts.

**Open question for the product owner:** old `set`/`remove` events don't say whether they came from the CLI or a file edit, and the contract only allows `import`, `cli` or `file`. I chose `"cli"`, with the actor shown as unknown. The alternatives are `"file"`, or adding an "unknown" value, which would extend the contract.

Nothing is pushed and no pull request was opened.
A1 (po): The contract says every `history` event has the Lineage fields. It says nothing about events recorded before step 4, or about upgrading stored history. Treat how those older events are shown as out of contract: your choice. State which you chose and why. Your current choice of "cli" with actor unknown is acceptable on that basis.