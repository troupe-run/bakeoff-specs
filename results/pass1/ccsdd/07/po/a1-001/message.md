Step 7 is done and committed on `main` (last commit `e6c8a62`), with nothing pushed and no PR. The full suite passes (4347 tests), and `mypy --strict` and ruff are clean. Final validation returned GO, and I also ran your scenarios through the real CLI against a local HTTP server.

**What works now**
- **Remote includes:** an `https://` or `http://` string is fetched when the configuration loads, as YAML if the URL path ends `.yml`/`.yaml` and as text otherwise. A failed fetch exits 4, naming the local file, the key path and the URL. `show --sources` labels remote values with their URL.
- **Remote content is read-only:** changing a remote value exits 3, and the message quotes the include line from the local file, for example: `troupe.yml: team.model: the value comes from the remote include http://…/team.yml (line 2); troupe does not change remote content: change that include line or the shared configuration`. New keys under a remote include become local overrides, so `team: <url>` becomes `team:` / `$ref: <url>` / `newkey: …`.
- **Schema:**
  - If `.troupe/troupe.schema.json` is present, the configuration must validate against it, else exit 4.
  - A `set` that would make it invalid exits 3.
  - Strings marked `"format": "uri"` (found through `properties`, `items` and `additionalProperties`) and strings tagged `!literal` are values, never includes. Every other explicit tag still exits 4.
- **Writing URLs and `file:` strings:** `set hook https://…` writes `hook: !literal https://…`, unless the schema marks that path as a URI or `--include` is given.

**Choices I made where the contract was silent** (all recorded in the spec's `research.md`; say if you want any changed):
- A `file:` include inside remote content exits 4, because there is no local folder to resolve it against.
- `!literal` is allowed only on single values. It exits 4 on a mapping, a list or a key, or when written before an anchor (`!literal &a x`).
- Include-like strings nested inside a mapping or list VALUE are also written `!literal`. A `{$ref: …}` VALUE without `--include` exits 3.
- Remote content is not cached on disk. `watch` never polls URLs, but it re-fetches them on every reload and does watch the schema file.
- `history` also fetches remote includes and checks the schema, since it loads the configuration on every run.
- Fetches time out after 10 seconds. Schema `$ref`s are never fetched over the network.
- Earlier `file:` VALUEs were written plain and became includes. They are now written `!literal` unless `--include` is given, and the older tests were updated to match.

**Two things you might trip over**
- The library behind the schema check, `jsonschema`, is now a dependency. Out of the box it downloads a schema's remote `$ref`, so the validator is set up to never do that.
- Replacing a whole remote include (`set team foo`) still uses the older "change the included file instead" refusal. It exits 3 and contains the URL, but it doesn't give the local line number like the other remote refusals do.

Before starting, I also committed some leftover step 6 changes that were sitting uncommitted (spec notes and roadmap ticks), after checking that the suite passed with them.