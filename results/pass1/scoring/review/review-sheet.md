# Review sheet

Fill in `score:` (0 to 4) and `reason:` for every item, then run the review-import stage. Every item needs both.

## Item 1: change_reason, Arm C, step 03

Rubric levels:

- 0: The step's changes carry no reason: commit messages are generic ('update', 'wip', 'fixes') and no spec, change record or decision ties the diff to the request.
- 1: A reason exists only at the coarsest level (one commit or record saying which step or feature); individual changes, and especially changes to existing behaviour, cannot be tied to why they were made.
- 2: Additions are tied to the request through a spec or change record, but modifications and removals of existing requirements, tests or code are unexplained.
- 3: Additions, modifications and removals are tied to the request in a commit message or record; one or two substantive diff hunks are left unexplained.
- 4: Every substantive diff hunk can be tied, through its commit message or a record the commit points at, to the request; every changed or removed requirement or test says what replaced it and why.

### archaeologist: score 4 (ok)

Evidence:

> ["/judge/repo/spec/troupe-config-get-show-01M411XB/spec.md:148 (C-001: the 'get and show' contract section replaces 'show PATH (step 1 and 2)')", "/judge/repo/spec/troupe-config-get-show-01M411XB/spec.md:161 (tests that expect show to refuse a mapping or list move to get)", "/judge/repo/spec/troupe-config-get-show-01M411XB/research.md:80 (step-1 show scalar tests move to test_get.py, renamed test_get_*)", "/judge/repo/spec/troupe-config-get-show-01M411XB/plan.md:8 (get PATH is the old show PATH under a new name; only the refusal message and help line differ)", "/judge/repo/spec/troupe-config-get-show-01M411XB/tasks.md:60 (move show.py logic into get.py, extract scalar_of into values.py)", "/judge/repo/spec/troupe-config-get-show-01M411XB/tasks/WP02-get-command.md:165 (switch value-reading helpers from show to get)", "/judge/repo/spec/troupe-config-get-show-01M411XB/research.md:39 (FR-008 amended for D-10, with the reason)", "/judge/diff.patch:2501-2508 (removed show refusal of a mapping or list, explained by C-001 and FR-005)"]

Notes:

> 

### product owner: score 3 (ok)

Evidence:

> ["/judge/diff.patch:338 (contracts/cli.md: 'This contract replaces the step-1 *show PATH* section. All other step-1/2 sections stay in force')", "/judge/diff.patch:1191 (spec.md C-001: step-3 'get and show' section replaces 'show PATH (step 1 and 2)')", "/judge/diff.patch:666 and :679 (plan.md: get is the old show under a new name; step-1 show tests move to test_get.py and test helpers switch to get)", "/judge/diff.patch:220 and :241 (analysis-report: the old step-1 contract is left unchanged and marked as superseded by C-001)", "/judge/diff.patch:2829-2830 (test_cli_basics usage-error test changed from 'config show' to 'config get'; no record explains this change)", "/judge/diff.patch:21 (acceptance-matrix.json: criteria are still 'TODO: replace with a real acceptance criterion')"]

Notes:

> As product owner, I can see where the request landed: the spec, contract and plan all tie the get/show split to the step-3 brief, and they say which step-1 contract section is replaced and why the step-1 show tests moved to get. Two gaps remain: the change to the existing usage-error test in test_cli_basics has no recorded reason, and the acceptance matrix is still placeholders. There was no git history in the repo, so I judged the records only, not commit messages.

### reviewer: score 4 (ok)

Evidence:

> ["repo/spec/troupe-config-get-show-01M411XB/tasks/WP02-get-command.md:157-168 (T009/T010 explain each test file whose helper switches from show to get, including test_reconcile_first's parametrize change)", "repo/spec/troupe-config-get-show-01M411XB/research.md:80-84 (why the step-1 show scalar tests move to test_get.py and the refusal tests now assert the 'config show' hint)", "repo/spec/troupe-config-get-show-01M411XB/spec.md:148 (C-001: the 'get and show' contract replaces 'show PATH (step 1 and 2)')", "repo/spec/troupe-config-get-show-01M411XB/tasks/WP03-show-command.md:130 (test_show.py is replaced with show tests because the scalar tests now live in test_get.py)", "diff.patch:2449-2514 (show.py rewrite; its docstring cites FR-004..FR-014 and decision DM-01M411YHFR2PMJEJWMHX4KN9C4)", "repo/spec/troupe-config-get-show-01M411XB/plan.md:94-110 (IC-01..IC-05 tie the cli.py, values.py scalar_of and test-migration hunks to FRs)"]

Notes:

> Reviewing hunk by hunk, I found a reason for every one. The new modules map to FRs, the show.py and cli.py changes are explained by C-001 and IC-01, and every modified or replaced test (the show-to-get helper switch, the test_show.py rewrite, the test_cli_basics edits) is listed in the WP02/WP03 tasks, which also say what replaced it and why. The repo has no git history, so I could not check commit messages and relied on the spec records; the acceptance matrix still has many 'TODO' notes, but that does not leave any hunk unexplained.

Your verdict (a whole number 0 to 4, and a reason):

score: 4
reason: Every hunk tied to the request; the test_cli_basics edits are explained in the WP02/WP03 tasks; the TODO acceptance matrix leaves no change unexplained

## Item 2: change_reason, Arm D, step 07

Rubric levels:

- 0: The step's changes carry no reason: commit messages are generic ('update', 'wip', 'fixes') and no spec, change record or decision ties the diff to the request.
- 1: A reason exists only at the coarsest level (one commit or record saying which step or feature); individual changes, and especially changes to existing behaviour, cannot be tied to why they were made.
- 2: Additions are tied to the request through a spec or change record, but modifications and removals of existing requirements, tests or code are unexplained.
- 3: Additions, modifications and removals are tied to the request in a commit message or record; one or two substantive diff hunks are left unexplained.
- 4: Every substantive diff hunk can be tied, through its commit message or a record the commit points at, to the request; every changed or removed requirement or test says what replaced it and why.

### archaeologist: score 2 (ok)

Evidence:

> ["docs/decisions.md:36-66 (decisions 34-42 added in this step explain remote fetching, URL-relative file: includes, schema/format:uri, !literal, set --include and show tagging)", "src/troupe/config.py:503 (diff.patch:500-504: include detection changed from `startswith(\"file:\")` to `include_like(...) and not uri and node.tag != LITERAL`; decision 40 partly explains the new rule but says nothing about the old one)", "src/troupe/writer.py:742 (diff.patch:741-742: `same(...)` replaced by `matches(...)` in assign; only covered indirectly by decision 41)", "src/troupe/config.py:484 (diff.patch:480-484: $ref error and accepted forms changed; README.md:16-19 describes the new behaviour only)", "/judge/repo has no .git directory, so no commit messages are available to blame"]

Notes:

> 

### product owner: score 3 (ok)

Evidence:

> ["docs/decisions.md:100-129 (decisions 34-42 added in this step: remote fetch, file: inside remote, origin reporting, read-only remote, schema validation, format:uri scope, !literal, set --include, show tagging)", "README.md:10-24 (the contract now covers remote includes, the schema and --include/!literal)", "diff.patch:741-747 (assign switched from same() to matches(), and the include refusal message was changed; only indirectly explained by decisions 37/41)", "diff.patch:480-484 ($ref now accepts URLs, which modifies the earlier 'file: include' rule; implied by README:16, with no decision recording the change)", "no .git directory in /judge/repo, so there are no commit messages to inspect"]

Notes:

> 

### reviewer: score 3 (ok)

Evidence:

> ["docs/decisions.md:100-129 (new decisions 34-42 explain remote fetch, URL-relative file: includes, the origin text, refusing remote writes, schema validation, format:uri resolution, !literal semantics, set --include behaviour and show tagging)", "README.md:16-24 (states the new remote-include and schema contract that the added code in config.py, schema.py and cli.py implements)", "diff.patch:243 (cli.py _loaded_texts: watch skipping remote includes is explained by decision 34)", "diff.patch:239 (watch now also tracks troupe.schema.json; no record mentions this)", "diff.patch:480-484 (config.py $ref check widened from file: to any include, with a new error message; covered only implicitly by the README line on remote includes)", "diff.patch:775-776 and 875-876 (literal-block and multiline handling skipped for tagged strings; explained by decision 41, 'written on one line')", "/judge/repo has no .git, so no commit messages are available to judge"]

Notes:

> No commit history is available, but most additions and the changes to existing behaviour (the include check, writer refusals, the no-op comparison now using matches, watch and multiline rendering) can be traced to decisions 34-42 or the README contract. No existing tests or requirements were removed. A couple of hunks have no stated reason, notably watch now tracking the schema file and the reworded $ref error.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Additions explained by decisions 34-42; most modifications trace to them indirectly; about two hunks (watch tracking the schema file, the reworded $ref error) have no stated reason

## Item 3: change_reason, Arm F, step 02

Rubric levels:

- 0: The step's changes carry no reason: commit messages are generic ('update', 'wip', 'fixes') and no spec, change record or decision ties the diff to the request.
- 1: A reason exists only at the coarsest level (one commit or record saying which step or feature); individual changes, and especially changes to existing behaviour, cannot be tied to why they were made.
- 2: Additions are tied to the request through a spec or change record, but modifications and removals of existing requirements, tests or code are unexplained.
- 3: Additions, modifications and removals are tied to the request in a commit message or record; one or two substantive diff hunks are left unexplained.
- 4: Every substantive diff hunk can be tied, through its commit message or a record the commit points at, to the request; every changed or removed requirement or test says what replaced it and why.

### archaeologist: score 4 (ok)

Evidence:

> ["/judge/diff.patch:1568-1580 (tests/e2e/test_history.py: renamed test_hand_edits_are_not_reconciled, with a comment saying step 2 FR-120/FR-121 supersede step 1 D-1, and the old/new expected events changed)", "/judge/diff.patch:43-45 (spec/001 D-1 marked 'Superseded in part by step 2', pointing to spec/002 FR-110–FR-122)", "/judge/diff.patch:975 (tasks.md T018 explains removing type=Path from --theatre: keep the raw string so the watch display matches what was typed, spec D-11; error_line factored out)", "/judge/diff.patch:1153-1164 (open_theatre docstring: old 'importing is not reconciling' replaced, citing FR-120 superseding D-1)", "/judge/diff.patch:1191-1192 (set_value lock comment cites FR-130)", "/judge/diff.patch:276,427 (FR-114 wording adjusted to projection order, reason recorded in research S-1)"]

Notes:

> Blame on three lines: the changed history test, the open_theatre change and the removed type=Path in cli.py. Each leads through a code comment or task to an FR/D/S entry that gives both the old behaviour (step 1 D-1) and why it changed. No git history was available to check the commit messages themselves, but every substantive hunk is covered by in-diff records.

### product owner: score 4 (ok)

Evidence:

> ["/judge/diff.patch:44-45 (spec/001 D-1 is marked 'Superseded in part by step 2' and points to spec/002 FR-110–FR-122)", "/judge/diff.patch:591-594 (spec/002 spec.md section 'What step 2 changes from step 1' names D-1 as superseded and confirms FR-042 and D-2 still hold)", "/judge/diff.patch:565-569 (spec/002 spec.md Input quotes the step 2 request and the contract text word for word)", "/judge/diff.patch:1568-1580 (the renamed test in tests/e2e/test_history.py has a comment saying FR-120/FR-121 supersede D-1)", "/judge/diff.patch:1155-1163, 1191-1192 (the changes to open_theatre and set_value in commands.py cite FR-120, FR-121 and FR-130)", "/judge/diff.patch:1088-1091 (cli.py theatre_display cites D-11)"]

Notes:

> The step 2 request appears word for word in spec/002, and the one earlier requirement it displaces (D-1) is marked superseded in place, with what replaced it and why. The changed test and the modified code hunks cite FR/D IDs. Only small refactors are unexplained (removing `type=Path`, the `error_line` helper), and no commit history was available to check.

### reviewer: score 3 (ok)

Evidence:

> ["/judge/diff.patch:44-45 (spec/001 D-1 is marked superseded and points to spec/002 FR-110 – FR-122)", "/judge/diff.patch:1568-1580 (tests/e2e/test_history.py: the renamed test changes its expected history, and a comment cites step 2 FR-120/FR-121 superseding D-1)", "/judge/diff.patch:975 (tasks.md T018 explains removing type=Path from cli.py and adding the error_line refactor)", "/judge/diff.patch:1191-1192 (set_value lock comment cites FR-130)", "/judge/diff.patch:1263-1264 (src/troupe/config/lock.py: a missing .troupe/ falls back to find_config, which contradicts tasks.md T003 at diff.patch:925, which expects a LoadError naming the lock file; no record explains the change)", "/judge/diff.patch:1369-1375 (run_watch takes a `sync` callable instead of the theatre/open_theatre signature in T016 at diff.patch:973; no record explains the change)", "/judge/repo has no .git, so there are no commit messages to check"]

Notes:

> 

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Well traced overall (D-1 superseded in place, FR/D citations), but two hunks depart from the arm's own plan with no record: the lock's find_config fallback contradicts T003, and run_watch's signature differs from T016

## Item 4: change_reason, Arm F, step 07

Rubric levels:

- 0: The step's changes carry no reason: commit messages are generic ('update', 'wip', 'fixes') and no spec, change record or decision ties the diff to the request.
- 1: A reason exists only at the coarsest level (one commit or record saying which step or feature); individual changes, and especially changes to existing behaviour, cannot be tied to why they were made.
- 2: Additions are tied to the request through a spec or change record, but modifications and removals of existing requirements, tests or code are unexplained.
- 3: Additions, modifications and removals are tied to the request in a commit message or record; one or two substantive diff hunks are left unexplained.
- 4: Every substantive diff hunk can be tied, through its commit message or a record the commit points at, to the request; every changed or removed requirement or test says what replaced it and why.

### archaeologist: score 3 (ok)

Evidence:

> ["/judge/diff.patch:85-98 (spec/001 FR-010 and FR-025 are annotated in place: 'Extended by step 7… see spec/007 FR-600, FR-620' and the !literal-tagging change to set, pointing to FR-640–FR-645)", "/judge/diff.patch:2448-2457 (loader.py removes INCLUDE_PREFIX/include_target; spec/007-remote-includes-schema/tasks.md:61-65 (T001) records the replacement: moved into includes.py as include_ref/REF_KEY)", "/judge/diff.patch:4436-4464 (test_merge.py changes path.name to Path(path).name; explained by research.md:37-43 'SourceFile.path becomes Path | str')", "/judge/diff.patch:2532 (main = main.resolve() added, and self.loaded removed at 2483, with no comment or task naming either change)", "spec/007-remote-includes-schema/checklists/requirements.md:148 (the behaviour change for existing users, plain https:// strings becoming includes, is recorded)"]

Notes:

> 

### product owner: score 3 (ok)

Evidence:

> ["/judge/diff.patch:85-98 (spec/001-config-load-show-set/spec.md FR-010 and FR-025 annotated 'Extended by step 7 … see spec/007 FR-600, FR-620, FR-640–FR-645')", "/judge/diff.patch:4075-4077 (tests/e2e/test_set_includes.py comment explains why existing tests now pass --include and points to test_set_literal.py)", "/judge/diff.patch:148-149 (checklists/requirements.md records the behaviour change for existing https:// strings and decisions D-60–D-70)", "repo/spec/007-remote-includes-schema/spec.md:461 (assumption on existing configurations reinterpreted as remote includes)", "/judge/diff.patch:4433-4464 (tests/unit/test_merge.py Path(...) rewrites carry no stated reason)", "/judge/diff.patch:4534-4535 (tests/unit/test_verify.py fake_plan signature change unexplained)"]

Notes:

> No commit history is available, so all traceability comes from the records. The request lands in spec/007, and the earlier requirements it changes (FR-010, FR-025) carry inline notes pointing to the new FRs. Changed tests in test_set_includes.py say what replaced the old behaviour and why. A few small test edits in test_merge.py and test_verify.py have no stated reason, which keeps this from a 4.

### reviewer: score 4 (ok)

Evidence:

> ["/judge/diff.patch:85-98 (old spec 001 FR-010/FR-025 get notes saying step 7 extends them, pointing to spec 007 FR-600, FR-620 and FR-640–FR-645)", "/judge/diff.patch:4075-4077 (comment in test_set_includes.py explains why the existing tests now pass --include and points to test_set_literal.py)", "repo/spec/007-remote-includes-schema/spec.md:455 (spec records the test_set_includes.py change, research U-13)", "repo/spec/007-remote-includes-schema/tasks.md:144,220,346 (tasks T011 and T029 and the line-220 edit cover the view.py and watch.py hunks)", "repo/spec/007-remote-includes-schema/research.md:37-43 (decision that SourceFile.path becomes Path | str explains the test_merge.py Path(...) edits)", "/judge/diff.patch:3051,3074-3075,3084-3086 (code comments cite research U-6 and decision D-65)"]

Notes:

> Every substantive hunk I checked traces to a step-7 spec FR, decision, research item or task, and changes to existing requirements and tests say what replaced them and why. The only gap is that the small type-follow-through edits in test_merge.py and test_verify.py have no comment of their own; they trace only through the research decision and FR-640, which is enough to approve them.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Old FRs annotated in place and most hunks trace to step-7 records; main.resolve() and the removal of self.loaded (plus a small test_verify signature change) have no stated reason

## Item 5: fit, Arm A, whole arm

Rubric levels:

- 0: The method does not fit: its core workflow cannot be run from inside Claude Code, or it depends on a tracker integration that cannot work in the arm, so the method breaks without it.
- 1: The method runs in Claude Code only with harness adaptations, overrides or disables Claude Code features (settings, memory, hooks) to work, or its tracker cannot be used from the arm at all.
- 2: The method works in Claude Code but through shims or a separate CLI the model must drive from the shell, or its tracker integration is partial (one-way, or needs a server or remote the arm does not have, so that part goes unused).
- 3: The method is native to Claude Code (its own slash commands, skills or plugin, loaded from the arm's config) with one friction point, such as an ordering the model must remember or a tracker step that must be invoked by hand.
- 4: The method is native to Claude Code, loaded from the arm's own config without workarounds, uses Claude Code's features as designed, and its tracking (its own, or the GitHub Issues baseline) works end to end from within the workflow, with no workaround.

### Claude Code power user: score 3 (ok)

Evidence:

> ["/judge/setup/shell/01.log:8-10 (installer writes 33 skill files to .claude/skills/, CLAUDE.md as project memory, and 16 settings templates to spec/settings/; exit 0)", "/judge/setup/checklist.json:39-79 (17 method skills found, nothing missing; CLAUDE.md present; no legacy .claude/commands; no foreign plugins; all model settings are aliases; entry commands present)", "/judge/setup/checklist.json:81-83 (GitHub Issues access works)", "/judge/setup/turns/setup-a1-001.prompt.md:1 (setup ran through the method's own slash skill, /method-command)", "/judge/06/transcript.md:2-4 (gh issue view used from inside the workflow alongside the method's spec.json phase tracking)", "/judge/03/transcript.md:41 (model records the requirements approval in spec.json by hand and tells the user the next commands to run in order)", "/judge/03/transcript.md:100-106,131,155 (model repeatedly cats SKILL.md and the implementer/reviewer templates via Bash and builds /tmp/method/common-context.md to brief subagents)", "/judge/setup/shell/01.log:24 (installer output leaves the {{method_DIR}} placeholder unfilled)"]

Notes:

> The method fits Claude Code natively: project skills load from .claude/skills, CLAUDE.md serves as project memory, it uses aliases rather than model overrides, and no settings or hooks are changed. Its spec.json/tasks.md tracking and GitHub issue reads both work from inside the workflow. The one friction point is that the model must remember the phase order and gates itself (record approvals by hand, invoke the next skill) and re-read the skill templates via Bash to brief subagents, so it is not fully seamless.

### team lead: score 2 (ok)

Evidence:

> ["/judge/setup/checklist.json:38-79 (17 method skills loaded from .claude/skills, project memory present, entry commands found, no legacy commands)", "/judge/setup/manifest.json:2-51 (method is loaded from the arm's own .claude/skills/method-command, spec/settings and CLAUDE.md)", "/judge/setup/checklist.json:81-84 (GitHub Issues access confirmed, but the method has no hook to it)", "/judge/06/transcript.md:2-5 (the only tracker contact: a manual gh issue view / gh api read of issue #2, and the first try came back empty)", "/judge/06/transcript.md:11 (the work is then tracked in spec/steering/roadmap.md and a brief, not in an issue)"]

Notes:

> The method itself fits Claude Code well: its skills load from the arm's own config with no workarounds. The GitHub Issues tracker sits outside the workflow, though. In all seven steps it was only read, once, by hand-driven gh shell commands, and no issue was ever created, updated or closed, so the tracker is a separate one-way chore.

### troupe architect: score 3 (ok)

Evidence:

> ["/judge/setup/shell/01.log:7-14 (installer writes 33 skill files to .claude/skills/, adds CLAUDE.md and spec/settings; detects non-interactive mode and completes with exit 0)", "/judge/setup/checklist.json:38-79 (17 method skills, project memory and entry commands present; no legacy commands; no model overrides)", "/judge/setup/checklist.json:80-85 (github.issues-access ok)", "/judge/06/transcript.md:2-5 (GitHub issue #2 read with ad-hoc gh issue view / gh api calls outside the skills; first call returned empty and needed a retry)", "/judge/06/transcript.md:12 (brief cites troupe-run/repo#2, so the issue was read)", "/judge/03/transcript.md:41 (approval is a human reply recorded into spec.json before the next /method-command phase)", "/judge/06/transcript.md:187-188 (autonomous mode reads approvals from spec.json, then runs a fresh implementer and a review per task)"]

Notes:

> Native Claude Code skills loaded from the arm's own .claude/skills and CLAUDE.md, with no harness overrides and machine-readable artefacts (spec.json, markdown specs), so it suits an agent loop. One friction point: the method has no tracker step, so GitHub Issues was read by hand (one empty result and a retry), and phase gates wait for a human approval in spec.json. For unattended troupe.run use, approvals need to be pre-granted or the --auto path used, and the gh issue read and write steps built into the skills.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Native skills from the arm's own config with no overrides; the tracker is read by hand outside the workflow and phase gates are recorded manually, treated as the friction point

## Item 6: fit, Arm C, whole arm

Rubric levels:

- 0: The method does not fit: its core workflow cannot be run from inside Claude Code, or it depends on a tracker integration that cannot work in the arm, so the method breaks without it.
- 1: The method runs in Claude Code only with harness adaptations, overrides or disables Claude Code features (settings, memory, hooks) to work, or its tracker cannot be used from the arm at all.
- 2: The method works in Claude Code but through shims or a separate CLI the model must drive from the shell, or its tracker integration is partial (one-way, or needs a server or remote the arm does not have, so that part goes unused).
- 3: The method is native to Claude Code (its own slash commands, skills or plugin, loaded from the arm's config) with one friction point, such as an ordering the model must remember or a tracker step that must be invoked by hand.
- 4: The method is native to Claude Code, loaded from the arm's own config without workarounds, uses Claude Code's features as designed, and its tracking (its own, or the GitHub Issues baseline) works end to end from within the workflow, with no workaround.

### Claude Code power user: score 2 (ok)

Evidence:

> ["/judge/setup/manifest.json:36-116 (the method installs as Claude Code skills, agents, settings.json and CLAUDE.md under .claude/, plus mirrored copies in ~/.claude/skills and ~/.claude/commands)", "/judge/setup/checklist.json:63-96 (SessionStart hooks run `method session-start` and `tracker-cli prime`; the tracker's hosted egress is refused, so only the local tracker is used)", "/judge/01/transcript.md:92,106 (entry points are Skill invocations such as method-command and method-implement-review)", "/judge/01/transcript.md:150-155 (the core loop is driven from Bash via the `method agent tasks move-task` CLI; lane approval guards were refused several times before the model fixed them by hand with `git rm --cached --sparse status.json` and commits)", "/judge/01/transcript.md:157,241,433 (the model drives the tracker through `tracker-cli remember/create` in Bash and records home-made prep-lane.sh, align-lane.sh and restore-status.sh scripts as the lane workaround)"]

Notes:

> The method loads natively from .claude (skills, agents, SessionStart hooks), but the actual workflow runs through a separate `method` CLI and `tracker-cli` that the model drives from Bash. Lane status guards also forced hand-written shim scripts in every step (about 100 mentions across the transcripts), and the tracker's hosted service went unused.

### team lead: score 2 (ok)

Evidence:

> ["/judge/setup/checklist.json:63-96 (method session-start and tracker-cli prime SessionStart hooks; tracker binding 'provider: tracker')", "/judge/setup/installed-commands.json:2-71 (native .claude skills/commands loaded from arm config)", "/judge/01/transcript.md:158-159 (model shells out to `method agent action implement` and `tracker-cli list` by hand)", "/judge/03/transcript.md:166-167 (review finding filed via manual `tracker-cli create` Bash call)", "/judge/03/transcript.md:366 (`tracker-cli close` invoked by hand after merge)", "/judge/07/transcript.md:1020-1022 (manual close, then reopen-style notes and unclaim via tracker-cli)"]

Notes:

> The method loads natively as skills and hooks, but the model drives its workflow by calling the separate `method` CLI from the shell. Tracker items are created, claimed and closed by hand with `tracker-cli` Bash calls, not by the method's work-package transitions, so for a team lead the tracker is a separate chore.

### troupe architect: score 2 (ok)

Evidence:

> ["/judge/setup/manifest.json:36-116 (the method ships as Claude Code skills/agents in .claude, plus /home/actor/.claude/commands)", "/judge/setup/checklist.json:81-84 (hosted_service REFUSED by channel_1, so the tracker's hosted/sync side goes unused)", "/judge/setup/checklist.json:93-96 (the tracker is a separate tracker-cli started by a SessionStart hook)", "/judge/01/transcript.md:150-157 (method 3.2.7 lane guards refuse move-task; the model hand-patches status.json with git rm --cached and records the workaround via tracker-cli remember)", "/judge/01/transcript.md:241 and :433 (the model writes its own prep-lane.sh/align-lane.sh/restore-status.sh shims, moving them from /tmp to ~/troupe-orch because /tmp is wiped)", "/judge/03/transcript.md:191 and :277 (every later step drives the `method agent action implement` CLI through those home-made shims with exported env vars and timeout wrappers)"]

Notes:

> Skills and agents load natively from .claude, but the real workflow runs through the separate `method` and `tracker-cli` CLIs from the shell. The model had to build and carry its own lane shims to get past the status.json guards, and the tracker's hosted side is refused. For troupe.run to run this unattended, those guard conflicts need fixing in the method itself (or the shims need to ship with it), and lane prep/align/restore should become built-in deterministic commands instead of ad-hoc scripts the model has to remember.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 7: fit, Arm E, whole arm

Rubric levels:

- 0: The method does not fit: its core workflow cannot be run from inside Claude Code, or it depends on a tracker integration that cannot work in the arm, so the method breaks without it.
- 1: The method runs in Claude Code only with harness adaptations, overrides or disables Claude Code features (settings, memory, hooks) to work, or its tracker cannot be used from the arm at all.
- 2: The method works in Claude Code but through shims or a separate CLI the model must drive from the shell, or its tracker integration is partial (one-way, or needs a server or remote the arm does not have, so that part goes unused).
- 3: The method is native to Claude Code (its own slash commands, skills or plugin, loaded from the arm's config) with one friction point, such as an ordering the model must remember or a tracker step that must be invoked by hand.
- 4: The method is native to Claude Code, loaded from the arm's own config without workarounds, uses Claude Code's features as designed, and its tracking (its own, or the GitHub Issues baseline) works end to end from within the workflow, with no workaround.

### Claude Code power user: score 4 (ok)

Evidence:

> ["/judge/setup/checklist.json:33-35 (control.no-method: found: none), so this is plain Claude Code with no method layered on top", "/judge/setup/checklist.json:21-23 (no-foreign-plugins: installed: none) and :45-47 (0 model settings, all aliases), so no settings, hooks or memory are overridden", "/judge/setup/installed-commands.json:1 ([]) and /judge/setup/setup-turns.json:1 ([]): no shims, no extra CLI and no setup turns were needed", "/judge/setup/checklist.json:51-53 (github.issues-access ok) and /judge/06/transcript.md:2 (gh issue view 2 -R troupe-run/repo run inside the workflow)"]

Notes:

> The arm runs stock Claude Code with nothing installed and nothing overridden, so nothing in it works against the tool. The GitHub Issues baseline tracker was reachable during setup and was used from inside the step workflow without any workaround.

### team lead: score 2 (ok)

Evidence:

> ["/judge/setup/manifest.json:1 (empty manifest: no method was installed)", "/judge/setup/installed-commands.json:1 (no slash commands or skills)", "/judge/setup/checklist.json:33-35 (control.no-method: found none)", "/judge/setup/checklist.json:51-53 (github.issues-access ok: the GitHub Issues baseline is reachable)", "/judge/06/transcript.md:2 (the only tracker contact is a hand-typed `gh issue view 2` from Bash)", "/judge/06/transcript.md:28 ('Issue #2 is fixed and committed... I didn't push or open a PR': the issue is never closed or linked)"]

Notes:

> This arm has no method installed, so nothing Claude Code doesn't already have, and nothing to break it. The GitHub Issues tracker is reached only by the model running the gh CLI by hand from the shell, and only once, to read issue #2 (06/transcript.md:2). In all seven transcripts no step creates, updates or closes an issue, so tracking is a separate chore, not part of the workflow.

### troupe architect: score 3 (ok)

Evidence:

> ["/judge/setup/manifest.json:1 (empty manifest: nothing installed)", "/judge/setup/installed-commands.json:1 (no slash commands or plugins)", "/judge/setup/checklist.json:33-35 (control.no-method: found none)", "/judge/setup/checklist.json:51-53 (github.issues-access ok)", "/judge/setup/setup-turns.json:1 (no interactive setup turns)", "/judge/06/transcript.md:2 (the only tracker interaction: a manual read-only `gh issue view 2`)", "/judge/01/transcript.md:38 (work is recorded only as git commits, with no issue link or close)"]

Notes:

> 

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Stock Claude Code with nothing overridden; the GitHub Issues tracker is only read once by hand and never written, so tracking isn't end to end (consistent with item 5)

## Item 8: fit, Arm F, whole arm

Rubric levels:

- 0: The method does not fit: its core workflow cannot be run from inside Claude Code, or it depends on a tracker integration that cannot work in the arm, so the method breaks without it.
- 1: The method runs in Claude Code only with harness adaptations, overrides or disables Claude Code features (settings, memory, hooks) to work, or its tracker cannot be used from the arm at all.
- 2: The method works in Claude Code but through shims or a separate CLI the model must drive from the shell, or its tracker integration is partial (one-way, or needs a server or remote the arm does not have, so that part goes unused).
- 3: The method is native to Claude Code (its own slash commands, skills or plugin, loaded from the arm's config) with one friction point, such as an ordering the model must remember or a tracker step that must be invoked by hand.
- 4: The method is native to Claude Code, loaded from the arm's own config without workarounds, uses Claude Code's features as designed, and its tracking (its own, or the GitHub Issues baseline) works end to end from within the workflow, with no workaround.

### Claude Code power user: score 3 (ok)

Evidence:

> ["/judge/setup/shell/01.log:1-34 (`method --here --force --integration claude` installs the Claude Code integration and puts skills in .claude/skills)", "/judge/setup/manifest.json:2-14 (13 `.claude/skills/method-command/SKILL.md` files loaded from the arm's own config)", "/judge/setup/shell/02.log:1-18 (`method add bug` adds the bug extension and warns 'Configuration may be required')", "/judge/setup/checklist.json:39-72 (skills, bug skills, entry commands and GitHub Issues access all report ok; no foreign plugins and no model overrides)", "/judge/06/transcript.md:2-17 (issue read by hand with `gh issue view` before the `Skill method-command` call)", "/judge/05/transcript.md:73,206 (model hand-writes spec/feature.json to switch the active feature before running spec/scripts/bash/check-prerequisites.sh)"]

Notes:

> The method installs as native Claude Code skills from .claude/skills and does not override settings, hooks or memory, and its file-based spec/tasks tracking works inside the arm. One friction point remains: the model has to keep the active-feature state by hand (writing spec/feature.json) and fetch GitHub issues itself with gh before calling the bug skills.

### team lead: score 2 (ok)

Evidence:

> ["/judge/setup/installed-commands.json:2-14", "/judge/setup/checklist.json:39-72", "/judge/06/transcript.md:2-5", "/judge/06/transcript.md:68", "/judge/06/transcript.md:85"]

Notes:

> The method is native to Claude Code: 13 skills load from the arm's .claude/skills, and the checklist shows no missing skills or foreign plugins. Its GitHub Issues link only goes one way. Issue #2 was read with ad-hoc `gh issue view` shell calls (06:2-5). The workflow never commented on, linked or closed it ('Nothing was pushed', 06:68). Work was tracked only in local spec/tasks.md files, so updating the tracker is a separate chore.

### troupe architect: score 2 (ok)

Evidence:

> ["/judge/setup/shell/01.log:1-36 (`method --here --force --integration claude` installs the skills into .claude/skills with no interactive prompts; --force skips the confirmation, line 14)", "/judge/setup/checklist.json:38-67 (method.skills, bug-skills and entry-commands all present; 0 model overrides; no foreign plugins)", "/judge/setup/shell/02.log:1-18 (`method add bug` adds the bug extension; it warns 'Configuration may be required')", "/judge/05/transcript.md:9 and :41 (the agent runs mkdir and printf to write spec/feature.json by hand instead of using create-new-feature.sh, because the work is delivered on main with no feature branch)", "/judge/05/transcript.md:14 (the commit was aborted because spec/feature.json is gitignored, so the workflow's state pointer is local and not versioned)", "/judge/06/transcript.md:2-5 (the issue is read from the shell with `gh issue view`; the first call returned nothing and needed retries)", "/judge/06/transcript.md:76 (the fix was committed on main but the issue was never commented on or closed; no transcript has a gh issue comment/close or a Fixes #)"]

Notes:

> The method is native to Claude Code: its skills load from the arm's own .claude config, setup runs non-interactively, and the commands run unattended. But the agent must hand-write the gitignored spec/feature.json pointer every time it starts a new feature, which bypasses the branch-based create-new-feature.sh. GitHub Issues tracking is also one-way: the bug extension reads issues through gh, but nothing ever comments on or closes them. For troupe.run to run this in an agent loop, it would need a non-branch feature-creation command or a versioned feature pointer, and a step in the bug fix/test commands that writes the result back to the issue.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Owner: 2.5, rounded down (sheet takes whole numbers). Friction similar to arms A and E (one-way tracker), but the agent works around the method's own feature script by hand-writing a gitignored spec/feature.json pointer

## Item 9: gates, Arm A, step 01

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:269", "/judge/transcript.md:300", "/judge/transcript.md:303", "/judge/transcript.md:2077"]

Notes:

> gates.md records no gates, but the transcript shows one real checkpoint after the specs and before any code (line 269). It lists seven choices to confirm or overrule, and the owner's answers, including reversal B on multi-file sets, went into the specs and were committed (lines 300-303) before implementation began. The later folded-value fix (line 2077) brought the code back in line with the authoritative contract, so it reversed no owner requirement and needed no extra gate.

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:8", "/judge/transcript.md:82", "/judge/transcript.md:334"]

Notes:

> This greenfield step reversed no requirements, but it split the work into two specs (transcript.md:8) and then moved from requirements to design, tasks and code without a human gate; the agent marked its own requirements approved in spec.json (line 82), and a reviewer subagent, not a human, gave the approval before code was committed (line 334). Nothing was approved after the fact and nothing was superfluous, but the step had no gate at the key point after the spec and before code, where a human decision would have been cheap.

### risk reviewer: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:269", "/judge/transcript.md:275", "/judge/transcript.md:2179"]

Notes:

> gates.md records no gates, but the transcript has a de facto gate in the right place: before any code was written, the specs-done report (transcript:269) lists the choices made where the contract was silent and asks the product owner to confirm or overrule them, and the answers, including reversing the multi-file `set` refusal, went into the specs before implementation (transcript:275). Two costly points had no gate: the specs were auto-approved with the `-y` fast-track before that report, and requirement 10.7 was changed after the final validation returned NO-GO, which the user only learned about in the closing report (transcript:2179), though that change brought the spec back in line with the user's contract.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: A real gate after the specs and before code, with seven choices to confirm; but requirement 10.7 was changed after a NO-GO validation and only reported in the closing summary (it realigned with the contract)

## Item 10: gates, Arm A, step 02

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:3-19", "/judge/gates.md:29-45", "/judge/gates.md:55-75", "/judge/transcript.md:111"]

Notes:

> All three gates came before any code was written: one after requirements, one after design, one after tasks. Each said in a few bullets what was being approved and which choices to confirm, including the open decisions 5.3/5.4/2.6 and the change that replaces config-foundation 6.9 and 7.3, so the reversal was stated openly before the design step. The task gate is the least focused because it mostly summarises the plan, but it is not after the fact and none of the gates is trivial.

### process coach: score 4 (ok)

Evidence:

> ["/judge/gates.md:3-19", "/judge/gates.md:29-45", "/judge/gates.md:55-75", "/judge/transcript.md:111", "/judge/transcript.md:376"]

Notes:

> There are three gates: requirements, design and tasks. Each comes before any step-2 code (transcript:111 says no code was written yet), and each concisely lists the decisions to confirm. That includes the reversal of config-foundation 6.9/7.3, which is flagged openly rather than buried. The later baseline change at task 4.1 was an internal design fix for a defect found in review, not a requirement change, so it reasonably had no gate.

### risk reviewer: score 4 (ok)

Evidence:

> ["/judge/gates.md:3-19 (Gate 5 stops before design; lists the requirement choices left open by the contract (5.3, 5.4, 5.5, 4.3, 2.6); flags the reversal of config-foundation 6.9/7.3 as a separate bullet)", "/judge/gates.md:29-45 (Gate 7 stops before tasks; lists the design choices to confirm: reconcile in open_theatre, the .troupe/ lock, 0.2s polling, signals, changes to step-1 files)", "/judge/gates.md:55-74 (Gate 8 comes after the task plan and before any code; the rewrite of step-1 tests is done in the same change as the new behaviour)", "/judge/transcript.md:376 (implementation review comes after the gates)"]

Notes:

> The costly points are reversing step-1 rules 6.9/7.3 so hand edits are now recorded, the lock and reconcile change to every CLI command, and watch's behaviour where the contract is silent. Each one was put to a gate before design or code, as a short bullet to confirm, and no gate approved work that was already finished.

Your verdict (a whole number 0 to 4, and a reason):

score: 4
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 11: gates, Arm C, step 01

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:3-23", "/judge/gates.md:16-19", "/judge/transcript.md:455", "/judge/transcript.md:470-473"]

Notes:

> The one recorded gate is the plan approval, which came after the spec and before any code. It names the five parts, the order of operations inside `set`, and three choices for the owner to confirm, so it can be judged in about a minute. When an implementer departed from the owner's earlier ruling on folded values, the arm enforced that ruling in review instead of quietly changing the requirement, so no extra gate was needed.

### process coach: score 4 (ok)

Evidence:

> ["/judge/transcript.md:9 (discovery gate before spec.md is written: scope summary plus one open question on hand-edit drift, with a recommended option A/B/C)", "/judge/transcript.md:22 (planning gate on the write-back strategy, asked first because it is the riskiest decision, before any plan or code)", "/judge/transcript.md:26 (history-storage question, then states that the alignment summary comes next)", "/judge/gates.md:3-23 (Engineering Alignment gate before plan.md: a short list of the parts, the order of steps inside `set`, and three implementer choices to confirm)", "/judge/transcript.md:17,44 (status reports state 'No code has been written yet'; no approval was requested after the fact)"]

Notes:

> All four gates come before any code, each where a human answer could still change the spec or plan cheaply, and each names its options and gives a recommendation. The discovery gate at line 9 is long, but its table is easy to scan and it ends with a clear ask (A/B/C plus corrections), so it is still easy to approve.

### risk reviewer: score 4 (ok)

Evidence:

> ["/judge/transcript.md:9 (discovery gate on whether files or the stored projection are the source of truth, asked before spec.md was written)", "/judge/transcript.md:22 (write-back strategy, span-splice vs ruamel round-trip, asked before plan; riskiest decision for NFR-001 byte preservation)", "/judge/transcript.md:26 (history storage location under .troupe/, asked before plan)", "/judge/gates.md:3-23 (Engineering Alignment gate before plan.md and before any code; names three implementer choices to confirm)", "/judge/transcript.md:44 (plan committed, 'No code has been written yet')"]

Notes:

> The costly decisions in this step were the source-of-truth rule for hand edits, byte-exact write-back to the files, and history storage under .troupe/. Each one got a focused A/B/C gate before the spec or plan was written, and a final plan-confirmation gate came before any code. That last gate is concise and lists the choices to confirm, and no gate was trivial or came after the work was done.

Your verdict (a whole number 0 to 4, and a reason):

score: 4
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 12: gates, Arm C, step 03

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1 (no gates recorded at this step, although the transcript shows a real pre-spec question)", "/judge/transcript.md:13 (a pre-spec gate asks one decision question with options A/B/C and a recommendation, lists 7 default choices to confirm, and no code had been written yet)", "/judge/transcript.md:22 (spec handoff reports the answer and 3 small details settled while writing the spec; still before any code)", "/judge/transcript.md:42 (plan handoff shows the FR-008 float change to an already-approved layout choice under its own 'Spec change' heading, before code)", "/judge/transcript.md:56 (tasks handoff asks one clear question, whether to implement all WPs, before implementation starts)", "/judge/transcript.md:179 (D-10 quoting rule decided during review without a gate, but it covers a case the contract leaves open, the PO had delegated such choices per line 33, and it only adds quoting)"]

Notes:

> gates.md records no gates, but the transcript has one real decision gate at line 13. It sits before the spec, it is short, it gives a recommended option, and it lists the default choices to confirm, so the owner's answer could still change the outcome cheaply. Later changes, the FR-008 float rule and the D-10 quoting rule, were within delegated authority. The float change was reported plainly before any code, and the D-10 rule only adds quoting where the contract is silent, so no gate is after the fact or superfluous.

### process coach: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:13", "/judge/transcript.md:56", "/judge/transcript.md:179", "/judge/transcript.md:182", "/judge/transcript.md:241"]

Notes:

> Two gates are well placed, though gates.md:1 records none for this step: the scalar --sources question before the spec was written (line 13, with options and a recommendation), and the go/no-go before implementation (line 56). However, FR-008 was amended mid-implementation, twice (D-10 quoting at line 182, the float rule at line 241), with no gate. The product owner had delegated contract-open choices, so these were defensible, but the user only heard about the changed requirement from status updates and the final report.

### risk reviewer: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:13", "/judge/transcript.md:32", "/judge/transcript.md:42", "/judge/transcript.md:179", "/judge/transcript.md:182", "/judge/transcript.md:367"]

Notes:

> /judge/gates.md:1 records no gates, but the transcript shows the step needed them. Two points were well placed: the ambiguous `show --sources` scalar case was asked before the spec, with choices to confirm (line 13), and implementation was offered before it started (line 56). The problem is that later spec changes went in with no gate. FR-008's float rule was changed during planning (line 32). The D-10 rule changed how `show` quotes strings, replacing the quoting rule the user had already accepted, and was committed and implemented mid-implementation (lines 179-182). The user only heard about D-10 in the final report after the merge to main (line 367).

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Well-placed gates before the spec and before implementation; the D-10 quoting change was made mid-implementation within delegated scope but only reported after the merge (consistent with item 9)

## Item 13: gates, Arm C, step 04

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/transcript.md:11 (discovery gate before the spec: one open contract gap with a recommended option, plus six numbered defaults to confirm, WAITING_FOR_DISCOVERY_INPUT)", "/judge/gates.md:3-28 (spec gate before any code: 'No code has changed yet'; lists the three open choices it settled and three choices it made alone, and asks the owner to say if any should change)", "/judge/gates.md:50-75 (approach gate before the plan is written: 'Proposed approach — please confirm or correct'; 'If this looks right, I'll write the plan')"]

Notes:

> All three gates came before work was finished: discovery before the spec, spec approval before code, and approach approval before the plan. At each one, the owner's answer could still change the outcome cheaply, and each gate listed the specific choices to confirm. The spec gate is a bit wordy (it includes repository-state housekeeping), but its decisions are clearly separated and no changed requirement is hidden in it.

### process coach: score 3 (ok)

Evidence:

> ["/judge/transcript.md:11 (discovery gate: asks one open contract question, WAITING_FOR_DISCOVERY_INPUT, before any spec)", "/judge/gates.md:3-36 (spec gate before code: 'No code has changed yet'; lists its own three choices for confirmation)", "/judge/gates.md:46-75 (plan-approach gate, 'please confirm or correct', before plan artifacts and code)", "/judge/transcript.md:69 (tasks gate asks whether to run implement-review over a long WP table; reply taken as yes at line 72)", "/judge/transcript.md:457 (after-delivery acceptance failure: gives three options with a recommendation, before touching main)"]

Notes:

> All five gates come before the work they approve: discovery, spec, plan, implementation go-ahead, and the acceptance retry. None asks approval after the fact, and the one contract ambiguity was raised before the spec. However, the spec gate and the tasks gate are long and dense (repo state, commit lists, WP tables), so the decisions to confirm are harder to pick out. The tasks gate also partly repeats the plan approval for a medium-sized change.

### risk reviewer: score 4 (ok)

Evidence:

> ["/judge/transcript.md:11", "/judge/gates.md:3-28", "/judge/gates.md:46-75", "/judge/transcript.md:145"]

Notes:

> The costly points in this step were how events recorded before step 4 are reported, `via: null` falling outside the contract, the `TROUPE_ACTOR` rule that exits 2, and old events being upgraded when read without rewriting the database. Each one was raised before the spec (transcript:11), confirmed at the spec gate, and confirmed again at the approach gate before any code was committed. Each gate says concisely what is being approved, the choices to confirm are labelled, and none is trivial or after the fact.

Your verdict (a whole number 0 to 4, and a reason):

score: 4
reason: All gates before the work they approve, each costly choice raised before the spec and confirmed before code; spec and tasks gates are dense but decisions are clearly labelled

## Item 14: gates, Arm D, step 01

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:46", "/judge/transcript.md:51", "/judge/transcript.md:54"]

Notes:

> gates.md records no formal gates, and the build itself needed no approval stop. Its contract-gap choices were reported clearly at transcript.md:46. The one interruption, at transcript.md:51, was a merge/PR/keep menu shown after the work was already committed to main. The agent said itself that options 1 and 2 did not apply, so the answer could not change the outcome; that makes it a superfluous, after-the-fact gate.

### process coach: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:7", "/judge/transcript.md:46", "/judge/transcript.md:51", "/judge/transcript.md:54"]

Notes:

> No gate came before the code: the arm wrote the whole subsystem (transcript lines 7-45) and only listed its many contract-gap choices at line 46, after committing. Its one approval request (line 51) was a routine merge/PR/keep menu for finished work, two of whose three options were a no-op or forbidden, and the arm answered it itself at line 54.

### risk reviewer: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:46", "/judge/transcript.md:51", "/judge/transcript.md:55"]

Notes:

> No requirement was reversed and no data rule was contradicted. The brief asked for autonomous delivery to main under a full contract, so going without a gate is mostly defensible. However, several gap-fill choices that change CLI behaviour (bare `a: b` exits 2, an identical replacement of an included value exits 3, merging collections) were decided alone and only reported after commit 10edbac. The integration-options prompt at line 51 was a trivial, after-the-fact question that the agent then answered itself.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: No gate before code; behaviour-changing contract-gap choices were decided alone and only reported after commit; the only approval request was a routine after-the-fact merge menu it answered itself

## Item 15: gates, Arm D, step 02

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:20", "/judge/transcript.md:21"]

Notes:

> No gates were recorded at this step. The step changed an earlier recorded decision: decisions.md #2, 'importing is not reconciling', was rewritten, and test_import_is_not_reconciling was deleted. The agent made several choices the spec left open (exit 4 at startup, retry on a broken config, event order) and committed straight to main; the owner heard about the change and those choices only in the final summary (transcript:21), when an answer could no longer cheaply change anything. The new spec did ask for the reversal, so this is a missing gate at one key point, not the requirement being reversed on the agent's own initiative.

### process coach: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:20", "/judge/transcript.md:21"]

Notes:

> No gates were recorded. The agent rewrote decision #2 and replaced test_import_is_not_reconciling. It also settled several choices the spec left open: watch's failure behaviour, polling instead of OS file notifications, and the flock design. None of this was brought to a human before the code was written; it was reported only after commit 7708ad1 was already on main. The reversal came from the new spec, so this is not a 0, but every open decision was presented after the fact.

### risk reviewer: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:20", "/judge/transcript.md:21"]

Notes:

> The step had no gates. Reversing 'importing is not reconciling' came from the new spec, so it was an approved change; the agent recorded it and replaced the test. But the step also made several CLI choices the spec left open, and none went to a gate before being committed to main: history never reconciles, watch exits 4 if the config can't load at start, and later load errors are printed once and retried. Those choices were only reported after commit 7708ad1.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: No gates; the spec-requested reversal was recorded, but several behaviour-changing open choices were decided alone and only reported after commit to main (consistent with item 14)

## Item 16: gates, Arm D, step 03

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:12", "/judge/transcript.md:21", "/judge/transcript.md:22"]

Notes:

> No gates were recorded. The step carried out what appears to be the requested change: it added `get` and turned `show` into a YAML/`--sources` printer. It did not reverse a requirement the owner had not already set. Where the spec was silent, the agent filled small gaps itself, recorded them in docs/decisions.md items 16–20 and listed them in the final summary, so the owner could correct any of them cheaply without needing an interruption.

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:12", "/judge/transcript.md:21", "/judge/transcript.md:22"]

Notes:

> The step had no gates, yet it reversed existing behaviour: `show PATH` used to reject collections and now prints them, and the old `show` became `get`, with existing tests switched to call `get` (transcript.md:12-14). It also settled five gaps in the spec without asking (decisions.md items 16–20), so these went to the user only in the final report, after commit 363d949 (transcript.md:21-22). Most of the work was routine enough not to need a gate, but the behaviour reversal and the spec interpretations, especially decision 19, should have been confirmed before the code was written.

### risk reviewer: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:12", "/judge/transcript.md:21", "/judge/transcript.md:22"]

Notes:

> No gate came before the costly CLI changes: the old `show` behaviour moved to a new `get` command, `show` now errors differently on collections, and `--sources` on a scalar now prints YAML instead of the `get` form (lines 12 and 21). Five decisions the spec did not cover (decisions.md items 16–20) were made and committed without approval and only reported afterwards (line 22). Those choices are clearly listed but were never confirmed before the code was written, so one key point lacks a gate.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: The main change was the requested get/show split, but five spec gaps (decisions 16-20, incl. the --sources scalar case another arm escalated) were decided alone and only reported after commit: one key point lacks a gate

## Item 17: gates, Arm D, step 04

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:7", "/judge/transcript.md:20", "/judge/transcript.md:21", "/judge/transcript.md:22"]

Notes:

> This step recorded no gates, and adding lineage as the contract specifies mostly didn't need one. One choice did: the agent wrote, committed (30b372a, transcript lines 20-21) and only then reported `via: null` for legacy set/remove events, a value outside the contract's three allowed `via` values (line 22). The report flags it clearly, so this is a small gap rather than a misplaced or after-the-fact gate, but a short check before writing code would have let the owner decide it cheaply.

### process coach: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:7", "/judge/transcript.md:21", "/judge/transcript.md:22"]

Notes:

> No gates were recorded, but this step needed at least one: the agent made several choices the contract did not cover, including a legacy `via: null` that falls outside the contract's three allowed values (transcript line 22), and it treated an empty `TROUPE_ACTOR` as invalid. It coded and committed all of these with no checkpoint (lines 7–21) and only listed them for review in the final summary after commit 30b372a, which is approval after the fact.

### risk reviewer: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:7", "/judge/transcript.md:9", "/judge/transcript.md:20", "/judge/transcript.md:21", "/judge/transcript.md:22"]

Notes:

> I found three places where a wrong turn would be costly. First, upcasting stored data gives legacy set/remove events `via: null`, which is outside the contract's three `via` values. Second, an invalid `TROUPE_ACTOR` now makes every CLI command exit 2. Third, an empty `TROUPE_ACTOR` counts as invalid, which differs from how `TROUPE_THEATRE` is treated. None of these had a gate: all were implemented and committed as 30b372a, and only raised afterwards in the final summary ("if your tests require one of the three values this is the place to change"). The one partial mitigation is that this after-the-fact disclosure is clear.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: No gates; out-of-contract choices (legacy via: null outside the allowed values, TROUPE_ACTOR handling) were coded and committed, then reported after the fact (consistent with items 14 and 15)

## Item 18: gates, Arm D, step 06

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:27", "/judge/transcript.md:44", "/judge/transcript.md:45"]

Notes:

> There were no gates. Most of the work was a bug fix that the contract largely specified, so going without a gate was mostly fine. But the agent settled real choices the contract left open without asking: how merge keys (`<<`) behave, including a design change mid-implementation (transcript line 27), and reversing the old refusal to set anchored values. You only heard about these after the commit (line 44), in the final summary (line 45), with an offer to undo them, so a short check before writing the code would have been cheaper.

### process coach: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:27", "/judge/transcript.md:44", "/judge/transcript.md:45", "/judge/transcript.md:50"]

Notes:

> No gates were recorded. The fix mostly followed an existing contract, and the one public action (commenting on the issue) was correctly held back for the user to decide (transcript:50). However, the agent changed the `--expand-alias` merge-key behaviour mid-step (transcript:27) and settled other open choices on its own. It committed them (transcript:44) and only then raised them for review, offering to change them afterwards (transcript:45). That after-the-fact surfacing keeps this from a 4.

### risk reviewer: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:27", "/judge/transcript.md:44", "/judge/transcript.md:45"]

Notes:

> Several costly decisions had no gate before them. These were the open merge-key (`<<`) policy, which the agent changed mid-implementation (transcript line 27), resolving merges on read so `get`/`show` output changes, and allowing writes to anchored scalars that were previously refused. All were committed (line 44) and only then shown to the user, with an offer to change them (line 45). gates.md:1 records no gates for this step, so every review came after the work was finished.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Mostly a contract-specified fix and it rightly held back the public issue comment, but it reversed an earlier refusal (anchored writes) and changed the merge-key policy mid-step, disclosing only after commit

## Item 19: gates, Arm D, step 07

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:36", "/judge/transcript.md:33", "/judge/transcript.md:41"]

Notes:

> No gates were recorded, and nothing in this step needed one: it adds remote includes and a schema without reversing an earlier requirement, and the agent recorded its gap-filling choices as decisions 34–42 and listed them in the summary (transcript:33, :36). The case for a gate is the jsonschema dependency and the decision not to follow $ref in the schema, both made without asking, but neither is a contradicted requirement, so 'no gate needed, none held' applies.

### process coach: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:10", "/judge/transcript.md:35", "/judge/transcript.md:36", "/judge/transcript.md:41"]

Notes:

> No gates were recorded for this high-risk step. The agent added the jsonschema dependency (transcript:9) and wrote the code without asking for approval first. It then committed to main (transcript:35) and only afterwards reported nine contract gaps it had settled on its own as decisions 34-42 (transcript:36), so the reviewer saw these choices only after the work was finished.

### risk reviewer: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:18", "/judge/transcript.md:19", "/judge/transcript.md:33", "/judge/transcript.md:35", "/judge/transcript.md:36"]

Notes:

> Several decisions were costly to get wrong, and none had a gate before it: adding the jsonschema dependency (line 9), changing `show` output to tag strings `!literal` (line 18), a new default for `set` plus a `--include` flag (line 19), and decisions 34–42 on behaviour the contract left open (line 33). These were all reported only after the commit (lines 35–36), and gates.md records no gates, so no human could weigh in while the choices were still cheap to change; it stops short of 0 because these choices fill gaps in the contract rather than reverse a stated requirement.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: High-risk step with no gates: new jsonschema dependency, show output change, a new set default and nine contract-gap decisions were all committed before being reported

## Item 20: gates, Arm E, step 01

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:39", "/judge/transcript.md:2-38"]

Notes:

> No gates were recorded. This was the first build of the config subsystem, and the transcript shows no requirement being changed or reversed, so it needed no gate. The judgement calls where the contract left room (e.g. show reads files, not history; hand edits are not reconciled into history) were made within that room and clearly listed in the final report (transcript.md:39). An owner might still have liked a say on the history choice before code was written.

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:7", "/judge/transcript.md:38", "/judge/transcript.md:39"]

Notes:

> This step had no gates (gates.md:1). The agent went straight from exploring the environment to writing code (transcript:7) and committed (transcript:38) before reporting five interpretive choices under 'Calls I made where the contract left room' (transcript:39). None of them reverses a requirement, but in a large greenfield build at least one, such as `show` reading files rather than history, needed a review before the code was written, when changing it was still cheap.

### risk reviewer: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:38", "/judge/transcript.md:39"]

Notes:

> No gate was recorded, even though the arm settled open data rules on its own: hand edits are never reconciled into the event history, and `set` merges collections entry by entry instead of replacing them (store.py at transcript:16, summary at transcript:39). These choices were only disclosed after the commit (transcript:38), so a costly point where the contract left room had no gate before it. Nothing in the request was reversed, which keeps the score above 1.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: Greenfield build with no gates; behaviour-shaping open choices (show reads files, hand edits never reconciled, set merges collections) were decided alone and reported only after commit (consistent with items 14 and 15)

## Item 21: gates, Arm E, step 04

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:17", "/judge/transcript.md:19", "/judge/transcript.md:22", "/judge/transcript.md:26"]

Notes:

> No gates were recorded, and most of this lineage step was ordinary implementation that did not need one. But the agent knowingly broke the contract for legacy events (via: null, change ids that are not UUIDs) and narrowed the TROUPE_ACTOR check to `set` only, committing both before asking; the 'Decision for you' came after the fact and led to a rework commit (transcript:26).

### process coach: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:17", "/judge/transcript.md:21", "/judge/transcript.md:22", "/judge/transcript.md:26"]

Notes:

> No gate was recorded (gates.md:1). The arm chose to break the contract for legacy events (`via: null` is not an allowed value, and old change ids are not UUIDs), then committed c3397d4. Only after that did it disclose these deviations and ask its one 'Decision for you' about the TROUPE_ACTOR scope (transcript:22). The approval point came after the code, and the actual requirement deviations never got a gate; the one question asked could still change the outcome cheaply, which led to b88f379 (transcript:26).

### risk reviewer: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:17-19", "/judge/transcript.md:21", "/judge/transcript.md:22", "/judge/transcript.md:26-28"]

Notes:

> I found two costly turns: the agent broke the data contract for legacy events (`via: null` and non-UUID change ids, transcript 17-21), and it chose to have only `set` check `TROUPE_ACTOR`, which changes CLI behaviour. No gate came before either one (gates.md: none recorded). Both were committed first and only then raised as a 'Decision for you' (transcript 22), so the user's choice led to rework (002, transcript 26-28) when one question before coding would have settled it cheaply.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: Knowingly broke the data contract (via: null, non-UUID change ids) and narrowed the TROUPE_ACTOR check, committed both, then asked one question after the fact that caused a rework commit

## Item 22: gates, Arm E, step 05

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:24", "/judge/transcript.md:27", "/judge/transcript.md:32", "/judge/transcript.md:35"]

Notes:

> No gates were recorded, but CR-A reverses the step 1 rule: new keys under an include now become overrides instead of going into the included file. That change, and its choice of the nearest include for nested includes, was implemented and committed before anyone approved it (transcript.md:24). The owner was asked about the --in-include check only after commit 3f073d6, and the agent then settled it alone in DECISIONS.md (transcript.md:35), so the owner's answer could no longer change anything cheaply.

### process coach: score 0 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:23", "/judge/transcript.md:24", "/judge/transcript.md:32", "/judge/transcript.md:35"]

Notes:

> No gates were recorded (gates.md:1). CR-A reverses the step 1 rule so that new keys become overrides, and it was implemented and committed with no gate (transcript:23), along with interpretation choices such as where nested-include overrides go. The only decision prompts ('Choices you may want to check' at transcript:24 and 'Decision for you' at transcript:32) came after the code was committed, and in arm-a1-003 the agent settled the open question itself instead of waiting for a human answer (transcript:35).

### risk reviewer: score 0 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:11-23", "/judge/transcript.md:24", "/judge/transcript.md:32", "/judge/transcript.md:35-40"]

Notes:

> Three costly points went through with no gate: CR-A reversed the step 1 write-back rule so new keys become overrides and shared files are rewritten into mapping form, CR-B added a new CLI flag, and the --in-include refusal is a data-safety rule. All three were committed first, and the open choices (nested-include target, skipping the disturb check) were raised only afterwards; the agent then settled the second one itself in DECISIONS.md.

Your verdict (a whole number 0 to 4, and a reason):

score: 0
reason: A step-1 rule reversal, a new flag and a data-safety choice were committed with no gate; every prompt came after the code, and the agent then settled its own open question in DECISIONS.md without waiting for an answer

## Item 23: gates, Arm E, step 07

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:30", "/judge/transcript.md:10", "/judge/transcript.md:29"]

Notes:

> No gates were recorded. The step reversed earlier behaviour: `set x file:foo.yaml` now writes `!literal` instead of creating an include, and `jsonschema` was added as a dependency. The owner only heard about either after the commit, in the final summary (transcript:30), not at a gate before the code was written. The rest of the work was routine and needed no gate, so only this one key point is missing.

### process coach: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9-11", "/judge/transcript.md:28-30"]

Notes:

> This was a high-risk step with no gate at all: it added the `jsonschema` dependency without asking, made `set file:...` write `!literal` instead of an include (a breaking change), and decided several points the spec left open. All of this was coded, committed as 571b7b5, and only then reported in the final summary, so the human only learned of these decisions after they were already made.

### risk reviewer: score 0 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:10", "/judge/transcript.md:22", "/judge/transcript.md:29", "/judge/transcript.md:30"]

Notes:

> I found several costly decision points: adding the jsonschema dependency (transcript line 10), adding a new `--include` flag and changing `set x file:foo.yaml` so it writes a literal instead of creating an include (lines 22 and 30), and choices the spec left open, such as making `file:` includes inside remote documents resolve on the server (line 29). gates.md:1 shows no gate before any of these, so this existing CLI behaviour was reversed with no gate, and the user only learned of these changes in the summary after the commit.

Your verdict (a whole number 0 to 4, and a reason):

score: 1
reason: High-risk step with no gates: new dependency, new --include flag, set file: now writing !literal (changing existing behaviour) and open choices all committed before being reported (consistent with item 19)

## Item 24: gates, Arm F, step 01

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:26", "/judge/transcript.md:141"]

Notes:

> No gates were recorded. This step built the contract-specified behaviour for the first time and never changed or reversed a requirement, so no gate was needed. The open-point choices (D-1..D-9, B-3..B-5) were stated briefly at the spec and plan hand-offs, and the one unrequested addition, `--theatre` before the subcommand, was removed to match the contract rather than kept as a new requirement (transcript.md:141).

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:26", "/judge/transcript.md:131", "/judge/transcript.md:141", "/judge/transcript.md:152"]

Notes:

> The spec and plan handoffs (transcript lines 9 and 26) work as gates at sensible points: they come before any code and name the choices to confirm (D-1, D-2, D-5, D-6, B-3–B-5, R-3), although gates.md records no formal gate. The weak spot is a requirement change with no prior approval: `--theatre` before the subcommand was added in code and only raised for review afterwards (line 131). It was then removed by the agent's own decision with no gate (lines 141 and 152), and choices B-13–B-15 were likewise reported only after implementation.

### risk reviewer: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:26", "/judge/transcript.md:130", "/judge/transcript.md:131", "/judge/transcript.md:141", "/judge/transcript.md:158"]

Notes:

> gates.md records no formal gates. Still, the stops after the spec (transcript:9, D-1/D-2/D-5/D-6 flagged for review) and after the plan (transcript:26, B-3/B-4/B-5/R-3 flagged) came before any code, named the choices to confirm and acted as well-placed checkpoints. At the riskiest CLI point there was no gate either way: `--theatre` before the subcommand was added during implementation (transcript:130) and flagged only afterwards (transcript:131). The agent then removed it by its own decision without asking (transcript:141). B-13 to B-15 and B-16 to B-18 were also decided and implemented before being reported.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Well-placed spec and plan gates before code, but --theatre before the subcommand was added, flagged afterwards and then removed by the agent alone; B-13 to B-18 reported only after implementation

## Item 25: gates, Arm F, step 02

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:8", "/judge/transcript.md:9", "/judge/transcript.md:11", "/judge/transcript.md:29"]

Notes:

> No gates were recorded, and none was needed: superseding step 1's D-1 was required by the owner's 'Sync with files' contract text (transcript.md:8), not chosen by the agent, and the open points (D-10–D-17) and the FR-114 rewording were conservative and reported at the end of each phase, before any code was written (transcript.md:11, 29). As the owner, I was never interrupted for anything not worth my time, and nothing that needed my decision went ahead without one.

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:11", "/judge/transcript.md:21-22", "/judge/transcript.md:29", "/judge/transcript.md:67", "/judge/transcript.md:100"]

Notes:

> 

### risk reviewer: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:11", "/judge/transcript.md:29", "/judge/transcript.md:67", "/judge/transcript.md:95"]

Notes:

> Three points carried real risk: superseding step 1's D-1 'hand edits are not recorded' rule (transcript:11, then a step 1 test rewritten at :67 and the step 1 spec edited at :95), eight open contract points the agent settled on its own (D-10 to D-17), and the agent's own rewording of FR-114 at the plan stage (:29). gates.md records no gate at all, so none of these was put to a human for approval. The spec and plan turns did end before any code was written and disclosed these choices, which gave informal review points, but neither asked for approval. The D-1 reversal came from the product owner's contract, which softens the lapse but does not supply a gate.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: The reversal was contract-required; open choices and the FR-114 rewording were disclosed at the end of the spec and plan phases before any code, though as disclosures rather than explicit approval requests

## Item 26: gates, Arm F, step 03

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 0 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:9", "/judge/transcript.md:12", "/judge/transcript.md:21", "/judge/transcript.md:29", "/judge/transcript.md:77"]

Notes:

> Step 3 replaced step 1's FR-015 (`show PATH` moved to `get`), and the agent revised its own committed decision D-22 (symlink resolution) during planning, yet gates.md records no gate at all; D-22 was only reported after the fact and D-23/D-24 were flagged only in a closing summary. The run went from spec to implementation and into earlier spec docs with no point where the owner was asked to approve the open decisions or the reversal.

### process coach: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:12", "/judge/transcript.md:21", "/judge/transcript.md:29", "/judge/transcript.md:111"]

Notes:

> No formal gate is recorded (gates.md:1), but each phase handoff stops before code is written, and those stops are well placed. The spec handoff (line 12) lists decisions D-20 to D-26 briefly and asks the user to confirm D-23 and D-24, and the user had requested the show→get change. The weak point: during planning the agent reversed its own spec decision D-22 (line 21) and only reported it in the plan summary (line 29). That was still before any code, but the user was not asked to approve the reversal first.

### risk reviewer: score 3 (ok)

Evidence:

> ["/judge/gates.md:1 (no formal gates recorded)", "/judge/transcript.md:12 (the step stopped after the spec and before any code, listed the open decisions D-20 to D-26 and asked the user to confirm D-23 and D-24)", "/judge/transcript.md:21 (D-22 was rewritten during planning, changing how the source path is computed: symbolic links are now followed)", "/judge/transcript.md:29 (the D-22 change is reported as 'One spec change during planning' in a long plan summary, without asking for approval, though still before code)", "/judge/transcript.md:111 (the U+2028 case is handed to the user as a requirement decision instead of being changed silently)"]

Notes:

> The costly risks were the user-requested reversal of `show`, the --sources path rule and the edge cases the contract left open. The work stopped after the spec and after the plan, before any code, and stated the choices to confirm, so the stops came where a decision could still change the outcome. However, the D-22 revision changed a spec decision after the spec stop and appeared mid-way through a long plan summary without an explicit request for approval.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Well-placed stops before code that explicitly asked to confirm D-23/D-24; the agent's revision of its own D-22 was buried in a long plan summary without an approval request

## Item 27: gates, Arm F, step 06

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 4 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:15", "/judge/transcript.md:68", "/judge/transcript.md:76"]

Notes:

> No gates were recorded, and this step needed none. The request said the work was done once the fix was committed on main (transcript:16), and the pasted Aliases contract set the required behaviour, which matched the issue's own expectation, so no requirement was changed or reversed. The choices the contract left open, such as flow-collection aliases and replacing the alias itself, were small and were reported for the owner to decide (transcript:68, 76), not silently settled behind a gate.

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:68", "/judge/transcript.md:76", "/judge/transcript.md:85"]

Notes:

> No gates were recorded. The user said 'handle it' and that the job was done once the fix was committed on main, which covers implementing the pasted Aliases contract, so the agent moved from assessment to fix without stopping (transcript:16). But the contract left some behaviour open: whether to allow replacing an alias itself, refusing --expand-alias inside flow collections, and comment placement. The agent decided these itself and only surfaced them after committing 8ec062d (transcript:68, 76). It also never wrote a step-6 spec (transcript:85), so one key decision point had no gate before code was written.

### risk reviewer: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:16", "/judge/transcript.md:68", "/judge/transcript.md:76"]

Notes:

> The user's pasted contract settled the main risk points: the exit-3 refusal through an alias, the --expand-alias flag and the merge-key rule. The request also said to go through to a commit on main, so going ahead without a gate there was reasonable. One costly behaviour was never put to a gate, though: whether replacing the alias itself (e.g. `set coder.settings '{a: 1}'`) is allowed. The agent logged it as an open question and still implemented its own answer, along with the flow-collection refusal. The user only heard about these after the commit (transcript:68, 76), when the decision was no longer cheap to change.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Autonomous fix as requested, contract-settled main risks; but open behaviour (replacing an alias itself, flow-collection refusal) was decided alone, even one logged as open, and surfaced only after commit (consistent with item 18)

## Item 28: gates, Arm F, step 07

Rubric levels:

- 0: Requirements were changed or reversed with no gate at all, or every gate asked approval for work already finished, or gates were so frequent or unfocused that the reviewer could not tell what was being approved.
- 1: Gates are mostly misplaced: approval is asked only after the code is written, or for routine matters, with at most one gate at a point where the decision could still change the outcome.
- 2: Most gates fall at sensible points, but one key point lacks one (e.g. a contradicting change implemented before its changed requirement was approved) or one gate is superfluous or after the fact.
- 3: Gates fall at the points where the decision still mattered and none is superfluous, but one gate is hard to approve: too long, missing the decisions to confirm, or burying a changed requirement.
- 4: Each gate falls where a human decision can still change the outcome cheaply (e.g. after the spec or plan, before code; before a requirement is reversed), states concisely what is to be approved and which choices to confirm, and none is trivial or after the fact. A step that needed no gate and had none also scores 4.

### owner at the gate: score 3 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:13", "/judge/transcript.md:34", "/judge/transcript.md:237", "/judge/transcript.md:238"]

Notes:

> 

### process coach: score 2 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:13", "/judge/transcript.md:34", "/judge/transcript.md:179", "/judge/transcript.md:186", "/judge/transcript.md:237"]

Notes:

> The stops after the spec and the plan come before any code and list the decisions to confirm (D-60 to D-69, the main design choices), but gates.md records no formal gate. The step 1 `set` reversal (`file:` values now written `!literal`, five step 1 tests changed) was not raised at the spec stop: it was coded first, reported only at line 186, and SC-606 was corrected only afterwards (line 237).

### risk reviewer: score 1 (ok)

Evidence:

> ["/judge/gates.md:1", "/judge/transcript.md:13", "/judge/transcript.md:12", "/judge/transcript.md:178-186"]

Notes:

> I found three costly risk points. First, plain https:// and http:// values are now fetched as includes, which can break existing configurations. Second, the agent chose the open decisions D-60 to D-70 itself rather than asking (transcript:12, 'decided rather than asked'). Third, `set` now writes `!literal` by default, which reversed step 1 behaviour and meant rewriting five step 1 tests. No gate is recorded (gates.md:1). The spec turn's 'Decisions you should check' list (transcript:13) worked as the only informal checkpoint before code, but it did not flag the reversal of step 1's `set` behaviour, which was disclosed only after implementation (transcript:186).

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Spec and plan stops before code listed the decisions to check, but the reversal of step 1's set behaviour (file: written as !literal, five tests rewritten) was coded before it was raised

## Item 29: hand_edit, Arm F, step 02

Rubric levels:

- 0: No sign the arm noticed the teammate's commit: the transcript never inspects it, and no spec, test or doc mentions TROUPE_THEATRE; or the step's work removed or broke the env default without any record that it existed.
- 1: The transcript shows the arm read the teammate's commit or the TROUPE_THEATRE code, but nothing was recorded: spec, tests and docs still describe --theatre as defaulting to the current directory only.
- 2: The env default is reconciled in one place only: a requirement or decision note mentions it but no test covers it, or a test covers it but the spec still does not describe it.
- 3: The spec states the env default (set and non-empty: default theatre; explicit --theatre wins) and a test covers it, but nothing records that it arrived outside the workflow, or the README or CLI help still omit it.
- 4: The arm named the commit as drift from outside its workflow (transcript, gate message or record), and spec, tests and docs now all describe the env default and its precedence; or it recorded a reasoned decision to change or remove it and surfaced that decision at a gate.

### drift detective: score 3 (ok)

Evidence:

> ["/judge/transcript.md:5 (git show 83f5964 --stat; grep -n \"TROUPE_THEATRE\")", "/judge/repo/spec/002-config-file-sync/spec.md:253", "/judge/repo/spec/002-config-file-sync/contracts/cli.md:12", "/judge/repo/tests/e2e/test_usage.py:59", "/judge/repo/README.md:9-12"]

Notes:

> At transcript line 5 the arm inspected the teammate's commit 83f5964 and searched for TROUPE_THEATRE. Its spec (D-11), CLI contract and e2e tests now cover the env default and the rule that an explicit --theatre wins, but it never called the commit drift from outside its workflow (the summary at transcript line 11 doesn't mention it), and the README still omits TROUPE_THEATRE.

### spec custodian: score 3 (ok)

Evidence:

> ["repo/src/troupe/cli.py:27", "repo/src/troupe/cli.py:64", "repo/spec/002-config-file-sync/contracts/cli.md:12", "repo/spec/002-config-file-sync/spec.md:252-254", "repo/tests/e2e/test_usage.py:56-65", "repo/README.md:9-12"]

Notes:

> The spec and the CLI contract say `--theatre` defaults to `$TROUPE_THEATRE`, then to the current directory, and the CLI help says the same. The e2e test covers the env default, the explicit flag winning and an empty value falling back. But README.md still lists `[--theatre DIR]` without the variable, and no spec or task records that the env default came from outside the workflow.

### teammate: score 3 (ok)

Evidence:

> ["transcript.md:5 (runs `git show 83f5964 --stat` and greps TROUPE_THEATRE)", "repo/spec/002-config-file-sync/spec.md:253", "repo/spec/002-config-file-sync/contracts/cli.md:12", "repo/spec/002-config-file-sync/contracts/cli.md:22", "repo/tests/e2e/test_watch_lifecycle.py:102", "repo/src/troupe/cli.py:43", "repo/README.md:9-12 (lists --theatre DIR with no mention of $TROUPE_THEATRE)", "transcript.md:11 (step summary never mentions the teammate commit)"]

Notes:

> 

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Inspected the teammate commit and folded TROUPE_THEATRE into spec, contract, help and e2e tests, but never named it as drift from outside the workflow; README still omits it

## Item 30: process, Arm A, step 06

Rubric levels:

- 0: No significant decision at this step is recorded with a reason anywhere durable (repo files, commits, gate messages): choices are visible only in the code, including a fallback or 'your choice' answer that explicitly asked for the decision to be recorded; this includes a step whose only significant decision is a fallback assumption left unrecorded.
- 1: Most significant decisions are unrecorded; the few with a reason have it in the transcript only, and an assumption made after a fallback or 'your choice' answer is not recorded anywhere durable.
- 2: About half the significant decisions are recorded with a reason; the rest are visible only in code or transcript; or every decision is recorded but an assumption made after a fallback or 'your choice' answer is stated only in the transcript; or every decision is recorded with a reason only in commit messages or gate messages, none in the repo's docs.
- 3: Every significant decision is recorded with a reason, including every fallback or 'your choice' assumption; the options considered are missing for one or two, or one decision lives only in a gate message or commit rather than in the repo's docs.
- 4: Every significant decision, including every fallback or 'your choice' assumption, is recorded in the repo (decision record, spec, plan or design note) with the real options considered, the one chosen and a reason specific to this project.

### assumption auditor: score 3 (ok)

Evidence:

> ["/judge/repo/spec/spec/config-aliases/requirements.md:246-283", "/judge/repo/spec/spec/config-aliases/research.md:233-261", "/judge/repo/spec/spec/config-aliases/research.md:105-110", "/judge/repo/spec/spec/config-aliases/research.md:264-265", "/judge/gates.md:29", "/judge/gates.md:61"]

Notes:

> All 17 out-of-contract choices are written down in the repo with reasons specific to this project, in requirements.md and research.md. That includes the change from the brief's merge-key default, flow-collection aliases, key lines that already have a comment, and the design-level refusal of copies that contain `<<`. But the real alternatives are missing for about half of them, for example choices 3 (Why only), 5, 7, 9, 10, 11, 14 and 16, so the step falls short of 4 even though nothing is left unrecorded.

### devil's advocate: score 3 (ok)

Evidence:

> ["/judge/repo/spec/spec/config-aliases/requirements.md:246-293", "/judge/repo/spec/spec/config-aliases/research.md:114-130", "/judge/repo/spec/spec/config-aliases/research.md:190-206", "/judge/repo/spec/spec/config-aliases/research.md:233-261", "/judge/repo/spec/spec/config-aliases/research.md:132-141", "/judge/gates.md:11"]

Notes:

> 

### successor: score 3 (ok)

Evidence:

> ["repo/spec/spec/config-aliases/requirements.md:246-293", "repo/spec/spec/config-aliases/research.md:233-261", "repo/spec/spec/config-aliases/research.md:103-110", "repo/spec/spec/config-aliases/research.md:114-130", "repo/spec/spec/config-aliases/research.md:177-188", "repo/spec/spec/config-aliases/research.md:227-231", "repo/spec/spec/config-aliases/research.md:300-302", "/judge/gates.md:11"]

Notes:

> As a successor, I could find every decision the contract left open in the repo, each with a project-specific reason: all 17 choices, the departure from the brief on merge keys, 8 design decisions, and the implementation notes for tasks 3.3 and 3.5. Alternatives are recorded for choices 1, 2, 3, 4 and 6 and for design decisions 1, 3 and 6, plus an architecture table. They are missing for several others: choices 7, 9, 13, 14, 15 and 16, and design decisions 2, 4 and 5. For those I could not tell what else was considered, so the record falls short of level 4.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 31: process, Arm C, step 04

Rubric levels:

- 0: No significant decision at this step is recorded with a reason anywhere durable (repo files, commits, gate messages): choices are visible only in the code, including a fallback or 'your choice' answer that explicitly asked for the decision to be recorded; this includes a step whose only significant decision is a fallback assumption left unrecorded.
- 1: Most significant decisions are unrecorded; the few with a reason have it in the transcript only, and an assumption made after a fallback or 'your choice' answer is not recorded anywhere durable.
- 2: About half the significant decisions are recorded with a reason; the rest are visible only in code or transcript; or every decision is recorded but an assumption made after a fallback or 'your choice' answer is stated only in the transcript; or every decision is recorded with a reason only in commit messages or gate messages, none in the repo's docs.
- 3: Every significant decision is recorded with a reason, including every fallback or 'your choice' assumption; the options considered are missing for one or two, or one decision lives only in a gate message or commit rather than in the repo's docs.
- 4: Every significant decision, including every fallback or 'your choice' assumption, is recorded in the repo (decision record, spec, plan or design note) with the real options considered, the one chosen and a reason specific to this project.

### assumption auditor: score 3 (ok)

Evidence:

> ["repo/spec/troupe-config-lineage-01M436R0/spec.md:28-32", "repo/spec/troupe-config-lineage-01M436R0/research.md:91-99", "repo/spec/troupe-config-lineage-01M436R0/decisions/DM-01M436TPQDWVSZQYFD6D5343DC.md:17-27", "repo/spec/troupe-config-lineage-01M436R0/research.md:5-80", "transcript.md:460-463"]

Notes:

> Every out-of-contract choice is recorded in the repo with a reason specific to this project. That covers pre-lineage events, when TROUPE_ACTOR is checked and what happens when the login name is unavailable (spec.md DMs). The post-merge 'safest assumption' fallback is also recorded, with its rejected alternatives (research.md D-11). Implementation decisions D-1 to D-9 list their alternatives. However, the decision on when TROUPE_ACTOR is checked has no options listed ('Options: _(none)_'), and the login-name decision mentions only one rejected alternative. That fits level 3, not 4.

### devil's advocate: score 3 (ok)

Evidence:

> ["repo/spec/troupe-config-lineage-01M436R0/spec.md:31-32", "repo/spec/troupe-config-lineage-01M436R0/decisions/DM-01M436TPQDWVSZQYFD6D5343DC.md:17-19", "repo/spec/troupe-config-lineage-01M436R0/decisions/DM-01M436RBNQT22F9AM54QER2FT9.md:17-21", "repo/spec/troupe-config-lineage-01M436R0/research.md:5-80", "repo/spec/troupe-config-lineage-01M436R0/research.md:91-99", "repo/spec/troupe-config-lineage-01M436R0/spec.md:116-121", "gates.md:5-28"]

Notes:

> Every significant decision is recorded in the repo with a reason tied to this project. That includes the out-of-contract choices, the PO's 'safest assumption' fallback (research D-11) and the edge cases the agent chose on its own. Most research entries weigh real alternatives, such as a ChangeRecorded event, a separate store, ULIDs and os.getlogin. However, the DMs for when TROUPE_ACTOR is checked and for a missing login name list no options. The edge-case choices (`--reason ""`, splitting the id at the first colon) also have no alternatives weighed, so the record falls short of 4.

### successor: score 3 (ok)

Evidence:

> ["/judge/repo/spec/troupe-config-lineage-01M436R0/research.md:5-80 (D-1 to D-9: each records the decision, the reason and the rejected alternatives, e.g. upcasting vs. row migration, UUID vs. stored sequence or ULID, getpass vs. os.getlogin)", "/judge/repo/spec/troupe-config-lineage-01M436R0/research.md:82-108 (D-10 to D-12: the --lenient acceptance, the manual integration after the merge failure, and the 'make the safest assumption' fallback, each with a reason and rejected options)", "/judge/repo/spec/troupe-config-lineage-01M436R0/decisions/DM-01M436RBNQT22F9AM54QER2FT9.md:17-25 (pre-lineage events: options listed, choice made, reason given)", "/judge/repo/spec/troupe-config-lineage-01M436R0/decisions/DM-01M436TPQDWVSZQYFD6D5343DC.md:17-23 (TROUPE_ACTOR check order: Options '(none)', reason given)", "/judge/repo/spec/troupe-config-lineage-01M436R0/decisions/DM-01M436TX68S2MGE4DN9AM02KTJ.md:17-23 (login name not found: Options '(none)', reason given)", "/judge/repo/spec/troupe-config-lineage-01M436R0/spec.md:116-121 (--reason \"\" and the first-colon id rule recorded as edge cases with a short reason)", "/judge/gates.md:25-28 (the three choices the arm made alone, later written into the spec)"]

Notes:

> Every significant choice the contract left open is recorded in the repo with a project-specific reason, including the out-of-contract and 'safest assumption' choices; I had to infer none of them from the code alone. It falls short of 4 because the options considered are missing for the TROUPE_ACTOR check-order and login-name-not-found decisions (both DMs list Options '(none)'), and for the edge-case choices (D-5, empty --reason).

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 32: process, Arm D, step 01

Rubric levels:

- 0: No significant decision at this step is recorded with a reason anywhere durable (repo files, commits, gate messages): choices are visible only in the code, including a fallback or 'your choice' answer that explicitly asked for the decision to be recorded; this includes a step whose only significant decision is a fallback assumption left unrecorded.
- 1: Most significant decisions are unrecorded; the few with a reason have it in the transcript only, and an assumption made after a fallback or 'your choice' answer is not recorded anywhere durable.
- 2: About half the significant decisions are recorded with a reason; the rest are visible only in code or transcript; or every decision is recorded but an assumption made after a fallback or 'your choice' answer is stated only in the transcript; or every decision is recorded with a reason only in commit messages or gate messages, none in the repo's docs.
- 3: Every significant decision is recorded with a reason, including every fallback or 'your choice' assumption; the options considered are missing for one or two, or one decision lives only in a gate message or commit rather than in the repo's docs.
- 4: Every significant decision, including every fallback or 'your choice' assumption, is recorded in the repo (decision record, spec, plan or design note) with the real options considered, the one chosen and a reason specific to this project.

### assumption auditor: score 3 (ok)

Evidence:

> ["/judge/repo/docs/decisions.md:6-8", "/judge/repo/docs/decisions.md:9-26", "/judge/transcript.md:54", "/judge/transcript.md:46", "/judge/transcript.md:39"]

Notes:

> The one fallback answer (how to finish the branch: keep the work on `main`, no push or PR) is recorded in the repo as decision 1 with a reason. The nine contract-gap choices are also recorded in the repo's docs, each with a reason, but most give no alternatives that were weighed. Decision 10 (state in SQLite) gives only a thin reason, and the YAML 1.2 typing rules chosen over PyYAML's 1.1 defaults are explained only in the transcript, so the record is short of full options-considered entries.

### devil's advocate: score 2 (ok)

Evidence:

> ["repo/docs/decisions.md:6-8", "repo/docs/decisions.md:15-16", "repo/docs/decisions.md:21-22", "repo/docs/decisions.md:26", "transcript.md:46", "transcript.md:54"]

Notes:

> The 'your choice' fallback (keep the work on main, no PR) is recorded in docs/decisions.md:6-8 with a reason tied to the contract, and nine contract-gap choices sit next to it. But almost none of them name the other options considered. Several give no reason at all (5, 8), and 10's reason is circular. Major choices appear only in the transcript (transcript.md:46): using PyYAML with a custom YAML 1.2 resolver instead of a round-trip library, and the event-per-leaf history design. About half the significant decisions are properly recorded with a reason.

### successor: score 3 (ok)

Evidence:

> ["repo/docs/decisions.md:6-8", "repo/docs/decisions.md:9-26", "transcript.md:54", "transcript.md:46", "transcript.md:39", "repo/README.md"]

Notes:

> docs/decisions.md records ten contract-gap decisions with reasons, including decision 1, the integration choice made after the 'your choice' prompt (transcript.md:54). However, almost no entry lists the alternatives considered, and a successor could only infer several decisions from the code or transcript: the YAML 1.2 core-schema resolver used instead of PyYAML's 1.1 rules (transcript.md:46), deriving set/remove events by comparing the config before and after a write, importing on the first command, and the choice of PyYAML and eventsourcing.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: decisions.md records ten choices incl. the fallback, but almost none list options, two lack reasons, and major design choices (YAML 1.2 resolver, event-per-leaf, first-command import, libraries) live only in transcript or code

## Item 33: question_value, Arm A, step 03

Rubric levels:

- 0: Every question asked was within reach (the contract, the PO brief, the repo or package docs already answered it) or superfluous (its answer could not change what was built).
- 1: Wasteful questions (within reach or superfluous) outnumber valuable ones, and at most one question resolved a genuine ambiguity.
- 2: Valuable and wasteful questions roughly balance; or most questions were valuable but two or more were wasteful (within reach or superfluous).
- 3: Most questions resolved a genuine ambiguity (escalated, answered 'out of contract: your choice', or the answer changed what was built) and at most one was within reach or superfluous.
- 4: Every question was worth asking and at least one exposed a gap the contract and brief did not cover (escalated to the owner, answered by the fallback, or raised by no other arm at this step), and its answer visibly shaped what was built; none was within reach or superfluous.

### consequence: score 1 (ok)

Evidence:

> ["/judge/questions.md:59-89", "/judge/questions.md:3-36", "/judge/questions.md:91-111", "/judge/questions.md:126-152", "/judge/questions.md:168-191", "/judge/others-questions.md:130-164"]

Notes:

> Only Q3 had a consequential answer: it raised the arm's own departure from the contract, a double-quoted fallback for CRLF text includes, and the PO's rejection changed requirement 4.5 and the built behaviour. The other eight questions with replies were next-command gates or rubber-stamp approvals whose answers could not change what was built, and the arm never directly asked about the open scalar `--sources` case that other arms escalated.

### product owner: score 1 (ok)

Evidence:

> ["/judge/questions.md:3-36 (Q1 next_command: discovery already decided and committed all open choices; reply was just the next command)", "/judge/questions.md:40-57, 113-124, 154-166, 193-205 (Q2, Q5, Q7, Q9 are next-command gates whose answers could not change what was built)", "/judge/questions.md:73-74, 89 (Q3: the CRLF double-quote fallback was something the arm itself said departed from the contract; I rejected it by quoting the contract, so the answer was within reach)", "/judge/questions.md:100-111 (Q4: it raised the knock-on clash between CRLF literal blocks and its own 'reads back exactly' promise; this was the one real tension, and I approved it unchanged)", "/judge/questions.md:128-152, 170-191 (Q6 and Q8 are approval gates I passed with no change)"]

Notes:

> Arm X asked no real clarifying questions. It settled every open choice itself, and its turns were mostly next-command or approval gates that could not change the build. The only answer that changed anything (Q3) fixed a departure from the contract that the arm had already spotted. Only Q4's knock-on tension came close to resolving a genuine ambiguity.

### researcher: score None (not_applicable)

Evidence:

> ["/judge/questions.md:3-232 (Questions 1-10 in the scored run are all of type next_command, approval or step_done; none is of type question)", "/judge/questions.md:28 (the arm says it chose and recorded its discovery decisions without asking)", "/judge/transcript.md (no WAITING_FOR_* or AskUser clarification markers found)"]

Notes:

> At step 3, Arm X sent only routine workflow messages: next-command handoffs, requirements/design/tasks approval requests and a completion report. It never asked a question to clear up an ambiguity. The PO's rejection at Q3 changed the build, but it was a review verdict on an approval request, not the answer to a question the arm asked, so there is nothing to score here.

Your verdict (a whole number 0 to 4, and a reason):

score: n/a
reason: Not applicable per the rubric (N.a and N.b both counted): no actual question in either run, only handoffs, approvals and reports; its silent choices are judged under gates and process

## Item 34: question_value, Arm D, step 03

Rubric levels:

- 0: Every question asked was within reach (the contract, the PO brief, the repo or package docs already answered it) or superfluous (its answer could not change what was built).
- 1: Wasteful questions (within reach or superfluous) outnumber valuable ones, and at most one question resolved a genuine ambiguity.
- 2: Valuable and wasteful questions roughly balance; or most questions were valuable but two or more were wasteful (within reach or superfluous).
- 3: Most questions resolved a genuine ambiguity (escalated, answered 'out of contract: your choice', or the answer changed what was built) and at most one was within reach or superfluous.
- 4: Every question was worth asking and at least one exposed a gap the contract and brief did not cover (escalated to the owner, answered by the fallback, or raised by no other arm at this step), and its answer visibly shaped what was built; none was within reach or superfluous.

### consequence: score 0 (ok)

Evidence:

> ["/judge/questions.md:3-22", "/judge/questions.md:24-36", "/judge/others-questions.md:396-428", "/judge/transcript.md (no matches for question or WAITING_FOR markers)"]

Notes:

> Arm X never asked for input on an open point. Turn 1 reported a finished step, and it settled the `show PATH --sources` scalar case (/judge/questions.md:17) on its own, without asking. Turn 2 offered merge, PR and keep options that it said did not apply, so no answer could have changed what was built; that turn was superfluous. Other arms asked about that scalar `--sources` gap, and Arm C escalated it to the owner (/judge/others-questions.md:583-614).

### product owner: score 0 (ok)

Evidence:

> ["/judge/questions.md:3-22", "/judge/questions.md:24-36", "/judge/transcript.md (no question ending in '?' found)"]

Notes:

> Arm X asked me nothing before building. It filled every gap the contract left open itself (the single-value `--sources` case, the CRLF fallback, quoting, paths outside the theatre) and recorded those choices in docs/decisions.md. Both of its turns were reports after the work was done: one listing what it built, one saying there was nothing to merge. Neither reply could change what was built, so both were superfluous, and no gap reached the owner, unlike Arm C, which put the `--sources` single-value question to me before building.

### researcher: score None (not_applicable)

Evidence:

> ["/judge/questions.md:3-22 (Q1 is a step_done completion report that lists choices already made, with no question to the PO)", "/judge/questions.md:24-36 (Q2 is a step_done delivery statement that ends 'the work is delivered' and gets an empty reply)", "/judge/transcript.md:19-27 (the arm's turns are progress narration and reports, with no question or WAITING_FOR marker)"]

Notes:

> Arm X asked no real question at step 3. Both logged turns are end-of-step reports: it made the open choices itself and recorded them in docs/decisions.md instead of asking about them, so there is no question value to score.

Your verdict (a whole number 0 to 4, and a reason):

score: n/a
reason: Not applicable per the rubric: no question in either run, only after-the-fact step_done reports; its silent gap-filling is penalised under gates (item 16) and process

## Item 35: question_value, Arm F, step 06

Rubric levels:

- 0: Every question asked was within reach (the contract, the PO brief, the repo or package docs already answered it) or superfluous (its answer could not change what was built).
- 1: Wasteful questions (within reach or superfluous) outnumber valuable ones, and at most one question resolved a genuine ambiguity.
- 2: Valuable and wasteful questions roughly balance; or most questions were valuable but two or more were wasteful (within reach or superfluous).
- 3: Most questions resolved a genuine ambiguity (escalated, answered 'out of contract: your choice', or the answer changed what was built) and at most one was within reach or superfluous.
- 4: Every question was worth asking and at least one exposed a gap the contract and brief did not cover (escalated to the owner, answered by the fallback, or raised by no other arm at this step), and its answer visibly shaped what was built; none was within reach or superfluous.

### consequence: score 3 (ok)

Evidence:

> ["/judge/questions.md:123-127", "/judge/questions.md:131-139", "/judge/questions.md:133", "/judge/questions.md:143-150", "/judge/questions.md:22", "/judge/questions.md:62"]

Notes:

> Of the four discovery questions, three were escalated as out of contract: merge-key reads, `--expand-alias` with no alias on the path, and a path through more than one alias. Their answers visibly shaped the build: the arm dropped its 'expand only the outermost alias' plan and expanded every alias on the path instead. The flow-style anchor question was answerable from the contract text ('a block-style copy'), which is one within-reach question and rules out a 4. In the scored run the arm asked no real questions; it only noted unsettled points, such as replacing the alias itself, in its status reports and did not ask the PO to decide them.

### product owner: score 1 (ok)

Evidence:

> ["/judge/questions.md:5-36 (Q1 reports a fix that was already committed; the reply was only a routing command)", "/judge/questions.md:62-64 (Q2 asks the owner to decide whether replacing the alias itself should be refused, but only after the work was built; the runner answered /method-command and nothing changed)", "/judge/questions.md:89-93 (Q3 raises the anchored include strings case, but no answer came back and nothing was built from it)", "/judge/transcript.md:14-16 (the arm went straight from assessment to fix and asked the PO nothing before building)"]

Notes:

> In the scored run, all three checkpoints were status hand-offs sent after the code was committed, so their answers could not change what was built. Two of them did point to real gaps the contract leaves open (replacing an alias, and an anchored include), but those were offered as afterthoughts, never resolved and never acted on.

### researcher: score None (not_applicable)

Evidence:

> ["/judge/questions.md:3", "/judge/questions.md:38", "/judge/questions.md:66", "/judge/transcript.md (no AskUserQuestion or WAITING_FOR prompts found)"]

Notes:

> In the scored run, Arm X sent only status handoffs: one next_command (Q1) and two step_done reports (Q2, Q3). It posed no real clarifying question. Its only open point was replacing the alias itself, which it noted in the assessment and mentioned in passing in the reports, and the runner or PO answered with a command or left it blank. So there are no questions to judge for value at this step.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Rubric counts N.a and N.b: three of four discovery questions were escalated as out of contract and reshaped the design (expand every alias on the path); one was within reach

## Item 36: req_test_code, Arm D, step 02

Rubric levels:

- 0: Requirements cannot be connected to tests: there is no identifiable requirement text, or no IDs, references or matching names link requirements and tests, so tracing means reverse-engineering the code.
- 1: Requirements exist, but fewer than half of those sampled can be traced to a test that asserts them, and only by guessing from topic words; the code has to be found by searching the whole repo.
- 2: Most sampled requirements can be traced to a test by matching names or topics, but there are no explicit links, or explicit links cover only some areas; finding the code from the test takes a search.
- 3: Nearly every sampled requirement has an explicit link (ID, reference, task entry) to a test that asserts it, and the code is reachable from the test; one or two links are missing or point at a test that no longer checks the requirement.
- 4: Every sampled requirement, including those this step introduced or changed, has an explicit, correct link to a test that asserts it and on to the code; no sampled test or requirement is an orphan, and no link points at superseded text.

### auditor: score 2 (ok)

Evidence:

> ["repo/docs/decisions.md:34", "repo/tests/test_sync.py:131", "repo/tests/test_sync.py:16", "repo/tests/test_config.py:263", "repo/docs/decisions.md:39", "repo/docs/decisions.md:23"]

Notes:

> I sampled five requirements and could trace three of them, but only by matching topics to test names, because there are no requirement IDs or references anywhere. The two step-2 items (watch exits 4 on a broken config, and commands reconciling hand edits) map to test_sync.py:131 and :16, and the step-1 rule that replacing an include exits 3 maps to test_config.py:263. Two items have no test I could find: reconcile emitting sets before removes (decision 15) and the double-quote fallback when a literal block would swallow comments (decision 9).

### maintainer: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_sync.py:16", "/judge/repo/tests/test_sync.py:41", "/judge/repo/tests/test_sync.py:131", "/judge/repo/tests/test_sync.py:177", "/judge/repo/docs/decisions.md:11", "/judge/repo/docs/decisions.md:34", "/judge/repo/README.md:16"]

Notes:

> I sampled three step-2 tests: test_commands_reconcile_hand_edits, test_watch_fails_on_broken_config and test_set_while_watching_emits_only_its_own_events. Each can be matched by topic to a README bullet (README.md:16) or a numbered decision (decisions 11, 13 and 14), and one inline comment points loosely at decision 14 (test_sync.py:41). But there are no requirement IDs or explicit references, and the tests only drive the CLI, so finding the code in store.py/cli.py takes a search.

### newcomer: score 2 (ok)

Evidence:

> ["repo/README.md:16-17", "repo/docs/decisions.md:11-15", "repo/tests/test_sync.py:9", "repo/tests/test_sync.py:16", "repo/tests/test_sync.py:76", "repo/tests/test_sync.py:122", "repo/tests/test_sync.py:155"]

Notes:

> The step-2 behaviour (reconcile before every command, `watch`, the flock lock, polling) is described in prose in README.md:16-17 and decisions.md:11-15, and you can match it to tests by topic: the sections 'reconcile on every command' and 'watch' in test_sync.py and test names like test_watch_survives_broken_edit. There are no requirement IDs or explicit references from spec to test or test to code, so getting to the implementation (store.py and cli.py) means searching.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: No requirement IDs or explicit links; 3 of 5 sampled requirements trace to tests only by topic name, 2 (decisions 9 and 15) have no test; code reached by search

## Item 37: req_test_code, Arm E, step 01

Rubric levels:

- 0: Requirements cannot be connected to tests: there is no identifiable requirement text, or no IDs, references or matching names link requirements and tests, so tracing means reverse-engineering the code.
- 1: Requirements exist, but fewer than half of those sampled can be traced to a test that asserts them, and only by guessing from topic words; the code has to be found by searching the whole repo.
- 2: Most sampled requirements can be traced to a test by matching names or topics, but there are no explicit links, or explicit links cover only some areas; finding the code from the test takes a search.
- 3: Nearly every sampled requirement has an explicit link (ID, reference, task entry) to a test that asserts it, and the code is reachable from the test; one or two links are missing or point at a test that no longer checks the requirement.
- 4: Every sampled requirement, including those this step introduced or changed, has an explicit, correct link to a test that asserts it and on to the code; no sampled test or requirement is an orphan, and no link points at superseded text.

### auditor: score 2 (ok)

Evidence:

> ["/judge/repo/README.md:6-16", "/judge/repo/tests/test_config.py:71", "/judge/repo/tests/test_config.py:96", "/judge/repo/tests/test_config.py:122", "/judge/repo/README.md:15-16"]

Notes:

> I sampled five requirements, all from the README since this is step 1: show, byte-surgical set, writing back through `file:` includes, the event history, and the missing-config error. All five can be traced to a test only by matching topic names (test_show, test_set_keeps_comment_column, test_set_include_targets, test_history, test_missing_config); no requirement has an ID or explicit link, and the code is found through the README's module layout list rather than from the tests.

### maintainer: score 1 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:96", "/judge/repo/tests/test_config.py:119", "/judge/repo/tests/test_config.py:82", "/judge/repo/README.md:11-16"]

Notes:

> The only requirement text is a short README summary with no IDs, and no test references a requirement or a source module. I sampled three tests. test_set_keeps_comment_column, test_set_include_targets (exit code 3) and test_new_keys_and_collections (exit code 5) check behaviour that appears in no requirement text at all, so a maintainer can only guess the intent from the test name and has to search to reach editor.py or cli.py.

### newcomer: score 1 (ok)

Evidence:

> ["/judge/repo/README.md:3-18", "/judge/repo/tests/test_config.py:76-79", "/judge/repo/tests/test_config.py:101-104", "/judge/repo/tests/test_config.py:135-136", "/judge/repo/src/troupe/cli.py:28-30"]

Notes:

> The only requirement text is a short README with no IDs. Its file-layout line points to modules, and tests can be matched to it only by topic names such as show, set, include and history. Most tested behaviour has no requirement text a newcomer could start from, including exit codes 3, 4 and 5, comment-column preservation and quoting, so tracing means reverse-engineering the tests and code.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: README requirements have no IDs or links; all sampled requirements match a test by name, but much tested behaviour (exit codes, comment column, quoting) has no requirement text (consistent with item 38)

## Item 38: req_test_code, Arm E, step 03

Rubric levels:

- 0: Requirements cannot be connected to tests: there is no identifiable requirement text, or no IDs, references or matching names link requirements and tests, so tracing means reverse-engineering the code.
- 1: Requirements exist, but fewer than half of those sampled can be traced to a test that asserts them, and only by guessing from topic words; the code has to be found by searching the whole repo.
- 2: Most sampled requirements can be traced to a test by matching names or topics, but there are no explicit links, or explicit links cover only some areas; finding the code from the test takes a search.
- 3: Nearly every sampled requirement has an explicit link (ID, reference, task entry) to a test that asserts it, and the code is reachable from the test; one or two links are missing or point at a test that no longer checks the requirement.
- 4: Every sampled requirement, including those this step introduced or changed, has an explicit, correct link to a test that asserts it and on to the code; no sampled test or requirement is an orphan, and no link points at superseded text.

### auditor: score 2 (ok)

Evidence:

> ["/judge/repo/README.md:5-11", "/judge/repo/README.md:14-21", "/judge/repo/README.md:23-25", "/judge/repo/tests/test_config.py:100", "/judge/repo/tests/test_config.py:191", "/judge/repo/tests/test_config.py:230", "/judge/repo/tests/test_config.py:154"]

Notes:

> The only requirement text is the README prose. It has no IDs, and no test cites it. I sampled five requirements: show --sources and reconcile/watch, which look recent, plus get, set and history. All five trace to a test only by topic name (test_show_sources, test_reconcile_on_command, test_watch, test_get, test_history), so each is matched but none is explicitly linked. From a test, the README's module layout list (README.md:23-25) points roughly to the code, but finding the exact function still takes a search.

### maintainer: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:191", "/judge/repo/tests/test_config.py:230", "/judge/repo/tests/test_config.py:100", "/judge/repo/README.md:18", "/judge/repo/README.md:23"]

Notes:

> The requirements live only as prose in the README. They have no IDs, and the tests have no references or docstrings pointing back to them. For the three tests I sampled (test_reconcile_on_command, test_watch, test_show_sources), I could only match each to a requirement by topic words such as 'reconciles', 'watch' and '--sources'. The tests drive the CLI through subprocess, so finding the code they exercise means looking up the README's module layout (for example, sync.py) and searching within it.

### newcomer: score 2 (ok)

Evidence:

> ["repo/README.md:14-16", "repo/README.md:23-25", "repo/tests/test_config.py:100", "repo/tests/test_config.py:191", "repo/tests/test_config.py:230"]

Notes:

> The only requirement text is the README prose. You can match its behaviours, such as `show --sources`, reconcile and watch, to tests by name (test_show_sources, test_reconcile_on_command, test_watch), and the README's layout line points to modules like render.py and sync.py. But there are no requirement IDs or explicit links from requirement to test to code, so tracing depends on matching topic words, and some details (the `.yaml` alternative, the `events.lock` serialisation) have no test that clearly asserts them.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Requirements are README prose with no IDs or links; all sampled requirements match a test only by name; some details lack a clear test; code reached via the README layout and a search

## Item 39: research_first, Arm C, step 01

Rubric levels:

- 0: Every question was asked bare: the transcript shows no reading of the contract, brief, repo or package docs on the point beforehand, and no options or recommendation; or a question asks something the arm had already read the answer to earlier in the transcript.
- 1: Most questions are bare; at most one shows prior research or offers options, and none gives a recommendation with a reason.
- 2: About half the questions show prior research in the transcript or arrive with options; the rest are bare problems, or options come without saying what was found or which the arm recommends.
- 3: Every question is preceded by research on its point (cited in the transcript) and states what was found; all but one also offer options with a recommendation and a reason.
- 4: Every question is preceded by research on its point, states what was found and where, lays out the options with their consequences, and recommends one with a reason, so the answer can be a single choice.

### decision-maker: score 3 (ok)

Evidence:

> ["/judge/questions.md:36-42", "/judge/questions.md:83-93", "/judge/questions.md:105-113", "/judge/questions.md:208-218", "/judge/questions.md:252-254", "/judge/questions.md:356", "/judge/transcript.md:9", "/judge/transcript.md:22-26"]

Notes:

> Five of the six real questions (Q1, Q3, Q4, Q8, Q15) can each be answered with a single choice: each says what was found (the contract's 'importing is not reconciling', the charter's TROUPE-001 wording, the eventsourcing SQLite module, the analysis findings, the merge failure), backed by research at transcript lines 9-26, and each recommends an option with a reason. Q3 and Q4 also spell out what each option leads to. Q7 is the exception and stops this reaching a 4: it presents decisions already made for checking, mostly with little reasoning, and its handoff question (questions.md:218) lists alternatives with no recommendation, so the product owner had to escalate it.

### investigator: score 3 (ok)

Evidence:

> ["/judge/transcript.md:2 (charter context and brief check before Q1)", "/judge/transcript.md:9 (Q1 quotes the contract's 'importing is not reconciling' and offers A/B/C, recommending A with a reason)", "/judge/transcript.md:20-22 (charter.md read, then Q3 cites what TROUPE-001 says and recommends A with a reason)", "/judge/transcript.md:25-26 (Q4 says eventsourcing has SQLite storage, but the library is only exercised later, at lines 50-52)", "/judge/questions.md:216-218 (the implement-review handoff question lists options with no recommendation)", "/judge/questions.md:252,356 (Q8 and Q15 state what was found and give reasoned recommendations)"]

Notes:

> Most questions come after research shown in the transcript (charter, contract, analysis report, merge failure), state what was found, and recommend an option with a reason. The exceptions are Q4, whose eventsourcing claim was not checked before it was asked, and the Q7 handoff question, which has options but no recommendation, so this stops short of 4.

### mentor: score 3 (ok)

Evidence:

> ["/judge/questions.md:36-42 (Q1 quotes the contract's 'importing is not reconciling' line and offers A/B/C, recommending A with a reason)", "/judge/transcript.md:20 (reads the charter and plan context before Q3; Q3 at /judge/questions.md:83-93 cites TROUPE-001 and the ruamel limits it found, and recommends A with a reason)", "/judge/questions.md:105-113 (Q4 claims eventsourcing ships SQLite persistence, but the library is first checked later, at /judge/transcript.md:35-36)", "/judge/questions.md:202-218 (Q7 cites findings R-13 to R-17 from library checks at /judge/transcript.md:49-55; its final skill question lists choices but gives no recommendation)", "/judge/questions.md:252 and 356 (Q8 and Q15 state what was found and recommend an option with a reason)"]

Notes:

> Most questions arrive with research cited, findings stated, options and a reasoned recommendation, so a mentor could answer them on the spot. However, Q4's library claim has no research in the transcript before it, and Q7's closing question about the skill has no recommendation, so it falls short of a 4.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 40: research_first, Arm D, step 01

Rubric levels:

- 0: Every question was asked bare: the transcript shows no reading of the contract, brief, repo or package docs on the point beforehand, and no options or recommendation; or a question asks something the arm had already read the answer to earlier in the transcript.
- 1: Most questions are bare; at most one shows prior research or offers options, and none gives a recommendation with a reason.
- 2: About half the questions show prior research in the transcript or arrive with options; the rest are bare problems, or options come without saying what was found or which the arm recommends.
- 3: Every question is preceded by research on its point (cited in the transcript) and states what was found; all but one also offer options with a recommendation and a reason.
- 4: Every question is preceded by research on its point, states what was found and where, lays out the options with their consequences, and recommends one with a reason, so the answer can be a single choice.

### decision-maker: score 3 (ok)

Evidence:

> ["/judge/transcript.md:50", "/judge/transcript.md:51", "/judge/questions.md:25-37"]

Notes:

> The only real question (Q2) came after a git status, diff, test-run and worktree check (transcript:50). It says what was found: tests pass, the tree is clean, there is no worktree and commit 10edbac is on main. It then gives each option's consequence: option 1 has nothing to do, option 2 breaks the no-push rule, option 3 leaves things as they are. It never explicitly recommends option 3 with a reason, so the product owner has to infer the pick, which falls short of a 4.

### investigator: score 1 (ok)

Evidence:

> ["/judge/questions.md:23-37 (Q2, the only real question; Q1 and Q3 are step_done reports)", "/judge/transcript.md:50 (git status, branch and worktree check run before asking)", "/judge/transcript.md:51 (states the work is already committed on main and that option 2 breaks the no-push instruction, but asks 'Which option?' without recommending one)", "/judge/transcript.md:54 (as soon as it was told to decide, the arm picked option 3 from the contract's no-push, commit-on-main rule)"]

Notes:

> The only real question (Q2) was preceded by a git check and gave options with their consequences, but it made no recommendation. The arm's own findings and the no-push, commit-on-main instruction it cited already settled the answer, so the question was close to redundant.

### mentor: score 3 (ok)

Evidence:

> ["/judge/transcript.md:50", "/judge/transcript.md:51", "/judge/questions.md:25-37", "/judge/questions.md:41"]

Notes:

> Question 2 is the only real question; Questions 1 and 3 are step_done reports. Before asking it, the arm checked git status, worktree and branch (transcript:50), reported what it found (tree clean, on main, no worktree) and gave the consequence of each option. It never stated a recommendation, though: it all but answered the question itself (option 3, since the brief forbids pushing) and still asked, so as mentor I would have said 'then say option 3 and why'.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: The one question (merge/PR/keep) was researched (git checks, findings, consequences per option) but gave no recommendation, though its own findings and the no-push rule already settled it

## Item 41: test_names, Arm A, step 02

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 3 (ok)

Evidence:

> ["tests/test_cli_streaming.py:122", "tests/test_cli_streaming.py:78", "tests/test_cli_watch.py:37", "tests/test_cli_watch.py:76", "tests/test_e2e_reconcile.py:105", "tests/test_e2e_reconcile.py:340"]

Notes:

> Nearly every name states a condition and an outcome that the body asserts exactly, such as test_set_after_hand_edit_records_reconcile_set_before_its_own_set_with_old_chained and test_unreadable_store_exits_4_naming_the_store. Two names say less than their bodies check: test_streaming_handler_troupe_error_keeps_the_conventions (cli_streaming.py:122) only says 'the conventions' where the body checks exit 5, empty stdout and the stderr format, and test_registered_subcommands_get_the_theatre_text (cli_streaming.py:78) says all subcommands but the body checks only `show`.

### falsifier: score 3 (ok)

Evidence:

> ["tests/test_reconcile.py:164", "tests/test_reconcile.py:156", "tests/test_recorded.py:81", "tests/test_reconcile.py:393", "tests/test_reconcile.py:381", "tests/test_reconcile.py:317"]

Notes:

> I checked the first 30 new step-2 tests (test_recorded.py, then test_reconcile.py; diff order assumed). Every name's claim is asserted (e.g. never_writes_user_files compares bytes, one_consecutive_batch checks seq numbers) and none overclaims. A few names say less than the body: nan_and_inf_unchanged_give_nothing also asserts a -0.0→0.0 set (:164), and null_valued_leaf_set_and_null_leaf_kept (:156) and import_set_remove_set_again_follows_re_creation (:81) don't name the expected result.

### spec reader: score 3 (ok)

Evidence:

> ["/judge/repo/tests/test_cli_streaming.py:122", "/judge/repo/tests/test_cli_streaming.py:78", "/judge/repo/tests/test_e2e_reconcile.py:105", "/judge/repo/tests/test_e2e_reconcile.py:340", "/judge/repo/tests/test_cli_watch.py:126", "/judge/repo/tests/test_e2e_history.py:182"]

Notes:

> No overclaims found; most names give the condition and expected result and the bodies check exactly that, e.g. test_set_after_hand_edit_records_reconcile_set_before_its_own_set_with_old_chained checks the exact event list. A few names are vague, such as test_streaming_handler_troupe_error_keeps_the_conventions, which does not say it pins exit 5, empty stdout and the formatted stderr, and test_registered_subcommands_get_the_theatre_text.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 42: test_names, Arm B, step 03

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 3 (ok)

Evidence:

> ["repo/tests/test_get.py:63 test_get_of_a_collection_exits_5_naming_the_path_and_pointing_to_show: the name states the condition and the result, and the body asserts exit 5, empty stdout, the path and 'config show' in stderr", "repo/tests/test_show.py:59 test_show_double_quotes_a_text_include_a_literal_block_cannot_hold: the expected output is checked byte for byte, as the name implies", "repo/tests/test_reconcile.py:171 test_get_and_show_reconcile_a_hand_edit_once: the body asserts exactly one recorded set event", "repo/tests/test_render.py:90-111 test_source_label_of_the_config_file / _of_a_nested_include / _with_a_relative_theatre: these names give only the condition, not the expected label", "repo/tests/test_show_sources.py:45,64,68,90 test_sources_for_a_section / _for_a_quoted_string_scalar / _with_a_relative_theatre: the condition is named but not the result", "repo/tests/test_show.py:111 test_show_of_a_missing_path_exits_5_naming_it: the body also checks --sources, which the name does not mention"]

Notes:

> I found no name that overclaims, and the get, show and reconcile tests read as a spec. A few source_label and --sources names state the condition but not the expected result, so from the name alone a triager could not tell what failed.

### falsifier: score 3 (ok)

Evidence:

> ["tests/test_get.py:31", "tests/test_cli.py:59", "tests/test_reconcile.py:171", "tests/test_show.py:24", "tests/test_render.py:73", "tests/test_render.py:99"]

Notes:

> I read the 30 checked tests in diff order: tests/test_cli.py, test_get.py, test_reconcile.py and test_render.py in full, plus the first nine in test_show.py. None overclaims: each name is backed by its assertions, for example 'reconcile_a_hand_edit_once' runs the command twice and asserts a single event, and the show tests compare output byte for byte. Two names are vague, so the score is 3 rather than 4: 'test_get_prints_each_scalar_type_per_contract' does not say what the contract is, and 'test_show_takes_an_optional_path' does not state the expected result (exit 0 and output starting 'model: x').

### spec reader: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_show_sources.py:45", "/judge/repo/tests/test_show_sources.py:64", "/judge/repo/tests/test_show_sources.py:68", "/judge/repo/tests/test_show_sources.py:90", "/judge/repo/tests/test_render.py:90", "/judge/repo/tests/test_render.py:109", "/judge/repo/tests/test_get.py:31", "/judge/repo/tests/test_show.py:24", "/judge/repo/tests/test_get.py:63"]

Notes:

> No name overclaims, and most names are specific spec statements whose bodies check exactly what they say (e.g. test_show.py:24 and test_get.py:63). But about six names give only the condition and not the expected result, so a failure would not say which rule broke: test_sources_for_a_section, ..._for_a_quoted_string_scalar, ..._for_an_empty_included_yaml_file, ..._with_a_relative_theatre, test_source_label_of_the_config_file and test_get_prints_each_scalar_type_per_contract. That is more than the one or two vague names allowed at level 3.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Most names read as spec statements and none overclaims; about six of 30 name only the condition, not the expected result

## Item 43: test_names, Arm C, step 04

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 3 (ok)

Evidence:

> ["repo/tests/integration/test_lineage_cli.py:205", "repo/tests/integration/test_history.py:271", "repo/tests/integration/test_history.py:129", "repo/tests/integration/test_lineage_changes.py:146", "repo/tests/integration/test_lineage_cli.py:239", "repo/tests/integration/test_lineage_changes.py:209"]

Notes:

> From the name alone I could tell what broke in almost every checked test (e.g. test_invalid_actor_exits_2_and_history_is_unchanged, test_change_ids_are_never_reused_across_commands), and the bodies assert what the names say; none overclaims. A few names say less than the body checks: test_refused_set_keeps_its_reconcile_but_not_its_reason also runs a 'failed' (exit 5) case, test_history_lines_have_lineage_keys_in_contract_order also checks actor/via/reason values, and test_history_does_not_reconcile_a_hand_edit also checks that a later get does reconcile.

### falsifier: score 3 (ok)

Evidence:

> ["tests/integration/test_lineage_recording.py:102", "tests/integration/test_lineage_recording.py:105", "tests/integration/test_lineage_cli.py:239", "tests/integration/test_lineage_pre_lineage.py:120", "tests/integration/test_history.py:330", "tests/unit/test_lineage.py:179", "tests/unit/test_pre_lineage_fixture.py:85"]

Notes:

> Almost every name states a condition and an expected result, and the body checks it at the level claimed: byte-identical history compares the two outputs for equality (test_lineage_pre_lineage.py:120), and key order is checked with list(...) rather than dict equality (test_lineage.py:179). One name overclaims: test_reason_option_is_rejected_on_commands_other_than_set (test_lineage_recording.py:102) only runs `get` (line 105), so it would still pass if `show`, `history` or `watch` accepted --reason. A few names, such as test_invalid_actor_exits_2_and_history_is_unchanged, say less than their bodies check (exact message, file snapshot).

### spec reader: score 3 (ok)

Evidence:

> ["/judge/repo/tests/integration/test_lineage_changes.py:113", "/judge/repo/tests/integration/test_lineage_recording.py:78", "/judge/repo/tests/integration/test_lineage_pre_lineage.py:68", "/judge/repo/tests/unit/test_lineage.py:207", "/judge/repo/tests/unit/test_lineage.py:179"]

Notes:

> Nearly every name states a condition and an expected result from the Lineage spec (for example `reconcile_and_set_in_one_command_are_two_changes`, `noop_set_with_reason_records_nothing`, `invalid_troupe_actor_is_reported_before_a_missing_or_broken_configuration`), and the bodies I read assert those claims; I found no overclaims. A few names are vague or say less than the body checks, which keeps this below 4: `pre_lineage_fields_follow_the_recorded_decision` and `lineage_fields_are_flat_and_ordered` don't say what the rule is, and `pre_lineage_history_prints_known_fields_and_marks_the_rest_unknown` checks the output byte for byte against an expected file, which the name doesn't say.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 44: test_names, Arm E, step 02

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 2 (ok)

Evidence:

> ["tests/test_config.py:199", "tests/test_config.py:160", "tests/test_config.py:230"]

Notes:

> No test name claims more than its body checks, but the names are too vague to triage from. `test_watch` (line 199) covers six behaviours: propagating config and include edits, ignoring the CLI's own set, ignoring formatting-only edits, following new includes, surviving broken YAML, and exiting cleanly on SIGTERM. Its name says none of them. `test_reconcile_on_command` (line 160) and `test_watch_sigint` (line 230) also say less than their bodies check: neither the 'history does not reconcile' rule nor the 'exits 0' result is in the name.

### falsifier: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:199", "/judge/repo/tests/test_config.py:160", "/judge/repo/tests/test_config.py:230", "/judge/repo/README.md:16"]

Notes:

> There is no git history, so I treated the reconcile and watch tests (lines 160, 199 and 230) as this step's additions. None of their names overclaims, but none states a condition and expected result: `test_watch` (line 199) covers about six behaviours (include following, broken-YAML recovery, no echo events from its own `set`, formatting-only edits, SIGTERM exit 0) and is too vague to tell what failed; `test_reconcile_on_command` (line 160) leaves out that `history` does not reconcile and that formatting-only edits produce no events; `test_watch_sigint` (line 230) omits the asserted clean exit code 0.

### spec reader: score 2 (ok)

Evidence:

> ["repo/tests/test_config.py:160", "repo/tests/test_config.py:199", "repo/tests/test_config.py:230", "repo/README.md:16-19"]

Notes:

> I had no diff, so I took the step's tests to be the reconcile and watch tests (test_reconcile_on_command, test_watch, test_watch_sigint). No name claims more than its body asserts, but test_watch only repeats the command name while its body checks five rules (formatting-only edits make no events, a set made during a watch records only its own events, includes are followed, the watch survives broken YAML, SIGTERM exits 0), and test_watch_sigint gives no expected result (exit 0), so the names do not read as a spec of the step.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 45: test_names, Arm E, step 03

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:230", "/judge/repo/tests/test_config.py:191", "/judge/repo/tests/test_config.py:261", "/judge/repo/tests/test_config.py:154", "/judge/repo/tests/test_config.py:139"]

Notes:

> I had no git history, so I took the step-3 tests to be the reconcile/watch tests at the end of the file. None of them overclaims. But `test_watch` (line 230) bundles six behaviours under one bare name: hand edits, include edits, its own `set`, formatting-only changes, newly added includes, broken YAML and SIGTERM exit; from the name alone a triager cannot tell which broke. `test_reconcile_on_command` and `test_watch_sigint` (which never says it expects exit 0) also say less than their bodies check, and older names such as `test_history` and `test_block_scalars` are just as vague.

### falsifier: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:191", "/judge/repo/tests/test_config.py:230", "/judge/repo/tests/test_config.py:261", "/judge/repo/tests/test_config.py:243"]

Notes:

> The repo has no git history, so I assumed this step's tests are the reconcile and watch tests after the new events/edits helpers (lines 181-264). No name overclaims, but `test_watch` and `test_watch_sigint` mostly just name the command: `test_watch` checks about six behaviours (formatting-only edits are ignored, new includes are followed, the watch survives broken YAML, it exits cleanly on SIGTERM) that its name doesn't mention, and `test_watch_sigint` doesn't say the expected result (exit 0). `test_reconcile_on_command` also checks less obvious claims, such as `history` not reconciling, that its name doesn't mention.

### spec reader: score 2 (ok)

Evidence:

> ["repo/tests/test_config.py:191", "repo/tests/test_config.py:230", "repo/tests/test_config.py:261"]

Notes:

> There is no git history, so I took the step's tests to be the reconcile/watch ones; none of the three names overclaims. `test_reconcile_on_command` (line 191) names the trigger but not the outcome; `test_watch` (line 230) only repeats the command while its body checks six rules (include following, formatting-only edits ignored, recovery from broken YAML, clean exit on SIGTERM); and `test_watch_sigint` (line 261) gives the condition but not the expected result (exit code 0).

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 46: test_names, Arm E, step 04

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:286", "/judge/repo/tests/test_config.py:312", "/judge/repo/tests/test_config.py:294-307", "/judge/repo/tests/test_config.py:318-320"]

Notes:

> There is no git history, so I took the tests added in this step to be the lineage tests, `test_lineage` and `test_bad_actor`. Neither name overclaims, but both are too vague to triage from the name alone: `test_lineage` only names the feature, yet its body checks actor parsing, via/reason fields, change grouping, distinct change IDs and timestamp format and order. `test_bad_actor` gives the condition but not the expected result (exit code 2, no stdout, config left unchanged, no events database created).

### falsifier: score 3 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:286", "/judge/repo/tests/test_config.py:289-307", "/judge/repo/tests/test_config.py:310-320", "/judge/repo/README.md:23-28"]

Notes:

> There is no git history, so I took the step-4 tests to be the two lineage tests the README describes: test_lineage and test_bad_actor. Neither name overclaims, but both are vague: test_lineage only names the feature while its body checks about ten separate things (actor kinds, via values, reasons, shared change IDs, RFC 3339 timestamps and their ordering), and test_bad_actor gives the condition but not the result it asserts (exit code 2, empty stdout, files unchanged, no events.sqlite created).

### spec reader: score 2 (ok)

Evidence:

> ["/judge/repo/tests/test_config.py:286", "/judge/repo/tests/test_config.py:310-320", "/judge/repo/README.md:23-28"]

Notes:

> The repo has no git history, so I took the lineage tests to be this step's additions: `test_lineage` and `test_bad_actor`. Neither name overclaims, but both are vague. `test_lineage` only names the feature, yet it checks many separate rules (actor kinds, via, a shared change id, a reason, an RFC 3339 timestamp, ordering). `test_bad_actor` gives the condition but not the result (exit 2, no stdout, and nothing written or recorded).

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Both new tests are vague: test_lineage names only the feature while checking about ten rules, test_bad_actor gives the condition but not the result (consistent with items 44 and 45)

## Item 47: test_names, Arm F, step 03

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 2 (ok)

Evidence:

> ["/judge/repo/tests/unit/test_view.py:32", "/judge/repo/tests/unit/test_view.py:69", "/judge/repo/tests/unit/test_view.py:108", "/judge/repo/tests/unit/test_view.py:143", "/judge/repo/tests/unit/test_view.py:148", "/judge/repo/tests/e2e/test_get.py:100", "/judge/repo/tests/e2e/test_show.py:56", "/judge/repo/tests/e2e/test_show.py:61", "/judge/repo/tests/e2e/test_get.py:76", "/judge/repo/tests/e2e/test_get_import.py:23"]

Notes:

> None of the names overclaims, and many give both the condition and the expected result (test_text_include_prints_exact_bytes_including_crlf, test_get_reconciles_a_hand_edit_first). But many others name only the input and not the expected output, so a failure triager could not tell what broke from the name alone: test_flat_mapping, test_empty_configuration, test_non_string_scalars, test_text_include_without_final_newline, test_empty_text_include, test_crlf_config_file, test_show_of_the_whole_configuration and test_show_of_a_section.

### falsifier: score 2 (ok)

Evidence:

> ["/judge/repo/tests/e2e/test_show.py:56", "/judge/repo/tests/e2e/test_show.py:61", "/judge/repo/tests/e2e/test_show.py:65", "/judge/repo/tests/e2e/test_show_sources.py:48", "/judge/repo/tests/e2e/test_show_sources.py:52", "/judge/repo/tests/e2e/test_show_sources.py:106", "/judge/repo/tests/e2e/test_show_sources.py:119", "/judge/repo/tests/unit/test_view.py:32", "/judge/repo/tests/unit/test_view.py:69", "/judge/repo/tests/unit/test_view.py:108", "/judge/repo/tests/unit/test_view.py:76", "/judge/repo/tests/e2e/test_get_errors.py:36", "/judge/repo/tests/e2e/test_get_import.py:23"]

Notes:

> I found no clear overclaims. Each name I checked would fail if its claim were false. Examples are test_get_of_a_collection_mentions_config_show, test_get_reconciles_a_hand_edit_first, test_show_prints_a_scalar_like_get and test_same_file_included_twice_is_shown_in_full_under_both_keys. One test is weaker than its name: test_strings_that_need_quoting_are_quoted_and_read_back checks only that the output is not the plain form and that it reads back, not that it is actually quoted. The score is held at 2 because many names give only a condition and no expected result, so a failure would not tell you what broke: test_whole_configuration, test_section, test_text_include_scalar, test_list_of_mappings, test_show_of_a_section, test_show_of_a_list, test_flat_mapping, test_empty_configuration and test_non_string_scalars. That is well over the 'one or two vague' allowed at level 3.

### spec reader: score 2 (ok)

Evidence:

> ["/judge/repo/tests/e2e/test_get.py:100 (test_crlf_config_file: names an input but not the expected result)", "/judge/repo/tests/e2e/test_show.py:56-66 (test_show_of_the_whole_configuration, test_show_of_a_section, test_show_of_a_list: no expected outcome named, although the bodies check exact block-YAML bytes)", "/judge/repo/tests/e2e/test_show_sources.py:48-52 (test_whole_configuration, test_section: the names don't say that --sources annotations are being checked)", "/judge/repo/tests/e2e/test_show_sources.py:106,119 (test_text_include_scalar, test_list_of_mappings: vague)", "/judge/repo/tests/e2e/test_get_errors.py:36 (test_get_of_a_collection_mentions_config_show: a specific name, by contrast)", "/judge/repo/tests/e2e/test_show.py:89 (test_show_reconciles_first: accurate)"]

Notes:

> None of the checked names overclaim, and many state a specific rule (for example get_of_a_collection_mentions_config_show and two_level_include_names_the_innermost_file). However, more than two names give only the input (test_section, test_whole_configuration, test_crlf_config_file, test_show_of_a_list, test_list_of_mappings), so you can't tell from the name which rule failed, such as block YAML layout or the source annotations.

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 48: test_names, Arm F, step 06

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 3 (ok)

Evidence:

> ["repo/tests/e2e/test_set_alias.py:16 test_setting_through_an_alias_is_refused — assert_refused checks exit 3, the --expand-alias mention and that every file kept its bytes (tests/conftest.py:278-293)", "repo/tests/e2e/test_set_alias.py:27 test_setting_at_the_anchor_changes_every_alias — checks the exact bytes, then both aliases with get", "repo/tests/e2e/test_set_alias.py:66 test_expand_alias_in_a_list_item — vague: names only the condition, not the expected result (a copy is made for that item only and the other *b alias stays)", "repo/tests/e2e/test_set_alias.py:116 test_refusal_without_the_flag_then_success_with_it — says less than the body checks (exit 3 with the flag mentioned in stderr, then the value read back)"]

Notes:

> All 13 tests added in this step have names that their bodies assert, and assert_set/assert_refused check exact file bytes, so none overclaims. One or two names (the list-item and refusal-then-success tests) are vague about the expected result, which rules out a 4.

### falsifier: score 3 (ok)

Evidence:

> ["tests/e2e/test_set_in_include.py:63", "tests/e2e/test_usage.py:118", "tests/e2e/test_set_in_include.py:77", "tests/e2e/test_set_in_include.py:30", "tests/e2e/test_set_in_include.py:123", "tests/unit/test_merge.py:121", "tests/e2e/test_usage.py:95"]

Notes:

> 

### spec reader: score 3 (ok)

Evidence:

> ["/judge/repo/tests/e2e/test_set_alias.py:2", "/judge/repo/tests/e2e/test_set_alias.py:16", "/judge/repo/tests/e2e/test_set_alias.py:66", "/judge/repo/tests/e2e/test_set_alias.py:80", "/judge/repo/tests/e2e/test_set_alias.py:111", "/judge/repo/tests/unit/test_verify.py:22"]

Notes:

> Step 6 is the yaml-alias-set bug fix (test_set_alias.py docstring, line 2). Its 13 test names read as a spec of the alias rules: refused through an alias, the anchor keeps its &, --expand-alias makes its own copy, merge keys are never written. Each body checks the claim byte for byte or by exit code. No name overclaims, but `test_expand_alias_in_a_list_item` (line 66) gives the condition without the expected result, so it is vague.

Your verdict (a whole number 0 to 4, and a reason):

score: 3
reason: Judges unanimous; owner accepted the judges' score after a one-line summary

## Item 49: test_names, Arm F, step 07

Rubric levels:

- 0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
- 1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
- 2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
- 3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
- 4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

### failure triager: score 3 (ok)

Evidence:

> ["/judge/repo/spec/bugs/yaml-alias-set/fix.md:4", "/judge/repo/tests/e2e/test_set_alias.py:16", "/judge/repo/tests/e2e/test_set_alias.py:27", "/judge/repo/tests/e2e/test_set_alias.py:66", "/judge/repo/tests/e2e/test_set_alias.py:104", "/judge/repo/tests/conftest.py:430"]

Notes:

> Step 7 is the yaml-alias-set bug fix: 13 tests in test_set_alias.py, with dates showing it came before 007. I found no overclaims. Each name I checked matched what its body asserts, through exact-byte assert_set or refusal plus unchanged-file checks in assert_refused. One name is vague: test_expand_alias_in_a_list_item gives the condition but not the expected result, so it keeps the set from reading as a full spec.

### falsifier: score 2 (ok)

Evidence:

> ["/judge/repo/tests/e2e/test_literals.py:19", "/judge/repo/tests/e2e/test_literals.py:43", "/judge/repo/tests/e2e/test_literals.py:142", "/judge/repo/tests/e2e/test_remote_errors.py:19", "/judge/repo/tests/e2e/test_remote_errors.py:44", "/judge/repo/tests/e2e/test_literals.py:90", "/judge/repo/tests/e2e/test_remote_errors.py:103"]

Notes:

> I found no real overclaims in the first 30 tests, which are all of test_literals.py and test_remote_errors.py in diff order (the repo has no git history, so I assumed alphabetical diff order). Several names do state both condition and result, e.g. literal_tag_on_a_number_gives_a_string and nested_fetch_failure_names_the_local_include. But many name only the condition, and the result is left to the module docstring: test_format_uri_via_properties/items/additional_properties, literal_tag_without_a_schema, literal_tag_on_a_folded_scalar, connection_refused, non_utf8_body, invalid_yaml_body and https_with_an_untrusted_certificate never say 'not fetched' or 'exit 4, nothing changes'. That is far more than one or two vague names, so the score is 2, not 3. stall_exceeds_ten_seconds also slightly overclaims: the body never asserts that 10 s passed, only that it finished in under 14 s.

### spec reader: score 2 (ok)

Evidence:

> ["/judge/repo/tests/e2e/test_literals.py:19", "/judge/repo/tests/e2e/test_literals.py:43", "/judge/repo/tests/e2e/test_literals.py:142", "/judge/repo/tests/e2e/test_remote_errors.py:19", "/judge/repo/tests/e2e/test_remote_errors.py:32", "/judge/repo/tests/e2e/test_remote_errors.py:72", "/judge/repo/tests/e2e/test_remote_read.py:72", "/judge/repo/tests/e2e/test_remote_read.py:127", "/judge/repo/tests/e2e/test_literals.py:51"]

Notes:

> None of the names I checked overclaims, and some state the condition and the result well, such as test_same_url_twice_is_fetched_once and test_literal_tag_on_a_mapping_cannot_load. But many name only the condition, such as test_format_uri_via_properties, test_literal_tag_without_a_schema, test_connection_refused, test_non_utf8_body, test_url_include_cycle and test_https_include, so the names alone don't say what the expected result is (not fetched, exit 4 naming the URL, nothing changed).

Your verdict (a whole number 0 to 4, and a reason):

score: 2
reason: Step-7 tests (literals, remote) mostly name only the condition, not the expected result; none materially overclaims. The failure triager's 3 assessed step 6's alias tests
