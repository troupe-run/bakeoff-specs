Q1: I've opened the first discovery question as decision `01M4AF3KPBFJBKFTDGKQXJ8V3J`.

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
A1 (po): The contract says the schema is JSON Schema 2020-12 and that the loaded configuration must validate against it, else exit 4. A `set` that would make it invalid exits 3. It names no subset of keywords. So validation has to follow JSON Schema 2020-12 as a whole. A validator that refuses some schemas or quietly validates them wrongly does not meet that requirement. Neither the contract nor the brief limits which libraries you may use, so how you implement this, including adding a dependency, is your engineering choice. State what you chose.

Q2: I've opened the second question as decision `01M4AF5NM3WP8S5TWK2BCMHEPE`.

**Question 2: remote content that changes on the server**

**What happens today:**
- Before every command, troupe reconciles: each resolved leaf that differs from the recorded history becomes one event. These events are attributed to "unknown actor, via file".
- `watch` compares the bytes of the local files a load read every 0.25 s. It reconciles only when one of them changes.

With remote includes, a shared team file can change on the server while nobody touches the theatre. The contract says it is "fetched when the configuration loads" and says nothing about history or `watch`.

**Options:**
- **(A) Record it like a hand edit (my recommendation).** The next command's reconcile fetches the URL and records every leaf that changed, with the same "unknown actor, via file" attribution, naming the include URL as the source. `watch` keeps polling local files only. Remote changes are recorded at the next reconcile it does, or the next command. Fetching every 0.25 s is never done.
- **(B) `watch` also polls the URLs**, on a slower fixed interval (say every 30 s), so remote changes are recorded close to when they happen. This adds steady network traffic and timing behaviour that is hard to test.
- **(C) Keep remote leaves out of history.** History would then no longer match what `get`/`show` return, which breaks the step-3 rule that history explains the current configuration.
- **(D) Something else.**

**My recommendation is (A).** It keeps history complete and honest, adds no polling, and reuses the existing reconcile rule unchanged.

The other gaps the contract leaves open are, as I see it, engineering choices. Unless you object, I'll record each one in the spec with its reason:
- **Fetch timeout:** 10 s. A timeout or any non-2xx response counts as a failed fetch, so exit 4.
- **Relative `file:` includes inside a remote file:** these resolve against the URL's directory and are fetched. They never read the local disk.
- **`--in-include` on a new key whose include is remote:** exit 3, naming the include string, because remote includes are read-only.
- **`!literal` on anything but a string:** exit 4.
- **Every other tag:** still exit 4, as in step 6.

Reply A–D or give your own answer, and flag any of the choices above you'd decide differently.

WAITING_FOR_DISCOVERY_INPUT
A2 (po+owner): On “When a remote include's content changes on the server, should the change be recorded in history like a hand edit at the next reconcile, with watch polling only local files (A), should watch also poll the URLs on a slower interval (B), should remote leaves be kept out of history (C), or something else?”: The contract says a remote include "is fetched when the configuration loads" (Remote includes and schema). Reconcile compares "the files with the configuration and emit[s] a set/remove event for each leaf that differs"; every command except `history` reconciles first; `watch` reconciles "within 2 seconds of any change to the config file or an included file" (Sync with files); file-originated events have actor {"kind": "unknown", "id": null} (Lineage). The contract does not say whether content that changes on the server counts as a change for reconcile or for `watch`. Treat that as out of contract: your choice - state which you chose and why.

On “Does a fetch that times out or gets a non-2xx response count as a failed fetch, so exit 4?”: Yes. The contract says a failed fetch exits 4 (Remote includes and schema), and a fetch that times out or gets a non-2xx response has failed. As with any non-zero exit, stdout is empty and stderr must name the offending include or file (Exit codes).

On “Is a 10-second fetch timeout acceptable?”: The contract says a remote include "is fetched when the configuration loads" (Remote includes and schema). Reconcile compares "the files with the configuration and emit[s] a set/remove event for each leaf that differs"; every command except `history` reconciles first; `watch` reconciles "within 2 seconds of any change to the config file or an included file" (Sync with files); file-originated events have actor {"kind": "unknown", "id": null} (Lineage). The contract does not say whether content that changes on the server counts as a change for reconcile or for `watch`. Treat that as out of contract: your choice - state which you chose and why.

On “Should a relative `file:` include inside a remotely fetched file resolve against the URL's directory and be fetched, never reading the local disk?”: The contract says a remote include "is fetched when the configuration loads" (Remote includes and schema). Reconcile compares "the files with the configuration and emit[s] a set/remove event for each leaf that differs"; every command except `history` reconciles first; `watch` reconciles "within 2 seconds of any change to the config file or an included file" (Sync with files); file-originated events have actor {"kind": "unknown", "id": null} (Lineage). The contract does not say whether content that changes on the server counts as a change for reconcile or for `watch`. Treat that as out of contract: your choice - state which you chose and why.

On “Should `set --in-include` on a new key whose include is remote exit 3, with stderr naming the include string?”: Yes. Remote includes are read-only from troupe's point of view: troupe refuses changes to them and tells the user which include line to change instead (step 7 brief). So `--in-include` can't write into a remote file, and the refusal is exit 3, 'write refused (no file changed)' (Exit codes). Put the include string in stderr exactly as it is written in the local file, as the contract requires for refused remote changes (Remote includes and schema).

On “Should `!literal` on a value that is not a string exit 4?”: The contract says a remote include "is fetched when the configuration loads" (Remote includes and schema). Reconcile compares "the files with the configuration and emit[s] a set/remove event for each leaf that differs"; every command except `history` reconciles first; `watch` reconciles "within 2 seconds of any change to the config file or an included file" (Sync with files); file-originated events have actor {"kind": "unknown", "id": null} (Lineage). The contract does not say whether content that changes on the server counts as a change for reconcile or for `watch`. Treat that as out of contract: your choice - state which you chose and why.

On “Should every YAML tag other than `!literal` still exit 4, as in step 6?”: The contract mentions only `!literal` ("A string tagged `!literal` is a literal", Remote includes and schema). It does not define other tags. Out of contract: your choice - state which you chose and why.