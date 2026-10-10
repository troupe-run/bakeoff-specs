# Commits (11, newest first)

Each commit's short SHA and subject, then its message body.

## aacd93a Test the step 2 edge cases convergence found untested

The main file being deleted and recreated while watching, a signal arriving
mid-reconcile, hand edits that change a node's kind, and a two-level include
under watch were handled but unproven; each test was checked against a
deliberate break.


## 71138fb Append convergence tasks for step 2

Three spec edge cases (main file deleted and recreated while watching, a signal
during a reconcile, hand edits that change a node's kind) are handled in code
but untested, which Constitution II forbids; SC-101 also asks for a nested
include under watch.


## 1ffdd01 Document watch and reconcile; mark step 1 D-1 superseded

Readers of the README and of the step 1 spec would otherwise still believe hand
edits are never recorded.


## ac3a198 Prove a set under watch is recorded exactly once

Without these tests nothing would catch a set's write-back being recorded a
second time by watch, or a hand edit recorded by two processes; they compare
whole histories with and without watch and show the lock is what prevents it.


## a5891db Add troupe config watch

People edit .troupe/ files in their editor while troupe runs; watch records
each edit within 2 seconds. It polls the exact bytes it last parsed, so the
'watching' line is a true promise and editors that save by rename are seen;
a broken file is reported once and retried instead of ending the watch.


## 32a6eec Reconcile hand edits before show and set

Edits made in an editor while nothing was running were invisible to history;
show and set now record them first, under the theatre lock. history still
reports only what was recorded, so the step 1 test asserting that hand edits
are never recorded is updated to the step 2 rule.


## a9a46ba Satisfy ruff in the reconcile change

The previous commit went in before ruff was run; the constitution requires a
clean lint and format check.


## 39823b7 Add reconcile and the theatre lock

Step 2 records hand edits by comparing the files with the projection; the lock
lets a command load, write and record without another process recording the
same change in between, so each change is recorded exactly once.


## 34b2667 Add step 2 task list

Orders the work so offline-edit reconcile (US1) ships first and is usable on
its own, then watch (US2), then the exactly-once interplay (US3), with a test
and a deliberate-break check for every behaviour as the constitution requires.


## ebf44e2 Add step 2 plan and design artifacts

Reconcile reuses step 1's leaf diff against the projection; a cross-process
flock held from load to record makes every change recorded exactly once, so a
set's own write-back is never recorded again by watch. watch polls the exact
bytes it parsed so its 'watching' line is a true promise. FR-114 is reworded
to the remove order the projection actually has.


## cd9b7dc Add step 2 spec: keep files and configuration in sync

Step 2 adds 'troupe config watch' and makes commands reconcile hand edits, so
history reflects every change exactly once. The spec restates the Sync with
files contract as testable requirements and records the open choices
(D-10..D-17), superseding step 1's D-1.

