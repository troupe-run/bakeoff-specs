### Gate 3 (attempt 1, approval)

Arm asked: ## Generated Requirements Summary
The requirements are written as 10 numbered requirements, all in EARS form:
- **Reading (1–3):** anchors, aliases and merge keys now load, which replaces the old exit 4 (decision H). `get`, `show`, `show --sources`, `history`, reconcile and `watch` all see the resolved configuration. Broken forms still exit 4: an undefined alias, an alias inside its own anchor, or an anchor on a key.
- **Setting at an anchor (4):** the change is made at the anchor and shows up at every alias, with history events for every affected path. The anchor stays when its value is replaced.
- **Refusal (5):** a path reached through an alias, including the alias's own key, exits 3. stderr names the file, PATH and `*name`, and mentions `--expand-alias`.
- **`--expand-alias` (6–8):** it takes no value and combines with `--reason` and `--in-include`. It writes a block-style copy with `# expanded from *<name> by troupe`, then sets the value in the copy. Nested aliases are expanded outermost first. It refuses with exit 3 when the alias is inside a flow collection or the key's line already has a comment.
- **Merge keys and safety (9–10):** troupe never writes `<<`, so any write through a merge key exits 3. Every write is checked by reading it back and is written atomically.

**One change from the brief:** merge keys now load, instead of staying exit 4. The contract names them, so files that use them are now covered, and reading them can't change a byte. Writes through them are still refused.

## Document Status
- `spec/spec/config-aliases/requirements.md` now includes the contract text from issue #2 and 17 choices with cautious defaults for you to review.
- `spec.json` is at phase `requirements-generated`.
- `roadmap.md` now has the corrected merge-key note.
- Committed on `main` as `7e9eb73`.

## Review Gate
Passed in two passes. The first fixed a contradiction: a no-change `set` through an alias now exits 3 in all cases (choice 17). It also fixed two sentences that weren't in EARS form.

## Next Steps
The decisions most worth your attention are choices 1, 2, 5, 6, 9 and 17. Once you approve:
```
/method-command config-aliases
```
Use `-y` to approve the requirements and go straight to design. `/method-command config-aliases` is optional.

PO verdict: Approved. The requirements are consistent with the step 6 Aliases section and the earlier contract sections in force. Writes at an anchor change the anchor (Req 4). A path reached through an alias, including the alias's own key and no-op sets, exits 3 and mentions `--expand-alias` (Req 5). `--expand-alias` writes a block-style copy with `# expanded from *<name> by troupe` two spaces after the key, then sets the value in the copy and leaves the anchor and the other aliases unchanged (Req 7). Merge keys are never written (Req 9). The contract doesn't cover reading through merge keys, several aliases on one path, `--expand-alias` without an alias, an alias inside a flow collection, or a key line that already has a comment, so those are your choices. You chose and recorded each one, as the brief asks.

Owner action: accept; approved: True

Final reply: Approved. The requirements are consistent with the step 6 Aliases section and the earlier contract sections in force. Writes at an anchor change the anchor (Req 4). A path reached through an alias, including the alias's own key and no-op sets, exits 3 and mentions `--expand-alias` (Req 5). `--expand-alias` writes a block-style copy with `# expanded from *<name> by troupe` two spaces after the key, then sets the value in the copy and leaves the anchor and the other aliases unchanged (Req 7). Merge keys are never written (Req 9). The contract doesn't cover reading through merge keys, several aliases on one path, `--expand-alias` without an alias, an alias inside a flow collection, or a key line that already has a comment, so those are your choices. You chose and recorded each one, as the brief asks.

### Gate 5 (attempt 1, approval)

Arm asked: ## Status
The design is written to `spec/spec/config-aliases/design.md` (507 lines) and committed on `main` as `c9ec8ef`. `spec.json` is now at `design-generated`: design generated, not yet approved.

## Discovery Type
Light, because this extends existing code. A subagent analysed the loader, model, writeback and CLI, and I tested ruamel.yaml 0.19.1 directly.

## Key Findings
- **ruamel loses where an alias is written.** At an alias it hands back the anchored node itself, so the `*d` position is gone. Overriding `Composer.compose_node(parent, index)` records each occurrence exactly by parent and slot. It also catches aliases used as keys. Two more things the loader must now handle: recursive aliases compose without error, and a reused anchor name prints a warning to stderr.
- **Writes at an anchor already have a mechanism.** The loader builds separate nodes for every place, and writes are keyed by where they are written in the file. Each alias place is therefore built again with the anchor's positions. Step 5's machinery for files included at several places then copies the anchor write to every alias place, and history gets an event for each path.
- **The expansion runs in memory first.** `--expand-alias` expands one alias, reloads the configuration from memory, and repeats while aliases remain on PATH, outermost first. Then the normal `set` runs, with one atomic write and one read-back against the original files. The alias check runs before the "nothing to change" check, so a no-op `set` through an alias is still refused.

## Review Gate
Passed. All 51 requirement IDs are in the traceability table. Two local fixes were made: a missing allowed dependency, and the security note, which wasn't recorded in `research.md` yet.

## Research Log
`research.md` holds the investigation, 8 design decisions, records for all 17 approved choices, and the risks. One consequence comes from the design rather than a requirement: an anchored node that contains `<<` can't be copied without writing a merge key, so `--expand-alias` refuses it under 9.1.

## Next Action
Review the design, then:
```
/method-command config-aliases
```
Use `-y` to approve the design at the same time. `/method-command config-aliases` is an optional review before that.

PO verdict: Approved. The design is consistent with the step 6 Aliases section and the earlier contract sections in force. A `set` at an anchor is written at the anchor, so it shows up at every alias. A `set` reached through an alias, including the alias's own key and a no-op, exits 3 before anything is written, and stderr mentions `--expand-alias`. `--expand-alias` swaps that one alias for a block-style copy, puts `  # expanded from *<name> by troupe` on the key's line (two spaces before `#`), and then sets the value in the copy. The anchor and the other aliases stay unchanged. Merge keys are never written. Every refusal happens before any write and names the file and PATH (Exit codes). The issue #2 end-to-end test checks the reporter's scenario byte for byte. The remaining behaviour (merge keys when reading, nested aliases, a flow-collection alias, a key line that already has a comment, copying an anchored node that holds `<<`, removing an anchor that is still used) is out of contract. You chose and recorded each one, as the brief asks.

Owner action: accept; approved: True

Final reply: Approved. The design is consistent with the step 6 Aliases section and the earlier contract sections in force. A `set` at an anchor is written at the anchor, so it shows up at every alias. A `set` reached through an alias, including the alias's own key and a no-op, exits 3 before anything is written, and stderr mentions `--expand-alias`. `--expand-alias` swaps that one alias for a block-style copy, puts `  # expanded from *<name> by troupe` on the key's line (two spaces before `#`), and then sets the value in the copy. The anchor and the other aliases stay unchanged. Merge keys are never written. Every refusal happens before any write and names the file and PATH (Exit codes). The issue #2 end-to-end test checks the reporter's scenario byte for byte. The remaining behaviour (merge keys when reading, nested aliases, a flow-collection alias, a key line that already has a comment, copying an anchored node that holds `<<`, removing an anchor that is still used) is out of contract. You chose and recorded each one, as the brief asks.

### Gate 8 (attempt 1, approval)

Arm asked: ## Status
The task plan is written to `spec/spec/config-aliases/tasks.md` and committed on `main` as `8514a80`, with `spec.json` at `tasks-generated`. That commit also includes the design clarifications from the last run. They are recorded in `research.md` as found during planning, with no behaviour change. The main one: `deep_merge` must keep alias, anchor and merge-key information, otherwise aliases behind `$ref` overrides would escape the alias check.

## Task Summary
5 major tasks and 18 sub-tasks, each sized at 1–3 hours, covering all 51 requirements:
1. **Foundation (1.1–1.2):** the model fields, the merge-key merge, and the composer that records where each alias is written.
2. **Loading (2.1–2.4):** anchors, then aliases, then merge keys, then a check that every command reads the expanded configuration.
3. **File layer (3.1–3.7):** layout, copying changes to every alias place, the alias check, keys next to `<<`, the two planner refusals, and the copy written by `--expand-alias`.
4. **`set` (4.1–4.4):** the refusals, writes at anchors, the expansion step, and the CLI flag.
5. **Validation (5.1–5.2):** the issue #2 scenario byte for byte, then the notes in the earlier specs and the traceability check.

Tasks 1.2, 3.2 and 3.3 can run in parallel.

Anchors start loading in 2.1, but the alias check only arrives in 4.1. Until then a temporary refusal, pinned by tests, stops `set` from writing through an alias or merge key.

## Quality Validation
- Every requirement is mapped to a task, and design coverage and dependencies were checked.
- The task-plan review gate passed.
- The task-graph sanity review, run by an independent subagent, returned `PASS` after one repair round. Its four minor suggestions are folded in.
- Testing is part of every task, and each task names its test file.

## Next Action
Tasks generated. Approve and proceed to implementation?

PO verdict: Approved. The task plan is consistent with the step 6 Aliases section and the earlier contract sections in force. A `set` at an anchor writes at the anchor and keeps `&name`, so the change shows at every alias, and history records events for each affected path (4.2, 5.1). A `set` reached through an alias exits 3 before any file changes, and stderr names the file and PATH and mentions `--expand-alias`. This includes the alias's own key and a no-op (3.3, 4.1, 5.1). `--expand-alias` swaps only that alias for a block-style copy with `  # expanded from *<name> by troupe` on the key's line, then sets the value in the copy. The anchor and the other aliases stay byte-identical (3.6, 3.7, 4.3, 4.4, 5.1). Merge keys are never written (3.4, 3.6). The design clarifications recorded in this commit are also consistent with the contract: keeping alias, anchor and merge-key provenance through `$ref` deep-merge, the order of refusals, and checking the expanded write against the original files. The temporary refusal of `set` between 2.1 and 4.1 means no intermediate commit can write through an alias. The remaining behaviour is out of contract, and you chose and recorded each one, as the brief asks. That covers removing an anchor that is still used, converting an anchored include, a no-op with `--expand-alias`, a flow-collection alias, a key line that already has a comment, and a copy that holds `<<`.

Owner action: accept; approved: True

Final reply: Approved. The task plan is consistent with the step 6 Aliases section and the earlier contract sections in force. A `set` at an anchor writes at the anchor and keeps `&name`, so the change shows at every alias, and history records events for each affected path (4.2, 5.1). A `set` reached through an alias exits 3 before any file changes, and stderr names the file and PATH and mentions `--expand-alias`. This includes the alias's own key and a no-op (3.3, 4.1, 5.1). `--expand-alias` swaps only that alias for a block-style copy with `  # expanded from *<name> by troupe` on the key's line, then sets the value in the copy. The anchor and the other aliases stay byte-identical (3.6, 3.7, 4.3, 4.4, 5.1). Merge keys are never written (3.4, 3.6). The design clarifications recorded in this commit are also consistent with the contract: keeping alias, anchor and merge-key provenance through `$ref` deep-merge, the order of refusals, and checking the expanded write against the original files. The temporary refusal of `set` between 2.1 and 4.1 means no intermediate commit can write through an alias. The remaining behaviour is out of contract, and you chose and recorded each one, as the brief asks. That covers removing an anchor that is still used, converting an anchored include, a no-op with `--expand-alias`, a flow-collection alias, a key line that already has a comment, and a copy that holds `<<`.
