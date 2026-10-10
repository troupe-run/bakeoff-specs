# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## 2588180 Refuse writes through YAML aliases; add set --expand-alias

PyYAML composes an alias to the anchored node itself, so setting
coder.settings.model through `settings: *d` edited the anchor and changed
every agent sharing it (troupe-run/repo#2).

The loader now records where each alias is written and marks values
reached through one. Setting such a path exits 3 and points at
--expand-alias, which replaces that alias with a block-style copy of the
anchored value (commented "# expanded from *name by troupe") and sets the
value in the copy. Setting at the anchor still changes every use, and now
keeps the anchor and tag. Merge keys (<<) are resolved on read and never
written; a recursive alias is a config error instead of a hang.

