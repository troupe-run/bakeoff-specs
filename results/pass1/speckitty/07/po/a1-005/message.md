The plan for step 7 is done and committed on `feat/troupe-config-remote-includes`, and `setup-plan` now reports the plan phase complete. Nothing has been merged into `main` yet, no product code has changed, and nothing was pushed.

**Branch:** we're on `feat/troupe-config-remote-includes`, which is also where the mission's work merges (`branch_matches_target: true`). That branch is merged into `main` locally once the mission is accepted.

**Validator decision:** as you directed, I took the safest option and recorded it as decision `01M4BMXJ…`. The plan adds `jsonschema` (2020-12), because a hand-written validator that was subtly wrong would accept or refuse configurations against the contract. To limit the risk of the new packages:
- the schema check never fetches anything outside the schema file;
- `rpds-py`, its compiled dependency, is never built from source;
- `research.md` has the supply-chain table.

**How the design hangs together:**
- **One place for the include rule.** It's currently copied in three places in the loader; a new module will decide what counts as an include, where it points, and whether it's YAML or text.
- **Fetching.** It uses only the Python standard library: a 10-second total deadline, redirects only to http/https, verified certificates. Each URL is fetched once per command, so a `set` checks its result against the same remote content it started from.
- **Remote content stays read-only.** One check refuses any change to it and quotes the include line as written. It runs before the alias refusal, and again on the exact files a `set` is about to write. File writes also assert that every target is a local file.
- **`!literal` tags.** The YAML layer will record where a tag sits, so rewriting a value keeps the tag. Without this, a rewrite would silently delete it.
- **Schema checks.** A configuration that fails the schema exits 4 when it loads, and a `set` that would make it fail exits 3. `watch` also reacts to changes to the schema file.

**Artifacts** (in `kitty-specs/troupe-config-remote-includes-01M4BMJ5/`):
- `plan.md`: summary, how the plan meets each charter rule, the files to add or change, 7 implementation areas (IC-01 to IC-07), and risks
- `research.md`: design decisions R-1 to R-13, the supply-chain review, and a challenge pass (7 findings, each accepted, changed or deferred with a reason)
- `data-model.md`, `contracts/cli.md` (exit codes and message wording), `quickstart.md`

Commits: `66d8e75` (plan) and `72281e4` (the other artifacts plus the decision record).

Things to know before implementation:
- **Challenge pass:** I reviewed the design alone; the multi-agent review the planning instructions call for was deferred, and `research.md` says why.
- **Slow tests:** the timeout tests take about 10 seconds each.
- **HTTPS test:** the one that checks certificates are verified needs `openssl` installed, and is skipped with a reason if it isn't.
- **No size limit:** nothing caps how large a fetched remote file can be. The spec doesn't ask for a limit, so I didn't invent one.

Next is `/spec-kitty.tasks` to turn these areas into work packages; I've stopped here until you run it.