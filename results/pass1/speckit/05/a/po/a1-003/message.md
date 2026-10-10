I've written the CR-B spec and committed it on `main` as `5e2767c`. Nothing was pushed. It's a spec only: CR-A's code isn't written yet, and CR-B builds on it.

- **Feature directory**: `specs/006-set-in-include`. `.specify/feature.json` now points here (it's gitignored).
- **Spec file**: `specs/006-set-in-include/spec.md`
- **Checklist**: all items pass on the first check, with no open questions.
- **Extension hooks**: none are registered, so none ran.

**What the spec says:**
- **The new option:** `set --in-include PATH VALUE` writes a new key under an included section into the included (shared) file, the way step 1 did. The file containing the include is left unchanged, and a one-line include is not converted to the `$ref` form. Without the option, CR-A's rules apply unchanged.
- **Combining:** it works alongside `--reason` and `--theatre` and is recorded in history like any other `set`.
- **Other commands:** using it on any other command is a usage error (exit 2).

**Choices I made where the contract was silent (D-50 to D-54):**
- **Only new keys are affected.** Existing values and list appends behave the same with or without the option. An overridden value is never written into the shared file, because the override would hide it there.
- **No include on the path is not an error.** The step 1 rule names the same file the default rule does.
- **Ancestor that exists only as an override:** if an override adds a section (say `limits`) that the shared file lacks, the key still goes into the shared file. The section is created there and merges with the override.
- **Chains of includes:** the key goes into the innermost file, the one the content actually comes from.

I also added a three-line note to CR-A's spec at its new-key rule, saying `--in-include` is the exception, so the two specs agree.

**Next:** `/speckit-plan`. This will also need a small addition to CR-A's plan: the planner's choice of where a new key goes will take the flag into account. After that, run `/speckit-tasks` covering both change requests.