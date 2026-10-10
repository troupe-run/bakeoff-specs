I've written the full plan for `troupe-config-load-show-set` and committed it on `main` as `ad4ba9f`, without pushing. `openspec validate --strict` passes. No project code has been written yet.

**What's in `openspec/changes/troupe-config-load-show-set/`:**
- **`proposal.md`**: why this step is needed, what it builds, the four capabilities, and the impact: a new uv project and two runtime libraries, `eventsourcing` and `ruamel.yaml`.
- **Specs**, one per capability, with concrete before/after examples:
  - `config-loading`: how the CLI is called, finding the config file, includes, path syntax, parsing `VALUE`, how values are printed, exit codes, and keeping state under `.troupe/`.
  - `config-show`: printing a value; mappings and lists exit 5.
  - `config-set`: every write-back rule in the contract, each with exact expected file bytes.
  - `config-history`: one event per leaf value, importing on first use, set/remove events, and the JSON Lines output.
- **`design.md`**: the parser reports where each value starts and ends in the file, and every edit replaces just that stretch of text. Before writing, each `set` is checked by re-reading the changed files and reloading the whole configuration. If the result isn't exactly the requested change, it exits 3 and changes nothing.
- **`tasks.md`**: 7 groups of tasks, each with its own tests, ending with end-to-end runs of `uv run troupe …` and the mypy and ruff checks.

**Choices the contract leaves open (all recorded in `design.md`; worth a look):**
- **Files on disk are the source of truth.** `show` and `set` read the current files every time. The event store records what troupe changed and drives `history`. Otherwise a hand edit made after the first import would be invisible to `show`. This is the most significant choice.
- **Non-string values in a text include:** `set` refuses with exit 3 in every case, not only when the target file uses CRLF line endings.
- **Setting below a scalar:** something like `set model.name x` when `model` is a scalar exits 5 rather than turning the scalar into a mapping.
- **Event order:** when one `set` both adds and removes leaves, its `set` events come before its `remove` events.
- **Small edge cases:**
  - An empty `VALUE` means null.
  - An empty or comment-only config file acts as an empty mapping.
  - Anchors and aliases are refused with exit 4 until step 6.

When you're ready to implement, run `/opsx:apply`.