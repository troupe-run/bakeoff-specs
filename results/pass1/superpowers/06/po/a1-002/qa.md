Q1: Fixed and committed on `main` as `2588180`. Nothing pushed, and I didn't comment on the issue. All 115 tests pass, including 20 new ones in `tests/test_aliases.py`.

**Cause:** the YAML parser (PyYAML) turns an alias like `*d` into the very same node as its anchor `&d`, so troupe couldn't tell the two apart. Setting `coder.settings.model` therefore edited the bytes at `defaults: &d`, and every agent sharing it changed. I reproduced this from the issue before fixing it.

**Fix:** the loader now records where each `*name` is written and marks values reached through one. On the issue's example:
- `set coder.settings.model sonnet` now exits 3. The error says `coder.settings` is an alias of `&d` and points to setting it at the anchor or using `--expand-alias`. Any write that would reach a shared value is refused too, such as setting the whole `coder` mapping.
- `set coder.settings.model sonnet --expand-alias` gives:
  ```yaml
  coder:
    settings:  # expanded from *d by troupe
      model: sonnet
  reviewer:
    settings: *d
  ```
  `defaults` and `reviewer` are unchanged.
- `set defaults.model sonnet` still changes it at the anchor, so everyone gets it.

**Two other bugs I fixed on the way:**
- **Anchored values:** setting a value that carries an anchor, like `x: &s opus`, used to be refused because the write dropped `&s`. The anchor (and any tag) is now kept.
- **Recursive aliases:** a file like `a: &a {b: *a}` made every command hang. It's now a config error (exit 4).

**Choices the contract left open** (recorded in `docs/decisions.md` items 30–33):
- **Merge keys (`<<`):** these are now resolved when reading, so `get`/`show` show the merged values. They're never written. Setting a merged value exits 3. With `--expand-alias`, it gets its own explicit key next to the `<<`, which overrides the merged value without touching `<<`. If you'd rather that case always exit 3, it's a small change.
- **The expanded copy** is the value as troupe reads it: nested aliases and merges are filled in, and an aliased include is copied as its contents, so the copy shares nothing with the anchor. Comments inside the anchored block aren't copied.
- **Flow style:** an alias inside a flow collection (`{s: *d}`) can't take a block-style copy, so `--expand-alias` exits 3 there.

One formatting detail: when a value on a line with a trailing comment gets longer, troupe keeps the comment where it was, so the gap before `#` can shrink to one space. Expanded copies are written with exactly two spaces, as the contract asks.

The README documents the new flag.
A1 (runner): /superpowers:finishing-a-development-branch