Q1: I've written the step 2 spec and committed it on `main` (`a149b58`). Nothing has been built yet: this step only produces the spec.

- **Feature directory:** `specs/002-config-file-sync`
- **Spec file:** `specs/002-config-file-sync/spec.md`
- **Checklist:** `specs/002-config-file-sync/checklists/requirements.md`. Every item passes on the first check and there are no open clarification questions.
- **Hooks:** none are registered in `.specify/extensions.yml`, so none ran.

**What the spec covers**
- **Four user stories:**
  1. Hand edits made while nothing is running are recorded by the next command.
  2. Live recording with `config watch`.
  3. A `set` made while `watch` runs is recorded once, not twice.
  4. An include added by hand is followed.
- **Requirements FR-050 to FR-066:**
  - `watch` prints `watching <dir>` only once every config file is being observed, and exits 0 on SIGINT or SIGTERM.
  - It reconciles within 2 seconds of a change, including saves where an editor renames a temporary file over the original.
  - The set of watched files changes as includes are added or removed.
  - Formatting-only and comment-only edits record nothing.
  - `history` never reconciles.
  - Event numbering stays correct when `watch` and other commands run at the same time.
- **Changes to step 1:** step 1 said hand edits are never recorded (D-1). The spec states which part of that this step overturns, and clarifies two related step 1 rules (FR-042, FR-043).

**Decisions I made where the contract leaves a choice open (D-10 to D-17), worth a look**
- **`<dir>` in the `watching` line:** the directory exactly as you gave it (from `--theatre` or `TROUPE_THEATRE`), or `.` if neither is set.
- **Broken file while `watch` runs:** nothing is recorded, an error naming the file goes to stderr, and `watch` keeps running. If the config can't be loaded when `watch` starts, it exits 4.
- **What counts as a change:** spelling differences don't count (`'x'` vs `"x"`, `0.20` vs `0.2`), but a change of type does (`1` vs `1.0` vs `"1"`).
- **Several saves within 2 seconds:** these may be recorded as a single net change, but the final state is always recorded.
- **Hand edits pending when you run `set`:** they are recorded first, and the `set`'s own events follow.

The next step is `/speckit-plan`, or `/speckit-clarify` if you want to revisit any of those decisions first.
A1 (po): /speckit-plan