Convergence isn't clean: it found five gaps, and I added five tasks (T028–T032) as Phase 9 at the end of `specs/007-remote-includes-schema/tasks.md`. I committed that to `main` (`e50bc88`). Nothing else changed: no spec, plan, existing task or code.

**The gaps:**
- **`watch` keeps fetching a failing URL (T029, HIGH).** While a fetch is failing, `watch` retries on every 0.2-second poll. I measured 15 fetches of the failing URL in 3 seconds. That contradicts D-65, which says `watch` does not poll URLs. The fix is to retry only after a local file changes, with tests.
- **Three working behaviours have no tests (T028, CRITICAL).** The constitution requires a test for every behaviour. The three are:
  - the read-only refusal through a `$ref` (mapping-form) remote include, which I checked by hand: exit 3, naming line 3;
  - `!literal` on a folded (`>`) value;
  - a `$dynamicRef` pointing outside the schema.
- **`set --include` refuses instead of removing the tag on some values (T030, MEDIUM).** On a `!literal` block or empty value it exits 3, but FR-644 says the tag must be removed. That refusal is also untested.
- **Nested fetch failures don't name the local include line (T031, LOW).** When a remote file included from another remote file fails to fetch, the error names only the remote file that includes it. FR-602 asks for the local file and line too.
- **Some implementation decisions aren't recorded (T032, LOW).** These are keeping `!literal` tags when expanding an alias, the `types-jsonschema` dev dependency, and the choices T029 and T030 will make. They should go in `research.md`.

**What was checked:**
- 37 functional requirements and 7 success criteria
- 32 acceptance scenarios and 22 edge cases
- 8 plan decisions and research decisions U-1 to U-12
- constitution principles I–VI

No extension hooks are registered for this step, so none ran.

Next step is `/speckit-implement` for T028–T032. Another `/speckit-converge` run afterwards should come back clean.