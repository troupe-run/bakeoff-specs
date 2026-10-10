## Implementation complete

Step 7 (remote includes and a schema) is built and committed to `main` as 8 commits, from `273bd08` to `b813885`. Nothing was pushed. All 30 tasks are done, the change is archived, and its specs are merged into `openspec/specs/`.

On the final run, all 773 tests passed and mypy, ruff and strict spec validation were clean.

**What now works:**
- **Remote includes:** `https://` and `http://` strings are includes, in plain form or as `$ref`. Each URL is fetched at most once per command. A failed fetch exits 4 and names the URL.
- **Remote values are read-only:** any change to them exits 3. The message quotes the include line in your own file, with the file name and line number, for example `… included by https://… in .troupe/troupe.yml line 3: change that include line instead`. New keys still become local overrides.
- **Schema:** `.troupe/troupe.schema.json` marks `format: uri` settings as plain strings, so they are never fetched. The configuration must be valid against it (exit 4 when loading, exit 3 for a `set`), and `watch` also watches this file.
- **`!literal`:** the tag now loads instead of failing. `set` writes include-looking values with it unless `--include` is given. This is the breaking change from the plan, and the README has an upgrade note.

**Where I departed from the plan, all recorded:**
- I put the `Literal` marker in `schema.py` rather than `edit/scalars.py`. design.md now says so.
- I renamed `include_target` to `include_string`, since it now returns the whole include string rather than just its target.
- I corrected two spec examples to match the existing rule that end-of-line comments keep their column. The behaviour was right; my written expectations were wrong.

**Choices you may want to revisit:** the ten points the contract left open are now README decisions 48–61. Each would be a small change in one place if you disagree.