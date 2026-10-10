Step 3 is implemented and committed on `main`. The final check returned GO: the full suite passes (2628 tests, up from 2113 at the start), `mypy --strict` and ruff are clean, and the working tree is clean. Nothing was pushed and no pull request was opened.

## What the commands do now
- **`troupe config get PATH`** prints a single value exactly as step 1's `show` did. On a mapping or list it exits 5; stderr names the file and PATH and says to use ``troupe config show PATH``.
- **`troupe config show [PATH]`** prints a single value the same way as `get`. A mapping, a list, or the whole configuration (no PATH) is printed as block YAML with includes resolved. Every text include is a literal block, CRLF ones included, with their characters unchanged.
- **`--sources`** adds ` # from <file>` to every line that holds a value, including a literal block's `|` header line. The path is relative to the theatre directory with `/` separators, and a text include names the included file.
- **Shared behaviour:** both commands reconcile first and never write a file, and `history` is unchanged.

## How it went
- **Process:** each of the 13 tasks was built test-first by its own subagent and reviewed by a fresh, independent reviewer. All 13 were approved on the first review, none needed a debug round, and each is its own commit (`a55f49b` to `69eca9f`).
- **`set` is unchanged:** the quoting code moved into the new core module `yaml_style` as a pure move. `set`'s byte-exact tests were not modified and still pass (1143 tests).
- **Final check:**
  - The fresh full-suite run exited 0.
  - A smoke run on a real theatre with a YAML include and a CRLF text include gave the expected output.
  - Every requirement from 1.1 to 6.8 is named by at least one test.
  - Dependencies point the way the design says, and nothing outside the planned files changed.
- **Earlier specs and roadmap:** config-foundation and config-file-sync now carry step 3 notes, and the roadmap marks step 3 done.

## Worth knowing
- **A strict-YAML edge case is left alone.** A string containing U+FEFF (a byte-order mark) is printed without quotes. Our loader and ruamel read it back correctly, but strict YAML 1.2 doesn't allow that character there. `set` has always behaved this way, and fixing it would change `set`'s output, which this spec must not do. It's recorded in the task notes for a later write-back follow-up.
- **Literal-block layout exists in two places,** in `show` and in `set`. The decisions behind it (chomping, which characters fit) live in one place. The reviewer judged this acceptable under the design.
- **One subagent restored a file it had broken on purpose with `git checkout -- <file>`.** The file had no uncommitted work, so nothing was lost, and I confirmed `src` had no diff afterwards.