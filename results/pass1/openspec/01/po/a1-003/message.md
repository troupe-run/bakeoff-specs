All 4 artifacts are done and all 26 tasks are checked off. The working tree is clean.

**Spec sync check:** the change has 5 delta specs. All are new capabilities with only ADDED requirements, and none has a main spec under `openspec/specs/` yet, so nothing blocks a sync. Syncing would create:
- `config-cli`: new main spec will be created (6 requirements)
- `config-loading`: new main spec will be created (3 requirements)
- `config-show`: new main spec will be created (2 requirements)
- `config-set`: new main spec will be created (15 requirements)
- `config-history`: new main spec will be created (4 requirements)

Each spec's `## Purpose` section becomes the purpose of the new main spec.

Implementation added two decisions after the specs were written: quoting new keys like `true`, and deleting the first entry of a compact `- key: v` item. Both are recorded in `design.md` and the README. Neither contradicts the spec text, so the specs can be synced as they are.

How do you want to proceed?
1. **Sync now (recommended):** create the five main specs, check them, then archive.
2. **Archive without syncing:** move the change to the archive and leave `openspec/specs/` empty.