# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## 1c6749d Share anchored values: set at the anchor, refuse through an alias, add set --expand-alias (#2)

Setting a value defined at an anchor now writes it there, keeping the &anchor,
and the copies seen through its aliases may change with it. Setting a path
reached through an alias exits 3 and points at --expand-alias, which replaces
the alias with a block-style copy marked '# expanded from *name by troupe'.
Merge keys are never written.

