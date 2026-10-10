Step 7 is done and committed on `main` as `571b7b5`. The full test suite passed (56 existing tests plus 3 new ones), and I checked a few edge cases by hand.

**Remote includes**
- Strings starting `https://` or `http://` are includes, in plain form or as `$ref:`. They're read as YAML if the URL path ends `.yml`/`.yaml`, and as text otherwise. A failed fetch exits with code 4.
- Changing a value that comes from a remote include exits with code 3. The error names the include string exactly as written in the local file.
- If one remote file includes another, the error still names the first include line written in a local file, since that's the one the user can change.
- New keys under remote content are written as overrides in the local file.
- `show --sources` shows remote values as coming from the URL.

**Schema** (`.troupe/troupe.schema.json`, using the `jsonschema` library I added as a dependency)
- If the loaded configuration doesn't match the schema, commands exit with code 4. A `set` that would break it exits with code 3 and writes nothing.
- A string is taken literally, not as an include, if its schema says `"format": "uri"` or it's tagged `!literal`.
- `set` writes a value that looks like an include tagged `!literal`, unless the schema marks that path as a URI or you pass the new `--include` flag. This applies to strings inside list and mapping values too.

**Behaviour changes to be aware of**
- `set x file:foo.yaml` used to create an include. It now writes `!literal file:foo.yaml`; you need `--include` to get an include.
- `watch` doesn't poll remote URLs. They're fetched fresh by every command and whenever a local file changes.

**Choices where the spec was silent**
- A relative `file:` include inside a remote document is looked up next to that document on the server, so it's read-only too.
- When finding the schema for a path, I also follow `$ref`, `allOf`/`anyOf`/`oneOf`, `patternProperties` and `prefixItems`, not just the three keywords the spec names.
- `show` prints `!literal` in front of tagged values.

These are written up in `DECISIONS.md`, and the README is updated.