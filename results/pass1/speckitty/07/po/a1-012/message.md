I chose a 1 MiB size limit, no warning for `http://` includes, and refusing `https` → `http` redirects. All three are merged into `main` (`f172d52`), not pushed. The full suite passed (2682 tests, including 8 new ones) and mypy and ruff are clean.

**Size limit (1j5.3): a remote include can be at most 1 MiB.** A larger file is a failed fetch: exit 4, with stderr `cannot fetch <url> (included from <file>, at <path>): larger than 1 MiB, the limit for a remote include`.
- **Why 1 MiB:** your configurations are under 1,000 leaves in under 50 files, so a real include is a few kilobytes and this limit is far above anything legitimate. Without a limit, a broken or hostile server could make troupe read an unbounded body into memory. Refusing can't lose or corrupt data, and a failed fetch is already contracted as exit 4.
- **How it's enforced:** the declared size is checked first, then the limit is enforced again while reading. A missing or false `Content-Length` can't get past it.

**No warning for `http://` includes (1j5.4).**
- The contract makes `http://` a normal include, and you write it on purpose.
- A warning would add stderr noise to every successful `get`, `show` and `set` that harnesses read, with no contract basis.

**Refuse `https` → `http` redirects (1j5.4).**
- It counts as a failed fetch: exit 4, stderr `redirect to <url> refused (https may not redirect to http)`, and the `http` URL is never contacted. Every hop of a redirect chain is checked.
- `http` → `https` and same-scheme redirects still work.
- **Why:** an `https://` include asks for an encrypted source, and silently following a downgrade would remove that protection. If you want plain http, you write an `http://` include.

These are recorded in the spec as agent choices S-14 to S-16, with the contract's message table, FR-003 and research updated to match. Issues `1j5.3` and `1j5.4` are closed.

Four smaller follow-ups remain open under the parent issue `1j5`:
- `1j5.1`: a fetch fails outright instead of falling back to IPv4 on hosts with IPv6 disabled.
- `1j5.2`: an error-message ordering edge case with `--include`.
- `1j5.5`: one refusal message is missing the configuration path.
- `1j5.6`: `watch` holds a lock for up to 10 s while a remote include keeps failing.