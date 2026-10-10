I'm keeping it out of contract: history recorded before step 4 is not upgraded. troupe won't detect, convert or fill in lineage for events from steps 1–3, and what any command does with such a store is left undefined and untested.

**Why:**
1. **Any filled-in value would be a guess.** Those events never recorded who made them, how, when, or which change they belonged to. The contract has an "unknown" value for the actor, but none for the timestamp, `via` or `change`. Filling those in means inventing values, which is exactly what the step says not to do.
2. **Nothing needs upgrading.** I checked: there's no theatre with an older store anywhere in the repository. Steps 1–3 only ran against fresh theatres that the tests create.
3. **It would be work with no contract behind it.** The constitution says to build for the current stage only. A migration would be extra code with no defined behaviour to test it against.

Your configuration files aren't affected either way: lineage only changes troupe's own store under `.troupe/`.

I rewrote decision D-37 in `specs/004-config-lineage/spec.md` to state this choice and reasons, and updated the checklist note to match. It's committed on `main` as `1d2cb85`, not pushed. The spec is ready for `/speckit-plan`.