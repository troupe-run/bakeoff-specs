## Archive Complete

**Change:** config-load-show-set
**Schema:** spec-driven
**Archived to:** `openspec/changes/archive/2026-10-02-config-load-show-set/` (its `.openspec.yaml` moved with it)
**Specs:** ✓ Synced to main specs

You asked me to choose between syncing and archiving without syncing. I synced: it only adds spec files, so nothing can be lost, and it keeps a spec on record for the behaviour the code and tests implement. The decision and its reason are in the archived `design.md` under "Archive decision".

Five new main specs are now in `openspec/specs/`:

| Spec | Requirements |
|---|---|
| `config-cli` | 6 |
| `config-loading` | 3 |
| `config-show` | 2 |
| `config-set` | 16 |
| `config-history` | 4 |

Each one passes `openspec validate --strict`. Its requirement and scenario headings match its delta spec exactly.

All artifacts and all 26 tasks are complete, and there are no active changes left. Everything is committed on `main` (`592e463`) and nothing was pushed.