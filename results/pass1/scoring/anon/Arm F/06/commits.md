# Commits (2, newest first)

Each commit's short SHA and subject, then its message body.

## 32d38d2 Record verification of the yaml-alias-set fix


## 8ec062d Refuse setting through a YAML alias; add set --expand-alias

`set coder.settings.model sonnet` with `settings: *d` used to rewrite the
anchored value, silently changing `defaults` and every other alias of it
(troupe-run/repo#2).

The loader now marks alias occurrences, so a path below an alias is
refused with exit 3, naming --expand-alias. `set --expand-alias` replaces
the alias with a block-style copy commented `# expanded from *<name> by
troupe`, then sets the value in the copy. Setting at the anchor keeps the
`&name` and changes every alias. Merge keys (`<<`) are never written.

