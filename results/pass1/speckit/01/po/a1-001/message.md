I've written the specification for step 1 and committed it to `main` as `70df9f2`. It contains no code yet; building the tool is still to come.

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