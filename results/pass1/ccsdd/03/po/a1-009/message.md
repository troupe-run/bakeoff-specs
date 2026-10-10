Tasks approved. `spec.json` now has the tasks marked approved and `ready_for_implementation` set to true. That change is committed on `main` as commit `8db034c`, and the working tree is clean.

Start implementation with:

```
/kiro-impl config-get-show
```

Run without task numbers, it works through the plan task by task, each in its own subagent with an independent review, then validates the whole feature. The plan starts with 1.1, the move into `yaml_style`, which must pass `set`'s byte-exact tests unchanged before any `show` code is written. The step 3 work counts as delivered only once every task is committed on `main`.