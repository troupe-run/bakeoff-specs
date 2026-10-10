## Feature name: `config-get-show`
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