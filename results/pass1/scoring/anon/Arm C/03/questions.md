## Scored run

### Question 1 (question, answered by po)

Arm asked: I have one question before I write the spec. The rest I can decide from the contract and the existing code.

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

Reply: On “What should `troupe config show PATH --sources` print when PATH names a single scalar: (A) the scalar as YAML with a `# from <file>` comment, (B) exactly what `get` prints, ignoring `--sources`, or (C) the plain value followed by a separate `# from <file>` line?”: The contract doesn't define `--sources` for a scalar PATH. `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments. Treat this case as out of contract. The choice is yours: state which option you chose and why.

On “Are there any corrections to the listed choices (YAML layout, multi-line strings as literal blocks, source comment on the block header line, source paths relative to the theatre directory, show reconciling first, exit 5 for a missing path and for get on a mapping or list with a pointer to config show, help text and tests moving to get)?”: No corrections. None of the listed choices contradicts the contract. Where a choice covers something the contract doesn't specify, such as YAML layout details or `../` paths for targets outside the theatre, it is yours to make, as long as you record what you chose.

### Question 2 (next_command, answered by po)

Arm asked: The spec for mission `troupe-config-get-show-01M411XB` is written and committed (`92a3460`) on `feat/troupe-config-get-show`. No code has changed yet, and nothing is on `main` so far. Your request isn't done until the finished feature is merged into `main` at the end of the mission.

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

The quality checklist passes on every item and there are no open clarification markers. One file, `status.events.jsonl`, was modified again by the commit step and isn't committed yet. The next step is `/method-command`.

Reply: /method-command

### Question 3 (next_command, answered by po)

Arm asked: The plan for `troupe-config-get-show-01M411XB` is done and committed on `feat/troupe-config-get-show` (`87eb8b5` for the plan, `0ff8b1b` for the other artifacts). No code has changed yet. I didn't ask further planning questions because you'd said the open choices are mine; each one is recorded in `research.md` as D-1 to D-9.

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

Files are in `spec/troupe-config-get-show-01M411XB/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

The next step is `/method-command`, which you need to run yourself.

Reply: /method-command

### Question 4 (next_command, answered by po)

Arm asked: Tasks are finalized and committed on `feat/troupe-config-get-show` (`2da8c18` maps requirements to work packages, `7bcbde0` adds the tasks). There are 3 work packages with 15 subtasks; no code has changed yet.

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

**Should I use the `/method-implement-review` skill to implement all WPs until completion?** It sends each work package to an implementing agent and then a reviewing agent, handles rejected work, and merges all lanes at the end.

Before any implementation can start, `/method-command` must run; it checks that the spec, plan and tasks agree. If you say yes, I'll run it first. Afterwards the feature branch still has to be merged into `main` to meet your delivery requirement (no push, no PR). You can also choose which agents implement and review, or limit the run to some of the work packages.

Reply: /method-implement-review

### Question 5 (continue, answered by po)

Arm asked: WP01 passed re-review and is approved; WP02 is approved. The WP03 implementer is now running in lane-c, which contains WP01's and WP02's code.

| WP | Stage |
|---|---|
| WP01 | Approved after one fix cycle |
| WP02 | Approved |
| WP03 | Implementation |

Reply: Please continue.

### Question 6 (continue, answered by po)

Arm asked: The WP03 implementer is running again from its saved progress. I'll start WP03's review as soon as it reports back.

Reply: Please continue.

### Question 7 (step_done, answered by runner)

Arm asked: `troupe config get` and the new `troupe config show [PATH] [--sources]` are done and merged into `main` (merge commit `a589041`). Nothing was pushed and no pull request was opened. On `main` before the merge, all 1528 tests passed and type checking, lint and format checks were clean.

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
- **Open tracker issues from this mission:**
  - P4 bug: mapping keys longer than 1024 characters can't be printed as valid YAML. That's a YAML limit the contract doesn't cover, so it needs your decision.
  - P4: a docstring in `src/troupe/yamlcore.py` says no other module imports the YAML library; the new renderer now does.
- **Leftover cleanup:** the mission's coordination branch couldn't be deleted because its worktree is still checked out at `.worktrees/troupe-config-get-show-01M411XB-coord`. Nothing depends on it.
- method suggests a post-merge mission review (`/method-mission-review`) as the next step; I haven't run it.

Reply: /method-command

### Question 8 (step_done, answered by runner)

Arm asked: The command's verdict is **"Outstanding acceptance issues detected"**: it did not record a new acceptance and changed nothing.

It reported two blocking items:

1. **It ran on the wrong branch.** Acceptance must run on `feat/troupe-config-get-show` or the mission branch, and this checkout is on `main`. `main` is correct here, because it already holds the delivered work (`a589041`).
2. **No `docs/` folder.** This is the same convention check as before; the repo has never had `docs/`.

The mission was already accepted on the right branch, so nothing is missing. That acceptance is `6a39050` on `feat/troupe-config-get-show`, run with `--lenient` because of the `docs/` check. The output above also shows all three work packages are now done, and the merge into `main` happened after that acceptance.

If you want a fresh acceptance record anyway, I can switch to `feat/troupe-config-get-show` and run `method agent mission accept --mission troupe-config-get-show-01M411XB --lenient`. That adds acceptance commits on the feature branch, which would then need merging into `main` again. Or we leave it as is; I'd leave it.

Reply: /method-command

### Question 9 (step_done, answered by po)

Arm asked: The merge command failed and changed nothing: it reports `✗ lane-a: Lane branch method/mission-troupe-config-get-show-01M411XB-lane-a does not exist`. Its earlier checks passed (all three WPs have review approval, dependencies complete).

The lane branch is missing because the mission was already merged. The earlier `method merge` merged lanes a–c into the mission branch and that into `feat/troupe-config-get-show` (`b51d09f`). It recorded all three WPs as done and deleted the lane branches. `feat/troupe-config-get-show` was then merged into `main` as `a589041`, which is still the tip of `main`. There's nothing left to merge, so this needs no action.

Reply: 

## Discovery run

### Question 1 (question, answered by owner)

Arm asked: I checked the current code (`src/troupe/commands/show.py`, `src/troupe/tree.py`) and the step‑1 contract. The new contract is clear apart from one case.

**Question: what should `show PATH --sources` print when PATH is a single value?**

The contract says `show` on a scalar prints the value the way `get` does, which isn't YAML. It also says `--sources` "prints the same YAML" with `# from <file>` comments. Together, those don't say what `show model.temperature --sources` should print.

- **(A) Recommended: print the value as a one-value YAML document with the source comment.**
  - `0.2  # from .troupe/troupe.yml`
  - A text include prints as a literal block whose header line carries the comment, e.g. `|  # from prompts/sys.md`, then the text.
  - The output still answers "where does this come from?", and the YAML stays valid.
- **(B) Print exactly what `get` prints and ignore `--sources` for scalars.**
  - Simpler, but you lose the source information in exactly the case where you asked for it.
- **(C) Something else.** Tell me what you want.

Unless you say otherwise, I'll make these choices myself, since the contract leaves them open, and record them in the spec:

- **Valid YAML:** the YAML output always reads back to exactly the same values.
  - Keys keep their file order.
  - Strings are quoted only when they'd otherwise read back as something else (`"true"`, `"0.2"`).
  - Empty sections print as `{}` / `[]`.
- **Text-include line endings and chomping:** text includes are always literal blocks, as the contract says, and the trailing-newline marker (`|-`, `|`, `|+`) matches the file exactly. A CRLF file therefore appears with plain line breaks in `show`; `get` still prints the exact bytes.
- **Which lines get `# from`:** only lines that hold a value get a comment. A line that only opens a section (`agents:`) and an empty `{}`/`[]` get none.
- **`get` error text:** for a section, the message names the path and points to `config show`, e.g. `tools is a list, not a scalar; use 'troupe config show tools'`.
- **Unchanged behaviour:** a path that doesn't exist exits 5 for both commands. Both commands still pick up hand edits first, as every command except `history` already does.

WAITING_FOR_DISCOVERY_INPUT

Reply: The contract doesn't define `--sources` for a scalar PATH: `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments (get and show, from step 3). Treat it as out of contract: your choice — state which you chose and why.

Escalated: ["What should `show PATH --sources` print when PATH resolves to a single scalar value (e.g. option A: a one-value YAML document carrying the `# from <file>` comment, option B: exactly what `get` prints, ignoring `--sources`, or something else)?"]

### Question 2 (next_command, answered by po)

Arm asked: I chose option (A) and committed the spec on `feat/troupe-config-get-show` (commit `99242aa`). Nothing has been implemented yet, and nothing is on `main` yet; that happens after the plan, tasks and implementation phases.

**The out-of-contract case (recorded as D‑1 in the spec and in the decision record):** `show PATH --sources` on a single value prints it as a one-value YAML document with the comment.
- A plain value prints as `0.2 # from .troupe/troupe.yml`.
- A text include prints its literal-block header line with the comment (`|- # from prompts/sys.md`), then the text indented below it.
- Without `--sources`, `show` on a value prints exactly what `get` prints, as the contract requires.

**Why:** `--sources` exists to say where a value comes from, so ignoring it would drop exactly what was asked for. A one-value YAML document is still "the same YAML" for a one-value result, and it reads back as valid YAML.

**Other open points:** the spec records them as D‑2 to D‑10, using the defaults I proposed last turn. Two details are new since then:
- The comment is separated from the value by exactly one space.
- A file outside the theatre directory is named with leading `../`; includes are allowed to point there.

One more case is new: a text include whose content a literal block can't hold falls back to a double-quoted string, so `show` still prints valid YAML.

**What's committed:**
- `spec/troupe-config-get-show-01M4075F/spec.md`: 14 functional requirements, 3 non-functional requirements, 4 constraints and 3 user stories.
- `checklists/requirements.md`: every item passes.
- The decision record and `meta.json`.

The decision check reports nothing open and no `[NEEDS CLARIFICATION]` markers remain.

**Loose ends:**
- The plan step has already been started, which confirms method accepted the spec. It created a `plan.md` placeholder and left `status.events.jsonl` with uncommitted changes; the plan phase will commit both.
- No code changed yet, so the tests, type checks and lint haven't been run for this work.

Next step is `/method-command`.

Reply: /method-command

### Question 3 (question, answered by po+owner)

Arm asked: I have one planning question and a short summary of the engineering design to confirm.

**Which YAML readers must read `show`'s output back as the same values?**

The spec says the YAML `show` prints reads back as the same values. Readers disagree about which unquoted strings count as plain text:
- troupe follows YAML 1.2 core, where `yes`, `on`, `1_000` and `0777` are plain strings.
- Readers that follow YAML 1.1, such as PyYAML and many CI tools, read those as `true`, `1000` or an octal number.

- **(A) Recommended: quote any string that either kind of reader would take for something else.**
  - For example, `enabled: "yes"` and `id: "1_000"`.
  - The output reads back correctly anywhere you paste it, at the cost of a few extra quotes. This follows TROUPE-002: take the choice that can't silently change a value.
- **(B) Quote only what YAML 1.2 core would misread.**
  - Fewer quotes, but `show | some-1.1-tool` could turn `yes` into `true`.

**Engineering summary, for you to confirm along with the question:**

- **New `get` command:** it gets the current single-value code from `show` unchanged. The only addition is that its error for a mapping or list points to `config show`.
- **New output module:** a small new module turns the loaded configuration into a list of output lines. Each line records the file it came from, or none for lines that only open a section.
  - `show` joins those lines and adds ` # from <file>` only when `--sources` is given.
  - So output with `--sources`, minus the comments, matches output without it by construction.
- **Quoting check:** whether a string can go unquoted is decided in one place, `yamlcore`, which already holds all the YAML parsing.
  - It tries the unquoted form and parses it back; if anything differs, the value gets double quotes.
  - Text includes are checked the same way: a literal block that wouldn't read back to the file's text falls back to double quotes.
- **No new dependencies.** ruamel.yaml is already a dependency, so the supply-chain checks aren't needed.
- **Tests:** the existing single-value `show` tests become `get` tests. A new `show` test file covers sections, the whole configuration, `--sources` and the D‑1 to D‑10 cases, and reads the output back with the real YAML library.
- **Unchanged:** other tests that use `show` on a single value keep working, because that output doesn't change. `set`, `history` and `watch` are untouched.

WAITING_FOR_PLANNING_INPUT

Reply: On “When show prints a string, should it quote every string that a YAML 1.1 or a YAML 1.2 reader would misread (A), or only strings that a YAML 1.2 core reader would misread (B)?”: The contract doesn't say which YAML reader `show`'s output must read back under. The only YAML version it names is YAML 1.2 core schema, for parsing `VALUE` on the command line. Treat the reader as out of contract: your choice — state which you chose and why.

On “Do you confirm this engineering summary: get reuses the existing single-value code and adds an error pointing to config show; a new output module produces lines tagged with their source file; ` # from <file>` is added only with --sources; quoting is decided in yamlcore; there are no new dependencies; the tests are reorganised as described; and set, history and watch are untouched?”: Confirmed. The summary is consistent with the contract. get prints a scalar as show did before. For a mapping or list it exits 5, and stderr mentions `config show`. show prints sections as YAML in block style, with includes resolved and text includes as literal blocks. --sources produces the same YAML plus `# from <file>` on lines that hold a scalar. Because both outputs come from the same lines, they can't drift apart, which fits "the same YAML".

Escalated: ["When show prints a string, should it quote every string that a YAML 1.1 or a YAML 1.2 reader would misread (A), or only strings that a YAML 1.2 core reader would misread (B)?"]

### Question 4 (next_command, answered by po)

Arm asked: The plan for `get`/`show` is done and committed on `feat/troupe-config-get-show` (commits `d6375aa` and `55c2b7a`). No code has been written yet, so the tests, type checks and lint haven't been run for this work.

**Quoting decision (D‑11), now also in the spec:** in `show`'s YAML output, a string goes unquoted only if three readers all get back exactly the same string: troupe's own YAML 1.2 core resolver, ruamel in YAML 1.2 mode and ruamel in YAML 1.1 mode. Everything else is double-quoted.

**Why:** the contract names a YAML version only for parsing `VALUE`, not for `show`'s output. That output is meant to be read and reused, possibly by tools that follow YAML 1.1. A few extra quotes can't change a value, but a reader turning `yes` into `true` would (TROUPE‑002).

I checked this against the real ruamel loader, and quoting needs more than the YAML 1.1 cases. Even in YAML 1.2 mode, ruamel reads `1_000` as an integer and `2001-12-14` as a date, and refuses `<<` and `=`. So unquoted strings are decided by reading each one back with all three readers, not from a fixed list.

**Design, as you confirmed it:**
- **`get`:** the old single-value `show` code, moved to `commands/get.py`. For a mapping or list it exits 5 with `troupe: agents is a mapping, not a scalar; use 'troupe config show agents'`. `get --sources` is a usage error (exit 2).
- **`show`:** a new `render.py` turns the configuration into lines, each tagged with its source file or none. `show` joins them and adds ` # from <file>` only with `--sources`, so the two outputs can't drift apart.
- **Quoting:** the read-back checks live in `yamlcore.py`, still the only module that uses ruamel. No new dependencies.
- **Tests:** the existing single-value `show` tests move to `test_get.py`. A new `test_show.py` reads the output back with the real ruamel library.

**Implementation concerns for the tasks step:**
- **IC‑01:** `get` and the command-line options.
- **IC‑02:** the quoting checks in `yamlcore`.
- **IC‑03:** the renderer and `show`.
- **IC‑04:** the contract, help text and docstrings.

Files are in `spec/troupe-config-get-show-01M4075F/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli-get-show.md`
- `quickstart.md`

The new contract replaces only the step‑1 `show PATH` row.

**Branch:** current, planning base and merge target are all `feat/troupe-config-get-show`. The finished work goes onto `main` by a local merge, with no push and no PR.

Next step is `/method-command`.

Reply: /method-command

### Question 5 (next_command, answered by po)

Arm asked: I've split the work into four work packages (18 subtasks) and committed the finalized tasks on `feat/troupe-config-get-show` (commit `78e2917`). No code has been written yet.

| WP | Goal | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | Read-back checks in `yamlcore`: when a string can be unquoted, double quotes, float form, literal blocks | 5 (T001–T005) | 182 lines | — |
| WP02 | `render.py`: a node becomes YAML lines, each tagged with its source file | 5 (T006–T010) | 184 lines | WP01 |
| WP03 | `get`, `show [PATH] [--sources]`, command-line options; move `test_show.py` to `test_get.py`; section tests | 5 (T011–T015) | 195 lines | WP02 |
| WP04 | `--sources` acceptance tests, read-only and reconcile-first tests, check of contract and quickstart against real output | 3 (T016–T018) | ~160 lines | WP03 |

- **Size and checks:** every work package has 3–5 subtasks and a prompt under 200 lines. Each starts with the "⚡ Do This First" section and is assigned the `python-pedro` profile. Validation passed: no overlapping files, no cycles, and every FR, NFR and constraint is mapped.
- **No parallel work:** each package uses the previous one's API, so they run one after another. method still gives each its own lane (lane‑a to lane‑d).
- **Minimum useful scope:** WP01–WP03 deliver `get` and `show`. WP04 is still required, because it holds the acceptance tests for the contract's `--sources` section.

**Changes from the plan:**
- **Existing test that changes:** `test_cli_basics.py` used `config show` with no PATH as its example usage error. That is now valid, so WP03 switches that test to `get`.
- **Contract edits stay with me:** work packages can't own files under `spec/`. WP04 checks the contract and quickstart against the real output and reports any exact corrections, and I apply them on the planning branch before acceptance.
- **Floats:** they'll be written with a dot (`1.0e+20`) so readers that follow YAML 1.1 read them as numbers.

`finalize-tasks` left two status files uncommitted: `status.events.jsonl` (modified) and `status.json` (new). The previous mission had the same lane-guard issue with `status.json`, so I've left them for the implementation workflow to handle.

**Branch:** planning base and merge target are `feat/troupe-config-get-show`. The finished work goes onto `main` by a local merge, with no push and no PR.

**Should I use the `/method-implement-review` skill to fully implement all work packages until completion?** It runs an implementing and a reviewing agent for each work package, handles rejection cycles, and merges all lanes when done. `/method-command` has to run first: implementation won't start until its `analysis-report.md` exists, and I'd run it as the first step. You can also choose which agents implement and review, or limit it to some work packages.

Reply: /method-implement-review

### Question 6 (continue, answered by po)

Arm asked: WP01 is being implemented in the background. I'll pick up the review once it reports back.

Reply: Please continue.
