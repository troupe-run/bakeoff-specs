# Commits (8, newest first)

Each commit's short SHA and subject, then its message body.

## f64a6ba Archive config-anchors-and-aliases and sync its specs into spec/specs

Synced so the main specs describe anchors, aliases, merge keys and
set --expand-alias as the code, tests and README do. The archived design.md
records what the implementation added to the plan and why.


## fc4c69e Wrap two docstrings over the line limit

ruff check failed after the --expand-alias commit; the full test, type and
lint run is clean again.


## d7a0c3d Add set --expand-alias to give one user of an anchor its own copy

The reporter needs to override coder's settings without touching defaults or
reviewer. With --expand-alias, each alias the set would be refused for is
replaced by a block-style copy of the anchored node as written, marked with
'# expanded from *name by troupe', and the value is then set in the copy.
Expansion reuses the planner: compute_set expands the alias it stopped at,
reloads and plans again, so nested aliases and mapping VALUEs work in one
command and the read-back check still guards the result.

Fixes troupe-run/repo#2.


## dd9c848 Never write merge keys, and add the --expand-alias flag

The contract says merge keys (<<) are never written. A value a merge key
supplies, the << entry itself, and anything holding one are now refused
(exit 3) instead of being rewritten at the anchor or dropped. The mapping's
own keys still work, and new keys go after its last written entry rather
than after merged-in entries that live at the anchor. A new key named <<
is quoted so it never turns into a merge key.

The --expand-alias flag is accepted and passed through to compute_set, which
does not act on it yet.

Part of troupe-run/repo#2.


## b2ee31a Refuse to set a value reached through an alias

This is the reported bug: set coder.settings.model followed *d to the
anchor and silently changed defaults and every other agent using it. The
planner now refuses (exit 3) any change, new key or mapping/list diff that
reaches through an alias, and says where the anchor is and that
--expand-alias gives a copy. Edit primitives now take an alias entry's
extent from its *name text, not from the anchored node elsewhere in the
file, so removing an alias entry or appending after one stays in place.

Fixes the refusal half of troupe-run/repo#2.


## 2ac6ead Keep the anchor when setting a value defined at an anchor

Setting defaults.model must change it at the anchor and so for every alias.
The read-back check expected only the set path to change, so every such set
was refused; the expected value is now built by node identity, which follows
aliases and merge keys. Replacements that write right after the key's colon
now write after the &name instead of in front of it.

Part of troupe-run/repo#2.


## f8b7ee6 Load anchors, aliases and merge keys instead of refusing them

Shared settings written with &anchor / *alias (and <<: merge keys) made the
whole configuration fail to load (exit 4). An alias now resolves to the
anchored node object itself, so get, show, history and reconcile see the
shared value at every path without special cases. Node spans exclude the
&name so later edits can keep the anchor. VALUE still may not contain
anchors or aliases.

Part of troupe-run/repo#2.


## 07a8527 Plan anchor and alias support for issue #2

Setting one agent's value through a shared alias silently changed every
agent using the anchor (troupe-run/repo#2). The
contract's new Aliases section defines the behaviour; this records the
proposal, spec deltas, design decisions and tasks.

