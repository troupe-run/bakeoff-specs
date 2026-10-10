# Commits (9, newest first)

Each commit's short SHA and subject, then its message body.

## 592e463 Archive config-load-show-set and sync its specs into spec/specs

Syncing (rather than archiving without it) keeps the main specs as the lasting
record of the behaviour the code and tests implement; recorded in design.md.


## f0f0cf5 Add end-to-end uv run smoke tests and README

The smoke suite drives the real 'uv run troupe config' entry point against a
multi-file theatre with comments, includes and a CRLF text include. The README
documents the commands, exit codes and the decisions taken where the contract
is open; design.md records the two decisions made during implementation.


## 142529b Test literal and folded block scalars; fill empty values after the colon

An implicit null ('key:' with nothing after it) has no text of its own, so
replacing it now writes right after the ':' instead of at the parser's mark,
which lies elsewhere and made such sets refuse with exit 3.


## 4a32734 Fix mypy in verification test: patch the ops module directly


## a4245fe Make ruff clean: allow long lines in byte-exact test tables


## ab66b62 Test set write-back for scalars, includes and structure; fix key quoting

New keys that would read back as non-strings (e.g. 'true') are now quoted
like string values, and deleting the first entry of a compact '- key: v'
item is supported instead of refused.


## 2c7409e Test loading, includes, event history and show

Covers config-file discovery, core-schema loading, YAML/text includes
(relative paths, missing targets, cycles), import-once history with path
filtering, state confinement, and show's printing and exit-5 cases.


## 2d55a87 Add troupe package: config loading, event store, CLI and write-back engine

Scaffolds the uv project and the troupe config subsystem modules (core-schema
resolution, path and VALUE parsing, include-aware loader, eventsourcing store,
byte-surgical edit engine). Tests land group by group in following commits.


## 27b502e Plan config load/show/set/history (method change config-load-show-set)

Proposal, specs, design and tasks for step 1 of troupe's configuration
subsystem, recording decisions on points the contract leaves open.

