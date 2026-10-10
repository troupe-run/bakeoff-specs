# Commits (17, newest first)

Each commit's short SHA and subject, then its message body.

## 2ad9e80 feat(config-lineage): align the earlier specs and docstrings with step 4 and check traceability

Spec, code and tests change together: the step 1-3 specs now point to where
lineage is specified, and every config-lineage requirement is named by a test.


## 6564346 feat(config-lineage): validate set --reason end to end


## 9ab02a7 feat(config-lineage): validate TROUPE_ACTOR end to end


## 5746c82 feat(config-lineage): validate lineage of each origin, change grouping and time end to end


## 3e4cd37 feat(config-lineage): accept --reason TEXT on set

People and agents can say why they changed a setting; the reason labels only
the set's own change, never the reconcile before it.


## 0fab38f feat(config-lineage): print the five lineage members on every history line

Auditors read lineage through history; step 1-3 tests keep pinning their facts
through one projection of the step-1 members, which now also rejects any stray
member.


## e47b082 feat(config-lineage): read histories recorded before step 4

Stores written by steps 1-3 have no lineage; upcasting them on read keeps
them readable, shows unknown where nothing is known, and never rewrites them.


## 7d1bc83 feat(config-lineage): store lineage with every history event and stamp each batch once

A recorded batch already is one import, one reconcile or one set, so the store
stamps it with one change id and one time; import, reconcile and set only say
who, how and why.


## b567ba3 feat(config-lineage): read the actor from TROUPE_ACTOR and refuse invalid values in every subcommand

The actor is a CLI input, so it is read once in run() before any handler and
rejected with exit 2 before any state is touched; tests no longer inherit it
from the developer's shell.


## 2e5fad2 feat(config-lineage): provide the lineage values, the batch stamp and the timestamp format

The core needs one home for who/how/why of a batch and for how its time and
change id are made, before the store can stamp batches.


## 8d54867 spec(config-lineage): record that pre-step-4 history display is our choice

The product owner confirmed the contract does not cover events recorded before
step 4, so their lineage (via cli, actor unknown for old set/remove) is a
recorded design choice rather than an open question.


## 051ac11 spec(config-lineage): generate and approve the implementation plan

Task-graph sanity review (independent): PASS after one repair pass.


## da167bc spec(config-lineage): design lineage stamping per batch, TROUPE_ACTOR and --reason

Each batch the store records is already one change, so the store stamps it
with one id and one time; callers only say who, how and why. Requirements
are approved with the design (fast-tracked run).


## a4dc342 spec(config-lineage): generate requirements for actor, via, time, reason and change id


## 90a1136 spec(config-lineage): initialise the step 4 lineage spec from the discovery brief


## c1e47c8 discovery(config-lineage): list the step 4 spec with the other specs in dependency order


## 23254c7 discovery(config-lineage): plan step 4 lineage of configuration changes

Auditors need to know who changed a setting, how, when, why, and what changed
with it. The brief fixes the boundary (lineage labels the batches the history
already records) and the open choices to settle in requirements.

