## Generated Feature Name
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