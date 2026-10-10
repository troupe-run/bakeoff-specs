The step 7 plan is written and committed on `main` (`c011391`). It's design only: no code has changed and no tests were run. It stays on `main` like the earlier steps; no branch was created. No plan hooks are registered, so none ran.

**Files written** (all in `specs/007-remote-includes-schema/`):
- `plan.md`: summary, technical context, a constitution check where every principle passes, the module layout and the design steps.
- `research.md`: technical decisions U-1 to U-12, each with the reason and what else was considered.
- `data-model.md`: how a source, a loaded configuration, the string classification and the schema rules fit together.
- `contracts/cli.md`: the `--include` option, the URL include forms, `!literal`, the schema file, and what happens for each refusal.
- `quickstart.md`: the checks to run (tests, mypy, ruff) and a manual walk-through using a local web server.

**Main design choices:**
- **Remote content can't be written, enforced by types.** A source's location becomes either a local path or a URL, and every write has to go through one helper that only accepts local paths. mypy then flags any write site that skips it. When a write is refused, the message names the remote include line on the route that PATH actually takes.
- **Literals are decided before anything is fetched.** The loader carries each node's part of the schema down as it builds the tree. A `format: uri` or `!literal` string is therefore never requested; the tests check this against the server's request log.
- **Validation happens when the configuration loads.** That gives exit 4 for every command, and `set`'s existing reload check turns a change that would break the schema into exit 3, with nothing written.
- **Tagging happens before `set` plans the edit.** Include-like values are marked first and the tag is written in one rendering spot, so none of the code that decides where values go changes. An existing `!literal` tag is kept unless `--include` is given.

**New dependency:** `jsonschema`, to validate against JSON Schema 2020-12. I checked that uv can install it. Fetching uses Python's standard library.

**Tests will use real HTTP and HTTPS:** a local server, with a self-signed certificate made by `openssl`, rather than a faked fetch. Proxy environment variables are cleared so they can't affect results. One test waits out the 10-second fetch limit, so it will be slow.

Next step is `/speckit-tasks`.