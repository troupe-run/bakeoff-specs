The work is now split into 6 work packages with 29 subtasks, finalized and committed on `fix/troupe-config-anchor-aliases`. Validation passed: no ownership overlaps, no dependency cycles, and every functional requirement FR-001 to FR-010 belongs to at least one work package. No code has changed yet.

| WP | Goal | Subtasks | Prompt lines | Depends on |
|---|---|---|---|---|
| WP01 | Rebuild the YAML reader to record where each anchor and alias is written; default behaviour unchanged | 4 | 178 | — |
| WP02 | Load anchors, aliases and merge keys so reads show resolved values; refuse unsupported uses with exit 4 | 6 | 205 | WP01 |
| WP03 | The bug's rule: refuse a `set` through an alias with exit 3, or hand it to expansion when the flag is given | 5 | 163 | WP02 |
| WP04 | Write the block-style copy and the `# expanded from *<name> by troupe` comment | 4 | 181 | WP02 |
| WP05 | Wire `set` end to end: expand-then-set, safety-net rules, anchors kept, `--expand-alias` flag, CLI tests | 6 | 190 | WP03, WP04 |
| WP06 | Acceptance: history, `watch` and reconcile with aliases, edge cases, quickstart, spec agreement, all gates | 4 | 127 | WP05 |

- **Size:** prompts run 127–205 lines and no package has more than 6 subtasks, so none is over the limits. Each starts with the required profile-loading section and is assigned the `python-pedro` profile.
- **Parallelism:** WP03 and WP04 can run at the same time once WP02 is done; everything else runs in order.
- **Suite stays green between packages:** WP01 keeps refusing anchors by default, and after WP02 a `set` through an alias is still refused with exit 3 by the existing safety check before WP03 adds the proper message.
- **Smallest useful slice:** WP01–WP03 plus the refusal half of WP05 already stop the reported bug. Delivery needs all six.

**Commits:** `5c06c23` adds the task list and work packages (`lanes.json` puts each package in its own lane). `297995b` records the status bookkeeping. Merge target is `fix/troupe-config-anchor-aliases`, which then goes to `main` by local merge after acceptance.

Shall I use the `/spec-kitty-implement-review` skill to implement and review all six work packages until done? `/spec-kitty.analyze` has to run first: implementation won't start until its `analysis-report.md` exists, so I'd run it before WP01. You can also name which models to use for implementing and for reviewing.