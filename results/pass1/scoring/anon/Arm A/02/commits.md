# Commits (21, newest first)

Each commit's short SHA and subject, then its message body.

## c89fc30 test(config-file-sync): cover watch's unknown-option usage error and the core-to-CLI boundary

Feature validation found that 4.7's unknown-option case was untested for watch, and
that only the write-back half of the core import rule was guarded. Both are now pinned
by tests.


## 7e516ec feat(config-file-sync): run the full quality gate and check traceability

Every config-file-sync requirement is named by at least one test that proves it, and
every new test names its requirements, so spec and tests can be checked against each
other. The roadmap now marks step 2's spec complete.


## cb21c18 feat(config-file-sync): validate concurrency, failures, signals and clean-up end to end

Proves with real processes that a set running alongside watch records exactly its
own events. Hand edits raced by show commands are recorded once with consecutive seq.
Invalid YAML is reported once and recovered. SIGINT and SIGTERM exit 0 cleanly, and
nothing but the history store is left under .troupe/. Background show loops make the
races real: the tests fail when the lock is removed.


## 96becbd feat(config-file-sync): validate watch observation end to end

Proves through a real watch process that an edit made the moment the readiness line
appears is recorded, that edits at any point of the poll cycle land within 2 s, and
that every include kind, rename-saves and hand-added or removed includes are followed.
Edits that change no leaf record nothing.


## bedf077 feat(config-file-sync): add the watch subcommand and the watch-process test helper

troupe config watch prints 'watching <dir>' only after its first sync, so the line is
a true promise. It reports problems on stderr only and exits 0 on SIGINT or SIGTERM.
The signal handlers only set a flag, so a reconcile in flight always finishes its
single transaction. The previous handlers are restored on every path.


## 1d178c3 feat(config-file-sync): let subcommands stream output and see the theatre as typed

watch must print its readiness line and keep running, which the buffered handler
model cannot do, and it must name the directory as given. run() now dispatches a
streaming handler with the same error conventions, and --theatre also keeps its raw
text. show, set and history are unchanged.


## 112d2ed feat(config-file-sync): build the watcher loop

watch must record edits within 2 s of a change, follow includes, and survive
half-saved files and an unreadable store. The loop compares byte snapshots of the
loaded files against a baseline built from the bytes each load actually read. That
way a file read mid-save, then restored, is still repaired. Failures are reported once
per distinct message and retried on every tick.


## b978b9b feat(config-file-sync): validate reconcile-first through the real CLI

Proves through real troupe config processes, on troupe.yml and troupe.yaml, that show
and set pick up edits made while nothing ran, that history never does, and that
failing commands keep or record nothing as specified. The positive cases fail when
reconcile-first is disabled.


## cced0b3 feat(config-file-sync): align docstrings and the step 1 specs with step 2

Spec, code and tests must agree. Docstrings no longer say set and remove events come
only from set, and the step 1 requirements, designs and roadmap say where step 2
supersedes 'hand edits add no event'. The step 1 text itself is kept, with notes
added beside it.


## cf46941 feat(config-file-sync): open every theatre under the lock and reconcile by default

Edits made while troupe was not running must reach the history, so every command
now locks the theatre and reconciles when it opens it. history opts out and only
reports what is recorded, though it still imports a fresh theatre. The step 1 tests
that asserted hand edits add no events are rewritten in this change, so the suite
never contradicts the code.


## 52cfe79 feat(config-file-sync): compute and record the reconcile changes

Reconcile diffs the files' leaves against the recorded configuration with the same
typed comparison as set: set events in document order, then remove events in creation
order, all recorded in one transaction. Formatting, comment and include-form rewrites
give nothing. The design is amended so removed paths are rebuilt without PATH
validation, because otherwise a removed empty key would block every later reconcile.


## bf13cf2 feat(config-file-sync): provide the exclusive per-theatre lock

Without mutual exclusion, watch could record a set's write-back between the set's
file write and its event record, and concurrent appends collide in the store. The lock
is a flock on the existing .troupe/ directory, so it creates no file (decision E) and
the kernel frees it when a process dies. A nested acquire raises instead of deadlocking.


## 9532675 feat(config-file-sync): fold the history into the recorded configuration

Reconcile compares the files with what the history records, so the history's
import/set/remove events are folded into live leaves. Each leaf keeps its creation seq,
which orders remove events (2.6). Creation is decided by presence in the fold, not by a
null old value, because a leaf can hold null.


## 92fe278 feat(config-file-sync): make typed comparison and watch constants available to core code

Reconcile must compare leaves exactly as set does without the core depending on the
write-back package, so scalar_equal moves into troupe.config.scalars, re-exported from
compare. A boundary test keeps core modules free of write-back imports.


## cc69eaf spec(config-file-sync): approve the implementation plan

The product owner approved the tasks, so the spec is ready for implementation.


## 7629e92 spec(config-file-sync): generate the implementation plan

The plan moves the history opt-out and the rewrite of the superseded step 1 tests into
the same task that makes reconcile the default, so no intermediate commit has history
reconciling. The watch-process helper comes before the first task that needs it. Design
approved by the product owner; task-graph sanity review passed (independent).


## 161879d spec(config-file-sync): design reconcile, theatre lock and watch

Reconcile runs inside open_theatre (history opts out), diffing the files against
the recorded configuration so a set's write-back is never recorded again. A file-less
flock on .troupe/ serialises commands, closing the window between a set's write and
its record. watch polls byte snapshots taken before each load so its readiness line
is a true promise. Requirements approved by the product owner.


## 1ba03be research(config-file-sync): analyse the gap between sync requirements and the code

Records what reconcile and watch can reuse (open_theatre, document.files, scalar_equal,
record_changes), and what is missing. That includes a verified failure: two processes
appending to the history collide with an IntegrityError, so a lock is required.


## 28e738a spec(config-file-sync): generate requirements for syncing files and history

Pins down reconcile against the recorded configuration, reconcile-first for every
command but history, the watch readiness promise and 2-second bound, and that a
set's write-back is recorded only once. States which step 1 criteria (foundation 6.9
and 7.3) this supersedes, and the conservative choices where the contract is silent.


## fa8cf30 spec(config-file-sync): initialise the step 2 sync spec from the discovery brief

The project description carries the step 2 contract section verbatim, so requirements
can be written against the contract rather than a paraphrase of it.


## 8f58c05 discovery(config-file-sync): plan step 2 sync between files and history

Step 2 makes hand edits reach the history, through reconcile-first commands and
troupe config watch. That reverses step 1's 'importing is not reconciling', so the
roadmap records the new spec, the approach (diff against the recorded configuration,
stdlib polling, an inter-process lock), and the existing-spec amendments.

