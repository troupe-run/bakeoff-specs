## Scored run

### Question 1 (next_command, answered by po)

Arm asked: I've written the plan for step 7 as the method change `config-remote-includes-and-schema` and committed it to `main` (`e55580c`); nothing was pushed. `method validate --strict` passes. No code has changed yet, so the step isn't delivered until it's implemented.

The artifacts are in `spec/changes/config-remote-includes-and-schema/`:
- **`proposal.md`**: why the change is needed and what it changes, including one breaking change (below).
- **`spec/`**: a new `config-schema` capability, plus changes to `config-loading`, `config-set`, `config-show`, `config-cli` and `config-sync`. Each case has a concrete scenario.
- **`design.md`**: how it will be built, and the choices made where the contract is silent.
- **`tasks.md`**: 7 groups of tasks, each with its own tests and README updates, ending with the full test, type and lint run, then commit and archive.

**Breaking change:** today `set prompt file:p.md` creates an include. Under the new rule it writes `prompt: !literal file:p.md`. `--include` gives the old behaviour, and three existing tests will be updated to pass it.

**How it will work:**
- **Includes:** one new module decides what counts as an include (prefix, `!literal` tag, schema).
- **Never writing to a URL:** fetched content is kept apart from the local files troupe writes back. Any edit that would land in it is refused with exit 3, from one check in the write step.
- **Fetching:** each URL is fetched at most once per command, even though `set` reloads the configuration several times.
- **Dependency:** adds `jsonschema` for 2020-12 validation. Fetching uses the standard library.
- **Tests:** they use a real local HTTP server and real schema files on disk.

**Choices the contract leaves open (I chose; please override any you disagree with):**
1. A `file:` include inside fetched content resolves against that content's URL, so shared config can never read the user's local files.
2. The literal rule covers every include-looking string in a mapping or list VALUE, not just a single string, so a list of URLs can't silently trigger fetches.
3. `--include` on a path the schema marks `format: uri` is refused with exit 3, rather than quietly writing a literal.
4. Setting an include to its own string without `--include` is refused with exit 3, because it asks for a literal string in place of the include. With `--include` it does nothing, as before.
5. A `!literal` tag stays when its value changes to another string, and is removed when the value becomes a number, boolean, null or collection.
6. The refusal message names the outermost include written in a local file, since that's the only line the user can edit. New keys under nested remote includes become overrides next to that include.
7. Fetching: 30-second timeout, redirects followed only to http/https, a 2xx response and UTF-8 body required, nothing cached between commands.
8. `watch` also watches the schema file but doesn't poll URLs. Remote changes show up at the next reconcile, recorded like hand edits.
9. The schema is always read as 2020-12. `format` isn't checked, and any `$ref` pointing outside the schema file is refused (exit 4), so nothing is fetched for it.
10. `show --sources` names a remote value's source by its URL.

The artifacts are ready for review. When you're ready, run `/method-command`.

Reply: /method-command

### Question 2 (step_done, answered by runner)

Arm asked: ## Implementation complete

Step 7 (remote includes and a schema) is built and committed to `main` as 8 commits, from `273bd08` to `b813885`. Nothing was pushed. All 30 tasks are done, the change is archived, and its specs are merged into `spec/spec/`.

On the final run, all 773 tests passed and mypy, ruff and strict spec validation were clean.

**What now works:**
- **Remote includes:** `https://` and `http://` strings are includes, in plain form or as `$ref`. Each URL is fetched at most once per command. A failed fetch exits 4 and names the URL.
- **Remote values are read-only:** any change to them exits 3. The message quotes the include line in your own file, with the file name and line number, for example `… included by https://… in .troupe/troupe.yml line 3: change that include line instead`. New keys still become local overrides.
- **Schema:** `.troupe/troupe.schema.json` marks `format: uri` settings as plain strings, so they are never fetched. The configuration must be valid against it (exit 4 when loading, exit 3 for a `set`), and `watch` also watches this file.
- **`!literal`:** the tag now loads instead of failing. `set` writes include-looking values with it unless `--include` is given. This is the breaking change from the plan, and the README has an upgrade note.

**Where I departed from the plan, all recorded:**
- I put the `Literal` marker in `schema.py` rather than `edit/scalars.py`. design.md now says so.
- I renamed `include_target` to `include_string`, since it now returns the whole include string rather than just its target.
- I corrected two spec examples to match the existing rule that end-of-line comments keep their column. The behaviour was right; my written expectations were wrong.

**Choices you may want to revisit:** the ten points the contract left open are now README decisions 48–61. Each would be a small change in one place if you disagree.

Reply: /method-command

### Question 3 (step_done, answered by po)

Arm asked: There's nothing left to archive. `config-remote-includes-and-schema` was archived at the end of the apply run, and there are no other active changes.

## Archive Complete

**Change:** config-remote-includes-and-schema
**Schema:** spec-driven
**Archived to:** `spec/changes/archive/2026-10-08-config-remote-includes-and-schema/`
**Specs:** ✓ Synced to main specs
- New capability: `config-schema`.
- Updated: `config-loading`, `config-set`, `config-show`, `config-cli` and `config-sync`.
- Strict validation of all 9 main specs passes.

All 4 artifacts and all 30 tasks are complete. The archive is committed on `main` as `b813885`, and the working tree is clean. Nothing was pushed.

When syncing, the archive dropped the note explaining what `<base>` means in the scenarios, because it sat outside the requirement blocks. I added it back by hand to the Purpose sections of `config-loading` and `config-set`.

Reply: 

## Discovery run

### Question 1 (next_command, answered by po)

Arm asked: I've written the plan for step 7 as the method change `config-remote-includes-and-schema` and committed it on `main` (b7f6525). It passes `method validate --strict`. No project code has changed yet.

**Artifacts** (in `spec/changes/config-remote-includes-and-schema/`):
- **`proposal.md`**: why the change is needed, what changes (including one breaking change), and which code it affects.
- **Delta specs** for five existing capabilities:
  - `config-loading`: URL includes, the `!literal` tag, and the schema (which strings count as literals, and validation on load).
  - `config-set`: how include-like strings are written, `--include`, refusing changes to remote values, and refusing changes that make the configuration invalid.
  - `config-show`: `--sources` names a remote value by its URL.
  - `config-cli`: the new `--include` flag.
  - `config-sync`: `watch` also watches the schema file, and remote changes are picked up by the next command.
- **`design.md`**: how each rule is built, kept in one place per rule, plus the choices the contract leaves open.
- **`tasks.md`**: 7 groups of tasks. Each group brings its own tests (against a real HTTP server on 127.0.0.1) and its README updates.

**Breaking change you should know about:** because the contract says so, `set prompt file:p.md` will now write `prompt: !literal file:p.md` (a plain string), not an include. Scripts that create includes through `set` need to add `--include`. This replaces README decision 4.

**Choices the contract leaves open:**
1. **`file:` inside remote content** fails to load (exit 4). The alternative is to resolve it against the URL. I refused it so a shared file can never make troupe read files on the user's machine.
2. **No caching:** each command fetches every URL once, with a 10-second timeout. With a URL in the configuration, every command, including `history`, needs the network.
3. **Nested remote includes:** a new key goes into an override in the user's own file, next to the outermost include.
4. **Strings inside a mapping or list VALUE** also get `!literal`. Otherwise `set a '{p: file:x}'` would still create an include without the user asking.
5. **`--include` is refused (exit 3)** where it cannot create an include: on a path the schema marks `format: uri`, and on a text include.
6. **The schema check treats `format` as information only**: an odd value at a `uri` path does not make the configuration invalid. Only `properties`, `items` and `additionalProperties` are followed to find `format: uri`.

The rest of the list is in design.md under D9. The plan also adds one dependency, `jsonschema`, which isn't installed yet, so the first implementation step needs the network once.

All artifacts needed for implementation are ready. The artifacts are ready for review. When you are ready, run `/method-command`.

Reply: /method-command
