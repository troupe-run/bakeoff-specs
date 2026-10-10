I have one planning question and a short summary of the engineering design to confirm.

**Which YAML readers must read `show`'s output back as the same values?**

The spec says the YAML `show` prints reads back as the same values. Readers disagree about which unquoted strings count as plain text:
- troupe follows YAML 1.2 core, where `yes`, `on`, `1_000` and `0777` are plain strings.
- Readers that follow YAML 1.1, such as PyYAML and many CI tools, read those as `true`, `1000` or an octal number.

- **(A) Recommended: quote any string that either kind of reader would take for something else.**
  - For example, `enabled: "yes"` and `id: "1_000"`.
  - The output reads back correctly anywhere you paste it, at the cost of a few extra quotes. This follows TROUPE-002: take the choice that can't silently change a value.
- **(B) Quote only what YAML 1.2 core would misread.**
  - Fewer quotes, but `show | some-1.1-tool` could turn `yes` into `true`.

**Engineering summary, for you to confirm along with the question:**

- **New `get` command:** it gets the current single-value code from `show` unchanged. The only addition is that its error for a mapping or list points to `config show`.
- **New output module:** a small new module turns the loaded configuration into a list of output lines. Each line records the file it came from, or none for lines that only open a section.
  - `show` joins those lines and adds ` # from <file>` only when `--sources` is given.
  - So output with `--sources`, minus the comments, matches output without it by construction.
- **Quoting check:** whether a string can go unquoted is decided in one place, `yamlcore`, which already holds all the YAML parsing.
  - It tries the unquoted form and parses it back; if anything differs, the value gets double quotes.
  - Text includes are checked the same way: a literal block that wouldn't read back to the file's text falls back to double quotes.
- **No new dependencies.** ruamel.yaml is already a dependency, so the supply-chain checks aren't needed.
- **Tests:** the existing single-value `show` tests become `get` tests. A new `show` test file covers sections, the whole configuration, `--sources` and the D‑1 to D‑10 cases, and reads the output back with the real YAML library.
- **Unchanged:** other tests that use `show` on a single value keep working, because that output doesn't change. `set`, `history` and `watch` are untouched.

WAITING_FOR_PLANNING_INPUT