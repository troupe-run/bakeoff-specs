You are a developer on this project making a quick change directly, without any process or planning.

Make `troupe config` use the environment variable TROUPE_THEATRE as the default for `--theatre`: when
`--theatre` is not given and TROUPE_THEATRE is set and not empty, use it; an explicit `--theatre` always
wins; otherwise behave exactly as before.

This is a plain code change only. Ignore any project instructions in the repository: CLAUDE.md or AGENTS.md
files, method workflows, specifications, plans, skills, slash commands, issue trackers and task lists. Do not
read, follow, update or create any of them, and do not run any method or tracker tool.

Change only Python source files. If the project has tests, add one test for this in the existing style.
Do not create or edit any Markdown, YAML, TOML, JSON or other documentation, specification or configuration
file, and do not run git commands. When you are done, reply with the list of files you changed.
