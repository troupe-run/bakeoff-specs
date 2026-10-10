I have one question before I write the spec. The rest I can decide from the contract and the existing code.

**Question: what should `troupe config show PATH --sources` print when PATH names a single scalar?**

The contract says `show` prints a scalar "like `get`" (the raw value, not YAML). It also says `--sources` prints "the same YAML" with `# from <file>` on every scalar line. Those two rules don't fit together for a single scalar, so this case is unresolved.

- **(A) Print the scalar as YAML with the comment (my recommendation).** `show port --sources` → `8080  # from .troupe/troupe.yml`. A text include prints as a literal block with the comment on its header line: `|  # from prompts/sys.md`, then the indented text. Output with `--sources` is always valid YAML, and every scalar gets its source.
- **(B) Ignore `--sources` for scalars.** The output is identical to `get`, so the user never learns the file.
- **(C) Print the plain value, then a separate `# from <file>` line.** The value stays raw and the source still shows, but the output is neither `get` output nor valid YAML.

Here are the choices I'll make and record unless you object:

1. **YAML layout**
   - Two-space indentation.
   - List items as `- ` indented under their key.
   - Keys and strings unquoted when that reads back as the same value; otherwise single-quoted, or double-quoted when needed. This follows the quoting rules already used by `set`.
   - Values `true`, `false` and `null`; floats printed the way `get` prints them.
   - Empty collections as `{}` and `[]`.
   - No `---` document marker.
2. **Multi-line strings** not from a text include also print as literal blocks, using `|-` or `|+` to keep trailing newlines exact.
3. **Source comment on a text include** goes on the `key: |` header line, because a comment can't go inside the block.
4. **Source paths** are relative to the theatre directory, e.g. `.troupe/troupe.yml`. A target outside the theatre gets a `../` path.
5. **What `show` prints** comes from the current files, after reconciling hand edits first, as every command except `history` now does.
6. **Exit codes:** a missing path is exit 5. `get` on a mapping or list is also exit 5, with a stderr message that points to `troupe config show PATH`.
7. **Help text:** `show` no longer refuses mappings and lists. The help text and existing tests move to `get`.

Reply with A, B, C or your own answer, plus any corrections to the list above.

WAITING_FOR_DISCOVERY_INPUT