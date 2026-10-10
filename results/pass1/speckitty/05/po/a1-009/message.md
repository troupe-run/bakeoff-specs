Both foundation packages are being implemented in parallel:

| WP | Stage | Lane |
|---|---|---|
| WP01 Load and read `$ref` includes | Implementation running | lane-a |
| WP02 Include conversion edits | Implementation running | lane-b |
| WP03 Where a `set` writes | Waiting for WP01 | — |
| WP04 `set` wiring and story tests | Waiting for WP02 and WP03 | — |
| WP05 Acceptance | Waiting for WP04 | — |

I'll start each review as soon as its implementation is ready.