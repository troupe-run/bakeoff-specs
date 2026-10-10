I've written the step 7 spec and committed it to `main` as `ddf54c7`. This step only produces the spec; nothing is implemented yet.

- **Feature directory:** `specs/007-remote-includes-schema/`
- **Spec file:** `specs/007-remote-includes-schema/spec.md`
- **Checklist:** `specs/007-remote-includes-schema/checklists/requirements.md`. Every item passed after one wording fix, and there are no `[NEEDS CLARIFICATION]` markers.
- **Hooks:** `.specify/extensions.yml` registers no hooks, so none ran.

**What the spec covers:** The contract text is quoted word for word. Five user stories cover:
1. Reading remote includes.
2. Refusing changes to remote values with exit 3. The error message names the include string plus the local file and line that hold it.
3. Literals, marked either by `format: uri` in the schema or by the `!literal` tag.
4. Checking the configuration against the schema: exit 4 when it loads invalid, exit 3 when a `set` would make it invalid.
5. `set` adding the `!literal` tag automatically, and the new `--include` flag.

Requirements are numbered FR-600 – FR-650. Where they change step 1 FR-010, FR-020 and step 5 FR-431, the spec says so.

**Decisions I made where the contract is silent** (D-60 … D-71). These four have the most effect, so they're worth checking:
- **D-61:** a `file:` include inside a remote file is resolved against that file's URL and fetched. A remote file can therefore never make troupe read a local file.
- **D-65:** URLs are not watched. Remote content is fetched again on every load, and changes in it are recorded like hand edits (`via: file`, actor unknown).
- **D-66:** to decide whether a string is a literal, the schema is searched only through `properties`, `items` and `additionalProperties`, because those are the three the contract lists. `$ref`, `allOf` and the like are not followed for this, though they still count when checking the configuration. If you want `$ref` followed, this is the one decision to change.
- **D-70:** `--include` exits 2 if the value contains nothing that would be read as an include, and exits 3 if the schema marks the setting `format: uri`.

Smaller defaults I picked: a 10-second fetch timeout, redirects followed, no caching, no authentication, and `format` not checked during validation (the JSON Schema 2020-12 default).

`.specify/feature.json` now points at the new directory. Git ignores that file, so it isn't in the commit.

The next step is `/speckit-plan`, or `/speckit-clarify` first if you want to revisit any of the decisions above.