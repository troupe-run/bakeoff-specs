I've written the CR-B plan and committed it on `main`. There were no extension hooks to run, every constitution check passes, and nothing needs clarifying.

**Plan:** `specs/006-set-in-include/plan.md`
**Other documents:** `research.md` (choices I-1 to I-5), `data-model.md`, `contracts/cli.md`, `quickstart.md`.

**Design in brief:**
- **The flag:** `--in-include` is a plain on/off flag on `set`. The argument parser rejects it on other subcommands and rejects it with a value (exit 2), before anything is loaded.
- **Where it acts:** it is passed down to the single function from CR-A that decides where a new key goes. That function is the only code that reads it. Existing values, list appends and keys inside list items never reach that function, so the flag can't affect them (D-50).
- **Sections with keys from both files:** these will keep a reference to their original, unmerged section from the shared file. With the flag, the new key is laid out there using step 1's rules unchanged. With nested includes, it goes to the deepest file.

**Change to CR-A's plan** (committed separately as `c7595fa`): CR-A's plan had the check before each write identify every include by its reference. That would refuse a new key written into a file included at two keys, which step 1 allows and `--in-include` depends on. Now only override writes are checked by reference; everything else keeps step 1's check. I amended CR-A's `research.md` (O-6) and `plan.md` for this.

**Commits:** `2d319c9` (CR-B spec), `c7595fa` (CR-A fix), `a83fa90` (CR-B plan).

CR-B is designed to be implemented together with CR-A. Next step is `/speckit-tasks`. `.specify/feature.json` points at 006, so it would generate CR-B's tasks; CR-A (005) still needs its own tasks.