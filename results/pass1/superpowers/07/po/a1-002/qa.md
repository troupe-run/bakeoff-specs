Q1: Step 7 is committed on `main` as `a568313`. Nothing was pushed. All 127 tests pass, including 12 new ones in `tests/test_remote.py` that run against a local HTTP server.

**Remote includes** (`config.py`, `writer.py`)
- Strings starting `https://` or `http://` are includes, and so are `$ref:` values that are URLs. They're fetched when the configuration loads: YAML if the URL path ends `.yml`/`.yaml`, otherwise text. A failed fetch exits 4.
- Troupe never writes to a remote file. Changing a value from one exits 3. That includes setting an existing key, replacing the whole include, writing a new key with `--in-include` and expanding an alias. The message gives the include string exactly as written, with its file and line, e.g. `troupe.yml:2: 'https://…/c.yml'`. When one remote file includes another, it points to the local line that leads to them.
- New keys under a remote include become local overrides, as in step 5.

**Schema** (new `schema.py`)
- `.troupe/troupe.schema.json` is checked as JSON Schema 2020-12 using the `jsonschema` library, which I added as a dependency. If the loaded configuration doesn't validate, the command exits 4. A `set` that would make it invalid exits 3 and changes no files.
- While loading, troupe follows the schema through `properties`, `items` and `additionalProperties`. Strings marked `"format": "uri"` are literals. So are strings tagged `!literal`.
- `set PATH VALUE` writes an include-looking string as `!literal …` unless the schema marks that path as a URI or you pass the new `--include` flag. With `--include`, an existing `!literal` tag is removed and troupe checks that the string is read back as that include.

Some behaviour the contract didn't specify, so I chose it (recorded as decisions 34–42 in `docs/decisions.md`):
- **`file:` inside a remote file** resolves against that file's URL, so a remote file can never point at a local file.
- **`$ref` and `allOf` in the schema aren't followed** when looking for `format: uri`. The contract names only the three keywords above, so a URI defined through a `$ref` will still be read as an include.
- **Setting a remote value to the value it already has** does nothing and exits 0, the same as any other unchanged value.
- **`show` also tags include-looking strings `!literal`**, so its output still reads back as the same configuration.
- **`watch` doesn't poll remote URLs.** It fetches them again only when a local file changes.
A1 (runner): /superpowers:finishing-a-development-branch