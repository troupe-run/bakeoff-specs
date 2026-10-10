Q1: I have one question before I write the spec. The rest I can decide from the contract and the existing code.

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
A1 (po): On “What should `troupe config show PATH --sources` print when PATH names a single scalar: (A) the scalar as YAML with a `# from <file>` comment, (B) exactly what `get` prints, ignoring `--sources`, or (C) the plain value followed by a separate `# from <file>` line?”: The contract doesn't define `--sources` for a scalar PATH. `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments. Treat this case as out of contract. The choice is yours: state which option you chose and why.

On “Are there any corrections to the listed choices (YAML layout, multi-line strings as literal blocks, source comment on the block header line, source paths relative to the theatre directory, show reconciling first, exit 5 for a missing path and for get on a mapping or list with a pointer to config show, help text and tests moving to get)?”: No corrections. None of the listed choices contradicts the contract. Where a choice covers something the contract doesn't specify, such as YAML layout details or `../` paths for targets outside the theatre, it is yours to make, as long as you record what you chose.

Q2: The spec for mission `troupe-config-get-show-01M411XB` is written and committed (`92a3460`) on `feat/troupe-config-get-show`. No code has changed yet, and nothing is on `main` so far. Your request isn't done until the finished feature is merged into `main` at the end of the mission.

**Your scalar `--sources` case:** I chose option A. `show port --sources` prints `8080 # from .troupe/troupe.yml`. A text include prints as a literal block with the comment on its `key: |` header line. With A, `--sources` output is always valid YAML and every value shows its file, which matches "the same YAML". Without `--sources`, a single value still prints exactly like `get`. The choice is recorded as decision DM 01M411YHFR2PMJEJWMHX4KN9C4.

**What the spec covers:**
- **`get PATH`** prints one value byte-for-byte as `show` did in steps 1 and 2. A section is refused with exit 5 and a stderr message that mentions `config show`. A missing path is also exit 5.
- **`show [PATH]`** prints a single value like `get`. A section, or the whole configuration when PATH is omitted, prints as block-style YAML. Includes are resolved and text includes appear as literal blocks.
- **`--sources`** adds ` # from <file>` to every line that holds a value and to no other line. File paths are relative to the theatre directory, with `../` for files outside it.
- **Both commands** pick up hand edits first and never change any configuration file.

The layout choices you approved are all in the spec, plus three details I settled while writing it:
- **CRLF text includes** print double-quoted with escapes, because a literal block can't keep carriage returns.
- **Source comments** have exactly one space before the `#`. My earlier example showed two; the spec uses one.
- **`get` doesn't accept `--sources`** and exits with a usage error (exit 2) if given it.

This isn't a rename across the codebase: `show` keeps its name, and single-value reads behave the same as before. Only the existing tests that expect `show` to refuse a section move over to `get`.

The quality checklist passes on every item and there are no open clarification markers. One file, `status.events.jsonl`, was modified again by the commit step and isn't committed yet. The next step is `/spec-kitty.plan`.
A2 (po): /spec-kitty.plan

Q3: The plan for `troupe-config-get-show-01M411XB` is done and committed on `feat/troupe-config-get-show` (`87eb8b5` for the plan, `0ff8b1b` for the other artifacts). No code has changed yet. I didn't ask further planning questions because you'd said the open choices are mine; each one is recorded in `research.md` as D-1 to D-9.

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
A3 (po): /spec-kitty.tasks

Q4: Tasks are finalized and committed on `feat/troupe-config-get-show` (`2da8c18` maps requirements to work packages, `7bcbde0` adds the tasks). There are 3 work packages with 15 subtasks; no code has changed yet.

| WP | What it delivers | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | YAML renderer with source comments (`src/troupe/yamlout.py` plus unit tests) | 5 | ~243 lines | none |
| WP02 | `get` command, CLI registration, `get` tests, and test helpers switched to `get` | 5 | ~195 lines | none |
| WP03 | New `show [PATH] [--sources]`, its tests, and a final run of every quickstart command plus all quality checks | 5 | ~191 lines | WP01, WP02 |

- **Size:** every work package has 3–7 subtasks and is well under 700 lines (about 210 on average). Each prompt starts with the required "load agent profile" section.
- **Validation:** the finalize step passed with no ownership warnings. All 15 functional requirements are mapped to a work package.
- **Parallel work:** WP01 and WP02 run at the same time in separate lanes. WP03 starts when both are done.
- **Smallest useful first step:** WP02 on its own already delivers `get`.
- **Agent profile:** all three use `python-pedro` (implementer).

**Ordering safeguard:** WP02 must not touch `show`, so `show` keeps its old behaviour until WP03 replaces it. WP03 is allowed one edit to `src/troupe/cli.py`, which WP02 owns, limited to the `show` command definition. This is safe because WP03 runs only after WP02 is finished.

Two files are still uncommitted, both written by the tooling: `status.events.jsonl` (modified) and `status.json` (new).

**Should I use the `/spec-kitty-implement-review` skill to implement all WPs until completion?** It sends each work package to an implementing agent and then a reviewing agent, handles rejected work, and merges all lanes at the end.

Before any implementation can start, `/spec-kitty.analyze` must run; it checks that the spec, plan and tasks agree. If you say yes, I'll run it first. Afterwards the feature branch still has to be merged into `main` to meet your delivery requirement (no push, no PR). You can also choose which agents implement and review, or limit the run to some of the work packages.
A4 (po): /spec-kitty-implement-review

Q5: WP01 passed re-review and is approved; WP02 is approved. The WP03 implementer is now running in lane-c, which contains WP01's and WP02's code.

| WP | Stage |
|---|---|
| WP01 | Approved after one fix cycle |
| WP02 | Approved |
| WP03 | Implementation |
A5 (po): Please continue.

Q6: The WP03 implementer is running again from its saved progress. I'll start WP03's review as soon as it reports back.
A6 (po): Please continue.

Q7: `troupe config get` and the new `troupe config show [PATH] [--sources]` are done and merged into `main` (merge commit `a589041`). Nothing was pushed and no pull request was opened. On `main` before the merge, all 1528 tests passed and type checking, lint and format checks were clean.

**What the commands do now**
- **`get PATH`** prints a single value exactly as `show` used to. On a section it exits 5 with `troupe: server is a mapping, not a scalar; use 'troupe config show server'`.
- **`show PATH`** on a single value prints the same thing as `get`. On a section, or with no PATH, it prints the configuration as YAML, with includes filled in and text includes shown as `|` blocks.
- **`show --sources`** adds ` # from <file>` to every line that holds a value, for example `port: 8080 # from .troupe/server.yml`. Paths are relative to the theatre directory, with `../` for files outside it. On a single value it prints `8080 # from …`; that was my call, since the contract doesn't cover that case.

**Decision added during review (D-10):** some values were printed unquoted but read back as something else when the output is parsed as YAML. For example, `2001-12-14` came back as a date, `1_000` and `yes` changed type, and `<<` broke the mapping. `show` now quotes any value a common YAML reader (YAML 1.2 or the older 1.1) would misread. It also writes exponent floats with a decimal point (`1.0e+20`) so older readers see a float. `get` output is unchanged. This is recorded in `research.md` and the spec.

**How it went**
- WP02 (`get`) and WP03 (`show`) passed review first time. WP01 (the YAML renderer) needed one fix cycle, for D-10.
- The WP03 implementer was cut off twice when sessions ended. Its code was complete but untested, so I ran the tests, committed it and ran the full checks myself before an independent reviewer approved it.
- Twice, setting up a lane hit a merge conflict in a planning file. I resolved them with the repo's helper scripts; no code conflicted.

**Things to know**
- **Acceptance ran in lenient mode.** It wants a `docs/` folder, which this repo has never had, so that convention is reported as a warning instead of creating an empty folder to pass.
- **Open beads issues from this mission:**
  - P4 bug: mapping keys longer than 1024 characters can't be printed as valid YAML. That's a YAML limit the contract doesn't cover, so it needs your decision.
  - P4: a docstring in `src/troupe/yamlcore.py` says no other module imports the YAML library; the new renderer now does.
- **Leftover cleanup:** the mission's coordination branch couldn't be deleted because its worktree is still checked out at `.worktrees/troupe-config-get-show-01M411XB-coord`. Nothing depends on it.
- Spec-kitty suggests a post-merge mission review (`/spec-kitty-mission-review`) as the next step; I haven't run it.
A7 (runner): /spec-kitty.accept