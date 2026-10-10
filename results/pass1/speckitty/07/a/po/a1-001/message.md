I've opened the first discovery question as decision `01M4AF3KPBFJBKFTDGKQXJ8V3J`.

**Question 1: how does troupe validate against the schema?**

The contract says the loaded configuration must validate against `.troupe/troupe.schema.json` (JSON Schema 2020-12), or troupe exits 4. A `set` that would make it invalid exits 3.

**What I found in the repo:**
- The only runtime dependencies are `eventsourcing` and `ruamel.yaml`. Nothing can validate JSON Schema today.
- TROUPE-004 fixes the platform (Python 3.12+, uv). It doesn't forbid new libraries, but it would be the first one added since step 1.
- The contract only says which keywords decide "is this a URI literal": `properties`, `items`, `additionalProperties` and `format: uri`. Validation itself is "must validate against the schema", with no subset named.

**Options:**
- **(A) Add the `jsonschema` library.** Validation follows the full 2020-12 standard. `format` stays an annotation, as 2020-12 says by default, so a `format: uri` value isn't rejected for not looking like a URI. It only means "this is a literal". Errors are reported with the failing path and the schema file named.
- **(B) Write our own validator for a subset of keywords** (`type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`, …). There's no new dependency, but any schema that uses an unsupported keyword would either have to be refused or be validated wrongly without anyone noticing.
- **(C) Something else.**

**My recommendation is (A).** "Validate against JSON Schema 2020-12" is only honest with a complete validator. A partial one risks accepting invalid configuration without telling anyone, which is the outcome the charter treats as worst.

Reply A, B or your own answer.

WAITING_FOR_DISCOVERY_INPUT