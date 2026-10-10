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

Q4: The plan for `get`/`show` is done and committed on `feat/troupe-config-get-show` (commits `d6375aa` and `55c2b7a`). No code has been written yet, so the tests, type checks and lint haven't been run for this work.

**Quoting decision (D‑11), now also in the spec:** in `show`'s YAML output, a string goes unquoted only if three readers all get back exactly the same string: troupe's own YAML 1.2 core resolver, ruamel in YAML 1.2 mode and ruamel in YAML 1.1 mode. Everything else is double-quoted.

**Why:** the contract names a YAML version only for parsing `VALUE`, not for `show`'s output. That output is meant to be read and reused, possibly by tools that follow YAML 1.1. A few extra quotes can't change a value, but a reader turning `yes` into `true` would (TROUPE‑002).

I checked this against the real ruamel loader, and quoting needs more than the YAML 1.1 cases. Even in YAML 1.2 mode, ruamel reads `1_000` as an integer and `2001-12-14` as a date, and refuses `<<` and `=`. So unquoted strings are decided by reading each one back with all three readers, not from a fixed list.

**Design, as you confirmed it:**
- **`get`:** the old single-value `show` code, moved to `commands/get.py`. For a mapping or list it exits 5 with `troupe: agents is a mapping, not a scalar; use 'troupe config show agents'`. `get --sources` is a usage error (exit 2).
- **`show`:** a new `render.py` turns the configuration into lines, each tagged with its source file or none. `show` joins them and adds ` # from <file>` only with `--sources`, so the two outputs can't drift apart.
- **Quoting:** the read-back checks live in `yamlcore.py`, still the only module that uses ruamel. No new dependencies.
- **Tests:** the existing single-value `show` tests move to `test_get.py`. A new `test_show.py` reads the output back with the real ruamel library.

**Implementation concerns for the tasks step:**
- **IC‑01:** `get` and the command-line options.
- **IC‑02:** the quoting checks in `yamlcore`.
- **IC‑03:** the renderer and `show`.
- **IC‑04:** the contract, help text and docstrings.

Files are in `kitty-specs/troupe-config-get-show-01M4075F/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli-get-show.md`
- `quickstart.md`

The new contract replaces only the step‑1 `show PATH` row.

**Branch:** current, planning base and merge target are all `feat/troupe-config-get-show`. The finished work goes onto `main` by a local merge, with no push and no PR.

Next step is `/spec-kitty.tasks`.
A4 (po): /spec-kitty.tasks

Q5: I've split the work into four work packages (18 subtasks) and committed the finalized tasks on `feat/troupe-config-get-show` (commit `78e2917`). No code has been written yet.

| WP | Goal | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | Read-back checks in `yamlcore`: when a string can be unquoted, double quotes, float form, literal blocks | 5 (T001–T005) | 182 lines | — |
| WP02 | `render.py`: a node becomes YAML lines, each tagged with its source file | 5 (T006–T010) | 184 lines | WP01 |
| WP03 | `get`, `show [PATH] [--sources]`, command-line options; move `test_show.py` to `test_get.py`; section tests | 5 (T011–T015) | 195 lines | WP02 |
| WP04 | `--sources` acceptance tests, read-only and reconcile-first tests, check of contract and quickstart against real output | 3 (T016–T018) | ~160 lines | WP03 |

- **Size and checks:** every work package has 3–5 subtasks and a prompt under 200 lines. Each starts with the "⚡ Do This First" section and is assigned the `python-pedro` profile. Validation passed: no overlapping files, no cycles, and every FR, NFR and constraint is mapped.
- **No parallel work:** each package uses the previous one's API, so they run one after another. Spec Kitty still gives each its own lane (lane‑a to lane‑d).
- **Minimum useful scope:** WP01–WP03 deliver `get` and `show`. WP04 is still required, because it holds the acceptance tests for the contract's `--sources` section.

**Changes from the plan:**
- **Existing test that changes:** `test_cli_basics.py` used `config show` with no PATH as its example usage error. That is now valid, so WP03 switches that test to `get`.
- **Contract edits stay with me:** work packages can't own files under `kitty-specs/`. WP04 checks the contract and quickstart against the real output and reports any exact corrections, and I apply them on the planning branch before acceptance.
- **Floats:** they'll be written with a dot (`1.0e+20`) so readers that follow YAML 1.1 read them as numbers.

`finalize-tasks` left two status files uncommitted: `status.events.jsonl` (modified) and `status.json` (new). The previous mission had the same lane-guard issue with `status.json`, so I've left them for the implementation workflow to handle.

**Branch:** planning base and merge target are `feat/troupe-config-get-show`. The finished work goes onto `main` by a local merge, with no push and no PR.

**Should I use the `/spec-kitty-implement-review` skill to fully implement all work packages until completion?** It runs an implementing and a reviewing agent for each work package, handles rejection cycles, and merges all lanes when done. `/spec-kitty.analyze` has to run first: implementation won't start until its `analysis-report.md` exists, and I'd run it as the first step. You can also choose which agents implement and review, or limit it to some work packages.
A5 (po): /spec-kitty-implement-review