Step 7 (remote includes and a schema) is merged into `main` at `bc8d285`. Nothing was pushed and no pull request was opened.

**Checks:** the full suite on the merged code passed (2674 tests, none skipped, so the TLS certificate test ran too), and mypy and ruff are clean. `main`'s tree is identical to that tested tree, and a smoke run on `main` passed.

**What it does:**
- **Remote includes:** a string starting `https://` or `http://` is now an include, fetched when the configuration loads. A fetch never takes more than 10 seconds, certificates are verified, and redirects go to http(s) only. Any failure exits 4 and names the URL.
- **Remote content is read-only:** changing a value that comes from a remote include exits 3 and quotes the include line to change instead. New keys under a remote include become local overrides.
- **Schema:** if `.troupe/troupe.schema.json` exists, the configuration must match it. A mismatch exits 4 when loading, and exits 3 for a `set` that would break it. Settings the schema marks `"format": "uri"`, and strings tagged `!literal`, are never treated as includes.
- **`set`:** writes include-looking strings as `!literal …` unless `--include` is given.
- **One behaviour change you should know about:** `set b file:p.md` used to create an include; it now writes `b: !literal file:p.md`. The contract requires this, and the two existing tests that relied on the old behaviour now pass `--include`.

**How it went:**
- **Reviews:** all 10 work packages were reviewed separately. Four were rejected once each and then fixed; three of those defects mattered:
  - A fetch could run past 10 seconds.
  - A loader change let a `set` silently change an unrelated value through a shared YAML anchor.
  - Read-only refusals could come with the wrong error message.
- **Final review:** the post-merge review gave "pass with notes". I fixed the spec and research wording it flagged; the code findings are filed as issues below.
- **Planning-document fixes:** during implementation, three expectations in my own planning documents turned out to contradict the spec. I fixed those documents.
- **Choices I made where the brief was silent:** these are recorded in the spec as S-1 to S-13. They include resolving `file:` includes inside remote files against the URL, and adding the `jsonschema` library for validation.

**Needs your decision:**
- `1j5.3`: there is no limit on how large a fetched remote file can be.
- `1j5.4`: `http://` includes travel unencrypted with no warning, and an `https` include can be redirected to `http`.

**Smaller follow-ups:** issues `1j5.1`, `1j5.2`, `1j5.5` and `1j5.6` (fetch fallback on IPv6-disabled hosts, an error-message ordering edge case, one error message missing its path, and `watch` holding a lock up to 10 s while a remote include keeps failing). The parent issue `1j5` stays open only because these six are its children.

One leftover: spec-kitty couldn't delete the mission's coordination branch because its worktree is still checked out. Earlier missions left theirs in place too; I've left it.