Q1: I've written the plan for step 7 as the OpenSpec change `config-remote-includes-and-schema` and committed it to `main` (`e55580c`); nothing was pushed. `openspec validate --strict` passes. No code has changed yet, so the step isn't delivered until it's implemented.

The artifacts are in `openspec/changes/config-remote-includes-and-schema/`:
- **`proposal.md`**: why the change is needed and what it changes, including one breaking change (below).
- **`specs/`**: a new `config-schema` capability, plus changes to `config-loading`, `config-set`, `config-show`, `config-cli` and `config-sync`. Each case has a concrete scenario.
- **`design.md`**: how it will be built, and the choices made where the contract is silent.
- **`tasks.md`**: 7 groups of tasks, each with its own tests and README updates, ending with the full test, type and lint run, then commit and archive.

**Breaking change:** today `set prompt file:p.md` creates an include. Under the new rule it writes `prompt: !literal file:p.md`. `--include` gives the old behaviour, and three existing tests will be updated to pass it.

**How it will work:**
- **Includes:** one new module decides what counts as an include (prefix, `!literal` tag, schema).
- **Never writing to a URL:** fetched content is kept apart from the local files troupe writes back. Any edit that would land in it is refused with exit 3, from one check in the write step.
- **Fetching:** each URL is fetched at most once per command, even though `set` reloads the configuration several times.
- **Dependency:** adds `jsonschema` for 2020-12 validation. Fetching uses the standard library.
- **Tests:** they use a real local HTTP server and real schema files on disk.

**Choices the contract leaves open (I chose; please override any you disagree with):**
1. A `file:` include inside fetched content resolves against that content's URL, so shared config can never read the user's local files.
2. The literal rule covers every include-looking string in a mapping or list VALUE, not just a single string, so a list of URLs can't silently trigger fetches.
3. `--include` on a path the schema marks `format: uri` is refused with exit 3, rather than quietly writing a literal.
4. Setting an include to its own string without `--include` is refused with exit 3, because it asks for a literal string in place of the include. With `--include` it does nothing, as before.
5. A `!literal` tag stays when its value changes to another string, and is removed when the value becomes a number, boolean, null or collection.
6. The refusal message names the outermost include written in a local file, since that's the only line the user can edit. New keys under nested remote includes become overrides next to that include.
7. Fetching: 30-second timeout, redirects followed only to http/https, a 2xx response and UTF-8 body required, nothing cached between commands.
8. `watch` also watches the schema file but doesn't poll URLs. Remote changes show up at the next reconcile, recorded like hand edits.
9. The schema is always read as 2020-12. `format` isn't checked, and any `$ref` pointing outside the schema file is refused (exit 4), so nothing is fetched for it.
10. `show --sources` names a remote value's source by its URL.

The artifacts are ready for review. When you're ready, run `/opsx:apply`.
A1 (po): /opsx:apply