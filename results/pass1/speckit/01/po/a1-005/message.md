The convergence check found three gaps. I appended three tasks as **Phase 7: Convergence** in `tasks.md` (T051–T053) and committed that as `ca25f94` on `main`. No code was changed in this step.

- **T051 (critical):** if `.troupe/` can't be written, `troupe config set` exits 1 with a raw SQLite traceback. That breaks the documented exit codes, and the message doesn't name the file. The task maps storage and write failures to exit 3 or 4 with the file named.
- **T052 (critical):** `set` replaces a read-only `troupe.yml` anyway, because replacing a file only needs permission on its directory, not on the file. The task makes `set` refuse with exit 3 instead.
- **T053 (low):** accepting `--theatre` before the subcommand is my addition, not something the contract asks for. The task is to record it as a decision in the spec or remove it.

Everything else matched the spec: show, set (including through includes), history and event behaviour all worked as specified in the probes.

No extension hooks are registered for this step. Next step: run `/speckit-implement` to complete T051–T053; another converge run afterwards should find nothing left.