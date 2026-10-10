Q1: I have one question before I write the spec. The rest I can decide from the contract and the existing code.

**Question: what should `troupe config show PATH --sources` print when PATH names a single scalar?**

The contract says `show` prints a scalar "like `get`" (the raw value, not YAML). It also says `--sources` prints "the same YAML" with `# from <file>` on every scalar line. Those two rules don't fit together for a single scalar, so this case is unresolved.

- **(A) Print the scalar as YAML with the comment (my recommendation).** `show port --sources` → `8080  # from .troupe/troupe.yml`. A text include prints as a literal block with the comment on its header line: `|  # from prompts/sys.md`, then the indented text. Output with `--sources` is always valid YAML, and every scalar gets its source.
- **(B) Ignore `--sources` for scalars.** The output is identical to `get`, so the user never learns the file.
- **(C) Print the plain value, then a separate `# from <file>` line.** The value stays raw and the source still shows, but the output is neither `get` output nor valid YAML.

Here are the choices I'll make and record unless you object:

1. **YAML layout**
   - Two-space indentation.
   - List items as `- ` indented under their key.
   - Keys and strings unquoted when that reads back as the same value; otherwise single-quoted, or double-quoted when needed. This follows the quoting rules already used by `set`.
   - Values `true`, `false` and `null`; floats printed the way `get` prints them.
   - Empty collections as `{}` and `[]`.
   - No `---` document marker.
2. **Multi-line strings** not from a text include also print as literal blocks, using `|-` or `|+` to keep trailing newlines exact.
3. **Source comment on a text include** goes on the `key: |` header line, because a comment can't go inside the block.
4. **Source paths** are relative to the theatre directory, e.g. `.troupe/troupe.yml`. A target outside the theatre gets a `../` path.
5. **What `show` prints** comes from the current files, after reconciling hand edits first, as every command except `history` now does.
6. **Exit codes:** a missing path is exit 5. `get` on a mapping or list is also exit 5, with a stderr message that points to `troupe config show PATH`.
7. **Help text:** `show` no longer refuses mappings and lists. The help text and existing tests move to `get`.

Reply with A, B, C or your own answer, plus any corrections to the list above.

WAITING_FOR_DISCOVERY_INPUT
A1 (po): On “What should `troupe config show PATH --sources` print when PATH names a single scalar: (A) the scalar as YAML with a `# from <file>` comment, (B) exactly what `get` prints, ignoring `--sources`, or (C) the plain value followed by a separate `# from <file>` line?”: The contract doesn't define `--sources` for a scalar PATH. `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments. Treat this case as out of contract. The choice is yours: state which option you chose and why.

On “Are there any corrections to the listed choices (YAML layout, multi-line strings as literal blocks, source comment on the block header line, source paths relative to the theatre directory, show reconciling first, exit 5 for a missing path and for get on a mapping or list with a pointer to config show, help text and tests moving to get)?”: No corrections. None of the listed choices contradicts the contract. Where a choice covers something the contract doesn't specify, such as YAML layout details or `../` paths for targets outside the theatre, it is yours to make, as long as you record what you chose.

Q2: The spec for mission `troupe-config-get-show-01M411XB` is written and committed (`92a3460`) on `feat/troupe-config-get-show`. No code has changed yet, and nothing is on `main` so far. Your request isn't done until the finished feature is merged into `main` at the end of the mission.

**Your scalar `--sources` case:** I chose option A. `show port --sources` prints `8080 # from .troupe/troupe.yml`. A text include prints as a literal block with the comment on its `key: |` header line. With A, `--sources` output is always valid YAML and every value shows its file, which matches "the same YAML". Without `--sources`, a single value still prints exactly like `get`. The choice is recorded as decision DM 01M411YHFR2PMJEJWMHX4KN9C4.

**What the spec covers:**
- **`get PATH`** prints one value byte-for-byte as `show` did in steps 1 and 2. A section is refused with exit 5 and a stderr message that mentions `config show`. A missing path is also exit 5.
- **`show [PATH]`** prints a single value like `get`. A section, or the whole configuration when PATH is omitted, prints as block-style YAML. Includes are resolved and text includes appear as literal blocks.
- **`--sources`** adds ` # from <file>` to every line that holds a value and to no other line. File paths are relative to the theatre directory, with `../` for files outside it.
- **Both commands** pick up hand edits first and never change any configuration file.

The layout choices you approved are all in the spec, plus three details I settled while writing it:
- **CRLF text includes** print double-quoted with escapes, because a literal block can't keep carriage returns.
- **Source comments** have exactly one space before the `#`. My earlier example showed two; the spec uses one.
- **`get` doesn't accept `--sources`** and exits with a usage error (exit 2) if given it.

This isn't a rename across the codebase: `show` keeps its name, and single-value reads behave the same as before. Only the existing tests that expect `show` to refuse a section move over to `get`.

The quality checklist passes on every item and there are no open clarification markers. One file, `status.events.jsonl`, was modified again by the commit step and isn't committed yet. The next step is `/spec-kitty.plan`.
A2 (po): /spec-kitty.plan