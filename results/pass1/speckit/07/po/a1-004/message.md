Step 7 is implemented and committed on `main`, with all 27 tasks done. Nothing was pushed and no PR was opened. The final run on the committed code: 931 passed and 1 skipped (the same skip as before step 7), with `mypy --strict` and ruff clean.

**What works now:**
- **URL includes (US1):** a string starting `https://` or `http://` is fetched each time a command loads the configuration, at most once per command. It's read as YAML if the URL path ends `.yml`/`.yaml`, otherwise as text. Overrides and nested includes work, and `show --sources` labels remote values with their URL. Any failed fetch exits 4 and names the URL and the file that includes it: no connection, a non-2xx status, more than 10 seconds, a body that isn't UTF-8, or invalid YAML. So do a `file:` include inside fetched content and a cycle of URL includes.
- **Remote content is read-only (US2):** any change that would land in fetched content exits 3. The message gives the include string as written, plus its local file and line number. For example: `agents.coder.model: comes from the remote include http://…/agents.yaml (line 1 of .troupe/troupe.yml); … change that include line instead`. A new key under remote content still becomes a local override.
- **Literals (US3):** a string tagged `!literal`, or whose path the schema marks `format: uri`, is never fetched or read. The tests confirm this from the test server's request log.
- **Validation (US4):** a configuration that fails the schema exits 4 for every command, naming the schema file and the failing path. A `set` that would break it exits 3 and writes nothing.
- **`set` and `--include` (US5):** `set docs https://…` writes `docs: !literal https://…` unless the schema marks the path `format: uri`. With `--include` it writes an include instead.

**Things you should know:**
- **Existing URL settings now break loading.** Any plain `https://` or `http://` value is now fetched, and commands exit 4 if it can't be. Teams need to mark these in the schema or with `!literal`. The README now says so.
- **I updated five step 1 tests.** They set a value to a `file:` string and expected an include. Under step 7 that writes `!literal` by default, so they now pass `--include` and still test what an include written by `set` does.
- **I fixed two of my own step 7 tests.** Their schemas said `type: string` for values that load as mappings; once validation was added, those configurations correctly failed.
- **One earlier full run reported a sixth failure I couldn't reproduce.** The output was cut off before its name. It didn't recur in the e2e or unit reruns or in the final full run. It may have been a timing flake, since that run overlapped my manual walk-through.
- **Two additions beyond the task list:**
  - `types-jsonschema` as a dev dependency, so mypy can check the schema code.
  - Expanding an alias now keeps `!literal` tags in the copy. Without this, the copy would become an include and the `set` would be refused.
- **Slower tests:** the HTTPS tests use a self-signed certificate made with `openssl`, so they need it installed. The two 10-second timeout tests add about 20 seconds to the suite.

I also ran the `quickstart.md` walk-through by hand. Every step behaved as specified, but I had to reorder the quickstart: it added a URL setting before the schema existed, and that setting was then fetched as an include.

The work is in nine commits on top of the task-list commit, from `dd208b2` to `8fa9208`. No implement hooks are registered, so none ran.