I've written the CR-B plan and design docs and committed them on `main` as `8faa069`. Nothing was pushed. No code has changed yet. No extension hooks are registered, so none ran. Every principle passes the constitution check before and after design, with no exceptions to justify.

**Artifacts** (in `specs/006-set-in-include/`):
- `plan.md`
- `research.md`: four decisions, I-1 to I-4
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

**The design** treats `--in-include` as a second option inside CR-A's single "where does a new key go" decision:
- **CLI to planner:** a placement value (`"override"` by default, `"include"` with the flag) is passed from `cli.py` down to the planner. Other commands don't define the option, so it is rejected there with exit 2 without any extra code.
- **Merged sections:** where an override is merged into a section of the shared file, the in-memory tree now also keeps the shared file's own version of that section (`LocatedMapping.base`). That lets the planner reuse step 1's new-key writer unchanged: the key goes after the shared file's last entry, in its style and indentation. I recorded this field in CR-A's `data-model.md` too, so the two designs agree.
- **Choosing the target:** with the flag, the planner walks up from the deepest existing section and picks the first one that exists in the shared file. Sections that exist only as overrides are skipped. Lists, existing values and appends never reach this choice, so they behave the same with or without the flag.
- **Safety check:** this is step 1's. A shared file included twice gains the key in both places. A key that an override would hide is refused with exit 3.

**Next:** `/speckit-tasks`, covering CR-A and CR-B in order, since CR-B is a branch inside CR-A's code.