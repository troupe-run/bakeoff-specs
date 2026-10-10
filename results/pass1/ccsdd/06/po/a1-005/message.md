## Status
The design is written to `.kiro/specs/config-aliases/design.md` (507 lines) and committed on `main` as `c9ec8ef`. `spec.json` is now at `design-generated`: design generated, not yet approved.

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
/kiro-spec-tasks config-aliases
```
Use `-y` to approve the design at the same time. `/kiro-validate-design config-aliases` is an optional review before that.