I've written the plan for step 1 as the OpenSpec change `config-load-show-set` and committed it on `main` (commit `27b502e`). No code is written yet, so the delivery itself, a working CLI on `main`, is not done. `openspec validate --strict` passes on the plan.

**What's in `openspec/changes/config-load-show-set/`:**
- **`proposal.md`**: why this is needed, what's being built, and five capabilities: `config-cli`, `config-loading`, `config-show`, `config-set` and `config-history`.
- **`specs/…/spec.md`**: one spec per capability, covering every section of the contract. Each rule has test scenarios, most of them giving the exact file bytes before and after a `set`.
- **`design.md`**: how it will be built, including the module layout, the event store, and how edits are made and checked before writing.
- **`tasks.md`**: 9 groups, 22 tasks. Each task names the test that proves it's done.

**Approach:**
- **Parsing:** ruamel.yaml is used only to read files and locate each value in the text. A quick test showed its "YAML 1.2" mode treats `2001-01-01` as a date and `1_000` as a number, so the plan includes our own strict core-schema type rules.
- **Writing:** `set` changes only the bytes of the value in the original text. Before anything is written, the edited files are reloaded and checked against the intended result. Any mismatch exits 3 with no file changed.
- **Event store:** `eventsourcing` with SQLite, stored at `.troupe/events.sqlite`. Nothing is created if the config fails to load.

**Decisions the contract left open** (listed in `design.md`; tell me if any should change before implementation):
1. A null or scalar parent (e.g. `agents:` with no value) is not a mapping, so `set agents.coder x` exits 5.
2. A digit segment that would need a missing parent created exits 5.
3. An empty or comment-only config file counts as an empty mapping.
4. A string `VALUE` starting with `file:` becomes an include. If the config then can't load, the write is refused with exit 3.
5. Setting a mapping or list on a mapping or list applies only the differences: unchanged entries keep their bytes and missing keys are deleted. Changing or deleting an included value through a parent path exits 3.
6. Any command imports a theatre the first time its config loads, and the import is kept even if that command then exits 3 or 5.
7. `show` and the `old` values in `set` events come from the files as they are now, so hand edits show up there. Hand edits themselves still don't create events.
8. `history PATH` with no matches prints nothing and exits 0. `.inf` and `.nan` appear in the JSON as strings.
9. Anchors, aliases and non-standard tags fail to load with exit 4 until step 6.

The artifacts are ready for review. When you are ready, run `/opsx:apply`.