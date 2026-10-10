## Status
The implementation plan is written to `.kiro/specs/config-get-show/tasks.md` and committed on `main` as commit `9ac56c2`. `spec.json` shows phase `tasks-generated`; the tasks are not yet approved.

## Task summary
There are 4 groups with 13 sub-tasks, each roughly 1–3 hours, and every requirement from 1.1 to 6.8 is covered.

1. **Foundation (1.1–1.2).** Move the shared quoting rules into `yaml_style` as a pure move, proven by `set`'s unchanged byte-exact tests. Then add quoting for a value printed on its own.
2. **Core (2.1–2.5).** The `get` lookup with the `config show` hint, source labels, and the YAML writer: layout, then literal blocks, then `--sources` comments. 2.1, 2.2 and 2.3 can run in parallel.
3. **Integration (3.1–3.3).**
   - 3.1 adds `get` first.
   - 3.2 replaces `show`. In the same task it updates every existing test that relied on step 1 `show`, so the suite stays green at every step.
   - 3.3 adds step 3 notes to the config-foundation and config-file-sync requirements and updates docstrings.
4. **Validation (4.1–4.5).** End-to-end tests for `get`, `show`, read-back and `--sources`, all four runnable in parallel. Then the full quality gate and a traceability check.

## Quality checks
- **Plan review gate:** passed. Every requirement and design component maps to a task.
- **Independent task-graph review:** a fresh reviewer agent did it. It returned NEEDS_FIXES on the first run: existing tests would have broken, because `show` with no PATH no longer exits 2 and `show` on a list no longer exits 5. It returned PASS after I fixed them.

## Next action
Tasks generated. Approve and proceed to implementation?