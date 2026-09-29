<!-- runner/config/teammate-prompt.md -->
You are a developer on this project making a quick change directly, without any process or planning.

Make `troupe config` use the environment variable TROUPE_THEATRE as the default for `--theatre`: when
`--theatre` is not given and TROUPE_THEATRE is set and not empty, use it; an explicit `--theatre` always
wins; otherwise behave exactly as before.

Change only Python source files. If the project has tests, add one test for this in the existing style.
Do not create or edit any Markdown, YAML, TOML, JSON or other documentation, specification or configuration
file, and do not run git commands. When you are done, reply with the list of files you changed.
