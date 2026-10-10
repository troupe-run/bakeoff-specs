Q1: I've scoped step 2 as one new spec, `config-file-sync`, and committed its brief and a Phase 2 section of the roadmap on `main` (commit `d020466`). This was discovery only: no code, requirements, design or tasks yet, so `watch` and reconcile don't exist so far.

**Why it gets its own spec:** step 2 reverses decision A from step 1. Hand edits used to be shown but never recorded; now they are recorded as `set`/`remove` events. That cuts across both existing specs. The text in those specs that says hand edits are not recorded will be amended inside the new spec's tasks, so the spec, code and tests change together. That text is config-foundation requirements 6.9 and 7.3 plus the decision A record, and the 15.x wording in config-set-writeback. About seven existing tests assert "hand edits add no event"; the brief lists them because they will need changing.

**Approach I chose (recorded in the brief with the alternatives and why they were rejected):**
- **Reconcile:** compare the leaves in the files with the values recorded in the history, then record a `set` or `remove` for each difference. A formatting-only or comment-only edit changes no leaf, so it records nothing. The existing `diff_leaves` gets refactored so `set` and reconcile share it.
- **Not recording troupe's own writes:** this needs no extra bookkeeping. After a `set` records its events, the recorded values already match the files, so the watcher has nothing to add. The one gap is the watcher reading the files after `set` has written them but before it has recorded its events. A single exclusive lock closes that gap. It is taken on the `.troupe` directory itself, so no lock file is left behind (decision E). The design still has to confirm this lock works on macOS.
- **Watching:** check the files about every 0.25 s and only reconcile once a change has held for one more check. That stays well inside the 2-second limit, adds no new dependency, behaves the same on macOS and Linux, and naturally follows includes added by hand. The `watching <dir>` line is printed only after the starting snapshot and the start-up reconcile.

**Open choices I made, all written in the brief:**
- **`history`** still does the first-run import, but never reconciles.
- **Reconcile runs first in `show`, `set` and `watch`.** Its events stay recorded even if the command then fails, because the hand edit really happened.
- **Broken files while watching:** if a file stops loading mid-watch (for example an editor's half-saved file), `watch` reports it on stderr, records nothing, and keeps running.
- **What `watching` prints:** the line shows the theatre directory exactly as it was given.

**Risk for the design:** recorded values must come back from the store with exactly the same type as freshly loaded ones (for example `1` versus `1.0`, and the non-finite floats from decision F). If they don't, every command would record events that aren't real changes.

**Next:** `/kiro-spec-init config-file-sync`, or `/kiro-spec-quick config-file-sync` to go straight through requirements, design and tasks.
A1 (po): /kiro-spec-init config-file-sync

Q2: ## Feature name
`config-file-sync`, the name the discovery brief chose. The directory held only `brief.md`, so I initialized the spec in place and there was no naming conflict.

## Project summary
Keep the recorded configuration in step with hand-edited `.troupe/` files, both live through `troupe config watch` and when any other command except `history` starts, without recording troupe's own write-backs a second time.

## Created files
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-file-sync/spec.json` (phase `initialized`, language `en`)
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-file-sync/requirements.md`

The project description in `requirements.md` covers the problem, the current state and the desired outcome, taken from the brief. It also quotes the step 2 contract section "Sync with files" word for word, so the requirements phase works from the exact contract text. I committed both files on `main` as `fb07559`.

## Next step
```
/kiro-spec-requirements config-file-sync
```
A2 (po): /kiro-spec-requirements config-file-sync