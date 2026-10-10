# Commits (8, newest first)

Each commit's short SHA and subject, then its message body.

## 3344886 Document lineage in the README and earlier specs

Docs and the step 1-2 specs must agree with the new history fields and set --reason
(Principle VI), including that step 2's no-source-field assumption is now superseded.


## 5eabdfe Test that lineage survives restarts unchanged

An audit trail that changes after the fact is not one: later processes, under any actor,
must print earlier events' lineage byte for byte, read from the store.


## c13700c Let set record a reason, and pin when each change happened

Auditors need to know why a setting changed and when. set --reason TEXT is kept exactly on
the set's own events only, never on a reconcile the same invocation records, and timestamps
are proven to be UTC and inside the recording command's run.


## d4c0a20 Test that change ids group exactly one unit's events

A multi-value change is only reviewable as a unit if its events can be told apart from the
next action's; these tests pin that an import, a reconcile and a set made by one invocation
are three units, and that filtering history never alters the ids.


## 2d3ef22 Record who changed each setting and how, stored with every event

The Lineage contract needs an auditable answer to who changed a setting and through what.
Lineage travels as arguments of the existing LeafChanged event, so it is persisted, replayed
and recorded atomically with the event itself. One Lineage per import, reconcile or set
gives each unit a shared change id and timestamp by construction, and hand edits and imports
are stamped with the unknown actor rather than the CLI user's. TROUPE_ACTOR is checked by
every subcommand before the theatre is touched, so an invalid identity records nothing.


## cb7367b Add step 4 tasks: lineage, test-first by user story

Breaks the lineage plan into ordered, test-first tasks so implementation can proceed
story by story, with the shared storage and history output done first.


## 9a1001e Add step 4 plan: lineage stored in each LeafChanged event

Design for the Lineage contract: lineage travels inside the existing event so it is as
durable and atomic as the event itself, one Lineage per store call groups each unit, and
TROUPE_ACTOR is checked in the CLI before anything is loaded.


## dcc95db Add step 4 spec: lineage for every history event

Records who, how, when, why and with-what-else for each configuration change, as the
product owner's Lineage contract requires, and fixes the open points (change units,
TROUPE_ACTOR validation, empty values) as decisions so planning can start.

