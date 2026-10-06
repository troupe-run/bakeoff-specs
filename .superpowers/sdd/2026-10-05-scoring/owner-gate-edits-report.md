# Owner-gate edits report

Commits: e8c52ad (item 1), 1869990 (item 2), 223be1d (item 3), eeca2ba (item 4). Item 5 folded into each.
Final: `uv run pytest tests/runner/scoring -q` -> 562 passed, 6 skipped (docker/live).

## 1. excluded-tests.toml
- All three stay `defect`; `decided = "owner 2026-10-06"` on all (the aggregate "draft" flag no longer fires).
- Entry 2: exit 5 cited as contract L20-22 (exit-5 line L21); no L23-24 left.
- Entry 3: "owner may prefer hard" removed; added the corpus case `plain -> multi-line (EOL comment moves to header)` (old column 10) and the design section 11 bullet quote.

## 2. scoring/stale/step-0N.toml
- Removed: cli-watch-subcommand (02), set-reason-option (04), set-in-include-option and sources-provenance-overrides (05), set-expand-alias-option and set-events-all-alias-leaves (06), set-literal-tagging (07).
- Folded: set-literal-tagging's content (include-looking strings written `!literal` unless `format: uri` / `--include`) into step 7's set-planner-remote-and-schema. The others were already covered by existing items (step 4 cli-set-path-lineage mentions reason; step 6 set-path-resolution-aliases) or were pure additions, so dropped.
- Every step's [legitimate] paths gain .gitignore, .python-version, Makefile, justfile, .github/**, pytest.ini.
- step 7 reconcile-literal-awareness why: now "both narrows (`format: uri` and `!literal` strings are literals) and widens (`https://`/`http://` strings become includes)".
- No test asserted removed ids (grep). test_stale.py passes.
- Side effect: `.github/**` in the anonymised stale list tripped test_anonymise's banned substring `github/` (meant for owner/repo names); the test now strips the literal `.github/**` before checking.

## 3. Rubrics
- question_value: `not_applicable = true`; no-question scale removed from levels 0-3; level 2 now also covers "most valuable but two or more wasteful"; lens text says answer not_applicable when no question (researcher lens no longer scores unasked ambiguities). Owner rule comment kept.
- fit: evidence = ["setup", "transcript"]; level 4 no longer requires "no extra server or credential".
- process: level 0 covers a step whose only decision is an unrecorded fallback assumption; level 2 covers all decisions recorded with a reason only in commit/gate messages.
- setup_effort: level 2 and 4 no longer mention verification effort (2: documented step awkward, setup clearly longer than docs suggest; 4: dropped the "machine-verified / eye in a minute" clause).
- Code (test first): judge.inputs_for for an arm-unit rubric now returns the arm's anon root as the inputs dir with files `setup/...` plus, when the rubric's evidence includes "transcript", `NN/transcript.md` for every step dir present. setup_effort is unchanged apart from the `setup/` prefix (the mounted dir is now the arm root; mounts use /judge/<file> so the dir name is not exposed). A missing step transcript yields input_missing (absent() policy) rather than a thinner input. The arm prompt says "and its step transcripts" only when transcripts are in the files.
- RED: new tests in test_judge.py (3) and test_rubrics.py (1) failed before the change (4 failed, 81 passed). GREEN: full suite below.
- Existing tests updated: test_not_applicable_is_offered_only_by_rubrics_with_the_explicit_key (now question_value + research_first), test_arm_unit_parts_read_the_anonymised_setup_record (setup_effort, new path shape), test_run_writes_each_verdict... (inputs list).

## 4. phase sample
- phase-sample.json `checked_by = "owner 2026-10-06"`; test's skip replaced with `skipif(results/pass1 absent)`. It passes against the worktree snapshot.

## Concerns
- Fit judges now get all steps' transcripts (larger input; judge-estimate size will rise).
- A missing transcript at any step makes fit input_missing for that arm (strict, consistent with step units).

## Fix: arm-unit fit through the real judge (review Important)
- check_mounts: a call spanning items is accepted only as an arm-unit call: exactly one label, every input either `setup/**` or `NN/transcript.md`, each mounted individually read-only. Refused: second label, other step files (questions.md, others-questions.md, diff.patch, gates.md, repo/), the label dir, the bare `01`/`setup` dirs, anon/, the key. Single-item behaviour unchanged.
- ContainerJudge.ask: arm root handled (unit "arm": call dir `judge-calls/<label>/arm/`, slug `<label>-arm-<digest>-<k>`, step 0); anon/ itself raises PermissionError instead of IndexError.
- Tests (RED first: 4 failed): real `check_mounts(mounts(...))` on `inputs_for(fit, arm)` (also in the transcript-evidence test); 7 parametrised negatives incl. `01/questions.md`; second-label negatives (setup file and transcript); ContainerJudge.ask on an arm-unit fit item with faked run_turn (mount set, call dir, slug); anon/ refused.
- `uv run pytest tests/runner/scoring -q` -> 573 passed, 6 skipped.
