I've written the step 2 spec and committed it on `main` as `cd9b7dc`. Nothing was pushed. This step only produces the spec; there's no code yet.

- **Spec directory:** `specs/002-config-file-sync`
- **Spec file:** `specs/002-config-file-sync/spec.md`
- **Checklist:** `specs/002-config-file-sync/checklists/requirements.md`. All items pass on the first check, and there are no open clarification markers.
- **Hooks:** `.specify/extensions.yml` registers none, so none ran before or after.
- **Active feature:** `.specify/feature.json` now points at the new directory. That file is gitignored, so it is set locally but not in the commit.

**What the spec covers:**
- **Stories:**
  - Commands pick up edits made while nothing was running.
  - `watch` records edits within 2 seconds.
  - A `set` made while `watch` runs records only its own events.
- **Requirements FR-100 – FR-131:**
  - **`watch`:** the `watching <dir>` line is printed only once it can see changes; it follows includes added or removed by hand; SIGINT or SIGTERM exits 0.
  - **Reconcile:** a value counts as changed only if its type or value differs, so `1` → `"1"` is a change but formatting and comments are not. Events are ordered the same way as a `set`'s, and one reconcile is recorded entirely or not at all.
  - **Which commands:** `show`, `set` and `watch` reconcile first; `history` never does.
  - **Running alongside `watch`:** every change is recorded exactly once.
- **Change from step 1:** step 1 decided that hand edits between commands are not recorded (D-1). This spec replaces that decision; all other step 1 rules still apply.

**Decisions I made where the contract leaves a choice (D-10 – D-17):**
- "The configuration" that files are compared against means what the recorded events describe. That's why a `set`'s own write-back finds nothing new.
- `<dir>` in the `watching` line is the directory as you gave it. If none is given, it is the absolute path of the current directory.
- `watch` prints nothing to stdout except that one line. Load errors go to stderr.
- If a file becomes invalid while `watch` runs (say, a half-saved edit), `watch` reports it and keeps going. If the configuration can't load at startup, it exits with code 4 like the other commands.
- Several quick edits may be recorded together as their net change.
- Events from a reconcile stay recorded even if the command then fails with exit 3 or 5.
- `watch` running alongside one other command is supported. Two `set`s at once, and more than one `watch` on the same theatre, are left out.

Next is `/speckit-plan`. The main design question there is how one change gets recorded exactly once when `watch` and another command run at the same time.