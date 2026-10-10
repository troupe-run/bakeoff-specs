I've written the spec for step 1 and committed it on `main` (`540c4fe`). It covers load, `show`, `set` and `history`. Nothing is implemented yet.

- **Feature directory:** `specs/001-config-load-show-set`
- **Spec file:** `specs/001-config-load-show-set/spec.md`
- **Quality checklist:** all items pass, saved in `checklists/requirements.md`. I wrote no clarification markers.
- **Extension hooks:** none are registered, so none ran.
- **Not committed:** `.specify/feature.json` is gitignored, so it exists locally but isn't in the commit.

**What the spec contains:**
- **Three user stories:** reading a setting (P1), changing a setting without disturbing the file (P1), and listing changes (P2), each with acceptance scenarios.
- **Requirements:** the full contract written out as numbered requirements, grouped into General, Includes, `show`, where `set` writes, how `set` writes, and `history`.
- **Edge cases and success criteria:** the edge cases listed, plus success criteria checked by comparing files byte-for-byte before and after a change.

**Decisions I made where the contract leaves room** (recorded with reasons under Assumptions; each can be changed with `/speckit-clarify`):
1. **The files, not the stored history, are what `show` and `set` read.** After someone hand-edits a file, `show` prints the edited value, and `set` takes its "old" value from the file. The stored history isn't updated to match hand edits ("importing is not reconciling"). This is the most important decision; if you meant `show` to read the stored history instead, now is the time to say.
2. **A command that fails records nothing**, not even the first import, so "write refused (no file changed)" holds strictly.
3. **Before writing, `set` checks the result.** If the changed files wouldn't load or wouldn't read back as `VALUE`, it exits 3 and changes nothing. This also covers writing a `file:` string whose target doesn't exist.
4. **Errors and node types:**
   - A value that isn't valid YAML, or a malformed path like `a..b`, exits 2.
   - Setting a key under a null value (`a.b` when `a` has no value) exits 5.
   - An empty `troupe.yml` counts as an empty configuration.
   - Empty `{}` and `[]` produce no history events.
5. **File details:** lines added to a file keep its LF or CRLF line endings and its final-newline state. Infinity and NaN are written as `.inf`, `-.inf` and `.nan`.
6. **Event order within one `set`:** removals first, then sets, each in document order.

The next step is `/speckit-plan`, or `/speckit-clarify` first if you want to revisit any of these decisions.