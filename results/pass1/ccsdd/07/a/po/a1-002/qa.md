Q1: I've planned step 7 and committed the plan to `main` (not pushed). Step 7 is only planned, not built: remote includes, the schema and `!literal` don't work yet. That takes specs, then implementation.

**Step 7 becomes two new specs, built in this order:**
1. **config-remote-includes**
   - `https://` and `http://` strings become includes, both as plain strings and as `$ref`.
   - They are fetched when the configuration loads, using Python's standard library, with nothing saved to disk.
   - A URL path ending `.yml`/`.yaml` is read as YAML; anything else is text. A failed fetch gives exit 4.
   - Remote content is read-only. One check before `set` writes anything (like the alias check) refuses with exit 3 and quotes the include line as written in the local file.
   - New keys under a remote include become local overrides, as in step 5.
2. **config-schema-literals**
   - Reads `.troupe/troupe.schema.json` using the `jsonschema` library. It's MIT-licensed and I checked that it installs with uv.
   - Settings marked `format: uri` are found through `properties`, `items` and `additionalProperties` only, as the contract says.
   - `!literal` becomes the one explicit tag that's allowed.
   - A configuration that fails the schema gives exit 4 on load, and a `set` that would break it gives exit 3.
   - `set` writes include-looking values as `!literal` unless `--include` is given.

   It depends on the first spec because both need the same rule for which strings are includes.

Doing it all as one spec would have meant more than 20 tasks covering two separate sets of rules. The roadmap also lists step-7 notes for five existing specs: config-foundation, config-set-writeback, config-include-overrides, config-get-show and config-file-sync.

**Choices the contract leaves open:** I didn't stop to ask you about these. Each brief proposes a cautious default to confirm when the requirements are written. The ones you'd most likely want to weigh in on:
- A `file:` include inside remote content gives exit 4, so a remote file can never read local files.
- `watch` doesn't poll URLs. Remote changes are picked up by the next command or local edit.
- Include-looking strings nested inside a mapping or list value also get `!literal`.
- `!literal` on something that isn't a string gives exit 4.

**Commits:**
- `ecaed25`: the working tree already had uncommitted step-6 wrap-up edits (spec notes, roadmap checkboxes, a docstring in `loader.py`). I committed them separately. Only the docstring touches code. ruff and mypy pass on that file and the 321 loader tests pass. The full test run was at 55% with no failures when I stopped it, so it didn't complete.
- `d81b923`: the step-7 roadmap section and the two briefs, `.kiro/specs/config-remote-includes/brief.md` and `.kiro/specs/config-schema-literals/brief.md`.

**Next step:** `/kiro-spec-batch` writes both specs in dependency order. If you'd rather check the first one before batching the rest, run `/kiro-spec-init config-remote-includes` instead.
A1 (po): /kiro-spec-batch