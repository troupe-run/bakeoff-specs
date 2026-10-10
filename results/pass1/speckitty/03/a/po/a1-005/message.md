I've split the work into four work packages (18 subtasks) and committed the finalized tasks on `feat/troupe-config-get-show` (commit `78e2917`). No code has been written yet.

| WP | Goal | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | Read-back checks in `yamlcore`: when a string can be unquoted, double quotes, float form, literal blocks | 5 (T001–T005) | 182 lines | — |
| WP02 | `render.py`: a node becomes YAML lines, each tagged with its source file | 5 (T006–T010) | 184 lines | WP01 |
| WP03 | `get`, `show [PATH] [--sources]`, command-line options; move `test_show.py` to `test_get.py`; section tests | 5 (T011–T015) | 195 lines | WP02 |
| WP04 | `--sources` acceptance tests, read-only and reconcile-first tests, check of contract and quickstart against real output | 3 (T016–T018) | ~160 lines | WP03 |

- **Size and checks:** every work package has 3–5 subtasks and a prompt under 200 lines. Each starts with the "⚡ Do This First" section and is assigned the `python-pedro` profile. Validation passed: no overlapping files, no cycles, and every FR, NFR and constraint is mapped.
- **No parallel work:** each package uses the previous one's API, so they run one after another. Spec Kitty still gives each its own lane (lane‑a to lane‑d).
- **Minimum useful scope:** WP01–WP03 deliver `get` and `show`. WP04 is still required, because it holds the acceptance tests for the contract's `--sources` section.

**Changes from the plan:**
- **Existing test that changes:** `test_cli_basics.py` used `config show` with no PATH as its example usage error. That is now valid, so WP03 switches that test to `get`.
- **Contract edits stay with me:** work packages can't own files under `kitty-specs/`. WP04 checks the contract and quickstart against the real output and reports any exact corrections, and I apply them on the planning branch before acceptance.
- **Floats:** they'll be written with a dot (`1.0e+20`) so readers that follow YAML 1.1 read them as numbers.

`finalize-tasks` left two status files uncommitted: `status.events.jsonl` (modified) and `status.json` (new). The previous mission had the same lane-guard issue with `status.json`, so I've left them for the implementation workflow to handle.

**Branch:** planning base and merge target are `feat/troupe-config-get-show`. The finished work goes onto `main` by a local merge, with no push and no PR.

**Should I use the `/spec-kitty-implement-review` skill to fully implement all work packages until completion?** It runs an implementing and a reviewing agent for each work package, handles rejection cycles, and merges all lanes when done. `/spec-kitty.analyze` has to run first: implementation won't start until its `analysis-report.md` exists, and I'd run it as the first step. You can also choose which agents implement and review, or limit it to some work packages.