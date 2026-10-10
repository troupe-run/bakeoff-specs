## Arm A

## Scored run

### Question 1 (next_command, answered by po)

Arm asked: Discovery for step 3 is written and committed on `main` as commit `1db2f7e`. Nothing has been built yet: this step only produces the plan. Running it to completion means the specify-and-implement steps below.

**What I decided.** The roadmap already existed, so I added to it. The work is one new spec plus two small updates to existing specs:
- **New spec `config-get-show`** covers the `get PATH` command, `show [PATH]` printing YAML, and `--sources`.
- **config-foundation:** its Requirement 6 (the old `show PATH`) becomes `get`, and the exit-5 message also mentions `config show`.
- **config-file-sync:** `get` joins the commands that reconcile with the files first; `history` still never does.

**Approach.** I chose a small YAML writer of our own that works over the configuration tree the loader already builds.
- That tree already records which file each value came from, and a text include points at the included file. So `--sources` needs no extra work to find the source.
- The `# from <file>` comment is added as each line is built, so no lines have to be matched to values afterwards.
- Scalars reuse the quoting and literal-block rules that `set` already uses.
- The rule throughout: the printed YAML must load back to exactly the same configuration.

I rejected the ruamel.yaml-based options because ruamel would control comment placement, quoting and number formats, and inserting comments after the fact is fragile. The reasons are recorded in the brief.

**Open choices with my defaults.** These are recorded in the brief, to settle during requirements:
- `show PATH --sources` on a single value still gets the `# from <file>` comment, printed as YAML.
- For a literal block, the comment goes on the `|` header line, because a comment can't sit inside the block's content.
- A text include that a literal block can't hold exactly falls back to a double-quoted string, so the value never changes.
- Empty sections print as `{}` and `[]`.
- Indentation is 2 spaces, with one space before `#`.
- File labels are relative paths with `/`, such as `.troupe/troupe.yml`. An include outside the theatre directory gets a `../` path.

The discovery process normally asks you to confirm the decision and the approach. Because you asked for the work to be committed in this run, I chose and recorded them without asking; tell me if you want any of them changed.

Files:
- `spec/spec/config-get-show/brief.md` (new)
- `spec/steering/roadmap.md` (new step 3 section; `config-get-show` added to the main spec list; earlier content unchanged)

**Next:** `/method-command config-get-show`, or `/method-command config-get-show` to go straight on. After that, revisit config-foundation and config-file-sync with `/method-command` for the updates above.

Reply: /method-command config-get-show

### Question 2 (next_command, answered by po)

Arm asked: ## Feature name: `config-get-show`
I kept the folder that discovery created. The name matches the step 3 contract section "`get` and `show`" and the earlier `config-*` specs.

## Project summary
`get PATH` prints a single value, as `show` used to. `show [PATH]` prints a value, a section or the whole configuration as block-style YAML with includes resolved. `--sources` adds a `# from <file>` comment to each line that holds a value.

## Created files
- `/work/repo/spec/spec/config-get-show/spec.json`: phase `initialized`, nothing approved yet.
- `/work/repo/spec/spec/config-get-show/requirements.md`: the project description is the brief's Problem, Current State and Desired Outcome, plus the step 3 contract section quoted word for word, as step 2 did. It points to `brief.md` for the approach and the open choices.

Both files are committed on `main` as commit `c2ef9e5`.

## Next step
```
/method-command config-get-show
```

Reply: /method-command config-get-show

### Question 3 (approval, answered by po)

Arm asked: ## Requirements summary
The requirements are written in `spec/spec/config-get-show/requirements.md`: six requirements with 40 acceptance criteria.

- **R1 `get PATH`**: prints a single value exactly as step 1's `show` did. A mapping or list exits 5, and stderr names the path, the file and `config show`. Bad command lines exit 2.
- **R2 `show [PATH]`**: a value prints like `get`. A mapping, list or the whole configuration (no PATH) prints as YAML. `--sources` can come before or after PATH.
- **R3 YAML layout**: block style with 2-space indents, document order and includes resolved. `{}` and `[]` are used for empty sections. The user's comments, quoting and formatting are not carried over.
- **R4 Values in the YAML**: the output must parse back to exactly the same values. Strings are quoted only when needed. Text includes and other multi-line strings print as literal blocks (`|`, `|-`, `|+`).
- **R5 `--sources`**: each line holding a value ends with ` # from <file>`, relative to the theatre directory with `/` separators. A literal block gets the comment on its header line, and a text include names the included file.
- **R6 Shared behaviour**: both commands reconcile first and never change any file. Errors follow the step 1 conventions, and stdout stays empty on failure.

## Choices I made where the contract is silent
These are listed in the Boundary Context and still need recording in `research.md`. The ones you may want to look at:
- **`show PATH --sources` on a single value** prints it as YAML with the comment, rather than in `get`'s raw form.
- **Text includes with CRLF line endings, or characters a literal block can't hold,** print as double-quoted strings instead of literal blocks. This departs from the contract's "literal blocks", but otherwise the printed value would differ from the real one.
- **`get --sources`** is a usage error (exit 2).

## Document status
- `requirements.md` is written. `spec.json` shows phase `requirements-generated`; the requirements are not yet approved.
- The changes this implies for config-foundation (Requirement 6 now describes `get`) and config-file-sync (`get` also reconciles first) are noted in the Boundary Context. The existing specs themselves are updated during implementation, in the same change as the code.
- Committed on `main` as commit `88ebdc5`.

## Next steps
Approve the requirements or ask for changes, then run:
```
/method-command config-get-show     # optional: compare with the existing code
/method-command config-get-show
```

Reply: Not approved. Requirement 4.5, and Boundary Context choice 3, contradict the contract section "`get` and `show` (from step 3)". That section says a mapping or list is printed as YAML with "text includes as literal blocks" and makes no exception. Requirement 4.5 instead prints some text includes as double-quoted strings, for example ones with CRLF line endings. Your summary already says this departs from the contract. Every text include must be shown as a literal block. Please revise 4.5 and choice 3 to match, then ask again. I found no other conflict with the contract or the step brief.

### Question 4 (approval, answered by po)

Arm asked: I've changed the requirements so that every text include is printed as a literal block, with no exception. The revision is committed on `main` as commit `54634ed`, and the requirements are still unapproved.

## What changed
- **4.4**: a text include is always printed as a literal block (`|`), whatever its text.
- **4.5**: if a literal block can't reproduce a text include exactly, such as a file with CRLF line endings, it is still a literal block. Its content lines are the file's exact text, CRLF line breaks included. The double-quoted fallback now applies only to other multi-line strings, which are not text includes and which the contract doesn't cover.
- **Choice 3** in the Boundary Context now says the same and gives the reason.

## Knock-on changes you should check
Two criteria had to change so they don't conflict with the new 4.5:
- **4.1, "reads back exactly"**: a YAML reader turns CRLF into LF, so a CRLF text include can't read back character for character. I added one exception: a text include that a literal block can't reproduce is excused from the read-back promise. The output still shows the file's exact text, and nothing is changed to make it fit.
- **4.6, "non-printable characters only as escapes"**: this now applies outside text includes. Inside a text include, such characters appear unescaped.

## Approval
Do you approve the requirements as revised? Once you do, the next step is:
```
/method-command config-get-show
```

Reply: Approved. The revised requirements now print every text include as a literal block, with no exception, as the contract section "`get` and `show` (from step 3)" requires (4.4, 4.5, choice 3). `get` on a mapping or list exits 5 and mentions `config show`. `show` on a scalar prints like `get`. `--sources` adds `# from <file>` with the path relative to the theatre directory and `/` separators, and a text include names the included file. Both commands reconcile first, while `history` still does not (Sync with files). The choices you made where the contract is silent are stated in the Boundary Context, as the brief asks. I found no remaining conflict with the contract or the step brief.

### Question 5 (next_command, answered by po)

Arm asked: I've recorded your approval. `spec.json` now marks the requirements as approved, and that change is committed on `main` as commit `9a59e64`.

The next step is the design. Before that, you can optionally compare the requirements with the existing code; it would show, for example, how much of `set`'s quoting and literal-block code can be reused for `show`.

```
/method-command config-get-show     # optional
/method-command config-get-show
```

Reply: /method-command config-get-show

### Question 6 (approval, answered by po)

Arm asked: ## Status
The design is written to `spec/spec/config-get-show/design.md`, with its decision log in `research.md`, and committed on `main` as commit `2f54cd2`. `spec.json` now shows phase `design-generated`; the design is not yet approved.

## Discovery
I used the light discovery process, since this extends an existing CLI and adds no new dependency.

## Key findings
- **`show` needs a refactor first.** The quoting and literal-block rules `show` needs already exist in the `set` code. But an existing test forbids core modules from importing that code, and those functions reject some strings with "write refused". So the design moves the parts that don't write files into a new core module, `troupe/config/yaml_style.py`. `set` keeps using them under the same names, and its byte-exact tests must still pass unchanged. This move is the riskiest step and is planned as a separate first task.
- **`--sources` needs no loader change.** The loaded configuration already records which file every value came from, and for a text include that is the included file. The new YAML writer builds each output line together with the file of the value it holds. Removing the comments therefore gives exactly the plain output (5.5) without extra work.
- **Literal-block indentation, settled by experiment.** Content must sit 2 columns past the key or dash that owns the block (`- k: |` puts the content under `k`). This is how the design reads the wording of 4.4; reading it more literally would print YAML that doesn't load back correctly. The same experiment confirmed that CRLF content reads back as LF, which is the case 4.5 exempts.

## Review gate
Passed:
- Every requirement ID (1.1–6.8) is traced to a component.
- The boundary sections are filled in.
- Every component has a file path.

## Next action
Review and approve the design, then:
```
/method-command config-get-show   # optional
/method-command config-get-show
```

Reply: Approved. The design matches the contract section "`get` and `show` (from step 3)". `get` prints a scalar as step 1 did. On a mapping or list it exits 5 and stderr names the file, PATH and `config show`. `show` prints a scalar like `get` and a mapping, a list or the whole configuration as block YAML with includes resolved. Every text include is printed as a literal block, with no exception, as the approved 4.4 and 4.5 require. `--sources` adds ` # from <file>` to every line that holds a scalar, including a literal block's header line. The path is relative to the theatre directory with `/` separators, and a text include names the included file. Both commands reconcile first and never write any file, while `history` is untouched (Sync with files). Errors keep the General exit codes, with empty stdout and a message naming the path or file. The refactor that moves code into `yaml_style` keeps `set`'s bytes unchanged, as the `set PATH VALUE` section requires. I found no conflict with the contract or the step brief.

### Question 7 (next_command, answered by po)

Arm asked: I've recorded your approval. `spec.json` now marks the design as approved, and that change is committed on `main` as commit `c185fb4`.

The working tree is clean. The on-disk change to `design.md` that the editor flagged was my own clarification of 4.4, which is already in commit `2f54cd2`.

The next step is the implementation plan. I'll plan the move into `yaml_style` as its own first task, checked against `set`'s unchanged byte-exact tests, before any `show` code is written.

```
/method-command config-get-show
```

Reply: /method-command config-get-show

### Question 8 (approval, answered by po)

Arm asked: ## Status
The implementation plan is written to `spec/spec/config-get-show/tasks.md` and committed on `main` as commit `9ac56c2`. `spec.json` shows phase `tasks-generated`; the tasks are not yet approved.

## Task summary
There are 4 groups with 13 sub-tasks, each roughly 1–3 hours, and every requirement from 1.1 to 6.8 is covered.

1. **Foundation (1.1–1.2).** Move the shared quoting rules into `yaml_style` as a pure move, proven by `set`'s unchanged byte-exact tests. Then add quoting for a value printed on its own.
2. **Core (2.1–2.5).** The `get` lookup with the `config show` hint, source labels, and the YAML writer: layout, then literal blocks, then `--sources` comments. 2.1, 2.2 and 2.3 can run in parallel.
3. **Integration (3.1–3.3).**
   - 3.1 adds `get` first.
   - 3.2 replaces `show`. In the same task it updates every existing test that relied on step 1 `show`, so the suite stays green at every step.
   - 3.3 adds step 3 notes to the config-foundation and config-file-sync requirements and updates docstrings.
4. **Validation (4.1–4.5).** End-to-end tests for `get`, `show`, read-back and `--sources`, all four runnable in parallel. Then the full quality gate and a traceability check.

## Quality checks
- **Plan review gate:** passed. Every requirement and design component maps to a task.
- **Independent task-graph review:** a fresh reviewer agent did it. It returned NEEDS_FIXES on the first run: existing tests would have broken, because `show` with no PATH no longer exits 2 and `show` on a list no longer exits 5. It returned PASS after I fixed them.

## Next action
Tasks generated. Approve and proceed to implementation?

Reply: Approved. The plan matches the contract section "`get` and `show` (from step 3)" and the approved requirements and design. Task 3.1 adds `get`, which prints a scalar as step 1 did. On a mapping or list it exits 5, and stderr names the file and PATH and mentions `config show`. Task 3.2 replaces `show`: a scalar prints like `get`, and a mapping, a list or the whole configuration (no PATH) prints as block YAML with includes resolved. Task 2.4 prints every text include as a literal block, with no exception, CRLF included. Task 2.5 adds ` # from <file>` to every line that holds a scalar, including a literal block's header line. Task 2.2 makes that path relative to the theatre directory with `/` separators, and a text include names the included file. Both commands reconcile first and never write any file, and `history` is unchanged (Sync with files). Errors keep the General exit codes, with empty stdout. Task 1.1 moves the quoting code as a pure move that must pass `set`'s unchanged byte-exact tests, as the `set PATH VALUE` section requires. I found no conflict with the contract or the step brief.

### Question 9 (next_command, answered by po)

Arm asked: Tasks approved. `spec.json` now has the tasks marked approved and `ready_for_implementation` set to true. That change is committed on `main` as commit `8db034c`, and the working tree is clean.

Start implementation with:

```
/method-command config-get-show
```

Run without task numbers, it works through the plan task by task, each in its own subagent with an independent review, then validates the whole feature. The plan starts with 1.1, the move into `yaml_style`, which must pass `set`'s byte-exact tests unchanged before any `show` code is written. The step 3 work counts as delivered only once every task is committed on `main`.

Reply: /method-command config-get-show

### Question 10 (step_done, answered by po)

Arm asked: Step 3 is implemented and committed on `main`. The final check returned GO: the full suite passes (2628 tests, up from 2113 at the start), `mypy --strict` and ruff are clean, and the working tree is clean. Nothing was pushed and no pull request was opened.

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

Reply: 

## Discovery run

### Question 1 (approval, answered by runner)

Arm asked: Discovery for step 3 is done and committed to `main` as `8fc75f7`, without pushing. That commit holds only planning documents: `get` and the new `show` are not implemented yet, so the request isn't delivered until the spec and implementation steps below have run.

**Path chosen: Path E.** I'm adding one new spec, `config-get-show`, and adding notes to two existing specs:
- **config-foundation:** Requirement 6 ("Show a value") is replaced. It now describes `get`, and the "mapping or list → exit 5" rule applies only to `get`.
- **config-file-sync:** a wording fix only ("`get`, `show` and `set` reconcile first"). No behaviour changes.

**Approach:** a small YAML writer of our own, built on the existing configuration model. That model already records which file every value comes from, so `--sources` needs no extra pass. It reuses the quoting and literal-block rules that `set` already uses. I rejected the YAML library's built-in output because it's hard to control where comments land on literal blocks, and its quoting and line wrapping can change between versions.

**Choices I made where the contract leaves room.** They're recorded in the brief; please confirm or override them before we write requirements:
1. YAML printed by `show` must load back to exactly the same values and types. For example, the string `"true"` is quoted, and infinity prints as `.inf`.
2. Layout: 2-space indent, the files' key and list order, `{}` and `[]` for empty sections, no document markers, LF line endings. An empty configuration prints `{}`.
3. Every multi-line string, not just text includes, is printed as a literal block when one can hold it exactly. When it can't (CRLF, control characters), it's printed double-quoted instead, so the value never changes.
4. On a literal block, `# from <file>` goes on the `|` line. A comment on a content line would become part of the value.
5. `show SCALAR --sources` prints the value as YAML with the comment (e.g. `5 # from .troupe/troupe.yml`). Without `--sources`, it prints exactly like `get`.
6. `<file>` is the path as written, not following symlinks, relative to the theatre directory. A file outside that directory gets `../`.
7. `get` on a section exits 5 and its message suggests `troupe config show PATH`.

Many existing tests call `config show` to read a single value. They'll be switched to `get` in the same change as the behaviour.

**Files written:**
- `spec/spec/config-get-show/brief.md`
- `spec/steering/roadmap.md` (new "Step 3" section; steps 1–2 untouched)

**Next step:** `/method-command config-get-show`, or `/method-command config-get-show --auto` to go straight to tasks. After that, `/method-command config-get-show` builds it on `main`.

Reply: 

## Arm B

## Scored run

### Question 1 (next_command, answered by po)

Arm asked: I've written the plan for step 3 as the method change `config-get-and-show` and committed it on `main` (663cef9). It passes `method validate --strict`. No project code has changed yet.

**What's in it** (`spec/changes/config-get-and-show/`):
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

The artifacts are ready for review. When you are ready, run `/method-command`.

Reply: /method-command

### Question 2 (next_command, answered by po)

Arm asked: ## Implementation complete

All 14 tasks of `config-get-and-show` are done and committed on `main`; nothing was pushed. The final run had 455 tests passing, and mypy, ruff check, ruff format and `method validate --strict` all clean.

**What it does now:**
- **`troupe config get PATH`** prints a single value, exactly as `show PATH` did before. On a mapping or list it exits 5, and the error names the path and says to use `troupe config show <path>`.
- **`troupe config show [PATH] [--sources]`**:
  - A single value prints the same as `get`.
  - A section, a list, or the whole configuration (no PATH) prints as YAML. Includes are resolved, and text includes appear as literal blocks (`|`).
  - With `--sources`, each line holding a value ends with `# from <file>`, e.g. `# from .troupe/agents/coder.yaml`. For a text include it names the included file.
- **`get` records hand edits before reading**, the same way `show` does.

**How it's built:** a new `src/troupe/render.py` writes the YAML. It reuses the quoting and literal-block code `set` already had, so both commands write values the same way.

**Tests:**
- The old scalar tests moved to `tests/test_get.py`.
- New exact-output tests are in `tests/test_show.py` and `tests/test_show_sources.py`.
- `tests/test_render.py` reads the output back and checks the values and their types match the configuration.
- There are new `get` cases for recording hand edits, and a `uv run` end-to-end test.

Three existing tests assumed the old behaviour and were updated:
- `show agents` exiting 5 is now `get agents` in the end-to-end tests.
- `show` with no PATH used to be a usage error and is now valid.
- The test that read commands leave your files untouched now also runs `get`, `show` and `show --sources`.

**What a deliberate breakage showed:** forcing strings to print unquoted makes the read-back tests fail, as intended. Turning off literal blocks does not: double-quoted strings still read back as the same data. The exact-output tests in `test_show.py` and `test_show_sources.py` are what pin the `|` layout.

**README:** it now documents `get`, `show --sources` and how to move scripts from `show` to `get`, and lists the choices I made where the contract was open. I put the new section after the `watch` example, because its demo overwrites `troupe.yml` and would otherwise break that example. I ran every README command in order against a fresh `/tmp/demo`, and they all work as written.

You can archive this change with `/method-command`.

Reply: /method-command

### Question 3 (step_done, answered by po)

Arm asked: ## Archive complete

**Change:** config-get-and-show
**Schema:** spec-driven
**Archived to:** `spec/changes/archive/2026-10-03-config-get-and-show/`
**Specs:** ✓ Synced to main specs. All 7 main specs validate under `method validate --specs --strict`.

The workflow normally asks whether to sync the specs before archiving. I went ahead with the recommended option, as the two earlier changes did, so say if you'd rather have archived without the sync.

**What changed in the main specs:**
- **`config-get`** (new): the requirements for `get` printing one value and refusing mappings and lists.
- **`config-show`**:
  - Its purpose now covers reading any part of the configuration.
  - "Show a scalar value" was updated.
  - "Show collections as YAML" and "Show sources" were added.
  - "Show refuses collections and missing paths" was removed.
- **`config-cli`**: `get` is now in the subcommand list, and the "files untouched" scenario covers `get` and `show --sources`.
- **`config-sync`**: `get` is now one of the commands that record hand edits before running.

I also pointed the README's decisions list at the archived design path. Everything is committed on `main` (4ef5d76) and nothing was pushed. There are no other active changes. All artifacts complete. All tasks complete.

Reply: 

## Discovery run

### Question 1 (next_command, answered by po)

Arm asked: I've planned the change `config-get-and-show` in `spec/changes/config-get-and-show/` and committed the plan on `main` as `28a2740`. Nothing is pushed and no project code has changed. `method validate --strict` reports the change as valid, and all 4 artifacts are complete.

**What's in it:**
- **`proposal.md`**: why and what. `get PATH` takes over what `show` did. `show [PATH] [--sources]` prints a value, a section or the whole configuration as YAML, and `--sources` says which file each value comes from. It's marked **breaking** because `show agents` no longer exits 5.
- **Specs**:
  - **`config-get`** (new): prints a scalar. A mapping or list exits 5, and the error names the path and mentions `config show`.
  - **`config-show`**:
    - A scalar prints exactly as `get` prints it.
    - The YAML layout rules come with exact-output scenarios.
    - `--sources` comments.
    - Missing paths still exit 5.
    - The old "refuses collections" rule is removed, with a migration note pointing to `get`.
  - **`config-cli`**: `get` is a subcommand, `show`'s `PATH` is optional, and `--sources` is accepted only by `show`.
  - **`config-sync`**: `get` picks up hand edits before running, as `show` and `set` do.
- **`design.md`**: how to build it (D1–D8). A new module, `render.py`, prints the configuration as YAML, reusing the quoting rules `set` already uses. Each literal block is parsed back and checked before it's printed; if it doesn't read back exactly, the string is printed in double quotes instead.
- **`tasks.md`**: 4 groups, each carrying its own tests and README updates.

**Choices I made where the contract is silent** (all recorded in `design.md`; implementation will add them to the README's decisions list):
1. **`show PATH --sources` on a single value** prints it as a one-line YAML document, e.g. `m  # from .troupe/troupe.yml`. The plain `get` form has no safe place for a comment, since a value can contain `#` or end in blank lines.
2. **Which lines get a `# from` comment:** only lines holding a value. Key-only lines like `agents:` and empty `{}`/`[]` get none. For a multi-line text block, the comment goes on the `|` line, because a comment on a content line would become part of the text.
3. **Multi-line strings** written in the file, not only text includes, are also printed as `|` blocks. Text a `|` block can't hold exactly, such as CRLF line endings, is printed in double quotes.
4. **File names** are worked out from real paths with symlinks resolved, relative to the theatre. A file outside the theatre is named with `..`.
5. **Layout details:** two spaces before `#`, two-space indentation, and lists indented under their key.

Choice 1 changes what users see the most, so if you'd rather it print the plain value or refuse `--sources` for single values, it's a one-place change and better made before implementation.

The plan is ready for review. When you're ready, run `/method-command`.

Reply: /method-command

## Arm D

## Scored run

### Question 1 (step_done, answered by runner)

Arm asked: `get` and the new `show` are working, and the work is committed on `main` as `363d949`. All 66 tests pass, and I checked the output with the real `troupe` command too.

- **`get PATH`** prints a single value, exactly as `show` used to. If the path is a mapping or list it exits 5, and the error says to use `troupe config show <path>` instead.
- **`show [PATH]`** prints a single value the same way `get` does. A mapping or list is printed as YAML in block style, with includes filled in and text includes shown as literal blocks (`|`). With no `PATH` it prints the whole configuration.
- **`show [PATH] --sources`** adds `# from <file>` at the end of every line that holds a value. The file is given relative to the theatre directory, for example `.troupe/agents/coder.yaml`. For a text include it names the included file.

The new rendering code is in `src/troupe/dump.py`, and the command changes are in `src/troupe/cli.py`. The existing tests now call `get`, and `tests/test_show.py` adds tests for `show`. Several of those tests read the printed YAML back in and check it gives the same configuration.

The spec didn't cover a few cases, so I made these choices and recorded them in `docs/decisions.md` (items 16–20):
- **Quoting:** values are quoted only when leaving them bare would change their meaning. Comments and the original files' quoting are not kept.
- **Text that can't be a literal block:** a text include or multi-line string is printed double-quoted if a literal block can't hold it exactly. Examples are text with Windows line endings, a first line starting with a space, or a value that is only line breaks.
- **Where the comment goes on a literal block:** with `--sources`, it goes on the `key: |` line, because a comment on any line below would become part of the text.
- **`show PATH --sources` on a single value** prints it as YAML (quoted if needed) with the comment, rather than in the plain `get` form, because the spec describes `--sources` output as YAML.
- **Files outside the theatre directory** are named with `..`, still relative to it.

I also updated the README for the new commands.

Reply: /method-command

### Question 2 (step_done, answered by po)

Arm asked: All 66 tests pass, and the working tree is clean: the `tests/test_show.py` already in commit `363d949` is the version on disk.

This is an ordinary repository, not a separate worktree, and the work was committed directly on `main`. That means the skill's three options don't apply:

1. **Merge back to the base branch:** there's no separate branch to merge; the work is already on `main`.
2. **Push and create a pull request:** your delivery rule forbids pushing and opening pull requests, so I haven't done either.
3. **Keep as-is:** this is where things already stand.

There's nothing to merge or clean up, so the work is delivered: `363d949` ("Add config get; make show print sections as YAML, with --sources") is on `main`.

Reply: 

## Arm E

## Scored run

### Question 1 (step_done, answered by po)

Arm asked: `get` and the new `show` are in, and the work is committed on `main` as `b3cec0d`. All 23 tests pass.

- **`troupe config get PATH`** prints a single value, exactly as `show` did before. If the path is a mapping or list it exits with code 5, and the error says `(use \`troupe config show PATH\`)`.
- **`troupe config show [PATH]`** prints a single value the same way `get` does. A mapping or list comes out as block-style YAML with includes resolved, and leaving out `PATH` prints the whole configuration. I checked that the YAML output reads back as the same values.
- **`show --sources`** adds `# from <file>` to the end of every line that holds a value, e.g. `model: sonnet # from .troupe/agents/coder.yaml`. Paths are relative to the theatre directory, so they start with `.troupe/`. A text include's value is credited to the included file.

Where the spec didn't say, I chose:

- **Comments on multi-line values:** the comment goes on the `|` line (`prompt: | # from .troupe/agents/prompt.md`). A comment on a content line would become part of the text.
- **Windows line endings in a text include:** they are shown as normal line breaks inside the literal block, because a literal block can't hold them. `get` still prints the raw bytes.
- **`show PATH --sources` on a single value:** it prints the value as one line of YAML plus its comment (`demo # from .troupe/troupe.yml`), not the raw `get` output.
- **Empty sections:** they print as `{}` or `[]` with no source comment, since they hold no value.

The YAML output is in a new class in `render.py`. `get` and the `show` changes are in `cli.py`. I updated the README and replaced the old `show` tests with tests for `get`, its errors, section output and `--sources`.

Reply: 

## Arm F

## Scored run

### Question 1 (next_command, answered by po)

Arm asked: I've written the step 3 spec and committed it on `main` (b4d3d3d). This step only covers the spec; there's no code or tests yet.

- **Feature directory:** `spec/003-config-get-show`
- **Spec file:** `spec/003-config-get-show/spec.md`
- **Checklist:** `spec/003-config-get-show/checklists/requirements.md`. Every item passed on the first check, and no questions were left open for you.
- **Hooks:** `spec/extensions.yml` has none registered, so none ran.

**What the spec covers:**
- **`get PATH`** behaves as `show` did in step 1. Asking it for a mapping or list exits 5, and the error message names the path and mentions `config show`.
- **`show [PATH]`** prints a single value exactly as `get` does. A section, or the whole configuration when PATH is left out, is printed as YAML with includes filled in and text includes as literal blocks.
- **`show --sources`** adds ` # from <file>` to each line holding a value, with the file relative to the theatre directory. For a literal block, the comment goes on its first line (`prompt: | # from …`).
- Any `show` output can be read back as YAML and gives the same values.
- The new requirements are FR-200 to FR-240 and replace step 1's FR-015. Everything else from steps 1 and 2 still applies.

**Choices I made where the contract leaves room (recorded as D-20 to D-26):**
- **D-20:** `get` and `show` both first record any hand edits made since the last command. Step 2 says every command except `history` does this.
- **D-21:** YAML layout is 2-space indentation, lists indented under their key, quoting only where needed, and keys in file order. Empty sections print as `{}` or `[]`, because block style can't express them.
- **D-22:** A file outside the theatre directory is named with `..` segments. Symbolic links are not followed.
- **D-23:** `show <single value> --sources` prints that value as YAML with its comment, e.g. `0.2 # from .troupe/troupe.yml`. The contract doesn't say what happens here, so this is the least obvious choice; tell me if you want something else.
- **D-24:** A text include with Windows (CRLF) line endings still prints as a literal block, so in `show`'s YAML it reads back with plain `\n` line breaks. `get` still prints the text exactly.
- **D-25, D-26:** One space goes before the `#`. `--sources` is accepted only by `show`; on `get` it's a usage error (exit 2).

Existing step 1 tests that expect `show` to refuse a mapping or list will need to move to `get` when this is built. The spec says so.

The next step is `/method-command`, or `/method-command` if you want to change D-23 or D-24 first.

Reply: /method-command

### Question 2 (next_command, answered by po)

Arm asked: The step 3 plan and design documents are written and committed on `main` (eadad43). No code has changed yet, and no extension hooks are registered, so none ran.

**Plan:** `spec/003-config-get-show/plan.md`. It passes the constitution check before and after design, with no exceptions to justify.

**The approach:**
- **`get`** is the current `show` renamed. The only change is the error for a mapping or list, which now says ``use `troupe config show PATH` to print it``.
- **`show`** prints a single value exactly as `get` does. Sections are printed by a new module, `src/troupe/config/view.py`. It works from the loaded configuration tree, which already records the file each value came from, so `--sources` gets its file names from there.
- **Reuse:** quoting rules and literal blocks (`|`, `|-`, `|+`, and an indentation number when the text starts with a space) come from the existing `edit/render.py`. The layout code that `set` uses for new values is not reused. Hooking `--sources` comments into it would tie a read-only view to the code that rewrites your files.
- **Behaviour shared with other commands:** both commands load the configuration and record pending hand edits first, then print. Neither writes any configuration file.
- **Tests:** the step 1 tests for `show` printing a value move to `get`, so they still prove that `get` behaves exactly as `show` did. New tests compare `show` output byte-for-byte, check that the YAML reads back as the same configuration, and check that no file changes.

**One spec change during planning:** I revised D-22 in `spec.md`. The file in `# from <file>` is now worked out from real locations, with symbolic links followed. The loader already identifies every file that way. It also means a theatre under a linked directory (like `/tmp` on macOS) still shows `.troupe/troupe.yml` rather than a path full of `..`.

I checked parsing against the installed YAML library. Comments after a value and on a literal-block header line are ignored, and indented literal blocks with an indentation number read back correctly, including at the top level.

**Other files in `spec/003-config-get-show/`:**
- `research.md`: technical decisions G-1 to G-7
- `data-model.md`
- `contracts/cli.md`: exact `get`/`show` output, layout and exit codes
- `quickstart.md`: the quality checks and a sample theatre to try the commands on

Next step: `/method-command`.

Reply: /method-command

### Question 3 (next_command, answered by po)

Arm asked: The step 3 task list is at `spec/003-config-get-show/tasks.md` and is committed on `main` (a853539). It has 21 tasks, and all of them use the required format (checkbox, ID, story label where needed, file path). No extension hooks are registered, so none ran.

| Phase | Tasks | What it covers |
|---|---|---|
| Setup | T001 | Run the tests, `mypy --strict` and ruff on the current code first |
| Foundational | — | Nothing needed; both commands reuse existing code |
| US1 `get` (P1, MVP) | T002–T008 (7) | Rename the code and step 1 tests to `get`, add the "use `config show`" hint and tests that `get` picks up hand edits, update usage tests |
| US2 `show` YAML (P1) | T009–T014 (6) | Unit tests for the layout, exact-output tests, read-back tests, the new `view.py`, the new `show` command |
| US3 `--sources` (P2) | T015–T017 (3) | Comment tests: main file, nested and text includes, files outside `.troupe/`, a single value, a symlinked theatre |
| Polish | T018–T021 (4) | README, notes in the step 1 and 2 docs that `show PATH` is now `get`, quickstart walk-through, final checks |

**Order matters:** the stories have to run in sequence. US1 first moves the old `show` tests and code to `get`, so the `show` name is free before US2 replaces it. US3 adds the comments to the output that US2's `view.py` produces. Keeping this order means the full test suite passes at every commit.

**Running work in parallel:** within US1, T002, T003 and T004 touch different files and can run together. Within US2, T009, T010 and T011 can run together. In Polish, T018 and T019 can run together.

**How each story is tested:**
- **US1:** `get` gives the same output, errors and exit codes as step 1's `show`. A mapping or list exits 5 and the error mentions `config show`.
- **US2:** `show` output matches the expected YAML byte for byte, and parsing it back gives the same configuration with the same types.
- **US3:** every line holding a value ends with the correct `# from <file>`, and no other line has one.

**Existing tests:** most step 1 and 2 tests call `show` on a single value. They stay as they are, because `show` still prints single values exactly like `get`. Only three need changing, and T005 covers them: the "collection exits 5" cases, the usage test expecting `config show` with no PATH to exit 2, and `test_error_messages.py`.

**Suggested first slice:** Setup plus US1 gives a working `get` that behaves exactly like the old `show`.

Every story ends with a step that deliberately breaks the behaviour, confirms a test fails, then restores it, as Principle II of the constitution requires.

Next step: `/method-command`.

Reply: /method-command

### Question 4 (step_done, answered by runner)

Arm asked: Step 3 is built and committed on `main`, and the working tree is clean. Nothing was pushed and no pull request was opened. All 21 tasks are marked done. The pre-implementation requirements checklist had all 16 items checked, and no extension hooks are registered.

**Final checks:** 539 tests pass (442 before step 3), `mypy --strict` reports no issues across 63 files, and ruff check and format are clean.

**What changed:**
- **`get PATH`** (0c9e74b) prints a single value exactly as `show` did before. The step 1 `show` tests moved over to `get` unchanged. Asking `get` for a mapping or list exits 5 with: ``agents.coder: is a mapping, not a scalar; use `troupe config show agents.coder` to print it``.
- **`show [PATH]`** (5bcb6b7) still prints a single value like `get`. A section, or the whole configuration if PATH is left out, prints as YAML: 2-space indent, includes filled in, text includes as literal blocks. It uses the quoting rules `set` already had. The output reads back as the same configuration with the same types; a Windows line-ending text include is the one exception, as the spec records.
- **`show --sources`** (cc5775a) ends each value's line with `# from <file>`, relative to the theatre. This came from the same new `view.py` module, so this commit only added tests. They cover the main file, nested includes, text includes, files outside `.troupe/` or the theatre, single values, and a theatre reached through a symlink.
- **Docs** (adf65bb): the README, and notes in the step 1 and step 2 docs that `show PATH` is now `get PATH`.

**How the tests were checked:**
- For each story I broke the behaviour on purpose and confirmed a test failed, then restored the code. The breaks were: the `config show` hint, `get` not picking up hand edits, text includes not as literal blocks, list layout, quoting, the wrong source file, the symlink handling, and a comment on a section line.
- One of those first looked uncaught. It turned out my edit hadn't changed the code; with the edit applied, the tests catch it.
- One new test was wrong at first: I expected `show agents` to include the `agents:` key itself, but it correctly prints only what's inside it. I fixed the test, not the code.

I also ran the quickstart by hand. Every command printed what the spec shows, and no configuration file was modified.

Reply: /method-command

### Question 5 (next_command, answered by po)

Arm asked: Convergence found remaining work, so I added two tasks as **Phase 7: Convergence** at the end of `spec/003-config-get-show/tasks.md` and committed it (8cfe423). Nothing else in `tasks.md`, the spec, the plan or the code was changed.

- **T022 (HIGH):** `show` prints YAML that won't parse when a text starts with a line of only spaces (e.g. `"    \nabc\n"`). The fix goes in `needs_indent_indicator` in `src/troupe/config/edit/render.py`. `set` uses the same function, so the task also adds a `set` test for such a value.
- **T023 (LOW):** add a test for the "same file included twice" case. It already works correctly; it just has no test.

No extension hooks are registered for this step.

Next: run `/method-command` to do T022 and T023, then `/method-command` again to confirm nothing is left.

Reply: /method-command

### Question 6 (next_command, answered by po)

Arm asked: I've fixed both convergence tasks, T022 and T023, and committed the work on `main` (9699529). All 23 tasks in `tasks.md` are now marked done. The working tree is clean, and nothing was pushed or opened as a pull request.

- **T022:** a text whose first line contains only spaces (e.g. `"    \nabc\n"`) made `show` print YAML that wouldn't parse, and made `set` refuse the value with exit 3. The fix is in `needs_indent_indicator` in `src/troupe/config/edit/render.py`. Such text now gets an indentation number (`|2`) and reads back exactly.
  - New tests cover a text include, a value inside a list item, and a top-level value with `--sources`. A new `set` test checks it now writes `k: |2` followed by the indented lines.
  - All four tests failed before the fix and pass after it, which also served as the deliberate-break check.
- **T023:** added a test that a file included under two keys is shown in full under both, each line marked `# from .troupe/s.yaml`. That behaviour was already correct, so I didn't do a deliberate break for this one.

Final checks: 544 tests pass, `mypy --strict` reports no issues across 63 files, and ruff check and format are clean. No extension hooks are registered.

Running `/method-command` again should now report nothing left to do.

Reply: /method-command

### Question 7 (step_done, answered by po)

Arm asked: ## Convergence Findings

No actionable findings.

| ID | Gap Type | Severity | Source | Evidence | Remaining Work |
|----|----------|----------|--------|----------|----------------|
| — | — | — | — | — | — |

**What I re-checked:**
- **Previous convergence tasks:** T022 and T023 are in place. `needs_indent_indicator` handles a leading spaces-only line, and both new tests exist and pass.
- **Read-back fuzzing:** I generated 6,000 random keys and values covering quoting characters, `#`, `:`, leading spaces and tabs, blank and spaces-only lines, `~`, and non-ASCII. Each went into a plain value, a list item and a text include, and was printed with `--sources`. Every output read back exactly: 0 mismatches.
- **One case that is not a gap:** strings containing U+2028 (the Unicode "line separator") next to a space can read back without that space when parsed with ruamel.
  - The cause is ruamel treating U+2028 as a line break. YAML 1.2, which FR-214 names as the standard, treats it as ordinary text, so our output is valid 1.2.
  - Writing U+2028 unescaped inside double quotes is what step 1's FR-028 requires, and FR-222 adopts that rule.
  - So `show` is right per the spec. Changing it would mean changing FR-028, which would be your decision.

**Summary metrics:**
- **Checked:** 26 functional requirements (FR-200 to FR-240), 4 success criteria, 19 acceptance scenarios and 17 edge cases.
- **Plan decisions checked:** 7 (G-1 to G-7), plus the files the plan says to create or edit.
- **Constitution:** 6 principles plus the technical constraints. The last implement pass showed 544 tests passing with mypy and ruff clean, and the working tree is still clean.
- **Findings:** none of any type (missing, partial, contradicts or unrequested) at any severity.

✅ Converged — the implementation satisfies the spec, plan, and tasks.

I left `tasks.md` exactly as it was. All step 3 work is committed on `main` (latest 9699529), not pushed, with no pull request opened, as you asked. No further implement pass is needed. No extension hooks are registered.

Reply: 

## Discovery run

### Question 1 (next_command, answered by po)

Arm asked: I've written the step 3 spec and committed it on `main` (commit `2676c1b`, not pushed). It covers only the specification; no code has changed yet.

- **Feature directory:** `spec/003-config-get-show`
- **Spec file:** `spec/003-config-get-show/spec.md`, with its checklist in `checklists/requirements.md`
- `spec/feature.json` now points to the new directory. Git ignores that file, so it isn't in the commit.

**What the spec says:**
- **`get PATH`** prints a single value exactly as the old `show` did. Asking it for a section exits with code 5, and the error names the path and mentions `config show`.
- **`show [PATH]`** prints a value the same way `get` does. A section, or the whole configuration when no path is given, comes out as YAML with includes filled in and text includes as literal blocks. The printed YAML must read back to exactly the same values and types.
- **`--sources`** adds ` # from <file>` to every line that holds a value. The file is given relative to the theatre directory, e.g. `.troupe/agents/coder.yaml`.
- The step 1 rule that `show` rejects sections (FR-015) is marked as replaced. All other step 1 and step 2 rules still apply: both commands still pick up hand edits first, and the exit codes are unchanged.

**Choices I made where your contract was silent** (recorded as D-20 to D-27 in the spec; tell me if any are wrong):
- **A single value with `--sources`:** it's printed as YAML with the comment on its line. For a plain value like `0.2` that's just `0.2 # from .troupe/troupe.yml`. For a text include it becomes a literal block, because adding a comment to raw text would change the text.
- **Text includes a literal block can't hold exactly**, such as files with Windows (CRLF) line endings: these are printed in double quotes so the value is never shown wrong.
- **`show agents.coder`** prints what's inside the section, without the `coder:` key above it.
- **Layout:** one space before `# from`, 2-space indentation, lists indented under their key, and `{}` / `[]` for empty sections.
- **Files outside the theatre directory** are named with leading `../` rather than as absolute paths.
- **`get --sources`** is rejected as a usage error (exit 2) rather than ignored.

**Checklist:** all items passed first time, and I didn't need to ask you anything. The next step is `/method-command`, or `/method-command` if you want to revisit any of the choices above.

Reply: /method-command

### Question 2 (next_command, answered by po)

Arm asked: I've written the step 3 implementation plan and committed it on `main` (commit `2941d0f`, not pushed). The Constitution Check passes before and after the design, nothing is left unresolved, and no hooks are configured.

**Location:** `spec/003-config-get-show/` (delivery stays on `main`; there is no feature branch)
- `plan.md`: summary, technical context, Constitution Check, file layout, design overview
- `research.md`: the technical choices, numbered G-1 to G-8
- `data-model.md`: one new field on an existing in-memory record, plus the shape of output lines
- `contracts/cli.md`: command forms, exact output shapes and errors. It replaces the `show PATH` rows of the step 1 contract.
- `quickstart.md`: the quality checks and commands to run by hand to see the feature work

**Design in brief:**
- **One renderer for both outputs.** The loaded configuration already records which file each value came from, including text includes. A new `config/view.py` walks it and pairs each output line with its source file. `--sources` then just adds ` # from <file>` to those lines, so stripping the comments always gives exactly the plain `show` output.
- **Quoting rules are shared, not copied.** The rules for how a value is written (plain, quoted, literal block) move out of `edit/render.py` into a new `config/spelling.py`, used by both `set` and `show`. This makes the printed YAML read back to the same values and types. The logic doesn't change, and the existing byte-exact `set` tests will confirm that.
- **File names are shown as the path was written.** Each loaded file gains a second path that doesn't follow symbolic links, so names come out like `.troupe/agents/coder.yaml` or `../shared/x.yaml`. One limitation: if the same file is included by two different routes, the first route's name is shown.
- **The commands:**
  - `get` keeps the old `show` code; asking it for a section exits 5 and points to `config show`.
  - `show` takes an optional path plus `--sources`.
  - The command-line parser already rejects `get --sources` with exit 2.

**Existing tests that will change:** the ones expecting `show` on a section to exit 5 move to `get`. Tests of `show` on a single value stay valid as they are.

I checked the YAML points the design relies on against the installed `ruamel.yaml`. A comment after a `|` header and a top-level literal block with an indentation digit both read back correctly. No code has been written yet; next is `/method-command`.

Reply: /method-command

### Question 3 (next_command, answered by po)

Arm asked: I've written the step 3 task list to `spec/003-config-get-show/tasks.md` and committed it on `main` (commit `953343e`, not pushed). No hooks are configured.

**28 tasks in total**, every one in the checklist format with an ID and file path; tasks inside a user-story phase also carry a story label:

| Phase | Tasks | Count |
|---|---|---|
| 1. Setup: run the quality checks on the unchanged code | T001 | 1 |
| 2. Foundational: move the shared quoting rules into `config/spelling.py` (no behaviour change) | T002–T004 | 3 |
| 3. US1, `get` (P1), the first deliverable | T005–T010 | 6 |
| 4. US2, `show` for sections (P1) | T011–T019 | 9 |
| 5. US3, `show --sources` (P2) | T020–T024 | 5 |
| 6. Polish: README, mark the old step 1 rule as replaced, walk the quickstart, final checks | T025–T028 | 4 |

**How each story is tested on its own:**
- **US1:** `get` output is byte-identical to the old `show` for every existing single-value case. A section exits 5, and the error names the path and mentions `config show`.
- **US2:** exact expected YAML for each spec scenario. A separate test reads `show` output back with a YAML parser and checks it equals the configuration, with types kept.
- **US3:** exact `--sources` output; the text include is credited to its own file; files outside the theatre get `../` names. Removing the comments must give exactly the plain `show` output.

**What can run in parallel:**
- The Phase 2 move and US1 touch different files, so they can run side by side.
- Within the stories: T005 with T006, T011 with T013 and T014, T020 with T021.
- In the polish phase: T025 with T026.

**Existing tests that will change:** tests expecting `show` on a section to exit 5 move to `get` (T007). The test treating a bare `config show` as a usage error is turned into a success case (T015), since a missing path now means the whole configuration.

Tests are written before the code, as the project's rules require. Each story ends by deliberately breaking the behaviour once to confirm the tests catch it, then committing.

**Suggested first deliverable:** Phase 1 plus US1, which gives scripts a stable `get` straight away. Next is `/method-command`.

Reply: /method-command
