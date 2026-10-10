Both features validate **GO** at the current HEAD (`0291201` on `main`). The working tree is clean, and the validation changed nothing.

| | config-foundation | config-set-writeback |
|---|---|---|
| Tasks | 20/20 done, none blocked | 32/32 done, none blocked |
| Requirements traced to tests | 10/10 sections | 16/16 sections (all 99 criteria) |
| Tests | 1,902 pass, in parallel and serially | 1,902 pass |
| mypy `--strict`, ruff lint, ruff format | clean | clean |
| Real CLI from the repo root | `show`/`history` work | `set`/`show`/`history` work |
| Own contract probes | about 40, all pass | 57, all pass |

**Did adding `set` disturb the foundation?** No. Since config-foundation was last validated, none of its modules changed. The only edits are the planned registration of `set` in `src/troupe/cli/main.py` and a matching line in its registration test. `show` and `history` behave exactly as before, including a value like `-x`.

**What the `set` probes covered:** includes inside lists, CRLF files with flow collections, a BOM with new keys, block scalars inside list items, comment columns with multi-byte characters, `history` filters after removals, and failures part-way through writing two files. Every probe was checked byte for byte across all files and directory listings, with values read back through `show`.

**Small points, none blocking:**
- **Undocumented dependency change:** I added `pytest-xdist` to `pyproject.toml` (dev dependency only), although the set design says that file isn't modified. The design should record this.
- **Private argparse API:** `set` accepts VALUEs like `-1e3` by overriding a private part of Python's argument parser. It works and is tested, but a future Python release could break it.
- **Recording-failure path not probed:** the case where saving to history fails mid-`set` is covered only by the existing tests, not by an end-to-end probe.
- **Stale documentation:** both `spec.json` files still say `tasks-generated`. The design's list of test file names doesn't match the actual files, and `.kiro/steering/structure.md` still says no code exists. `/kiro-steering` would refresh the steering file.