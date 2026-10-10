## Scored run

### Question 1 (step_done, answered by po)

Arm asked: `get` and the new `show` are in, and the work is committed on `main` as `b3cec0d`. All 23 tests pass.

- **`troupe config get PATH`** prints a single value, exactly as `show` did before. If the path is a mapping or list it exits with code 5, and the error says `(use \`troupe config show PATH\`)`.
- **`troupe config show [PATH]`** prints a single value the same way `get` does. A mapping or list comes out as block-style YAML with includes resolved, and leaving out `PATH` prints the whole configuration. I checked that the YAML output reads back as the same values.
- **`show --sources`** adds `# from <file>` to the end of every line that holds a value, e.g. `model: sonnet # from .troupe/agents/coder.yaml`. Paths are relative to the theatre directory, so they start with `.troupe/`. A text include's value is credited to the included file.

Where the spec didn't say, I chose:

- **Comments on multi-line values:** the comment goes on the `|` line (`prompt: | # from .troupe/agents/prompt.md`). A comment on a content line would become part of the text.
- **Windows line endings in a text include:** they are shown as normal line breaks inside the literal block, because a literal block can't hold them. `get` still prints the raw bytes.
- **`show PATH --sources` on a single value:** it prints the value as one line of YAML plus its comment (`demo # from .troupe/troupe.yml`), not the raw `get` output.
- **Empty sections:** they print as `{}` or `[]` with no source comment, since they hold no value.

The YAML output is in a new class in `render.py`. `get` and the `show` changes are in `cli.py`. I updated the README and replaced the old `show` tests with tests for `get`, its errors, section output and `--sources`.

Reply: 
