`get` and the new `show` are working, and the work is committed on `main` as `363d949`. All 66 tests pass, and I checked the output with the real `troupe` command too.

- **`get PATH`** prints a single value, exactly as `show` used to. If the path is a mapping or list it exits 5, and the error says to use `troupe config show <path>` instead.
- **`show [PATH]`** prints a single value the same way `get` does. A mapping or list is printed as YAML in block style, with includes filled in and text includes shown as literal blocks (`|`). With no `PATH` it prints the whole configuration.
- **`show [PATH] --sources`** adds `# from <file>` at the end of every line that holds a value. The file is given relative to the theatre directory, for example `.troupe/agents/coder.yaml`. For a text include it names the included file.

The new rendering code is in `src/troupe/dump.py`, and the command changes are in `src/troupe/cli.py`. The existing tests now call `get`, and `tests/test_show.py` adds tests for `show`. Several of those tests read the printed YAML back in and check it gives the same configuration.

The spec didn't cover a few cases, so I made these choices and recorded them in `docs/decisions.md` (items 16–20):
- **Quoting:** values are quoted only when leaving them bare would change their meaning. Comments and the original files' quoting are not kept.
- **Text that can't be a literal block:** a text include or multi-line string is printed double-quoted if a literal block can't hold it exactly. Examples are text with Windows line endings, a first line starting with a space, or a value that is only line breaks.
- **Where the comment goes on a literal block:** with `--sources`, it goes on the `key: |` line, because a comment on any line below would become part of the text.
- **`show PATH --sources` on a single value** prints it as YAML (quoted if needed) with the comment, rather than in the plain `get` form, because the spec describes `--sources` output as YAML.
- **Files outside the theatre directory** are named with `..`, still relative to it.

I also updated the README for the new commands.