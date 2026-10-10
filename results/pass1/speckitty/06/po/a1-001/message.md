I've created the mission and claimed the bug. Before I write the spec, I need one decision from you.

**Setup**
- Mission: `troupe-config-anchor-aliases-01M48SQ8`
- Branch: `fix/troupe-config-anchor-aliases`, started from `main`. Spec Kitty won't commit planning files straight to `main`, so the work goes on this branch and gets merged into `main` locally at the end. Nothing is pushed and no PR is opened.
- Bug `bakeoff-specs-speckitty-qht` is claimed.

**What I found:** the reporter's exact file can't be loaded on `main`. Every command stops with exit 4 and `cannot parse …/troupe.yml: anchors and tags are not supported at line 1`, so today `set` can't change the wrong agent. Fixing this means adding the new step 6 Aliases behaviour: troupe has to start reading anchors and aliases, and `set` then follows the contract you gave.

**Question 1 of a short interview: merge keys (`<<`).** The contract says troupe never writes `<<`, which suggests `<<` can appear in a file. For example:

```yaml
defaults: &d
  model: opus
coder:
  <<: *d
  temperature: 0.2
```

How should troupe read this, and what should `set coder.model sonnet` do?

- **(A) Recommended:** read `<<` the standard YAML way, where keys written in the mapping itself win. A value that arrives through `<<` counts as reached through an alias, so `set` exits 3. `--expand-alias` on such a path also exits 3, because expanding it would mean rewriting the `<<` line. This is the safest option: it never guesses.
- **(B)** Read the same way, but `set coder.model sonnet` adds `model: sonnet` next to `<<` in `coder`. `<<` isn't written and nobody else changes, but it quietly overrides the shared value without the explicit opt-in the reporter asked for.
- **(C)** Refuse any file containing `<<` at load (exit 4), as anchors are refused today.
- **(D)** Something else.

After this I'll show you a short summary of the remaining choices, each with my recommendation, for you to confirm. Those cover what `show` prints for aliased values, how a value that is itself just an alias (`model: *m`) is handled, how nested aliases are expanded, and how history records a change made at an anchor.

WAITING_FOR_DISCOVERY_INPUT