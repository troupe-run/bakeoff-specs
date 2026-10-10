## Feature name
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