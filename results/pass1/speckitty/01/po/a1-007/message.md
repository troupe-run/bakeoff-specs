The tasks are finalized and committed: 8 work packages covering all 24 functional requirements. The validation dry run still passes after my last edits. No code has been written yet.

**Branch contract:** planning, base and Spec Kitty merge target are all `feat/troupe-config-load-show-set`, and the current branch matches. After acceptance, it is merged into `main` locally, with no push and no PR.

**Commits on that branch:** `4f345c4` (requirement mapping), `cc97760` (tasks, from `finalize-tasks`), `4ba6222` (agent profiles plus the updates to `research.md` and `plan.md`). Spec Kitty's `status.events.jsonl` and `status.json` aren't committed; they're the tool's own bookkeeping.

**Work packages** (all prompts are in `kitty-specs/troupe-config-load-show-set-01M3XGPG/tasks/`):

| WP | Goal | Subtasks | Lines | Depends on |
|---|---|---|---|---|
| WP01 | Project setup, CLI, exit codes, finding the root file | 5 | 259 | — |
| WP02 | Loader, includes, paths, YAML 1.2 core resolver | 5 | 198 | WP01 |
| WP03 | `eventsourcing` history, import on first command, `history` | 5 | 204 | WP02 |
| WP04 | `VALUE` parsing, scalar printing, `show` (User Story 1) | 4 | 132 | WP02, WP03 |
| WP05 | Atomic writes, quoting and escaping, comment columns | 5 | 192 | WP02 |
| WP06 | Literal and folded block scalars | 5 | 164 | WP05 |
| WP07 | New keys and items, flow appends, replacing one kind of node with another | 6 | 184 | WP05, WP06 |
| WP08 | `set` end to end, with byte-for-byte integration tests (User Story 2) | 7 | 200 | WP02–WP07 |

- **Size:** 42 subtasks, 132 to 259 lines per prompt (about 190 on average). Nothing goes over the limits (more than 10 subtasks or 700 lines), and every prompt opens with the "Do This First: Load Agent Profile" section. All 8 use `python-pedro` (the Python implementer profile).
- **Parallel work:** after WP02, the history and `show` branch (WP03 → WP04) can run alongside the write-back branch (WP05 → WP06 → WP07). No two WPs own the same file.
- **Smallest useful slice:** WP01 → WP04 gives working `show` and `history` commands.

**Findings from checking the libraries, recorded in `research.md` (R-13 to R-17):**
- **YAML 1.2 core values:** ruamel's "1.2" mode is not strict YAML 1.2 core; `2001-12-14` becomes a date and `1_000` becomes 1000. Plain values will use our own core-schema resolver in `yamlcore.py`, the only module that imports ruamel.
- **Byte-order mark:** files are decoded as plain UTF-8 so a byte-order mark stays in the text and is written back unchanged.
- **History store lifetime:** one history store object is kept open for each command, because the library closes its SQLite connection when the object is dropped.
- **Verify before writing:** `set` reloads the edited text in memory before writing. If PATH doesn't hold the new value, or any other value changed, it refuses with exit 3 and changes no file, so a bug can't corrupt a file.

**Decisions I made where the contract is open — please check:**
- **Text include, non-string `VALUE`:** if the target uses CRLF, exit 3, as the contract says. If it uses plain LF line endings, the content becomes the value's YAML text (`5`, `true`). A mapping or list is refused with exit 3.
- **Replacing a flow collection:** replacing `tools: [a, b]` (a list written inline) under a normal block mapping writes the new list in block style. I read the "new collection value" rule literally, so the line changes shape.
- **Refusals on edge cases:** these exit 3 or 5 rather than guess:
  - a `key:` with no value, treated as null rather than a mapping;
  - changing a folded value that already has more-indented lines;
  - a path like `tools.2.name` that continues past a list append.

**Next step:** `/spec-kitty.analyze` is required before implementation. The implement step won't start until its `analysis-report.md` exists.

**Should I use the `/spec-kitty-implement-review` skill to implement all WPs to completion?** It would run `/spec-kitty.analyze` first, then implement and review every WP, handle rejections, merge all lanes, and finally merge into `main` locally. You can also pick which models implement and review, choose a subset (say, WP01–WP04 first), or run `/spec-kitty.analyze` alone to look at the findings first.