## Requirements summary
The requirements are written in `.kiro/specs/config-get-show/requirements.md`: six requirements with 40 acceptance criteria.

- **R1 `get PATH`**: prints a single value exactly as step 1's `show` did. A mapping or list exits 5, and stderr names the path, the file and `config show`. Bad command lines exit 2.
- **R2 `show [PATH]`**: a value prints like `get`. A mapping, list or the whole configuration (no PATH) prints as YAML. `--sources` can come before or after PATH.
- **R3 YAML layout**: block style with 2-space indents, document order and includes resolved. `{}` and `[]` are used for empty sections. The user's comments, quoting and formatting are not carried over.
- **R4 Values in the YAML**: the output must parse back to exactly the same values. Strings are quoted only when needed. Text includes and other multi-line strings print as literal blocks (`|`, `|-`, `|+`).
- **R5 `--sources`**: each line holding a value ends with ` # from <file>`, relative to the theatre directory with `/` separators. A literal block gets the comment on its header line, and a text include names the included file.
- **R6 Shared behaviour**: both commands reconcile first and never change any file. Errors follow the step 1 conventions, and stdout stays empty on failure.

## Choices I made where the contract is silent
These are listed in the Boundary Context and still need recording in `research.md`. The ones you may want to look at:
- **`show PATH --sources` on a single value** prints it as YAML with the comment, rather than in `get`'s raw form.
- **Text includes with CRLF line endings, or characters a literal block can't hold,** print as double-quoted strings instead of literal blocks. This departs from the contract's "literal blocks", but otherwise the printed value would differ from the real one.
- **`get --sources`** is a usage error (exit 2).

## Document status
- `requirements.md` is written. `spec.json` shows phase `requirements-generated`; the requirements are not yet approved.
- The changes this implies for config-foundation (Requirement 6 now describes `get`) and config-file-sync (`get` also reconciles first) are noted in the Boundary Context. The existing specs themselves are updated during implementation, in the same change as the code.
- Committed on `main` as commit `88ebdc5`.

## Next steps
Approve the requirements or ask for changes, then run:
```
/kiro-validate-gap config-get-show     # optional: compare with the existing code
/kiro-spec-design config-get-show
```