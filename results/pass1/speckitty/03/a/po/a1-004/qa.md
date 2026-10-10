Q1: I checked the current code (`src/troupe/commands/show.py`, `src/troupe/tree.py`) and the step‑1 contract. The new contract is clear apart from one case.

**Question: what should `show PATH --sources` print when PATH is a single value?**

The contract says `show` on a scalar prints the value the way `get` does, which isn't YAML. It also says `--sources` "prints the same YAML" with `# from <file>` comments. Together, those don't say what `show model.temperature --sources` should print.

- **(A) Recommended: print the value as a one-value YAML document with the source comment.**
  - `0.2  # from .troupe/troupe.yml`
  - A text include prints as a literal block whose header line carries the comment, e.g. `|  # from prompts/sys.md`, then the text.
  - The output still answers "where does this come from?", and the YAML stays valid.
- **(B) Print exactly what `get` prints and ignore `--sources` for scalars.**
  - Simpler, but you lose the source information in exactly the case where you asked for it.
- **(C) Something else.** Tell me what you want.

Unless you say otherwise, I'll make these choices myself, since the contract leaves them open, and record them in the spec:

- **Valid YAML:** the YAML output always reads back to exactly the same values.
  - Keys keep their file order.
  - Strings are quoted only when they'd otherwise read back as something else (`"true"`, `"0.2"`).
  - Empty sections print as `{}` / `[]`.
- **Text-include line endings and chomping:** text includes are always literal blocks, as the contract says, and the trailing-newline marker (`|-`, `|`, `|+`) matches the file exactly. A CRLF file therefore appears with plain line breaks in `show`; `get` still prints the exact bytes.
- **Which lines get `# from`:** only lines that hold a value get a comment. A line that only opens a section (`agents:`) and an empty `{}`/`[]` get none.
- **`get` error text:** for a section, the message names the path and points to `config show`, e.g. `tools is a list, not a scalar; use 'troupe config show tools'`.
- **Unchanged behaviour:** a path that doesn't exist exits 5 for both commands. Both commands still pick up hand edits first, as every command except `history` already does.

WAITING_FOR_DISCOVERY_INPUT
A1 (owner): The contract doesn't define `--sources` for a scalar PATH: `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments (get and show, from step 3). Treat it as out of contract: your choice — state which you chose and why.

Q2: I chose option (A) and committed the spec on `feat/troupe-config-get-show` (commit `99242aa`). Nothing has been implemented yet, and nothing is on `main` yet; that happens after the plan, tasks and implementation phases.

**The out-of-contract case (recorded as D‑1 in the spec and in the decision record):** `show PATH --sources` on a single value prints it as a one-value YAML document with the comment.
- A plain value prints as `0.2 # from .troupe/troupe.yml`.
- A text include prints its literal-block header line with the comment (`|- # from prompts/sys.md`), then the text indented below it.
- Without `--sources`, `show` on a value prints exactly what `get` prints, as the contract requires.

**Why:** `--sources` exists to say where a value comes from, so ignoring it would drop exactly what was asked for. A one-value YAML document is still "the same YAML" for a one-value result, and it reads back as valid YAML.

**Other open points:** the spec records them as D‑2 to D‑10, using the defaults I proposed last turn. Two details are new since then:
- The comment is separated from the value by exactly one space.
- A file outside the theatre directory is named with leading `../`; includes are allowed to point there.

One more case is new: a text include whose content a literal block can't hold falls back to a double-quoted string, so `show` still prints valid YAML.

**What's committed:**
- `kitty-specs/troupe-config-get-show-01M4075F/spec.md`: 14 functional requirements, 3 non-functional requirements, 4 constraints and 3 user stories.
- `checklists/requirements.md`: every item passes.
- The decision record and `meta.json`.

The decision check reports nothing open and no `[NEEDS CLARIFICATION]` markers remain.

**Loose ends:**
- The plan step has already been started, which confirms Spec Kitty accepted the spec. It created a `plan.md` placeholder and left `status.events.jsonl` with uncommitted changes; the plan phase will commit both.
- No code changed yet, so the tests, type checks and lint haven't been run for this work.

Next step is `/spec-kitty.plan`.
A2 (po): /spec-kitty.plan

Q3: I have one planning question and a short summary of the engineering design to confirm.

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
A3 (po+owner): On “When show prints a string, should it quote every string that a YAML 1.1 or a YAML 1.2 reader would misread (A), or only strings that a YAML 1.2 core reader would misread (B)?”: The contract doesn't say which YAML reader `show`'s output must read back under. The only YAML version it names is YAML 1.2 core schema, for parsing `VALUE` on the command line. Treat the reader as out of contract: your choice — state which you chose and why.

On “Do you confirm this engineering summary: get reuses the existing single-value code and adds an error pointing to config show; a new output module produces lines tagged with their source file; ` # from <file>` is added only with --sources; quoting is decided in yamlcore; there are no new dependencies; the tests are reorganised as described; and set, history and watch are untouched?”: Confirmed. The summary is consistent with the contract. get prints a scalar as show did before. For a mapping or list it exits 5, and stderr mentions `config show`. show prints sections as YAML in block style, with includes resolved and text includes as literal blocks. --sources produces the same YAML plus `# from <file>` on lines that hold a scalar. Because both outputs come from the same lines, they can't drift apart, which fits "the same YAML".