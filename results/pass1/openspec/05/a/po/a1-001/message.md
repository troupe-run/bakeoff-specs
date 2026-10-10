I've planned the change `config-include-overrides` in `openspec/changes/config-include-overrides/`. It passes `openspec validate --strict`, and I committed the plan on `main` as `b435bae`, as earlier changes did. I haven't written any code yet.

**What it plans:**
- **Mapping-form includes:** a mapping with a `$ref` key holding an include string, whose other keys are overrides deep-merged over the included content.
- **New keys under an include:** these go into the including file as overrides. A scalar-form include is first converted to mapping form, exactly as in the contract example (`coder:  # c` / `  $ref: …` / `  temperature: 0.3`).
- **Lists:** appending a list item, or adding a key inside a list item, still writes to the file that holds the list.
- **Existing values:** an overridden value changes in the override; any other value changes where it is written, even in a shared file.
- **Exit 4:** loading fails when a text include has overrides, or when overrides sit on included content that isn't a mapping.

**Artifacts:**
- **`proposal.md`:** why the change is needed, what changes (new-key placement under includes is a breaking change for `set`), and which code is affected.
- **Specs:**
  - `config-loading` gets one new requirement for mapping-form includes and how they merge.
  - `config-set` changes three requirements ("Creating new keys", "Target file for an existing value", "Refusing to replace an include"). It also extends "Values that are includes" to cover mapping form.
  - `config-set` adds four requirements: overrides for new keys, converting a scalar-form include, new keys and lists under an include, and deleting keys of an overridden mapping.
  - Every scenario gives the exact file bytes before and after.
- **`design.md`:** the loader stores each merged mapping's layers and where each mapping was written. One new module, `edit/target.py`, decides which file every write goes to. Read-back verification still refuses any write that doesn't reload as intended.
- **`tasks.md`:** 16 tasks in 4 groups (loading, where writes land, tests for `set`, then README and checks). Each task says how to verify it.

**Decisions the contract left open** (listed in `design.md` for the product owner to review):
1. **Nested includes:** I followed the contract literally, so a new key goes into the file holding the innermost include reference. That file can itself be a shared file. Writing into the outermost non-included file instead would be a one-function change.
2. **Deleting a merged key:**
   - A key only in the override is deleted there, and override mappings left empty are removed.
   - A key only in the included file is deleted there.
   - A key in both is refused with exit 3.
3. **`$ref` that isn't an include:** a `$ref` key whose value isn't a `file:` string stays an ordinary key.
4. **Breaking for existing files:** a mapping that already has a `$ref: file:…` key will now load as an include. Before this change it was ordinary data.
5. **Conversion limits:**
   - An include string that spans lines, or is written as a block scalar, is refused (exit 3) rather than rewritten.
   - A mapping-form include is never converted back to scalar form.

The artifacts are ready for review. When you're ready, run `/opsx:apply`.