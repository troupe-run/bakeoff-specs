The work is split into 5 work packages (27 subtasks), validated, finalized and committed on `feat/troupe-config-include-overrides` (`c0a22dc`, plus profile assignment in `82518a4`). Nothing is on `main` yet and nothing has been pushed. The task list is `kitty-specs/troupe-config-include-overrides-01M46FY4/tasks.md`, with one prompt file per package in `tasks/`.

| WP | Goal | Subtasks | Prompt lines | Depends on |
|---|---|---|---|---|
| WP01 | Load and read `$ref` includes (merged view, the three load errors, watched files) | 7 | ~212 | – |
| WP02 | Text edit that converts a plain include to mapping form (block, flow, list item, document root; D-11 refusal) | 5 | ~156 | – |
| WP03 | Where a `set` writes: overrides, `--in-include`, refusals (D-6, D-10) | 5 | ~174 | WP01 |
| WP04 | `set` wiring, pre-write safety check, `--in-include` flag, story tests, the two step-1 tests updated | 6 | ~160 | WP02, WP03 |
| WP05 | End-to-end edge and refusal tests, history/watch, quickstart walk-through, check that spec and code agree, full gates | 4 | ~116 | WP04 |

- **Size:** no package has more than 7 subtasks or 700 lines, and every prompt starts with "Do This First". The prompts average about 165 lines, under the 200–500 target. They're short because each points at research R-1…R-8 for the detailed rules instead of repeating them.
- **Ownership:** no two packages claim the same file. Validation reported no ownership or requirement warnings, and FR-001…FR-013 are all mapped.
- **Parallel work:** WP01 and WP02 can run at the same time. After that it's sequential. The tool computed 5 lanes.
- **Smallest useful slice:** WP01 alone lets mapping-form includes be read. CR-A and CR-B are both complete after WP04.
- **Profiles:** every package is assigned `python-pedro` (implementer, claude).

**Design details refined while writing the packages.** These are in research and the data model (`6072099`); behaviour is unchanged:
- The nearest include reference is found by matching the include whose target is the file holding the deepest existing ancestor.
- A merged mapping keeps both sides as found.
- Writes only ever go through a real parent mapping or list in the file that holds the value, never the merged view.

**Sequencing caveat:** once WP03 lands, the two step-1 tests that change under the new contract would fail until WP04 lands. WP03 is told to mark them `xfail(strict=True)` (a small edit to a WP04-owned file, with a stated reason), and WP04 removes those marks.

**Required gate:** `/spec-kitty.analyze` must run before implementation can start.

Should I use the `/spec-kitty-implement-review` skill to fully implement all WPs until completion? That means running `/spec-kitty.analyze` first, then implementing and reviewing every package and merging the lanes into `feat/troupe-config-include-overrides`. You can also name which models to use for implementing and reviewing.