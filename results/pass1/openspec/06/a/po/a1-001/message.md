I've written the plan for issue #2 as the `config-aliases` change and committed it on `main` (`7875dd5`); nothing is pushed. It passes `openspec validate --strict`. No code has changed yet. The fix itself starts when you run `/opsx:apply`.

**What I found:** on current `main`, the reported behaviour can't happen. Any file with an anchor or alias fails to load (exit 4, README decision 8), so today the issue's file doesn't work at all. The plan adds alias support with the contract's rules, which means the reported bug can't happen once aliases load.

**What the plan covers** (in `openspec/changes/config-aliases/`):
- **`proposal.md`**: why, what changes, and the four specs affected.
- **Spec changes:**
  - `config-loading`: anchors and aliases load, and a read through an alias gives the anchor's value. Undefined aliases, aliases used as keys, and YAML 1.1 merge keys (`<<: *d`) fail to load with exit 4.
  - `config-set`: setting at an anchor changes it there and keeps the `&name`. Setting through an alias exits 3, and the error names the alias and `--expand-alias`. `--expand-alias` replaces the alias with a block-style copy and adds the exact comment the contract specifies. `set` never writes a `<<` key.
  - `config-cli`: the new `--expand-alias` flag.
  - `config-history`: a change at an anchor records one event for each path it changes, including every alias path. An expansion alone records nothing.
- **`design.md`**: how it's built. An alias is the same node as its anchor in the loaded tree, so reads need no changes. The "no write through an alias" check lives in one place. Anchors are kept out of value spans, so every existing replace path keeps the `&name` without special cases.
- **`tasks.md`**: 4 groups, each with its own tests and README updates.

**Choices I made where the contract is silent** (each recorded with its reason in `design.md`):
1. **Merge keys:** I read "never written" as "`set` never adds or changes a `<<` key." Reading `<<: *d` in a file stays refused (exit 4), as it effectively is today. A `<<` key without an alias still loads as an ordinary key.
2. **Setting the alias path itself** (e.g. `coder.settings`) is refused too, not just paths below it. A parent value that would change something under an alias is also refused. Deleting an alias entry is allowed, since it changes nothing else.
3. **`--expand-alias` expands every alias on the path**, outermost first, each with its own comment. It only expands aliases on the path you name, not ones a mapping value would reach further down.
4. **The copy:** scalars keep the quoting and spelling written in the anchor, it uses block layout, and it has no anchors or comments. Aliases nested inside it stay aliases.
5. **Edge cases:**
   - A comment already on the alias line is kept, after troupe's.
   - An alias inside a flow collection (`{s: *d}`) can't be expanded and exits 3.
   - Setting a value it already has changes nothing, with or without the flag.

The artifacts are ready for review. When you are ready, run `/opsx:apply`.