`troupe config show`, `set` and `history` are built and committed on `main`, and all 50 tasks in `tasks.md` are marked done. Nothing was pushed. The final full run passed: `uv run pytest` 355 passed, `mypy --strict src tests` no issues, `ruff check` and `ruff format --check` clean.

**Commits:**
- `568a103`: loading with includes, value typing, the event store with first-run import, the CLI, and `show`
- `0c455a2`: `set`, which edits only the bytes of the changed value
- `6a3cd34`: end-to-end `history` tests
- `2a41167`: README, a test that every failure names its path or file, and `--theatre` accepted before the subcommand

**How `set` works:** it edits only the bytes of the value in the one file that holds it. Before writing, it re-reads the whole configuration with the edit applied. If the new value doesn't read back exactly, or any other setting would change, it refuses with exit 3 and leaves every file alone. Files are replaced in one step, never half-written.

**Tests:** end-to-end tests run the real `troupe` command (one literally as `uv run troupe` from the repo root) and compare every file byte for byte before and after. To check the tests catch real failures, I broke seven behaviours on purpose, one at a time; the relevant tests failed every time.

**Bugs found and fixed along the way:**
- **Folded values:** ruamel inserts `\x07` markers into `>` scalars where lines were folded, so `show` printed them. These are now removed when the value is read.
- **Empty values:** for a key with no value (`a:`), ruamel's end position points at the next line. The first version of `set` deleted the newline there; it now treats the empty value as sitting right after the colon.

**Decisions made during implementation** (recorded in `research.md`):
- **B-13:** when a flow list or mapping gets a new entry, an end-of-line comment on that line stays at its column (one space if the line now reaches it). The contract only states this for changed values.
- **B-14:** changing a folded (`>`) value that already contains more-indented lines is refused with exit 3, rather than guessing how to re-wrap it.
- **B-15:** when a literal block switches to keep chomping (`|+`), the blank lines right after it become part of the value.
- **R-8, corrected:** U+2028 and U+2029 are written literally inside double quotes, as the contract requires; I confirmed they read back correctly.

**Worth checking before step 2:**
- **Scalar replaced by a mapping or list:** I kept the end-of-line comment at its column, so `model: default  # pick one` becomes `model:          # pick one` with the new lines below. The contract's wording ("the key's line keeps its bytes up to and including its end-of-line comment") could be read differently. If the tests expect another layout, the change is local to `planner.py`.
- **`--theatre` before the subcommand:** this is accepted as well as the contract's placement after it. That's an addition the contract didn't ask for.

The test suite takes about 100 seconds, mostly from starting the CLI as a separate process for each test. No extension hooks are registered for implementation.