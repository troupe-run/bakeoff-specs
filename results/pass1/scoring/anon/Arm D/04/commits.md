# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## 30b372a Record lineage on every config history event

Each event now carries actor (TROUPE_ACTOR human:<id>/agent:<id>, default
the login name; unknown for imports and hand edits), via (import/cli/file),
an RFC 3339 UTC `at`, the `set --reason` text, and a `change` id shared by
all events of one command, reconcile or import. An invalid TROUPE_ACTOR
exits 2. Events stored before lineage are upcast: their time is known,
their actor is unknown, and a legacy set/remove has null via and change
because its origin cannot be told.

