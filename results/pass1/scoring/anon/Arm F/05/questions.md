## Scored run

### Question 1 (next_command, answered by po)

Arm asked: I've written the step 5 spec and committed it on `main` as `0aaad5a`. Nothing is implemented yet: this is the spec only, so CR-A is not delivered until the plan, tasks and implementation are done.

- **Feature directory:** `spec/005-include-overrides`
- **Spec file:** `spec/005-include-overrides/spec.md`
- **Checklist:** `spec/005-include-overrides/checklists/requirements.md`. Every item passes; one wording fix was needed so the contract's example comes out as exactly `coder:  # c`.

**What the spec covers:**
- **Stories:** four of them: adding a new key without touching the shared file, reading includes that carry overrides (`get`, `show`, `show --sources`, history), changing existing values where they live, and keeping list changes in the file that holds the list.
- **Requirements:** numbered FR-400 to FR-450. They replace step 1's rule for where a new key is written (FR-022) and refine its rule for existing values (FR-020); everything else from steps 1–4 still applies.
- **Clarification questions:** none. Where the contract leaves a choice open, I made it and recorded it as D-40 to D-46.

**Decisions you may want to check:**
- **D-40, nested includes:** if `troupe.yml` includes `coder.yaml`, which includes `model.yaml`, a new key under `model` is written as an override in `coder.yaml`. That is the literal reading of "the file that contains the include reference", but `coder.yaml` may itself be shared. If you want overrides always written in the main file, say so; it's a one-place change.
- **D-41:** a list item that is itself an include can carry overrides. It is converted to mapping form inside the list.
- **D-42:** a `$ref` whose value isn't a `file:` string is just an ordinary mapping key.
- **D-43:** overrides on a YAML include whose content is a list or scalar → exit 4, because merging keys into it would discard the included content.
- **D-44:** replacing a whole mapping that mixes override keys with keys from the included file → exit 3, because an override can't remove the included keys.
- **D-45 and D-46:** when an include is converted, its string keeps its original quoting. Merged keys keep the included file's order, with override-only keys after it.

There are no extension hooks to run. `spec/feature.json` now points at the new directory, but it is gitignored, so it isn't in the commit.

Next step is `/method-command`, or `/method-command` first if you want to change D-40.

Reply: /method-command

### Question 2 (preempted, answered by runner)

Arm asked: I've written the step 5 plan and design documents and committed them on `main`. There were no extension hooks to run.

**Plan:** `spec/005-include-overrides/plan.md`
**Other documents:** `research.md` (technical choices O-1 to O-9), `data-model.md`, `contracts/cli.md`, `quickstart.md`.

**Design in brief:**
- **Reading:** the loader recognises a `$ref` mapping and builds the merged result directly. Each value still remembers the file it's written in, so `get`, `show`, `show --sources`, history, reconcile and `watch` need no changes.
- **Where a new key goes:** `set` tracks, for each file, the include reference it was reached through. A new module, `edit/override.py`, uses that to decide where the key is written. It also converts a one-line include into the `$ref` form, keeping the original include string and any end-of-line comment. The existing code still lays out the new lines, so quoting and comment handling stay as they were.
- **Checking a write:** before writing, the check that the change lands only where intended now identifies an include by where it is referenced. This matters when one file is included twice: an override at one key is shown to leave the other alone.
- **Existing test:** `test_new_key_in_an_included_file` encodes the old rule (new key written into the shared file). It will be changed to expect the override.

**Spec changes from planning** (committed separately as `75b0bb8`):
- **D-48:** a section that has keys from both a shared file and an override counts as coming from the override's file. So a new key there goes into that override, or one level further out if that file is itself included. No shared file gains it.
- **D-47:** if the place that should receive the override is itself an include (for example an override `limits: file:l.yaml`), `set` refuses with exit 3 and changes nothing.

Every principle in the constitution check passes, and no clarifications are open. Next step is `/method-command`.

Reply: /method-command A second change request has arrived while you work on the first one:

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.

---

## In-include (from step 5, change request B)

- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.


### Question 3 (next_command, answered by po)

Arm asked: I've written the CR-B spec and committed it on `main` as `2d319c9`. This is the spec only; neither CR-A nor CR-B is implemented yet.

- **Feature directory:** `spec/006-set-in-include`. It's a separate directory because each specify run makes one feature. It builds on CR-A (`005`) and continues its numbering: FR-460 to FR-466, decisions D-50 to D-52.
- **Spec file:** `spec/006-set-in-include/spec.md`
- **Checklist:** every item passes on the first try, and there are no clarification questions.

**What it says:** `set --in-include PATH VALUE` writes a new key under included content by the step 1 rule. The key goes into the file holding the deepest existing setting above it, and the including file is not touched or converted. Without the flag, CR-A's override behaviour stays the default.

**Decisions you may want to check:**
- **D-50:** the flag is accepted on any `set` but only changes where new keys go. Existing values, list appends and keys inside list items land exactly where they would without it. The alternative was to make it change an overridden value in the shared file. I rejected that because the override would still win, so the visible value wouldn't change.
- **D-51:** if the section above the new key mixes keys from the shared file and from an override, the key goes into the shared file's part. If that section exists only in an override, it stays in the file holding the override, rather than creating a new section in the shared file.
- **D-52:** `--in-include` is a flag of `set` only, like `--reason`. Any other subcommand rejects it with exit 2, and so does giving it a value.

**Workflow choice:** CR-A already has a plan but no tasks yet. I'd plan CR-B next (`/method-command`, with `spec/feature.json` now pointing at 006). It's a small change on top of CR-A's design: skip the override placement when the flag is set. Then generate tasks for both and implement them together.

Reply: /method-command

### Question 4 (next_command, answered by po)

Arm asked: I've written the CR-B plan and committed it on `main`. There were no extension hooks to run, every constitution check passes, and nothing needs clarifying.

**Plan:** `spec/006-set-in-include/plan.md`
**Other documents:** `research.md` (choices I-1 to I-5), `data-model.md`, `contracts/cli.md`, `quickstart.md`.

**Design in brief:**
- **The flag:** `--in-include` is a plain on/off flag on `set`. The argument parser rejects it on other subcommands and rejects it with a value (exit 2), before anything is loaded.
- **Where it acts:** it is passed down to the single function from CR-A that decides where a new key goes. That function is the only code that reads it. Existing values, list appends and keys inside list items never reach that function, so the flag can't affect them (D-50).
- **Sections with keys from both files:** these will keep a reference to their original, unmerged section from the shared file. With the flag, the new key is laid out there using step 1's rules unchanged. With nested includes, it goes to the deepest file.

**Change to CR-A's plan** (committed separately as `c7595fa`): CR-A's plan had the check before each write identify every include by its reference. That would refuse a new key written into a file included at two keys, which step 1 allows and `--in-include` depends on. Now only override writes are checked by reference; everything else keeps step 1's check. I amended CR-A's `research.md` (O-6) and `plan.md` for this.

**Commits:** `2d319c9` (CR-B spec), `c7595fa` (CR-A fix), `a83fa90` (CR-B plan).

CR-B is designed to be implemented together with CR-A. Next step is `/method-command`. `spec/feature.json` points at 006, so it would generate CR-B's tasks; CR-A (005) still needs its own tasks.

Reply: /method-command

### Question 5 (next_command, answered by po)

Arm asked: I've written task lists for both change requests and committed them on `main` as `283ad8f`. You asked for CR-B's tasks; I also wrote CR-A's, because CR-B is built on CR-A's code and CR-A had no task list yet. There were no extension hooks to run. Tests are included throughout, since the constitution requires a test for every behaviour.

**CR-A: `spec/005-include-overrides/tasks.md`, 24 tasks**

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | T001–T002 (baseline checks; let the test helpers pass extra `set` options) | — |
| Foundational | T003–T006 (new tree fields, recognising and merging `$ref` mappings in the loader, merge unit tests) | — |
| US2: read overrides (P1) | T007–T010 | `get`, `show`, `--sources`, history and `watch` on hand-written `$ref` fixtures |
| US1: new key becomes an override (P1) 🎯 | T011–T017 | byte-for-byte comparison; only the including file changes |
| US3: existing values (P2) | T018–T019 | override vs shared file; whole-section replacement refused (exit 3) |
| US4: lists (P2) | T020–T021 | appends and keys inside list items stay in the list's file |
| Polish | T022–T024 | README, note in the step 1 spec, final checks |

- **Order:** reading (US2) comes before writing (US1). Every new-key write is checked by reloading the result, so the reading code must be proven first.
- **Existing test:** T012 changes the one existing test that encodes the old rule (new key written into the shared file), rather than deleting it.

**CR-B: `spec/006-set-in-include/tasks.md`, 10 tasks**

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | T001 (confirm CR-A is done and green) | — |
| Foundational | T002–T004 (flag parsing and errors, passing it down to placement, merged sections remember their shared-file part) | — |
| US1: key into the shared file (P1) 🎯 | T005–T006 | with the flag, only the included file changes, including the file-included-twice case |
| US2: flag changes nothing else (P2) | T007–T008 | each `set` runs with and without the flag on two fresh theatres; files and history must match |
| Polish | T009–T010 | README, final checks |

**Parallel work:** in CR-A, the merge tests (T003) can run alongside the tree change (T004), and the three US2 test files (T007–T009) can be written together. US3 and US4 can be done in either order, and T022/T023 together. In CR-B, T002 and T004 can run in parallel.

**MVP:** CR-A phases 1–4 deliver CR-A's main promise (shared files untouched). CR-B phases 1–3 add the flag.

**Format check:** all 34 tasks use the `- [ ] T### [P?] [US?] description` form with file paths; none are malformed.

Next step is `/method-command`, starting with CR-A. `spec/feature.json` points at 006, so switch it to `spec/005-include-overrides` first.

Reply: /method-command

### Question 6 (step_done, answered by runner)

Arm asked: Both change requests are implemented and committed on `main`, and all 34 tasks are checked off. Nothing was pushed and no pull request was opened. There were no extension hooks to run.

**Final checks:** `uv run pytest` gave 778 passed, 1 skipped (the baseline before this work was 689 passed, 1 skipped). `mypy --strict` and both `ruff` checks are clean, and I ran both quickstart walk-throughs by hand; the output matched what they predict.

**CR-A: new keys under a shared include become overrides**
- **Reading:** an include can be written as a mapping with `$ref` plus override keys. The loader builds the merged value directly, so `get`, `show`, `show --sources`, history, reconcile and `watch` all see it without other changes.
- **New keys:** a new key under an included section is written as an override in the file that holds the include, and the shared file is left untouched. A one-line include is converted first; the contract's example is a test, byte for byte. The code that decides where a new key goes lives in one new file, `edit/override.py`.
- **Existing values:** an overridden value changes in the override, any other value changes where it lives, and list changes stay in the file that holds the list.
- **Refusals:**
  - Overrides on a non-YAML include, or on an include that isn't a mapping, exit 4.
  - Replacing a section that has keys from the shared file exits 3, because an override can't remove those keys.
  - Adding a key where the override is itself an include exits 3.
- **Docs:** the one existing test that encoded the old rule now expects the override. Step 1's spec marks its rule as replaced, and the README documents overrides.

**CR-B: `set --in-include`**
- With the flag, a new key goes into the shared file by step 1's rule and the including file isn't touched. Only the placement code reads the flag. A test runs each other kind of `set` with and without it on two fresh theatres and requires identical files and history.
- Other subcommands reject the flag with exit 2.

**Things to know:**
- **Commit history:** the four commits from `5f7ccbf` up to `6c151d0` are not individually green. The verify unit tests' stand-in for the planner didn't accept the new keyword, so 4 tests failed in that range; I fixed it in `6c151d0`, which reaches the 778-passing state above. If you need every commit green for bisecting, `5f7ccbf` can be amended.
- **Tests checked against broken code:** I made each new test fail on the old code or on a deliberate break. Where a test passed against the old loader for the wrong reason, I tightened it.
- **Design changes found while building:** sections that mix shared-file and override keys keep a reference to their shared-file part. Without it, a new key below a nested include could have been written into a shared file. Also, the key in front of a converted include is looked up in that include's own file. Both are recorded in CR-A's `research.md`.
- **Decisions you may want to review:** D-40 (with nested includes, the override goes in the *nearest* including file, which may itself be shared) and D-50 (`--in-include` has no effect on existing values).

Reply: /method-command

### Question 7 (next_command, answered by po)

Arm asked: CR-A's code is correct in every case I checked, but four of its behaviours have no automated test. That breaks the constitution's rule that every behaviour must have one, so I've added five test tasks to CR-A's task list. CR-B has no remaining work, and no code was changed.

**CR-B (`spec/006-set-in-include`, the current feature): ✅ Converged.** Every requirement, success criterion and decision is implemented and covered by a test. Its `tasks.md` is unchanged.

**CR-A (`spec/005-include-overrides`): 5 tasks appended as Phase 8: Convergence (T025–T029)**, committed on `main` as `e8ea51c`. I assessed it too because it shipped with CR-B, even though `spec/feature.json` points at 006.

| Task | Severity | What it adds | Traces to |
|---|---|---|---|
| T025 | CRITICAL | Test: a new key added to an existing one-line (flow) `$ref` mapping | Constitution II, FR-425 |
| T026 | CRITICAL | Test: an include written as an item of a one-line list is converted in place | Constitution II, D-41, FR-423 |
| T027 | CRITICAL | Test: `set` on a `{$ref: file:p.md}` text include writes `p.md` and nothing else | Constitution II, FR-402 |
| T028 | CRITICAL | Test: a multi-line string added as an override is written as a literal block | Constitution II, FR-427 |
| T029 | MEDIUM | Two refusal tests also check that the error message names the path | SC-404 |

The four CRITICAL ratings come from the constitution's "every behaviour MUST have a test" rule, not from broken behaviour. I ran each of these cases against the real CLI and the output was right. Each task gives the exact input files and expected bytes, so they're quick to add.

**What I checked:**
- CR-A's FR-400 to FR-450 and SC-401 to SC-405, and CR-B's FR-460 to FR-466 and SC-460 to SC-463, with every user-story scenario in both specs.
- The design choices in both plans (O-1 to O-9, I-1 to I-5) and all six constitution principles.
- 7 extra CLI probes for cases the existing tests didn't cover.

Findings: 4 missing, 1 partial, none contradicting the spec and none unrequested.

There are no extension hooks. Next step: switch `spec/feature.json` to `spec/005-include-overrides` and run `/method-command` to add these tests. A second converge run on 005 should then come back clean.

Reply: /method-command

### Question 8 (step_done, answered by po)

Arm asked: I added the five tests from the convergence pass (T025–T029) and committed them on `main` as `62cb106`. Every task in CR-A's (005) and CR-B's (006) task lists is now checked off. There were no extension hooks to run, and CR-A's requirements checklist was fully checked.

**Added tests:**
- **T025:** a new key added to a one-line `{$ref: …}` mapping is appended in place: `{$ref: file:c.yaml, model: x, t: 1}`.
- **T026:** an include that is an item of a one-line list becomes `[{$ref: file:a.yaml, t: 1}]`.
- **T027:** `set` on a `{$ref: file:p.md}` text include writes `p.md` and leaves `troupe.yml` alone.
- **T028:** a multi-line string added as an override is written as a literal block (`p: |`).
- **T029:** the two refusal tests (D-44 and D-47) now also check that the error message names the path.

The implementation already handled all of these, so only tests changed. Because they passed on first run, I broke the code on purpose to check they can fail. Breaking the separator in the one-line conversion failed T026 and the existing flow-conversion test. Making new keys go into the shared file instead of the override failed T025. The code was restored after each break.

**Gates:** `uv run pytest` gives 782 passed, 1 skipped; `mypy --strict`, `ruff check` and `ruff format --check` are clean.

A second `/method-command` on 005 should now come back clean; 006 had already converged. Nothing was pushed and no pull request was opened.

Reply: 

## Discovery run

### Question 1 (next_command, answered by po)

Arm asked: I've written the step 5 spec for CR-A ("keep shared includes shared") and committed it on `main` as `59ae086`. Nothing was pushed. This step only produces the spec; no code has changed, so the request isn't delivered yet.

- **Feature directory**: `spec/005-include-overrides`
- **Spec file**: `spec/005-include-overrides/spec.md`. `spec/feature.json` now points at this directory. It's gitignored, so it wasn't committed.
- **Checklist**: all items pass on the first check, with no open questions. It's in `checklists/requirements.md`.
- **Extension hooks**: none are registered, so none ran.

**What the spec says**
- **Stories:** four.
  - Adding a new setting under a shared section writes it as an override in your own file; the shared file is left untouched.
  - Changing an existing setting updates the override if there is one, otherwise the file it comes from.
  - `get`, `show`, `show --sources` and history all see the merged configuration.
  - List changes stay in the file that holds the list.
- **Requirements:** FR-400 to FR-433. They replace step 1's rule for where a new key is written (FR-022) and refine the rule for changing an existing value (FR-020).

**Choices I made where the contract was silent (D-40 to D-48)**
- **Malformed includes fail to load (exit 4):** a `$ref` that isn't a `file:` string, or override keys on an included file whose content isn't a mapping.
- **`set` refuses (exit 3) if the result wouldn't equal what you set.** For example, setting a section that mixes keys from the shared file and from an override would leave the shared keys merged in. Refusing seemed safer than also editing the shared file.
- **Includes written inline in flow style (`{...}`)** are converted to a flow mapping with `$ref`, since block lines can't go there.
- **`$ref` can't be used as a path segment in `set` (exit 3).** This stops `set` from turning ordinary data into an include by accident.
- **In a chain of includes,** the override goes in the file that directly includes the shared one. Files further out don't change.

Next is `/method-command`, or `/method-command` first if you want to revisit any of those choices, especially the exit-3 refusal.

Reply: /method-command

### Question 2 (preempted, answered by runner)

Arm asked: The step 5 plan and design docs are written and committed on `main` as `0987e10`. Nothing was pushed. No code has changed yet, and no extension hooks are registered, so none ran. Every principle passes the constitution check before and after design, with no exceptions to justify.

**Artifacts** (all in `spec/005-include-overrides/`):
- `plan.md`: technical context, constitution check, files to change, design overview
- `research.md`: ten technical decisions, O-1 to O-10
- `data-model.md`: the changes to the in-memory configuration tree, the merge rule, and a table of where `set` writes
- `contracts/cli.md`: the `$ref` file format, the new write rules, and the new exit 3 and exit 4 cases
- `quickstart.md`: the quality checks plus a manual walk-through you can run

**The approach:**
- **Loading:** a `$ref` include is loaded into a merged tree built from the original nodes. Each value keeps the file it came from, so `get`, `show --sources`, history, reconcile, `watch` and changing an existing value all work without changes.
- **New keys:** while walking the path, `set` tracks the nearest include. A new key goes into that include's overrides, or converts a one-line include to the `$ref` form first, keeping the comment and the exact include text. Passing through a list switches back to the old rule of writing in the file that holds the list.
- **Refusing bad writes:** the existing reload-and-verify check already produces exit 3 when merging wouldn't give the value that was set, so that needs no special code. It does need one change: it must expect an override to show up only where its include appears, not everywhere the shared file is included.
- **Rename:** the loader parameter `overrides`, which means something else today, becomes `texts` so the word has one meaning.

One existing test asserts the rule being replaced: `test_set_new_key.py::test_new_key_in_an_included_file`. It will be rewritten to expect the override in `troupe.yml`.

Next is `/method-command`.

Reply: /method-command A second change request has arrived while you work on the first one:

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.

---

## In-include (from step 5, change request B)

- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.


### Question 3 (next_command, answered by po)

Arm asked: I've written the CR-B spec and committed it on `main` as `5e2767c`. Nothing was pushed. It's a spec only: CR-A's code isn't written yet, and CR-B builds on it.

- **Feature directory**: `spec/006-set-in-include`. `spec/feature.json` now points here (it's gitignored).
- **Spec file**: `spec/006-set-in-include/spec.md`
- **Checklist**: all items pass on the first check, with no open questions.
- **Extension hooks**: none are registered, so none ran.

**What the spec says:**
- **The new option:** `set --in-include PATH VALUE` writes a new key under an included section into the included (shared) file, the way step 1 did. The file containing the include is left unchanged, and a one-line include is not converted to the `$ref` form. Without the option, CR-A's rules apply unchanged.
- **Combining:** it works alongside `--reason` and `--theatre` and is recorded in history like any other `set`.
- **Other commands:** using it on any other command is a usage error (exit 2).

**Choices I made where the contract was silent (D-50 to D-54):**
- **Only new keys are affected.** Existing values and list appends behave the same with or without the option. An overridden value is never written into the shared file, because the override would hide it there.
- **No include on the path is not an error.** The step 1 rule names the same file the default rule does.
- **Ancestor that exists only as an override:** if an override adds a section (say `limits`) that the shared file lacks, the key still goes into the shared file. The section is created there and merges with the override.
- **Chains of includes:** the key goes into the innermost file, the one the content actually comes from.

I also added a three-line note to CR-A's spec at its new-key rule, saying `--in-include` is the exception, so the two specs agree.

**Next:** `/method-command`. This will also need a small addition to CR-A's plan: the planner's choice of where a new key goes will take the flag into account. After that, run `/method-command` covering both change requests.

Reply: /method-command

### Question 4 (next_command, answered by po)

Arm asked: I've written the CR-B plan and design docs and committed them on `main` as `8faa069`. Nothing was pushed. No code has changed yet. No extension hooks are registered, so none ran. Every principle passes the constitution check before and after design, with no exceptions to justify.

**Artifacts** (in `spec/006-set-in-include/`):
- `plan.md`
- `research.md`: four decisions, I-1 to I-4
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

**The design** treats `--in-include` as a second option inside CR-A's single "where does a new key go" decision:
- **CLI to planner:** a placement value (`"override"` by default, `"include"` with the flag) is passed from `cli.py` down to the planner. Other commands don't define the option, so it is rejected there with exit 2 without any extra code.
- **Merged sections:** where an override is merged into a section of the shared file, the in-memory tree now also keeps the shared file's own version of that section (`LocatedMapping.base`). That lets the planner reuse step 1's new-key writer unchanged: the key goes after the shared file's last entry, in its style and indentation. I recorded this field in CR-A's `data-model.md` too, so the two designs agree.
- **Choosing the target:** with the flag, the planner walks up from the deepest existing section and picks the first one that exists in the shared file. Sections that exist only as overrides are skipped. Lists, existing values and appends never reach this choice, so they behave the same with or without the flag.
- **Safety check:** this is step 1's. A shared file included twice gains the key in both places. A key that an override would hide is refused with exit 3.

**Next:** `/method-command`, covering CR-A and CR-B in order, since CR-B is a branch inside CR-A's code.

Reply: /method-command

### Question 5 (next_command, answered by po)

Arm asked: I've written two task lists, one for each change request, and committed them on `main` as `e1813f2`. Nothing was pushed. No code has changed yet. No extension hooks are registered, so none ran. All 38 tasks follow the required checklist format (checkbox, ID, labels where needed, file paths), checked with a grep.

The active feature is CR-B, but its code sits inside CR-A's, which had no task list yet. So I wrote both, and CR-A's runs first.

**`spec/005-include-overrides/tasks.md` (CR-A): 23 tasks**

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | 2 (T001–T002) | Quality checks pass on today's code; the loader's `overrides` parameter is renamed |
| Foundational | 5 (T003–T007) | Includes written with `$ref` load and merge correctly; malformed ones exit 4 |
| US1 – new key becomes an override (P1) 🎯 MVP | 6 (T008–T013) | `set agents.coder.temperature 0.3` leaves the shared file byte-identical |
| US2 – existing values (P1) | 2 (T014–T015) | Overridden → override; not overridden → shared file; a merged section set to a mapping → exit 3 |
| US3 – read and audit (P1) | 3 (T016–T018) | `show --sources` names each value's file; converting by hand records nothing |
| US4 – lists (P2) | 2 (T019–T020) | Appends and keys inside list items stay in the file that holds the list |
| Polish | 3 (T021–T023) | README, notes in the earlier specs, quality checks |

**`spec/006-set-in-include/tasks.md` (CR-B): 15 tasks.** It waits for CR-A's T001–T013.

| Phase | Tasks | Independent test |
|---|---|---|
| Setup | 2 | CR-A's prerequisite tasks done and checks pass; the `set` test helpers can pass options |
| Foundational | 3 | The merged tree keeps the shared file's side; the placement value reaches the planner; the CLI flag exists |
| US1 – shared file on purpose (P1) 🎯 MVP | 4 | `set --in-include` changes only the shared file; with or without the flag, other cases give identical files |
| US2 – recorded and validated (P2) | 3 | History records actor and reason; the flag on other commands exits 2 |
| Polish | 3 | README, keep both specs in agreement, quality checks |

**Parallel work:**
- **CR-A:** after the foundational phase, the four story test files (T014, T016, T017, T019) can be written in parallel. T003 and T004 can run together, as can T008 and T010.
- **CR-B:** its tests mostly share one file, so they run in sequence. Only T011 (`test_usage.py`) can run alongside them.

**Suggested MVP:** CR-A phases 1–3, which stop new keys from changing shared files, then CR-B phases 1–3.

Every behaviour is written as a failing test first, as the constitution requires. One existing test asserts the rule CR-A replaces: `test_set_new_key.py::test_new_key_in_an_included_file`. T009 rewrites it.

Next is `/method-command`. Start with `spec/005-include-overrides`, then switch `spec/feature.json` to `spec/006-set-in-include`.

Reply: /method-command
