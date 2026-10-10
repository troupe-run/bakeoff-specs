The plan for `troupe-config-get-show-01M411XB` is done and committed on `feat/troupe-config-get-show` (`87eb8b5` for the plan, `0ff8b1b` for the other artifacts). No code has changed yet. I didn't ask further planning questions because you'd said the open choices are mine; each one is recorded in `research.md` as D-1 to D-9.

**Branch:** planning happens on `feat/troupe-config-get-show`, which is also the mission's merge target, and `branch_matches_target` is true. Your requirement is still the final local merge into `main`, with no push and no PR.

**The design:**
- **`get PATH`** keeps the old `show PATH` logic in a new `src/troupe/commands/get.py`. A mapping or list exits 5 with `use 'troupe config show <path>'` in the message.
- **`show [PATH] [--sources]`** prints a scalar exactly like `get`. Anything else goes through a new self-contained module, `src/troupe/yamlout.py`. It builds the output line by line and tags each line with the file its value came from. `--sources` adds `# from <file>` to the tagged lines, so the YAML is otherwise identical with or without it.
- **Quoting and literal blocks** reuse the rules `set` already uses (`src/troupe/writeback/scalars.py`, `src/troupe/writeback/blocks.py`), so reading and writing quote strings the same way.
- **No new dependencies.**

**Spec change.** The spec said YAML floats print "as `get` prints them". `get` prints `inf`/`nan`, which YAML reads back as strings, so `show` output wouldn't parse back to the same data. FR-008 now uses `.inf`, `-.inf` and `.nan` inside YAML. `show` on a single value without `--sources` still matches `get`.

**Tests:**
- The existing `show` single-value tests move to `test_get.py`.
- Other test helpers that read single values switch to `get`.
- `test_cli_basics` now runs its "missing PATH → exit 2" check on `get`, because `show` no longer requires PATH.
- New tests cover `show` and `--sources`. Each one checks exact output and that the YAML parses back to the loaded configuration.

`status.events.jsonl` was modified again by the commit tool and is still uncommitted, same as after the spec.

Files are in `kitty-specs/troupe-config-get-show-01M411XB/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

The next step is `/spec-kitty.tasks`, which you need to run yourself.