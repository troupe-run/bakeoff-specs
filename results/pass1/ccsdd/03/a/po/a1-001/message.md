Discovery for step 3 is done and committed to `main` as `8fc75f7`, without pushing. That commit holds only planning documents: `get` and the new `show` are not implemented yet, so the request isn't delivered until the spec and implementation steps below have run.

**Path chosen: Path E.** I'm adding one new spec, `config-get-show`, and adding notes to two existing specs:
- **config-foundation:** Requirement 6 ("Show a value") is replaced. It now describes `get`, and the "mapping or list → exit 5" rule applies only to `get`.
- **config-file-sync:** a wording fix only ("`get`, `show` and `set` reconcile first"). No behaviour changes.

**Approach:** a small YAML writer of our own, built on the existing configuration model. That model already records which file every value comes from, so `--sources` needs no extra pass. It reuses the quoting and literal-block rules that `set` already uses. I rejected the YAML library's built-in output because it's hard to control where comments land on literal blocks, and its quoting and line wrapping can change between versions.

**Choices I made where the contract leaves room.** They're recorded in the brief; please confirm or override them before we write requirements:
1. YAML printed by `show` must load back to exactly the same values and types. For example, the string `"true"` is quoted, and infinity prints as `.inf`.
2. Layout: 2-space indent, the files' key and list order, `{}` and `[]` for empty sections, no document markers, LF line endings. An empty configuration prints `{}`.
3. Every multi-line string, not just text includes, is printed as a literal block when one can hold it exactly. When it can't (CRLF, control characters), it's printed double-quoted instead, so the value never changes.
4. On a literal block, `# from <file>` goes on the `|` line. A comment on a content line would become part of the value.
5. `show SCALAR --sources` prints the value as YAML with the comment (e.g. `5 # from .troupe/troupe.yml`). Without `--sources`, it prints exactly like `get`.
6. `<file>` is the path as written, not following symlinks, relative to the theatre directory. A file outside that directory gets `../`.
7. `get` on a section exits 5 and its message suggests `troupe config show PATH`.

Many existing tests call `config show` to read a single value. They'll be switched to `get` in the same change as the behaviour.

**Files written:**
- `.kiro/specs/config-get-show/brief.md`
- `.kiro/steering/roadmap.md` (new "Step 3" section; steps 1–2 untouched)

**Next step:** `/kiro-spec-init config-get-show`, or `/kiro-spec-quick config-get-show --auto` to go straight to tasks. After that, `/kiro-impl config-get-show` builds it on `main`.