Q1: I've written the spec for step 1 and committed it on `main` (`540c4fe`). It covers load, `show`, `set` and `history`. Nothing is implemented yet.

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
A1 (po): /speckit-plan

Q2: I've written the implementation plan and its design documents and committed them on `main` (`a12810d`). The plan passes the constitution check on every principle and technical constraint, both before and after design. Nothing is implemented yet.

**Main design decisions:**
- **Reading files:** `ruamel.yaml` is used only to read each file into a tree of nodes with their exact positions in the text. A probe confirmed the positions are exact, including in files with CRLF line endings. Its own output is never used to write files, because it can reformat comments and quoting.
- **Value types:** the tool works out plain values' types itself under the YAML 1.2 core schema. The probe showed ruamel reads `1_000` as an integer, which the core schema doesn't allow.
- **Writing (`set`):**
  - Each change is a small text replacement in the one file that holds the value.
  - Before anything is written, the changed text is re-read in memory. If it doesn't load, or doesn't read back as the requested value, `set` exits 3 and nothing changes.
  - The file is then replaced in one atomic step.
- **History:** events come from comparing every value before and after a `set`. That way a file included in two places produces events at both paths, and earlier hand edits never show up as `set` events.
- **Event store:** an `eventsourcing` record per theatre, kept in `.troupe/troupe-events.sqlite`. A history line's `seq` comes straight from the stored event order, so it never repeats or restarts.
- **Command line:** built with `argparse`, which already exits 2 on usage errors. All exit codes are defined in one module.

**Generated files** in `specs/001-config-load-show-set/`:
- `plan.md`
- `research.md` (12 decisions, each with reasons and alternatives)
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

No extension hooks are registered. The next step is `/speckit-tasks`.
A2 (po): /speckit-tasks