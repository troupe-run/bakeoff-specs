I've written the step 5 spec for CR-A ("keep shared includes shared") and committed it on `main` as `59ae086`. Nothing was pushed. This step only produces the spec; no code has changed, so the request isn't delivered yet.

- **Feature directory**: `specs/005-include-overrides`
- **Spec file**: `specs/005-include-overrides/spec.md`. `.specify/feature.json` now points at this directory. It's gitignored, so it wasn't committed.
- **Checklist**: all items pass on the first check, with no open questions. It's in `checklists/requirements.md`.
- **Extension hooks**: none are registered, so none ran.

**What the spec says**
- **Stories:** four.
  - Adding a new setting under a shared section writes it as an override in your own file; the shared file is left untouched.
  - Changing an existing setting updates the override if there is one, otherwise the file it comes from.
  - `get`, `show`, `show --sources` and history all see the merged configuration.
  - List changes stay in the file that holds the list.
- **Requirements:** FR-400 to FR-433. They replace step 1's rule for where a new key is written (FR-022) and refine the rule for changing an existing value (FR-020).

**Choices I made where the contract was silent (D-40 to D-48)**
- **Malformed includes fail to load (exit 4):** a `$ref` that isn't a `file:` string, or override keys on an included file whose content isn't a mapping.
- **`set` refuses (exit 3) if the result wouldn't equal what you set.** For example, setting a section that mixes keys from the shared file and from an override would leave the shared keys merged in. Refusing seemed safer than also editing the shared file.
- **Includes written inline in flow style (`{...}`)** are converted to a flow mapping with `$ref`, since block lines can't go there.
- **`$ref` can't be used as a path segment in `set` (exit 3).** This stops `set` from turning ordinary data into an include by accident.
- **In a chain of includes,** the override goes in the file that directly includes the shared one. Files further out don't change.

Next is `/speckit-plan`, or `/speckit-clarify` first if you want to revisit any of those choices, especially the exit-3 refusal.