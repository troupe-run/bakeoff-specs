Q1: I've finished discovery and committed it on `main` (`8f58c05`). This covers planning only: no code for `watch` or reconcile has been written yet. If the step is tested as delivered behaviour, those tests will fail until the spec is implemented.

**Path: mixed.** Step 2 needs one new spec, `config-file-sync`. It also reverses a step-1 rule in both existing specs: edits made by hand used to add no history events ("importing is not reconciling"), and now every command except `history` must record them. The rule that `show` and `set` read the files on disk stays as it is.

**Chosen approach** (recorded in `.kiro/specs/config-file-sync/brief.md`):
- **Reconcile** compares the leaves in the files with the configuration as recorded, which is worked out by replaying the history. It records a `set` or `remove` event for each leaf that differs, all in one transaction. Edits that only change formatting or comments produce no events.
- **A `set`'s own write-back is never recorded twice.** The `set` has already recorded those values, so the next reconcile finds nothing to add.
- **`set` and `watch` take turns through a lock** held on `.troupe/`, so no extra file is left behind. Without it, `watch` could reconcile between a `set` writing the file and recording its events, which would duplicate them.
- **`watch` checks file contents every few hundred milliseconds**, using only the standard library. It watches the config file and every included file, and re-reads the list after each load so a newly added include is followed. It takes its first snapshot before printing `watching <dir>`, so the line is true when it appears.
- **I didn't use a file-watching library** (watchfiles or watchdog). It would add a dependency and make the "only print once watching" promise harder to keep.

**Open choices**, listed in the brief for the requirements step:
- If the files can't be loaded during `watch` (for example, a half-saved file), it records nothing and keeps watching. It never treats that as every leaf being removed.
- `<dir>` in the `watching` line is printed exactly as it was given.
- `watch` on a theatre that has never been imported imports it first.
- `watch` prints only the `watching` line to stdout; everything else goes to stderr.

**Roadmap** (`.kiro/steering/roadmap.md`): I kept all the step-1 content and added a step-2 section. It lists `config-file-sync` as a new spec, plus requirement changes to `config-foundation` (6.9 and 7.3) and `config-set-writeback` (the 15.1 example). The step-1 tests that assert hand edits add no events will be updated within the new spec's tasks, in the same change as the new behaviour.

**Next steps:**
- `/kiro-spec-init config-file-sync`, or `/kiro-spec-quick config-file-sync` to go straight through to tasks.
- `/kiro-spec-requirements config-foundation` and `/kiro-spec-requirements config-set-writeback` to update the step-1 requirements this reverses.
A1 (po): /kiro-spec-init config-file-sync

Q2: ## Generated Feature Name
`config-file-sync`: I used the directory that discovery created, which held only `brief.md`, so there was no name conflict. The name covers what the spec owns: keeping the `.troupe/` files and the recorded configuration in step through reconcile and `watch`.

## Project Summary
`troupe config watch` will pick up edits to the config file and its includes within 2 seconds. Every command except `history` will first pick up edits made while troupe wasn't running. Troupe's own write-back will never be recorded a second time.

## Created Files
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-file-sync/spec.json`: phase `initialized`, language `en`, nothing approved yet.
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-file-sync/requirements.md`: the project description, taken from the brief's Problem, Current State and Desired Outcome. It also quotes the step 2 "Sync with files" contract word for word, so requirements are written against the contract itself rather than a summary.

Both files are committed on `main` (`fa8cf30`). No requirements, design or tasks have been written yet.

## Next Step
```
/kiro-spec-requirements config-file-sync
```
A2 (po): /kiro-spec-requirements config-file-sync

Q3: ## Generated Requirements Summary
I wrote seven requirements:
- **1. Reconcile first:** `show` and `set` reconcile before doing their own work, and keep the events even if they then exit 3 or 5. `history` never reconciles, though it still imports a theatre that has never been imported. A usage error or load failure records nothing. A hand edit made before a `set` is recorded ahead of the `set`'s own event.
- **2. Reconcile events:** a changed leaf gets `set` with the recorded value as `old`. A new leaf gets `set` with `old` null, and a leaf no longer in the files gets `remove`. Edits to formatting, comments or quoting record nothing, but a change of type does. All events from one reconcile are saved together or not at all, with consecutive `seq`: `set` events first, then `remove` events.
- **3. Includes added or removed by hand:** their leaves are recorded, and `watch` starts or stops following those files.
- **4–5. `watch`:** it uses the same default theatre as the other commands. It prints `watching <dir>` only once a change is certain to be seen, and reconciles within 2 seconds of a change. It also notices files saved by rename and `troupe.yml`↔`troupe.yaml` renames. SIGINT or SIGTERM exits 0, and a startup failure exits 4 under the step 1 rules.
- **6–7. Write-back and clean-up:** a `set` running alongside `watch` records exactly its own events. Each hand edit is recorded once, and events from two commands never interleave. Nothing new is left behind, and the history store is closed when a command ends.

Where the contract is silent, I made these choices; each is listed in the requirements and still needs recording in `research.md`:
- If the files can't be loaded while `watch` runs, it records nothing, reports the problem and keeps running. It never treats that as every leaf being removed.
- If the history store fails while `watch` runs, it reports the failure and retries later.
- Edits made in quick succession may be recorded as their net difference.
- `<dir>` is printed as it was given.

The Boundary Context section lists the step 1 criteria this replaces: config-foundation 6.9 and 7.3. It also notes the changed example in config-set-writeback 15.1.

## Document Status
- `.kiro/specs/config-file-sync/requirements.md` is written.
- `.kiro/specs/config-file-sync/spec.json` is at phase `requirements-generated`, with requirements marked generated but not approved.
- Both are committed on `main` (`28e738a`).

## Review Gate
The draft passed after one repair pass. Every heading has a numeric ID and every criterion has the EARS form. There are no technology terms in the requirements. The repair rewrote 5.5 and 6.1 into EARS form and gave a precise ordering rule for `remove` events (2.6).

## Next Steps
Review the requirements, especially the silent-contract choices. Then optionally run a gap analysis before moving to design:
```
/kiro-validate-gap config-file-sync
/kiro-spec-design config-file-sync
```
A3 (po): /kiro-validate-gap config-file-sync