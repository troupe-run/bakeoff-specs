# Commits (6, newest first)

Each commit's short SHA and subject, then its message body.

## a055610 Archive config-lineage and sync its specs into spec/specs

config-lineage becomes a main spec; config-cli and config-history take
their modified requirements, so the main specs describe step 4 as built.


## 0dac4a5 Document lineage in the README and mark config-lineage tasks complete

Users and agents need to know how TROUPE_ACTOR, --reason and change ids
appear in history, why hand edits show an unknown actor, and what
happens to step-3 stores. Full pytest, mypy and ruff runs are clean
(515 passed).


## 62ccfb7 Test lineage end to end: actors, via, reasons, change grouping, watch

Every config-lineage scenario runs through the real CLI on real theatres,
including a live watch process and separate uv run processes, so the
lineage a user audits is the lineage that was checked.


## 24291db Record lineage on every event and print it in history

Leaf events move to class version 2 carrying actor, via, at, reason and
change; one Lineage per save keeps 'one command, one change id' true by
construction. Step-3 stores are upcast on read (unknown actor, stored
time, legacy change ids), proven against a real step-3 events.sqlite.
TROUPE_ACTOR is checked for every subcommand before anything is stored,
and set takes --reason.


## afedc8a Add lineage values: actor from TROUPE_ACTOR, UTC timestamps, change ids

One module decides every lineage rule, so the import, reconcile and set
write sites cannot disagree on format or on what 'unknown' means. Tests
pin TROUPE_ACTOR and the login name so a developer's shell cannot leak in.


## 21a9bf9 Plan lineage: who, how, when, why and change id on every history event (method change config-lineage)

Step 4 makes configuration history auditable. The plan records the open
contract choices (TROUPE_ACTOR edge cases, timestamp format, change ids,
pre-step-4 stores) in design.md for product-owner review.

