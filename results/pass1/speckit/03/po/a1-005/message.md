Convergence found remaining work, so I added two tasks as **Phase 7: Convergence** at the end of `specs/003-config-get-show/tasks.md` and committed it (8cfe423). Nothing else in `tasks.md`, the spec, the plan or the code was changed.

- **T022 (HIGH):** `show` prints YAML that won't parse when a text starts with a line of only spaces (e.g. `"    \nabc\n"`). The fix goes in `needs_indent_indicator` in `src/troupe/config/edit/render.py`. `set` uses the same function, so the task also adds a `set` test for such a value.
- **T023 (LOW):** add a test for the "same file included twice" case. It already works correctly; it just has no test.

No extension hooks are registered for this step.

Next: run `/speckit-implement` to do T022 and T023, then `/speckit-converge` again to confirm nothing is left.