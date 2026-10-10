Tasks are finalized and committed on `feat/troupe-config-get-show` (`2da8c18` maps requirements to work packages, `7bcbde0` adds the tasks). There are 3 work packages with 15 subtasks; no code has changed yet.

| WP | What it delivers | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | YAML renderer with source comments (`src/troupe/yamlout.py` plus unit tests) | 5 | ~243 lines | none |
| WP02 | `get` command, CLI registration, `get` tests, and test helpers switched to `get` | 5 | ~195 lines | none |
| WP03 | New `show [PATH] [--sources]`, its tests, and a final run of every quickstart command plus all quality checks | 5 | ~191 lines | WP01, WP02 |

- **Size:** every work package has 3–7 subtasks and is well under 700 lines (about 210 on average). Each prompt starts with the required "load agent profile" section.
- **Validation:** the finalize step passed with no ownership warnings. All 15 functional requirements are mapped to a work package.
- **Parallel work:** WP01 and WP02 run at the same time in separate lanes. WP03 starts when both are done.
- **Smallest useful first step:** WP02 on its own already delivers `get`.
- **Agent profile:** all three use `python-pedro` (implementer).

**Ordering safeguard:** WP02 must not touch `show`, so `show` keeps its old behaviour until WP03 replaces it. WP03 is allowed one edit to `src/troupe/cli.py`, which WP02 owns, limited to the `show` command definition. This is safe because WP03 runs only after WP02 is finished.

Two files are still uncommitted, both written by the tooling: `status.events.jsonl` (modified) and `status.json` (new).

**Should I use the `/spec-kitty-implement-review` skill to implement all WPs until completion?** It sends each work package to an implementing agent and then a reviewing agent, handles rejected work, and merges all lanes at the end.

Before any implementation can start, `/spec-kitty.analyze` must run; it checks that the spec, plan and tasks agree. If you say yes, I'll run it first. Afterwards the feature branch still has to be merged into `main` to meet your delivery requirement (no push, no PR). You can also choose which agents implement and review, or limit the run to some of the work packages.