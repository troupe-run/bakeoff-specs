Q1: Discovery for step 3 is written and committed on `main` as commit `1db2f7e`. Nothing has been built yet: this step only produces the plan. Running it to completion means the specify-and-implement steps below.

**What I decided.** The roadmap already existed, so I added to it. The work is one new spec plus two small updates to existing specs:
- **New spec `config-get-show`** covers the `get PATH` command, `show [PATH]` printing YAML, and `--sources`.
- **config-foundation:** its Requirement 6 (the old `show PATH`) becomes `get`, and the exit-5 message also mentions `config show`.
- **config-file-sync:** `get` joins the commands that reconcile with the files first; `history` still never does.

**Approach.** I chose a small YAML writer of our own that works over the configuration tree the loader already builds.
- That tree already records which file each value came from, and a text include points at the included file. So `--sources` needs no extra work to find the source.
- The `# from <file>` comment is added as each line is built, so no lines have to be matched to values afterwards.
- Scalars reuse the quoting and literal-block rules that `set` already uses.
- The rule throughout: the printed YAML must load back to exactly the same configuration.

I rejected the ruamel.yaml-based options because ruamel would control comment placement, quoting and number formats, and inserting comments after the fact is fragile. The reasons are recorded in the brief.

**Open choices with my defaults.** These are recorded in the brief, to settle during requirements:
- `show PATH --sources` on a single value still gets the `# from <file>` comment, printed as YAML.
- For a literal block, the comment goes on the `|` header line, because a comment can't sit inside the block's content.
- A text include that a literal block can't hold exactly falls back to a double-quoted string, so the value never changes.
- Empty sections print as `{}` and `[]`.
- Indentation is 2 spaces, with one space before `#`.
- File labels are relative paths with `/`, such as `.troupe/troupe.yml`. An include outside the theatre directory gets a `../` path.

The discovery process normally asks you to confirm the decision and the approach. Because you asked for the work to be committed in this run, I chose and recorded them without asking; tell me if you want any of them changed.

Files:
- `.kiro/specs/config-get-show/brief.md` (new)
- `.kiro/steering/roadmap.md` (new step 3 section; `config-get-show` added to the main spec list; earlier content unchanged)

**Next:** `/kiro-spec-init config-get-show`, or `/kiro-spec-quick config-get-show` to go straight on. After that, revisit config-foundation and config-file-sync with `/kiro-spec-requirements` for the updates above.
A1 (po): /kiro-spec-init config-get-show

Q2: ## Feature name: `config-get-show`
I kept the folder that discovery created. The name matches the step 3 contract section "`get` and `show`" and the earlier `config-*` specs.

## Project summary
`get PATH` prints a single value, as `show` used to. `show [PATH]` prints a value, a section or the whole configuration as block-style YAML with includes resolved. `--sources` adds a `# from <file>` comment to each line that holds a value.

## Created files
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-get-show/spec.json`: phase `initialized`, nothing approved yet.
- `/work/bakeoff-specs-ccsdd/.kiro/specs/config-get-show/requirements.md`: the project description is the brief's Problem, Current State and Desired Outcome, plus the step 3 contract section quoted word for word, as step 2 did. It points to `brief.md` for the approach and the open choices.

Both files are committed on `main` as commit `c2ef9e5`.

## Next step
```
/kiro-spec-requirements config-get-show
```
A2 (po): /kiro-spec-requirements config-get-show