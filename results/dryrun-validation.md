# Dry-run validation

- results: {"dry1": {"completed": true}, "dry2": {"stopped_at": 2}, "dry3": {"halted": "{\n  \"reason\": \"same harness fault twice (design \\u00a79)\",\n  \"first\": {\n    \"at\": \"2026-09-29T18:29:48+00:00\",\n    \"pass\": \"dry3\",\n    \"arm\": \"dryrun-pinfault\",\n    \"step\": 1,\n    \"run\": \"a\",\n    \"attempt\": 1,\n    \"kind\": \"model-pin\",\n    \"signature\": \"claude-haiku-4-5\",\n    \"detail\": \"arm: assistant /Users/martin/Projects/troupe/bakeoff-specs.wt-t24/results/dry3/dryrun-pinfault/01/a/transcripts/a1/-work-bakeoff-specs-dryrun-pinfault/fa1e8bb0-1130-468d-bdbf-0fea17105c47/subagents/agent-1.jsonl.g"}, "dry4": {"completed": true}}
- secret findings (evidence + state, .gz decompressed): 0
- container specs built: 865; containing the token: 0
- leftover containers: 0

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
