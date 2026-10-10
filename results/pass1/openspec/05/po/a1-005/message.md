Artifacts and tasks are complete: 4/4 artifacts done, 17/17 tasks checked, and the working tree is clean. Neither the archive context nor guidance adds anything that changes this workflow.

**Spec sync assessment.** All four main specs exist, and none has this change applied yet:

| Capability | What the sync would apply |
|---|---|
| `config-loading` | **Add** "Mapping-form includes and overrides" |
| `config-set` | **Add** "New keys under includes are written as overrides". **Modify** "Target file for an existing value", "Refusing to replace an include", "Setting a collection value", "Creating new keys" and "Appending to lists"; every existing scenario is kept, and the scenario "New key inside an included mapping" now expects an override. |
| `config-show` | **Modify** "Show sources": overridden values name the overriding file, plus one new scenario |
| `config-sync` | **Modify** "Includes added by hand are followed": mapping form and overrides, plus three new scenarios |

Nothing is sync-blocked: no delta removes or renames requirements.

After archiving, I'll also update the README's link to this change's `design.md`, because the archive moves it under `archive/2026-10-05-config-include-overrides/`.

How do you want to proceed?
1. **Sync now (recommended)**: merge the deltas into `openspec/specs/`, check the result, then archive. Earlier changes were archived this way.
2. **Archive without syncing**