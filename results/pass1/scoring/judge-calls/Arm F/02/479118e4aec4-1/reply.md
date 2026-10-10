```json
{"score": 3, "evidence": ["repo/src/troupe/cli.py:45", "repo/spec/002-config-file-sync/contracts/cli.md:12", "repo/spec/002-config-file-sync/spec.md:252-254", "repo/tests/e2e/test_usage.py:56-65", "repo/tests/e2e/test_watch_lifecycle.py:98-102", "repo/spec/001-config-load-show-set/spec.md:156", "repo/README.md:9-12"]}
```

```json
{"score": 3, "evidence": ["repo/src/troupe/cli.py:45", "repo/spec/002-config-file-sync/contracts/cli.md:12", "repo/spec/002-config-file-sync/spec.md:252-254", "repo/tests/e2e/test_usage.py:56-65", "repo/tests/e2e/test_watch_lifecycle.py:98-102", "repo/spec/001-config-load-show-set/spec.md:156", "repo/README.md:9-12"], "notes": "The step-2 contract and spec D-11 say what --theatre defaults to: the flag first, then $TROUPE_THEATRE, then the current directory. Tests cover the env default, the flag winning and an empty value falling back. But the step-1 FR at spec 001:156 still says the default is the current directory only, the README omits the variable, the spec never mentions the empty-value case, and nothing records that the behaviour came from outside the workflow."}
```