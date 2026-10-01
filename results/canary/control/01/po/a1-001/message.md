I've built the configuration subsystem and committed it to `main` (c736bd4). `uv run troupe config show|set|history --theatre DIR` works from the repository root, and the 23 pytest tests pass (`uv run pytest`). I also ran a few dozen `set` cases by hand against sample theatres and checked each `git diff`: only the value's bytes changed.

**How it works**
- **Loading** (`model.py`): reads `troupe.yml` or `troupe.yaml` and follows `file:` includes recursively. YAML targets are embedded; any other target becomes its exact text. Values are read with the YAML 1.2 core schema. Missing files, cycles, both config files present, or invalid YAML give exit 4.
- **Writing** (`edit.py`): every change is an edit to a byte range in the original file. After applying the edits, any end-of-line comment on a changed line goes back to its column, or sits one space after the value if the value now reaches it. This covers the rules in the contract: quoting styles, literal blocks, folded rewrapping, placing new entries below trailing comments, flow collections, CRLF, and write-backs into included and text-include files.
- **Safety check:** before touching any file, the new text is re-parsed and the whole resulting configuration is compared with what's expected. If they don't match, the command exits 3 and changes nothing.
- **History** (`store.py`): an `eventsourcing` aggregate stored in SQLite at `.troupe/state.sqlite`. The first command imports every leaf; each `set` records `set`/`remove` events worked out from the configuration before and after. A `set` that changes nothing records nothing.

**Choices where the contract was silent**
- **Setting a whole collection over an existing one of the same kind** (e.g. `set tags "[a, b, c]"`) only changes the entries that differ: changed items are rewritten, missing ones removed, new ones appended. It does not rewrite the whole list in block style. Comments and flow style are kept, so the diff is smaller.
- **Empty `{}` / `[]`** count as leaves in `history`, so setting a value to an empty collection still shows up there.
- **The state file is created only when a command succeeds.** A failed command leaves `.troupe/` untouched, and the next command imports the theatre as before.
- **Replacing a path whose whole value comes from a YAML include** is refused with exit 3 even when the new value equals the current one.
- **Setting a key inside a null value** (e.g. `a.b` when the file has an empty `a:`) exits 5, because `a` is a scalar, not a mapping.

**Limitations**
- **Unusual layouts** the writer doesn't recognise are refused with exit 3 rather than risking a bad write. That can include deleting keys from a compact list-item mapping, or a list whose `-` markers aren't where they'd normally be.
- **Adding a key at the end of a file with no final newline** adds a line break after the old last line. The new last line is left without one, like the original.