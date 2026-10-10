I checked the current code (`src/troupe/commands/show.py`, `src/troupe/tree.py`) and the step‑1 contract. The new contract is clear apart from one case.

**Question: what should `show PATH --sources` print when PATH is a single value?**

The contract says `show` on a scalar prints the value the way `get` does, which isn't YAML. It also says `--sources` "prints the same YAML" with `# from <file>` comments. Together, those don't say what `show model.temperature --sources` should print.

- **(A) Recommended: print the value as a one-value YAML document with the source comment.**
  - `0.2  # from .troupe/troupe.yml`
  - A text include prints as a literal block whose header line carries the comment, e.g. `|  # from prompts/sys.md`, then the text.
  - The output still answers "where does this come from?", and the YAML stays valid.
- **(B) Print exactly what `get` prints and ignore `--sources` for scalars.**
  - Simpler, but you lose the source information in exactly the case where you asked for it.
- **(C) Something else.** Tell me what you want.

Unless you say otherwise, I'll make these choices myself, since the contract leaves them open, and record them in the spec:

- **Valid YAML:** the YAML output always reads back to exactly the same values.
  - Keys keep their file order.
  - Strings are quoted only when they'd otherwise read back as something else (`"true"`, `"0.2"`).
  - Empty sections print as `{}` / `[]`.
- **Text-include line endings and chomping:** text includes are always literal blocks, as the contract says, and the trailing-newline marker (`|-`, `|`, `|+`) matches the file exactly. A CRLF file therefore appears with plain line breaks in `show`; `get` still prints the exact bytes.
- **Which lines get `# from`:** only lines that hold a value get a comment. A line that only opens a section (`agents:`) and an empty `{}`/`[]` get none.
- **`get` error text:** for a section, the message names the path and points to `config show`, e.g. `tools is a list, not a scalar; use 'troupe config show tools'`.
- **Unchanged behaviour:** a path that doesn't exist exits 5 for both commands. Both commands still pick up hand edits first, as every command except `history` already does.

WAITING_FOR_DISCOVERY_INPUT