## General (from step 1)

- **Invocation:** `troupe config <subcommand> --theatre <dir> [arguments]`, run as `uv run troupe …` from the
  repository root. `--theatre` defaults to the current directory.
- **Config file:** `<dir>/.troupe/troupe.yml` or `<dir>/.troupe/troupe.yaml`. Neither, or both → exit 4.
- **State:** the implementation may keep state only under `<dir>/.troupe/`, and must not create or modify any
  file other than as this contract's write-back rules require.
- **Paths:** keys separated by `.`; a segment of digits indexes a list (0-based). Keys that contain `.`, and
  mappings with digit-only keys, are out of contract.
- **Values on the command line:** `VALUE` is parsed as a single YAML 1.2 (core schema) flow node: `0.2` is a
  float, `true` a boolean, `null` null, `abc` and `"0.2"` strings, `{a: 1}` a mapping, `[a, b]` a list, and
  `"line one\nline two\n"` a multi-line string.
- **Printing a scalar:** a string is printed exactly, followed by `\n` unless it already ends with `\n`;
  booleans as `true`/`false`; null as `null`; integers in decimal; floats as Python's `repr()` (e.g. `0.2`).
- **Exit codes:** `0` success · `2` usage error · `3` write refused (no file changed) · `4` configuration cannot
  be loaded · `5` path not found, or the path is the wrong kind of node for the command. On any non-zero exit,
  stdout is empty and stderr has a message naming the offending path or file.
- **Out of contract** (behaviour undefined, never tested): files with a TAB before an end-of-line comment,
  multi-document files, YAML anchors/aliases/merge keys (until step 6), concurrent writers.

## Includes (from step 1)

- A string value that starts with `file:` is an **include** of the path after `file:`, relative to the
  directory of the file containing it.
- Target ending `.yml` or `.yaml`: its content is embedded as if written in place of the string.
  Any other target: the value is the target file's exact text.
- Includes are recursive. A missing target, or a cycle, → exit 4.

## `show PATH` (step 1 and 2)

Prints the value at `PATH` if it is a scalar (a text include is a string). A mapping or list → exit 5.

## `set PATH VALUE` (from step 1)

Updates the configuration and writes the change back to the files, **byte-surgically**: after a successful
`set`, the only bytes that differ in any file are those this section requires to change.

Where the change is written:
1. An existing value is changed in the file that contains it. For a text include, the target file's
   content becomes `VALUE` exactly, except that if the target file used CRLF line endings, the new content
   uses CRLF line endings too (`VALUE` must then be a string, else exit 3).
2. A new key is written into the file containing the deepest existing ancestor mapping of `PATH`; missing
   intermediate mappings are created there. *(Changed at step 5.)*
3. `PATH` ending in the index equal to a list's length appends to that list. A larger index → exit 5.
4. Replacing the value at a path whose whole value comes from an include (e.g. `agents.coder` when it is
   `file:agents/coder.yaml`) → exit 3.

How it is written:
- A changed scalar keeps its quoting style if that style can represent the new value; otherwise plain if
  possible, else single-quoted, else double-quoted.
- A new key, and a new string value, copy the quoting style of the preceding sibling key or value; with no
  sibling, plain (or the minimal quoting the text needs).
- A double-quoted scalar escapes only what YAML requires (`\\`, `\"` and control characters, as `\t`, `\n`, …);
  every other character is written literally.
- A new collection value is written in block style at the file's indentation (default 2), unless its parent
  is a flow collection, in which case it is written in flow style.
- A multi-line string replacing a plain or quoted scalar is written as a literal block (`|`, with `|-` when
  the value has no trailing newline). A block scalar keeps its indicator and chomping unless the value's
  trailing newlines require a different chomping.
- A new key whose value is a multi-line string is written as a literal block in the same way, unless its
  parent is a flow collection, where it is written as a double-quoted flow scalar.
- **Folded (`>`) values:** paragraphs whose text is unchanged keep their bytes. A changed paragraph is
  re-wrapped, greedily by word, at the width of the longest content line of that paragraph before the
  change (a single word longer than the width takes a line of its own). A paragraph with no counterpart in
  the old value is wrapped at the width of the value's longest old content line. A change that would put a
  more-indented line into a folded value → exit 3.
- **New entries and trailing comments:** a new list item or mapping key goes after the collection's last
  entry *and below any comment lines that follow it* before the next less-indented line. A comment line
  indented less than a collection's entries ends that collection.
- In a flow collection, a new entry is appended after the last entry, on that entry's line.
- When a scalar is replaced by a block collection, the key's line keeps its bytes up to and including its
  end-of-line comment.
- **End-of-line comments:** when a changed value's length changes, the comment on that line is moved back to
  its previous column; if the new value reaches that column, exactly one space separates value and comment.
  No other line changes. Columns count Unicode code points.

## `history [PATH]` (from step 1)

Prints the configuration's events as JSON Lines, oldest first; with `PATH`, only events whose path equals
`PATH` or starts with `PATH.`. Each line is an object with at least:
`{"seq": <int from 1>, "op": "import" | "set" | "remove", "path": "<dotted>", "old": <json>, "new": <json>}`.
- Events are per **leaf** (a scalar, including a text-include string; list items are `list.0`, `list.1`, …).
- The first command run against a theatre imports it: one `import` event per leaf, `old` null. `history`
  also imports a theatre that has never been imported; importing is not reconciling.
- A `set` emits one `set` event per leaf whose value it changes or creates, and one `remove` event (`new`
  null) per leaf that no longer exists. A `set` that changes nothing emits nothing.
