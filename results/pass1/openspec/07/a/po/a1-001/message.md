I've written the plan for step 7 as the OpenSpec change `config-remote-includes-and-schema` and committed it on `main` (b7f6525). It passes `openspec validate --strict`. No project code has changed yet.

**Artifacts** (in `openspec/changes/config-remote-includes-and-schema/`):
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

All artifacts needed for implementation are ready. The artifacts are ready for review. When you are ready, run `/opsx:apply`.