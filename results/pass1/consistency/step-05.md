# Consistency check — pass1 step 5: confirmed

## Questions answered by the fallback in step 4's scored run (informational)

- speckitty: Should every `troupe config` command check TROUPE_ACTOR before loading anything, so that a bad TROUPE_ACTOR exits 2 even when the configuration also cannot be loaded (exit 4)?
- speckitty: If TROUPE_ACTOR is unset and the login name cannot be determined, should the actor be {"kind": "human", "id": null}?
- speckitty: Should a fresh acceptance record be made by re-running acceptance on `feat/troupe-config-lineage` with `--lenient` and merging that branch into `main` again, by creating a `docs/` folder on `main` and re-running there, or by leaving things as they are and relying on the earlier `--lenient` acceptance recorded at `8d4739f`?

## Round 1 (2026-10-05T04:58:49+00:00)

### Q1

Question: Should a `$ref` whose value is not an include string (e.g. `$ref: 5` or `flie:x.yaml`) exit 4 naming the file, rather than be treated as an ordinary key?
  openspec (step 5): The contract defines where the override goes: "the file that contains the include reference (the *including* file)". With nested includes, that is the file holding the reference to the include whose content the key's deepest existing ancestor comes from — in your example, `coder.yaml`. Follow the contract's definition; the change request explains why, the contract says what. For your other seven choices: where the contract's text covers them (the deep-merge rule, existing values changing where they live, refused writes), follow it; where it doesn't (e.g. a `$ref` whose value isn't an include string), it is out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

Owner: {"Q1": {"ok": true, "note": "", "seconds": 442.93851970800006}}
