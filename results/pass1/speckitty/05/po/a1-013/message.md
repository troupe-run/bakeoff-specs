WP04 is being implemented in lane-d.

| WP | Stage |
|---|---|
| WP01 Load and read `$ref` includes | Approved |
| WP02 Include conversion edits | Approved |
| WP03 Where a `set` writes | Approved |
| WP04 `set` wiring and story tests | Implementation running (lane-d) |
| WP05 Acceptance | Waiting for WP04 |

Besides its planned work, WP04 also:
- makes `$ref` defined in one place only;
- refuses with exit 3 to convert an include written with a YAML anchor or tag, instead of silently deleting it (bead `bakeoff-specs-speckitty-crs`). That's a new agent choice, so I'll add it to the spec as D-12 with its reason.

It commits work-in-progress as it goes, so another session interruption can't lose much.