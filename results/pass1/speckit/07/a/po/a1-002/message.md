I've written the step 7 plan and design documents and committed them on `main` as `20560a2`. This is design only; no code has changed.

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