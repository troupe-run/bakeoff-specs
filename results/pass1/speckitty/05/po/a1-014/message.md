WP05 (the last package) is being implemented in lane-e.

| WP | Stage |
|---|---|
| WP01 Load and read `$ref` includes | Approved |
| WP02 Include conversion edits | Approved |
| WP03 Where a `set` writes | Approved |
| WP04 `set` wiring and story tests | Approved (cycle 2) |
| WP05 Acceptance | Implementation running |

WP05 covers:
- end-to-end tests for edge cases, refusals, history and `watch`;
- the chained-include `--in-include` fix (bead `c3z`);
- a check that every requirement and agent choice maps to a test;
- the quickstart run.

When it reports, I'll make all the doc fixes in one batch on the planning branch. That covers its findings plus the analysis report's open low-priority items: data-model wording for `holder`, D-5's flow exception, and recording the next-line and whole-document conversion shapes. Then come acceptance and the merge to `main`.