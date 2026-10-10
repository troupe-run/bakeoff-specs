## Validation Report: config-remote-schema

Step 7 is ready. The full suite passes on the committed code, all 18 tasks are done, and nothing is blocked.

- **DECISION: GO**
- **MECHANICAL_RESULTS:**
  - **Tests: PASS.** `uv run pytest -n auto -q` gave 4347 passed, exit 0. `mypy --strict` is clean (173 files), and `ruff check` and `ruff format --check` are clean.
  - **TBD/TODO grep: CLEAN.** I checked every file under `src/` and `tests/` changed since the discovery commit `cb78611`.
  - **Secrets grep: CLEAN.** It matched 5 lines, but all are YAML alias variables named `token`, not credentials.
  - **Smoke boot: PASS.** `uv run troupe config --help` and `set --help` both run, and `set --help` lists `--include`. Earlier in this session I also ran the contract scenarios through the real CLI against a local HTTP server.
- **INTEGRATION:**
  - **Cross-task contracts: OK.**
    - Include recognition is decided only in `config/includes.py`.
    - Every include string is built only by `IncludeRef.string`.
    - The literal check made while loading and the marks put on VALUE strings in `set` use the same schema lookup (`uri_format_at`).
    - The read-back after a `set` reuses remote content already fetched, by its URL.
  - **Shared state consistency: OK.**
    - A failed fetch, a bad schema or an invalid configuration creates no history state and changes no file.
    - A refused `set` leaves files byte-identical and records no event.
  - **Boundary audit: OK.**
    - The network is reached only from `config/fetch.py`, the only module that imports `urllib.request`.
    - The core modules (`loader`, `schema`, `fetch`, `includes`, `model`) import nothing from `writeback` or `cli`.
    - The temporary blanket refusal from task 2.4 is gone. The `write_atomically` backstop that never writes a remote source is kept, as the design says, and a test pins it.
- **COVERAGE:**
  - **Requirements mapped: 10/10 sections.** Every ID from 1.1 to 10.4 is named in a test docstring, and no test names an ID that doesn't exist.
  - **Coverage gaps:** none.
- **DESIGN:**
  - **Architecture drift: minor, and recorded.**
    - The remote write guard sits at `_Planner._add` and `_replace_file` instead of `_layout`. A guard in `_layout` would also refuse unchanged remote entries next to a changed local override. This is recorded in `design.md` and in `research.md` Decision 5.
    - Five writeback files had small changes the File Structure Plan doesn't list. Their error messages now name a source by its URL or path as shown to the user, and tagged strings are kept on one line.
  - **Dependency direction:** no violations.
  - **File Structure Plan vs actual:** matches, apart from those five small changes.
- **OWNERSHIP:** LOCAL
- **UPSTREAM_SPEC:** N/A
- **BLOCKED_TASKS:** none. Every Implementation Note in `tasks.md` is resolved.
- **REMEDIATION:** none required.

The feature is validated end to end and committed on `main`. No further step is needed for step 7.