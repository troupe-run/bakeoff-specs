I kept the existing safety check for `set --in-include`, recorded the decision with its reason in a new `DECISIONS.md`, and committed it on `main` as `3c4bd64`. All 53 tests pass.

**What happens:** if the included file is also included somewhere else in the theatre, `--in-include` is refused with exit 3 and no file is changed. The behaviour is the same as before; it's now written down and tested.

**Why this is the safest choice:**
- The contract calls `--in-include` "the step 1 rule", and step 1 writes with this check in place, so keeping it doesn't go against the contract.
- Refusing loses nothing. The user can still add the key as an override (plain `set`) or edit the shared file by hand.
- Skipping the check would quietly change settings the user never named.

**Also in this commit:**
- `DECISIONS.md` also records the earlier choice from CR-A: with nested includes, the override goes in the file holding the nearest include reference, as the contract's wording says.
- A new test checks that `--in-include` is refused and leaves the files alone when another place includes the same file, and that a plain `set` of the same key works as an override.
- The README now mentions the refusal and points to `DECISIONS.md`.