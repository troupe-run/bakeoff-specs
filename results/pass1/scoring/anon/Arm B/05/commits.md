# Commits (14, newest first)

Each commit's short SHA and subject, then its message body.

## 9c1dfbd Archive config-set-in-include and sync its specs into spec/specs

Synced so the main specs describe set --in-include as the code, tests
and README do; the reason is recorded in the archived design.md.


## 351ab04 Mark config-set-in-include tasks complete after full test, type and lint run


## 5779127 Document set --in-include and the choices behind it


## 24fa3ca Add set --in-include to write new keys into the shared included file

Sometimes a new setting belongs in the shared file, for every theatre
that includes it. The flag turns off override placement for new keys
only; they go into the file holding their deepest existing ancestor (the
innermost included one when it is merged). Existing values, appends,
deletes, exit codes and events are as without it.


## ab49293 Archive config-include-overrides and sync its specs into spec/specs

Synced rather than archived alone so the main specs describe what the
code and tests now do (new keys under includes become overrides); the
reason is recorded in the archived design.md.


## 9b44549 Mark config-include-overrides tasks complete after full test, type and lint run


## 2c8805b Document mapping-form includes, overrides and where set writes


## c2a9408 Test that reconcile, watch and history follow mapping-form includes

Hand-added overrides are recorded as file edits, converting an include
to mapping form records nothing, files reached through $ref are watched,
and an end-to-end set leaves the shared file untouched.


## 4580f99 Change overridden values in the override; delete keys from every layer

An overridden value lives in the override, so set must change it there
or the include would still show the old one. A deleted key is removed
from the included file and from each override that sets it, because
overrides cannot delete and would otherwise bring it back; an override
mapping left empty is removed too. The bare include string no longer
counts as unchanged when overrides exist, so they are never dropped
silently.


## 282ca80 Write new keys under an include as overrides in the including file

Included files are shared between theatres, so a new setting under an
included section must not change them. The key goes into the $ref
mapping next to the include reference, converting a scalar-form include
to mapping form first. Lists are still written where they live, since
overrides cannot address list items.

Also fix where a new entry goes after an entry whose value is an include:
its end is the end of the reference, not of the included file.


## 8b6e0ab Load mapping-form includes: $ref plus overrides, deep-merged with the included content

Shared included files can now be specialised per theatre without editing
them. Merged mappings remember the mappings they were built from, so
every value still knows the file it is written in.


## 31fa98b Plan set --in-include: an explicit way to put a new key in the shared file (method change config-set-in-include)


## c6efc5f Record product-owner answers and the reasons for out-of-contract override choices


## deee957 Plan include overrides: new keys under shared includes go to the including file (method change config-include-overrides)

