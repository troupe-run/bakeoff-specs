# Consistency check — pass1 step 3: confirmed

## Questions answered by the fallback in step 2's scored run (informational)

- speckitty: When `troupe config watch` is running and a hand edit leaves the configuration unloadable (bad YAML, missing include target, include cycle, or both troupe.yml and troupe.yaml present), should watch keep watching and report the file on stderr, or exit 4?

## Round 1 (2026-10-03T09:57:46+00:00)

### Q1

Question: What should `show PATH --sources` print when PATH resolves to a single scalar value (e.g. option A: a one-value YAML document carrying the `# from <file>` comment, option B: exactly what `get` prints, ignoring `--sources`, or something else)?
  speckitty (step 3): The contract doesn't define `--sources` for a scalar PATH: `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments (get and show, from step 3). Treat it as out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

### Q2

Question: When show prints a string, should it quote every string that a YAML 1.1 or a YAML 1.2 reader would misread (A), or only strings that a YAML 1.2 core reader would misread (B)?
  speckitty (step 3): The contract doesn't say which YAML reader `show`'s output must read back under. The only YAML version it names is YAML 1.2 core schema, for parsing `VALUE` on the command line. Treat the reader as out of contract: your choice — state which you chose and why.
  Consistent with each other? Consistency with the brief's own text (its standing answers in scenario/po-brief.md) is your call: this check compares escalated answers only.

Owner: {"Q1": {"ok": true, "note": "", "seconds": 277.198775249999}, "Q2": {"ok": true, "note": "", "seconds": 11.887831541942433}}
