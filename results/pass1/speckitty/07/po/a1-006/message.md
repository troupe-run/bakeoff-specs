The work packages for step 7 are written, validated and committed on `feat/troupe-config-remote-includes`. Nothing is merged into `main` yet and nothing was pushed. Validation found no ownership overlaps or dependency problems, and all 12 functional requirements are mapped to at least one package.

**10 packages, 47 subtasks** (`kitty-specs/troupe-config-remote-includes-01M4BMJ5/tasks.md`):

| WP | What it does | Subtasks | Depends on |
|---|---|---|---|
| WP01 | URL type, fetching, local HTTP test server | 5 | — |
| WP02 | `!literal` in the YAML parser | 4 | — |
| WP03 | Schema module and the `jsonschema` dependency | 5 | — |
| WP04 | The include rule in one module | 4 | WP01, WP03 |
| WP05 | Loader: remote includes and literal strings | 5 | WP01, WP02, WP04 |
| WP06 | Load-and-validate entry point, sessions, `watch`; reading stories end to end | 6 | WP03, WP05 |
| WP07 | Writing `!literal` in new values | 4 | WP04, WP05 |
| WP08 | `set`: remote content read-only, schema checks, `--include` | 8 | WP06, WP07 |
| WP09 | Independent end-to-end tests of the `set` story (US6) and `--include` with URLs | 3 | WP08 |
| WP10 | Acceptance tests, quickstart run, docs agreement, all four gates | 3 | WP09 |

- **Size:** prompts run from about 120 to 260 lines. None exceeds 10 subtasks or 700 lines, and every prompt starts with the "Do This First: Load Agent Profile" section.
- **Parallel work:** WP01, WP02 and WP03 can start together, and WP06 and WP07 can run side by side after WP05. Each package has its own lane (10 lanes).
- **Smallest useful slice:** WP01–WP06 deliver reading remote includes, literal strings and schema validation. WP07–WP08 add the write rules.
- **Profiles:** every package is assigned `python-pedro` running on `claude`, and is linked to a new tracking issue, `bakeoff-specs-speckitty-1j5`.

**Plan changes made while writing the packages** (committed separately with reasons):
- **Field name kept:** `SourceFile.path` keeps its name but can now hold a URL as well as a file path. mypy still flags every place that needs a file on disk, and packages don't need to edit each other's files for a rename.
- **Copies keep `!literal`:** a `!literal` value copied by `--expand-alias` now stays literal. Before this fix the copy would have become a remote include.
- **Second marker:** strings written with `--include` are now marked separately, so the "nothing changed" check can tell an include from a literal with the same text.
- **Error message unchanged:** tags other than `!literal` keep the step-6 message, so existing tests don't change.

**Known exceptions to file ownership:**
- WP05 makes a small type-only edit in `apply.py`, which WP08 owns.
- WP08 updates the two step-1 tests that the new `!literal` default (S-13) changes.

**Commits:** `8992702` (requirement mapping), `5558c76` (tasks), `b52e9dc` (plan amendments), `fcb3564` (status bookkeeping).

**Next:** `/spec-kitty.analyze` has to run first; implementation refuses to start until its report exists.

Should I use the `/spec-kitty-implement-review` skill to implement and review all ten packages through to completion? It would run `/spec-kitty.analyze` first, then dispatch implementing and reviewing agents for each package, handle rejections, and merge the lanes when done. You can also pick which models implement and review, limit it to a subset (for example WP01–WP03), or just have me run `/spec-kitty.analyze` now so you can read the consistency report before deciding.