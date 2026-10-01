# Dry-run validation

- results: {"dry1": {"completed": true}, "dry2": {"stopped_at": 2}, "dry3": {"halted": "{\n  \"reason\": \"same harness fault twice (design \\u00a79)\",\n  \"first\": {\n    \"at\": \"2026-10-01T05:35:12+00:00\",\n    \"pass\": \"dry3\",\n    \"arm\": \"dryrun-pinfault\",\n    \"step\": 1,\n    \"run\": \"a\",\n    \"attempt\": 1,\n    \"kind\": \"model-pin\",\n    \"signature\": \"claude-haiku-4-5\",\n    \"detail\": \"arm: assistant results/dry3/dryrun-pinfault/01/a/transcripts/a1/-work-bakeoff-specs-dryrun-pinfault/b45fce0b-b94e-4859-bc3f-546e03e79978/subagents/agent-1.jsonl."}, "dry4": {"completed": true}}
- secret findings (evidence + state, .gz decompressed): 0
- container specs built: 920; containing the token: 0
- leftover containers: 0

## What each pass proves (every gate must hold)

- ok: dry1 hidden counts — 1: 101/101 passed, 0 failed (want 101); 2: 109/109 passed, 0 failed (want 109); 3: 121/121 passed, 0 failed (want 121); 4: 135/135 passed, 0 failed (want 135); 5: 146/146 passed, 0 failed (want 146); 6: 151/151 passed, 0 failed (want 151); 7: 161/161 passed, 0 failed (want 161)
- ok: dry1 N.a/N.b sha_before — 1: c3e8c8415c = c3e8c8415c; 2: 6ecbf5e90e = 6ecbf5e90e; 3: 496e33dd4d = 496e33dd4d; 4: 1b97d8bdb7 = 1b97d8bdb7; 5: 0bc81c24ee = 0bc81c24ee; 6: e88a1d8c98 = e88a1d8c98; 7: 9c0028ee39 = 9c0028ee39
- ok: dry1 hand-edit probe — {"env_default": true, "flag_wins": true, "unchanged_without_env": true, "installed": true}
- ok: dry1 model pin — ok for every N.a and N.b
- ok: dry2 stop rule — stopped_at 2; reason 'no progress in 3 attempts'
- ok: dry3 halt rule — ledger [('model-pin', 'claude-haiku-4-5', 'rerun'), ('model-pin', 'claude-haiku-4-5', 'halt')]; HALTED present
- ok: dry4 transient retry — 1.b interventions ['transient-retry:API Error:  overloaded']
- ok: dry4 timeout owned by the arm — breaches [{'step': 2, 'breach': 'turn_seconds', 'owner': 'arm'}]
- ok: dry4 pause and resume — progress step 1 review 'pause'; resume.json {'paused_after': 1}; run-ended 1.b x1; last run-ended (7, 'b'); run-log lines skipped: 0

## dry1: N.a → reset → consistency check → N.b, per step

- step 1: N.a stopped at code; consistency check confirmed; N.b hidden 101/101 passed, 0 failed
- step 2: N.a stopped at approval; consistency check nothing-new; N.b hidden 109/109 passed, 0 failed
- step 3: N.a stopped at approval; consistency check nothing-new; N.b hidden 121/121 passed, 0 failed
- step 4: N.a stopped at approval; consistency check nothing-new; N.b hidden 135/135 passed, 0 failed
- step 5: N.a stopped at approval; consistency check nothing-new; N.b hidden 146/146 passed, 0 failed
- step 6: N.a stopped at approval; consistency check nothing-new; N.b hidden 151/151 passed, 0 failed
- step 7: N.a stopped at approval; consistency check nothing-new; N.b hidden 161/161 passed, 0 failed

## Task 18 PLAN-2 NOTE tests in dry1

- step 2: `tests/hidden/test_step2_sync.py::test_watch_picks_up_an_edit_to_an_included_file`: passed
- step 4: `tests/hidden/test_step4_lineage.py::test_cli_actor_defaults_to_the_login_user`: passed
- step 7: `tests/hidden/test_step7_remote_schema.py::test_remote_yaml_and_text_includes_load`: passed

**Result: PASS**
