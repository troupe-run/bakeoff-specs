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