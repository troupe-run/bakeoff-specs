config-foundation is built and committed on `main`, and the final validation result is **GO**. `uv run troupe config show PATH` and `uv run troupe config history [PATH]` now work from the repository root. **`set` does not exist yet**; it belongs to the second spec.

**Checks, run fresh on the final commit:** 724 tests pass, and `mypy --strict`, ruff lint and ruff format are clean. `uv run troupe config --help` and real `show`/`history` runs against a sample theatre behave correctly. The validator also ran about 40 of its own probes against the contract, and all passed:
- Missing, duplicate or unloadable config files exit 4.
- A mapping, a list or a missing path exits 5.
- A text include prints byte for byte, including CRLF.
- History lines are strict JSON with `seq` counting from 1.
- A hand edit shows in `show` but adds no history event.
- After each command the only state is `.troupe/history.sqlite`, and user files keep identical bytes.

**How the run went:** all 20 sub-tasks went through implementer → independent reviewer → fresh checks → one commit each, from `e6d5ee7` to `0502077`. One review rejected a change: task 5.2 had added large-number handling for a case the history store already blocks, so it was simplified back to the design. I asked for one fix before review: an empty PATH used to print a message starting with ": ". No task was blocked. Every module the `set` spec builds on exists with the agreed signatures.

**Two problems to handle in `set`.** I've written both into config-set-writeback's implementation notes:
- **Values starting with `-`:** the argument parser treats `-1e3`, `-.inf` or `-x` as options and exits 2. Plain `-1` and `-0.5` work.
- **A type annotation that would crash the CLI:** copied as written from the `set` design, it fails when the module loads on Python 3.12, which would break every command. It needs to be quoted, as in `main.py`.

**Choices to know about:**
- `--theatre` is only accepted after the subcommand, as in the contract's `troupe config <subcommand> --theatre <dir>`.
- A file containing only `---` or `~` exits 4 rather than counting as an empty configuration.
- YAML allows a tab right after `key:`, but the parser we use (`ruamel.yaml`) rejects it, so such a file exits 4.

**Housekeeping:** `spec.json` still says `tasks-generated`, and `.kiro/steering/structure.md` still says no code exists. The full test suite takes about 95 seconds because the end-to-end tests run the real CLI in subprocesses.

**Next:** run `/kiro-impl config-set-writeback` (32 tasks) to build `set`.