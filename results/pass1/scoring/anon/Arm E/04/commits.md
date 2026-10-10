# Commits (2, newest first)

Each commit's short SHA and subject, then its message body.

## b88f379 Reject a malformed TROUPE_ACTOR in every troupe config command

The Lineage rule covers any CLI command, so get, show, history and watch
now exit 2 (empty stdout, message on stderr) before touching anything.


## c3397d4 Record lineage on every config event: actor, via, at, reason, change id

troupe config set takes --reason; its actor comes from TROUPE_ACTOR
(human:<id> | agent:<id>, else exit 2), defaulting to the login name.
Imports and file reconciles have an unknown actor. Events from before
lineage replay with an unknown actor and their stored timestamp.

