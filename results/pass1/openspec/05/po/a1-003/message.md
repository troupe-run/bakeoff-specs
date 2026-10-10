I've planned CR-B as `config-set-in-include` in `openspec/changes/config-set-in-include/`. It passes `openspec validate --strict` and the plan is committed on `main` as `31fa98b`. No project code has changed yet; CR-B is done only once its implementation is committed on `main`.

It builds on CR-A (`config-include-overrides`), which isn't implemented yet. CR-A has to be applied first, so its first task checks for that.

**Artifacts:**
- **`proposal.md`**: `set PATH VALUE --in-include` writes new keys into the shared included file, using the original step-1 rule. Like `--reason`, the flag can go anywhere after `set`.
- **Spec changes:**
  - `config-cli`: the invocation line now lists `[--in-include]`, with a new scenario for the flag and one where an extra argument exits 2.
  - `config-set`: a new requirement, "Writing new keys into the included file on request", with exact before/after file contents for each case.
- **`design.md`**: the flag is passed down to the single function from CR-A that decides where a new key goes, and turns the override off there. The key then goes into the innermost file that holds its parent section.
- **`tasks.md`**: a check that CR-A is done, then the flag and the placement rule with their tests and README updates, then the final test run and commits. CR-A gets archived before this change.

**Choices I made where the contract is silent:**
1. **Only new keys are affected.** The contract only talks about new keys. Existing values still follow CR-A: an overridden value is changed in the override. Otherwise the flag could write a value that an override then hides.
2. **With no include involved, the flag is accepted and changes nothing.** The step-1 rule picks the same file there anyway. Refusing would force scripts to check for includes before passing the flag.
3. **When the section is partly in the included file and partly in an override, the key goes into the included file.** That is where the shared content lives. A section that exists only in an override has no included file, so the key goes into the override's file, which is what the step-1 rule gives.
4. **With nested includes, the key goes into the innermost included file** (e.g. `agents/limits.yaml`). That's the file that holds the parent section.
5. **No new exit codes, and history is unchanged.** The flag changes where a key is written, not what the value is, and history records values, not files.

The artifacts are ready for review. When you're ready, run `/opsx:apply`: CR-A first, then this change.