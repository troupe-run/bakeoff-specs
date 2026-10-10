Q1: I've written the plan for step 3 as the OpenSpec change `config-get-and-show` and committed it on `main` (663cef9). It passes `openspec validate --strict`. No project code has changed yet.

**What's in it** (`openspec/changes/config-get-and-show/`):
- **`proposal.md`**: `get PATH` takes over what `show` did in steps 1 and 2. `show [PATH] [--sources]` now prints sections and the whole configuration as YAML. That is a breaking change for anything relying on `show` exiting 5 on a mapping or list; the fix is to call `get`.
- **Specs**:
  - `config-get` (new): reads one value. A mapping or list exits 5, and stderr names the path and mentions `config show`.
  - `config-show`: covers printing a value, printing collections as YAML, and `--sources`. Each has scenarios with the exact expected output. The old rule "show refuses collections" is removed.
  - `config-cli`: `get` is added to the subcommands, and `show`'s PATH becomes optional.
  - `config-sync`: `get` reconciles hand edits first, like `show`.
- **`design.md`**: a new `render.py` walks the loaded configuration, which already records the file each value came from. Quoting and literal blocks reuse the helpers `set` already uses to write values. Tests read the output back and compare values and types.
- **`tasks.md`**: 14 tasks in 4 groups: `get`, YAML rendering, the new `show` with README, then the full test, type and lint run and commits.

**Choices I made where the contract is open** (each is recorded in design.md for review):
1. **`--sources` on a single value** prints it as YAML with the comment (`x # from .troupe/troupe.yml`), not the plain `get` form. A bare value can't carry the comment.
2. **Comment format**: one space, `#`, one space, then the file. For a literal block it goes on the `|` line. Lines showing `{}` or `[]` get no comment, since they hold no scalar.
3. **File names in comments** are relative to the theatre directory with `..` folded away, so the config file reads as `.troupe/troupe.yml`. Symlinks are not followed, so the path matches how you named the theatre.
4. **Quoting in YAML output**:
   - Strings are written plain when that reads back as the same string. Otherwise they get single quotes, then double quotes, the same rule `set` uses.
   - Every multi-line string becomes a literal block when one can hold it exactly, not only text includes.
5. **`get` reconciles hand edits first**, like `show`.

The artifacts are ready for review. When you are ready, run `/opsx:apply`.
A1 (po): /opsx:apply