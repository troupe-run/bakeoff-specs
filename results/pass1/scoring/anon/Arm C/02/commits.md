# Commits (26, newest first)

Each commit's short SHA and subject, then its message body.

## 3b401de research R-11: record the retried method merge and the WP04 done override

## ad2413d Record acceptance commit for troupe-config-sync-files-01M3ZT6R

## b8b5b4c Accept troupe-config-sync-files-01M3ZT6R

## 3aed8a0 Record WP status history for troupe-config-sync-files-01M3ZT6R on main

The previous snapshot was empty: feat held only lifecycle events, while the WP
status events lived on the coordination branch. Combine both streams (as step
1's log does) and take the materialized snapshot (4/4 WPs done).


## 56a1700 Record final status snapshot for troupe-config-sync-files-01M3ZT6R

All four WPs done; tracked like step 1's status.json.


## 2956227 research R-11: record method merge squash failure and the manual squash of WP01-WP04

## 8e63090 feat(troupe-config): keep files and configuration in sync (watch, reconcile-first)

Step 2: people edit .troupe/ files by hand while troupe runs or while nothing
runs. Hand edits are now recorded in the history as set/remove events:

- reconcile compares the files' leaves with the recorded configuration (the
  history aggregate's replayed leaves) and records only the differences, so
  formatting- and comment-only edits record nothing;
- show and set reconcile first; history never reconciles;
- troupe config watch prints 'watching <dir>' once it can observe changes and
  reconciles within 2 s of any change to the root or an included file,
  following includes added or removed by hand, surviving unloadable edits,
  exiting 0 on SIGINT/SIGTERM;
- every session runs under an exclusive flock on the .troupe directory, so a
  set's write-back is already recorded before watch sees it and each hand
  edit is recorded exactly once.

Squash of WP01-WP04 from method/mission-troupe-config-sync-files-01M3ZT6R
(identical to the reviewed lane-d tree); method merge's squash failed on
sparse spec on the mission branch, so the code is brought across here.


## ea98937 Finalize acceptance artifacts for troupe-config-sync-files-01M3ZT6R

## 05c13a2 Record acceptance commit for troupe-config-sync-files-01M3ZT6R

## 81555f2 Accept troupe-config-sync-files-01M3ZT6R

## 71b6eb2 Record review cycles for troupe-config-sync-files-01M3ZT6R

WP01-WP04 review records, including WP04's cycle-1 rejection feedback (missing
black-box test for serialised reconciles).


## e1348b6 quickstart: portable in-place edits, mktemp theatre, kill -INT $! (review notes from WP04)

## 4ace511 chore: Capture baseline tests for WP04

## 51b08c6 chore: Capture baseline tests for WP03

## 8632ae0 chore: Capture baseline tests for WP02

## 3b0b505 docs(record-analysis): record analysis report for mission troupe-config-sync-files-01M3ZT6R

## 8efb3c1 chore: commit method WP01 claim frontmatter and vcs lock bookkeeping

record-analysis refuses to run on a dirty tree; these fields were written by
method when WP01 was claimed.


## ea36cf6 chore: Capture baseline tests for WP01

## 0125f53 docs(record-analysis): record analysis report for mission troupe-config-sync-files-01M3ZT6R

## 5102e12 data-model: open_session keeps Theatre arg and re-locates under the lock; replay tolerates step-1 removes of unrecorded paths

## 4e9d42e Add tasks for feature troupe-config-sync-files-01M3ZT6R

## df42267 chore: Map requirements for WP01, WP02, WP03, WP04 on spec troupe

## be613e5 Add research, data model, watch contract and quickstart; FR-009 echoes theatre dir as given (D-8)

## c340ce1 Add plan for feature troupe-config-sync-files-01M3ZT6R

## 2941e03 Add spec for troupe-config-sync-files: watch, reconcile-first, no re-detected write-backs

## 6079eb9 Add scaffold for feature troupe-config-sync-files-01M3ZT6R
