Both specs are implemented, and **`uv run troupe config show / set / history` now works from the repository root**. Everything is committed on `main` (last commit `0291201`, working tree clean), nothing was pushed, and the final validation for config-set-writeback is **GO**.

**Fresh checks on the final commit:** 1,902 tests pass, and `mypy --strict`, ruff lint and ruff format are clean. I also ran a real theatre with a comment, a YAML include and a CRLF text include through the CLI:
- `show temperature` printed `0.2`.
- `set model claude-sonnet` kept the comment at its column: `model: claude-sonnet # which model`.
- Sets inside the included file changed only that file, and adding a key to its flow mapping gave `{tokens: 100, time: 30}`.
- Replacing a whole include exited 3. An impossible path exited 5. `show` on a mapping exited 5. Each error named the file and the path.
- `history agents.coder` listed the import events, then the two set events.
- Afterwards `.troupe/` held only the user's files and `history.sqlite`.

**How the run went:** each of the 32 tasks had its own implementer, independent reviewer, fresh checks and commit. Reviewers rejected and sent back five tasks:
- **2.4:** a `<<` key would have been written in a form the loader rejects.
- **2.5:** word-wrapping could break a line before a TAB, which changes the value.
- **3.2 and 5.2:** two tests that couldn't fail.
- **5.11:** one requirement mapped to the wrong test.

**Final validation first came back NO-GO** on two contract violations, which I fixed, reviewed and committed before it passed:
- **Folded values with indented lines:** any edit to a folded (`>`) value containing an indented line, such as a code sample, was refused. The contract only refuses edits that would *add* such a line. Unchanged indented lines are now kept byte for byte, and requirement 10.7 is amended to match.
- **Quoting after a merge:** when a merge deleted a mapping's last entry, new keys copied that deleted entry's quoting. They now copy the last remaining entry, or use plain style when none remains.

**Behaviours to know about:**
- **VALUEs starting with `-`:** `-1e3`, `-.inf` and `-x` are accepted. This relies on overriding a private part of Python's argument parser, which a future Python release could break; the tests would catch it. A VALUE that looks like a long option, such as `--theatre`, must come after `--`.
- **Wrapping:** a changed folded paragraph is re-wrapped at its old width. In the `$ troupe run` example, the last paragraph becomes `Then check the` / `output.` rather than one line, because the contract requires it.
- **Merging into a mapping that comes wholly from an include** is refused with exit 3 (contract rule 4).
- **Deleting a list item's compact first key** (`- name: a`) is refused with exit 3.
- **VALUE parsing:** VALUE is parsed as YAML, so a real trailing newline in a shell argument is dropped. To get a newline, write it as an escape: `"bye\n"`.

**Housekeeping and other changes:**
- I added `pytest-xdist` as a dev dependency so the suite runs in about 55 seconds instead of about 3 minutes. Plain `uv run pytest` still works.
- `.kiro/steering/structure.md` still says no code exists, and the `spec.json` files still say `tasks-generated`. Running `/kiro-steering` would update them.