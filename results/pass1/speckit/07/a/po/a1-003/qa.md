Q1: I've written the step 7 spec and committed it to `main` as `ddf54c7`. This step only produces the spec; nothing is implemented yet.

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
A1 (po): /speckit-plan

Q2: I've written the step 7 plan and design documents and committed them on `main` as `20560a2`. This is design only; no code has changed.

- **Branch:** `main` (the setup script reported `007-remote-includes-schema`, but that's the spec folder name; no branch was created).
- **Plan:** `specs/007-remote-includes-schema/plan.md`
- **Also written:**
  - `research.md`: 13 technical decisions, U-1 … U-13
  - `data-model.md`
  - `contracts/cli.md`
  - `quickstart.md`
- **Constitution check:** all six principles and the technical constraints pass, before and after the design, with nothing to justify.
- **Hooks:** none are registered, so none ran.

**Main design choices:**
- **New dependency:** the plan adds `jsonschema` (version 4.18 or later) to validate against JSON Schema 2020-12. I confirmed it resolves from the package index. URL fetching uses the Python standard library.
- **Remote files are tracked separately from local ones.** `watch` re-reads every local file from disk on each poll, so a URL in that list would look changed every time and trigger endless reloads. This also means URLs are never watched, as the spec decided.
- **The loader decides what is an include.** It now handles URLs, tracks where each value sits in the configuration (for the schema's `format: uri` lookup), honours `!literal`, and checks the schema as its last step. Every command and `watch` get that check without further changes.
- **One check blocks remote writes.** A single guard at the point where a planned change is written catches every case: existing values, list appends, text includes and `--in-include`. It names the include string as written, plus the local file and line.
- **A `set` checks itself against the same remote content.** After planning a change, `set` reloads to verify it. That reload reuses what was already fetched, so the check can't be thrown off by the remote file changing in between.

**Two existing behaviours need fixing:**
- `!literal 3` currently loads as the number 3; the spec requires the string `"3"`.
- The byte range `set` replaces for a value starts at its tag, so changing a tagged value today would silently drop `!literal`.

Only one existing test file (`tests/unit/test_render.py`) contains URL strings; it may need updating once those strings count as includes.

The next step is `/speckit-tasks`.
A2 (po): /speckit-tasks