Q1: I've written the step 7 spec and committed it on `main` (`3b4d346`). I didn't push or open a PR. This is only the spec; nothing is implemented yet, and no tests were run.

- **Feature directory:** `specs/007-remote-includes-schema`
- **Spec:** `specs/007-remote-includes-schema/spec.md`, with the contract section quoted word for word. It uses FR-600 onward, decisions D-60 to D-70 and success criteria SC-600 onward, following the numbering of the earlier steps.
- **Checklist:** `specs/007-remote-includes-schema/checklists/requirements.md`. Every item passed on the first check, and there are no open clarification questions.
- **Hooks:** none are registered, so none ran.

**Behaviour change for existing users:** any plain `https://` or `http://` string in a configuration now counts as an include and gets fetched. Teams have to mark URL settings in the schema or with `!literal`. The spec lists this under Assumptions so the README covers it.

**Decisions you should check.** The contract left these open, so I chose the cautious option each time and recorded why:
- **D-60:** If a remote include sits inside another remote include, adding a new key under it is refused (exit 3). Step 5 would put the override in the nearest including file, and that file is remote here.
- **D-61:** A `file:` include inside remote content stops the configuration loading (exit 4). Otherwise a remote document could pull files from the user's disk into the configuration.
- **D-63:** Fetching follows redirects, accepts only 2xx responses, gives up after 10 seconds, doesn't retry or cache, and sends no credentials.
- **D-64:** When deciding whether a string is a literal, the schema lookup only follows `properties`, `additionalProperties` and `items`, as the contract lists. `$ref`, `allOf` and the like are ignored for that, though validation still uses them. `format` is treated as a label, not a rule that values must pass. A schema `$ref` pointing outside the file stops loading (exit 4), so the schema never triggers a fetch.
- **D-65:** When remote content changes between commands, the next command records the difference as a file change. `watch` doesn't poll URLs.
- **D-68 / D-69:** `--include` on a path the schema marks `format: uri` is refused (exit 3). Include-like strings inside a mapping or list value also get the `!literal` tag.

If any of these is wrong, it's a change to one decision in the spec. Next step is `/speckit-plan`, or `/speckit-clarify` first if you want to revisit them.
A1 (po): /speckit-plan

Q2: The step 7 plan is written and committed on `main` (`c011391`). It's design only: no code has changed and no tests were run. It stays on `main` like the earlier steps; no branch was created. No plan hooks are registered, so none ran.

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
A2 (po): /speckit-tasks