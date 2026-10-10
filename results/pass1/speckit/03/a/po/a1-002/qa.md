Q1: I've written the step 3 spec and committed it on `main` (commit `2676c1b`, not pushed). It covers only the specification; no code has changed yet.

- **Feature directory:** `specs/003-config-get-show`
- **Spec file:** `specs/003-config-get-show/spec.md`, with its checklist in `checklists/requirements.md`
- `.specify/feature.json` now points to the new directory. Git ignores that file, so it isn't in the commit.

**What the spec says:**
- **`get PATH`** prints a single value exactly as the old `show` did. Asking it for a section exits with code 5, and the error names the path and mentions `config show`.
- **`show [PATH]`** prints a value the same way `get` does. A section, or the whole configuration when no path is given, comes out as YAML with includes filled in and text includes as literal blocks. The printed YAML must read back to exactly the same values and types.
- **`--sources`** adds ` # from <file>` to every line that holds a value. The file is given relative to the theatre directory, e.g. `.troupe/agents/coder.yaml`.
- The step 1 rule that `show` rejects sections (FR-015) is marked as replaced. All other step 1 and step 2 rules still apply: both commands still pick up hand edits first, and the exit codes are unchanged.

**Choices I made where your contract was silent** (recorded as D-20 to D-27 in the spec; tell me if any are wrong):
- **A single value with `--sources`:** it's printed as YAML with the comment on its line. For a plain value like `0.2` that's just `0.2 # from .troupe/troupe.yml`. For a text include it becomes a literal block, because adding a comment to raw text would change the text.
- **Text includes a literal block can't hold exactly**, such as files with Windows (CRLF) line endings: these are printed in double quotes so the value is never shown wrong.
- **`show agents.coder`** prints what's inside the section, without the `coder:` key above it.
- **Layout:** one space before `# from`, 2-space indentation, lists indented under their key, and `{}` / `[]` for empty sections.
- **Files outside the theatre directory** are named with leading `../` rather than as absolute paths.
- **`get --sources`** is rejected as a usage error (exit 2) rather than ignored.

**Checklist:** all items passed first time, and I didn't need to ask you anything. The next step is `/speckit-plan`, or `/speckit-clarify` if you want to revisit any of the choices above.
A1 (po): /speckit-plan