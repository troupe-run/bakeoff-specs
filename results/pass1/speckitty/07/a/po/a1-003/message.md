Decision `01M4AF5NM3WP8S5TWK2BCMHEPE` is resolved with option A. I've settled every point you left to me, and the full scope is below. Please confirm it before I write the spec.

## Intent Summary: step 7, remote includes and a schema

**Who and when:** a theatre owner whose configuration includes shared team files by URL, or whose settings hold URLs. They run any `troupe config` command, and `set` in particular.

**What the contract requires:**
1. **Remote includes.** A string starting `https://` or `http://` is an include. It is fetched on every load: as YAML if the URL path ends `.yml`/`.yaml`, otherwise as text. Both the scalar form and the `$ref` mapping form with overrides work, as in step 5. A failed fetch exits 4, with empty stdout and stderr naming the include.
2. **Remote includes are read-only.** Changing a value that comes from a remote include exits 3 and changes no file. stderr contains the include string exactly as written in the local file. A new key under a remote include becomes a local override, as in step 5. `--in-include` into a remote include exits 3 the same way.
3. **The schema.** If `<dir>/.troupe/troupe.schema.json` exists, the loaded configuration must validate against it, or the command exits 4. A `set` that would make it invalid exits 3 and changes no file. A string whose schema has `"format": "uri"` is a literal, not an include. That schema is found from the root through `properties`, `items` and `additionalProperties` only, as the contract says. A string tagged `!literal` is also a literal.
4. **Writing include-looking values.** `set PATH VALUE` with a string that would be read as an include, at a `PATH` the schema doesn't mark `format: uri`, writes it tagged `!literal`. Passing `--include` writes it plain, so it becomes an include.

**Rule that always holds:** no `set` ever changes a remote file, and a refused `set` changes no file and records no event.

**Main edge case:** a value is overridden locally under a remote include, e.g. `coder: {$ref: https://…/coder.yaml, temperature: 0.3}`. `set coder.temperature 0.5` changes the local override, because that value lives locally. `set coder.model x`, where `model` comes only from the remote file, exits 3 naming `https://…/coder.yaml`.

**My choices where the contract is silent** (each will be in the spec with its reason):
- **Schema validation:** `jsonschema`'s full 2020-12 validator. `format` is an annotation, so it is not checked as a validation rule. These exit 4 naming the schema file:
  - a schema that is unreadable, not JSON, or not a valid 2020-12 schema;
  - a `$schema` naming another dialect;
  - a `$ref` that can't be resolved inside the schema document. The schema's own references are never fetched.
- **Server-side changes:** recorded by the next reconcile like a hand edit (actor unknown, via file). `watch` doesn't poll URLs.
- **What `watch` watches:** it also watches the schema file. While a load fails because of a fetch, it retries when a local file changes, and otherwise at most every 10 s instead of every 0.25 s.
- **Fetching:** 10 s timeout. A timeout, a non-2xx status, a connection error or a body that isn't UTF-8 counts as a failed fetch, so exit 4. Redirects are followed. Each URL is fetched once per command and reused when `set` verifies its write.
- **Includes inside a remote file:** relative `file:` includes resolve against the URL's directory and are fetched. Nothing in a remote file ever reads the local disk.
- **Nested remote includes:** the include string reported is the one written in the nearest local file on the chain. A new key whose ancestor is deep inside nested remote content becomes an override in that local file.
- **`show --sources`:** attributes remote values to the absolute URL.
- **`!literal`:**
  - On a scalar, the value is the scalar's text as a string, so `!literal 5` is `"5"`.
  - On a mapping or list it exits 4.
  - Every other tag still exits 4, as in step 6.
  - A `!literal` VALUE in `set` is accepted. Other tags in VALUE still exit 2.
- **`get`/`show`:** print literal strings without the tag, the same way they don't print anchors.
- **Strings inside a VALUE:** a mapping or list VALUE gets the same per-string `!literal` treatment.
- **Replacing a `!literal` value:** the tag is kept only if the new value needs it.
- **`--include`:** accepted only by `set`; other subcommands exit 2.
  - On a value that wouldn't be read as an include, it has no effect.
  - On a `format: uri` path it exits 3.
  - If the new include can't be loaded or makes the configuration invalid, the `set` exits 3 and no file changes.
- **Files with no URL strings, no schema and no `!literal`** behave exactly as in steps 1–6.

One consequence to flag: with no schema file, an existing setting such as `docs: https://example.com` becomes an include and is fetched, as the contract says. Theatres that hold URL values will need a schema entry or a `!literal` tag.

Does this match what you want? Reply "confirmed" or correct anything.

WAITING_FOR_DISCOVERY_INPUT