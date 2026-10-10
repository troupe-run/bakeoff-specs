Both decisions are implemented and committed on `main`, ending at `c9df576`; nothing was pushed. On the final state, the full suite passes (3251 tests), mypy and ruff are clean, and new criterion 4.8 is named by a test.

- **Own include string over overrides (choice 16, commit `28122c7`).** This is now refused with exit 3. The reason is recorded as Decision 10 in `research.md`: dropping or changing the overrides changes a value that comes wholly from an include, which choice 8 and rule 4 refuse, and a silent no-op would hide that the overrides were kept. The rule covers these cases:
  - **Refused:** the bare `file:` string, `{$ref: <same string>}`, and any other set of overrides all exit 3, name the PATH and the included file, and change nothing.
  - **No-op:** a VALUE with exactly the written overrides changes nothing.
  - **Still a no-op:** the same string over an include that has no overrides (config-set-writeback 2.8).
  - **Side effect:** a VALUE that adds an override to a scalar-form include, such as `{$ref: <same>, k: v}`, is also refused with exit 3, even when the included file already holds `k: v`. This follows the updated 7.5 wording.
- **Shared middle file (choice 17, commit `c9df576`).** The override is now written in the middle file and appears at every place that file is included. History records a `set` event for each place, and the read-back check still compares exactly. I added criterion 4.8 and Decision 11.

**Where I limited choice 17.** I applied it only to keys placed by the override rule. These cases still keep the step-1 refusal for shared files (exit 3, nothing changed):
- changing an existing value in a shared file;
- `--in-include` into a shared file;
- a new key inside a list item of a shared file;
- one VALUE that adds keys at two places of the same shared file.

The list-item case is the one most open to question. The contract writes it in the file holding the list, and your reasoning ("it appears in both, like any other content of that file") would apply there too. Tell me if you want any of these to follow choice 17 as well.