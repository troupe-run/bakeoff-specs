# Step 3 — `get` for values, `show` for anything

We are changing `show`. From now on:
- `troupe config get PATH` prints a single value — what `show` used to do.
- `troupe config show [PATH]` prints either a value or a whole section as YAML, and with `--sources` says
  which file each value comes from.

Contract sections added: get and show (replaces "show PATH (step 1 and 2)").
