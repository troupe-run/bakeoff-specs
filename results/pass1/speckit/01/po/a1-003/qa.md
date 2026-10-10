Q1: I've written the specification for step 1 and committed it to `main` as `70df9f2`. It contains no code yet; building the tool is still to come.

- **Feature directory:** `specs/001-config-load-show-set`
- **Spec file:** `specs/001-config-load-show-set/spec.md`
- **Checklist:** `specs/001-config-load-show-set/checklists/requirements.md`. Every item passed on the first check.

**What's in the spec:**
- **Three user stories:** show a setting (P1), change a setting without disturbing the file (P1), and list history (P2), each with concrete examples of input and expected output.
- **Requirements:** each rule in your contract is restated as a separate, testable requirement (general, includes, show, where `set` writes, how `set` writes, history), plus edge cases, what's out of contract, and five measurable success criteria.
- **No open questions:** where the contract left a choice, I picked the option that can't lose data and recorded why in the spec as D-1 to D-9. The ones most worth checking:
  - **D-1:** `show` and `set` read the files as they are at that moment, so hand edits are always respected. The event store only keeps history. A `set` works out its events by comparing the configuration before and after the change. Hand edits made between commands are not recorded as events.
  - **D-2:** the first import happens on the first command that loads the configuration successfully, and it stands even if that command then fails with exit 2, 3 or 5.
  - **D-5:** if the top level of the main file isn't a mapping, the tool exits with 4. An empty file counts as an empty mapping.
  - **D-6:** new or rewritten lines use the file's line ending, decided by its first line ending. The same rule decides whether a text-include target "used CRLF".

`.specify/feature.json` is in `.gitignore`, so it was written locally but not committed; it only tells the next Spec Kit commands which folder to use. The project has no extension hooks registered, so none ran.

**Next step:** `/speckit-plan` (or `/speckit-clarify` if you want to change any of D-1 to D-9 first).
A1 (po): /speckit-plan

Q2: I've written the implementation plan and design documents for step 1 and committed them to `main` as `7d5054e`. There is still no code; only the design is done. No extension hooks are registered, before or after planning.

**Generated in `specs/001-config-load-show-set/`:**
- `plan.md`: summary, technical context, file layout under `src/troupe/` and `tests/`, design overview, and the constitution check. All principles pass both before and after the design, so there are no exceptions to justify.
- `research.md`: technical choices R-1 to R-16, plus finer behaviour choices B-1 to B-12 for corners the contract doesn't cover.
- `data-model.md`: the parsed configuration (where each value sits in its file), leaves, how a `set` produces its events, and how the event store works.
- `contracts/cli.md`: command syntax, output formats and the exit-code table.
- `quickstart.md`: the quality-gate commands and a 13-step manual walk-through.

**Main design decisions:**
- **Two libraries, checked in a scratch project:**
  - `ruamel.yaml` is used only to find where each value sits in the file. Its own writer reformats files, so it is never used to write.
  - `eventsourcing` 9.5.5 stores events in `.troupe/events.sqlite3`. I confirmed they survive between separate commands.
- **Own number/boolean rules:** one function applies the YAML 1.2 rules for telling strings, numbers, booleans and null apart. It is used both for file values and for `VALUE` on the command line.
- **Check before every write:** a `set` edits only the needed bytes of the one file holding the value. Before writing, the tool re-reads the edited configuration in memory. If the target value is wrong or anything else changed, it refuses with exit 3 and writes nothing.
- **Safe writes:** files are replaced in one step, so they are never left half-written, and nothing is written when a `set` changes nothing.

**Corners where I made a call (worth checking before implementation):**
- **B-3, a scalar replaced by a block collection:** the old value is removed from the key's line, any end-of-line comment stays at its column, and the new lines go below.
- **B-4 and B-5, replacing a collection:** the whole old collection is replaced, and comments inside it are removed with it.
- **R-3, `VALUE` that isn't a flow node:** something like `a: b` or `- x` is treated as a usage error (exit 2).

**Next step:** `/speckit-tasks`.
A2 (po): /speckit-tasks