The spec for mission `troupe-config-get-show-01M411XB` is written and committed (`92a3460`) on `feat/troupe-config-get-show`. No code has changed yet, and nothing is on `main` so far. Your request isn't done until the finished feature is merged into `main` at the end of the mission.

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