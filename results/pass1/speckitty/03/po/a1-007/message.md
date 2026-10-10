`troupe config get` and the new `troupe config show [PATH] [--sources]` are done and merged into `main` (merge commit `a589041`). Nothing was pushed and no pull request was opened. On `main` before the merge, all 1528 tests passed and type checking, lint and format checks were clean.

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
- **Open beads issues from this mission:**
  - P4 bug: mapping keys longer than 1024 characters can't be printed as valid YAML. That's a YAML limit the contract doesn't cover, so it needs your decision.
  - P4: a docstring in `src/troupe/yamlcore.py` says no other module imports the YAML library; the new renderer now does.
- **Leftover cleanup:** the mission's coordination branch couldn't be deleted because its worktree is still checked out at `.worktrees/troupe-config-get-show-01M411XB-coord`. Nothing depends on it.
- Spec-kitty suggests a post-merge mission review (`/spec-kitty-mission-review`) as the next step; I haven't run it.