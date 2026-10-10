The spec covering both change requests (CR-A and CR-B) is written and committed on `feat/troupe-config-include-overrides`. Nothing is on `main` yet: that only happens after plan, tasks, implementation and the merge.

- **Mission:** `troupe-config-include-overrides-01M46FY4`. CR-B is folded in here rather than started as a separate mission.
- **Files:** `kitty-specs/troupe-config-include-overrides-01M46FY4/spec.md`, plus `checklists/requirements.md`.
- **Commits:** `b221059` (spec, meta, checklist) and `1493d5e` (decision records). Nothing pushed, no PR.
- **Branches:** we started on `main`; planning is on `feat/troupe-config-include-overrides`, which gets merged into `main` at the end, as with the previous four missions.

**What the spec says**

- **Mapping-form includes:** an include can be a mapping with a `$ref` key and override keys. Reads (`get`, `show`, `show --sources`, history, reconcile) all see the merged value, and override values are credited to the including file.
- **New keys under a shared section (CR-A):** they're written as overrides in the including file nearest the key's deepest existing ancestor (your answer to Question 1). A plain `file:` include is first converted to mapping form, keeping its end-of-line comment. The shared file isn't touched.
- **`set --in-include` (CR-B):** this puts a new key in the shared file instead, using the step-1 rule.
- **Existing values and lists:** these still change in the file that holds them. `--in-include` has no effect on them.
- **Errors:** a mapping-form include of a non-YAML file with extra keys exits 4. Replacing a whole include still exits 3.

**My choices where the contract is silent**

The spec records nine (D-1 to D-9) with reasons, as you asked. The ones worth checking:

- **D-1:** a `$ref` whose value isn't an include string exits 4 (your delegated Question 2).
- **D-6:** a `set` path containing a `$ref` segment exits 3, so a mapping can't be silently turned into an include or retargeted.
- **D-7:** overrides on an include whose YAML content isn't a mapping exit 4.

The others cover flow-style and list-item conversion, where `$ref` goes, preserving bytes, and where keys go when an ancestor exists in both the include and an override.

The quality checklist passed on the first pass, `decision verify` reports nothing outstanding, and the prerequisites check is valid. Next step is `/spec-kitty.plan`.