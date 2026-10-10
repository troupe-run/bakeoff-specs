# Commits (26, newest first)

Each commit's short SHA and subject, then its message body.

## 7fe7040 Record D-12: /method-command retry failed like D-10; WP05 done restored with override reason

## edb0ef3 Record D-11: post-merge acceptance re-run on the feature branch (lenient for docs/ only), main gains bookkeeping only

## 8cba484 Record acceptance commit for troupe-config-lineage-01M436R0

## b5777a9 Accept troupe-config-lineage-01M436R0

## 3d51b78 chore(troupe-config-lineage-01M436R0): capture mission retrospective


## 35ceee6 Merge feat/troupe-config-lineage: lineage (actor, via, at, reason, change) on every troupe config history event

TROUPE_ACTOR (human:<id> | agent:<id>, else exit 2) attributes CLI changes; imports and file reconciles are attributed to the unknown actor; set --reason records why; every producer gets one change id; lineage persists in the event store, and pre-lineage histories are reported honestly without being rewritten.


## 203d062 Integrate troupe-config-lineage: lineage on every history event (actor, via, at, reason, change)

Brings the reviewed WP01-WP05 code from the coordination branch (identical to lane-e) after method merge's squash conflicted on meta.json; planning files kept, event logs combined (research D-10). TROUPE_ACTOR is checked before the theatre is located; set --reason; old histories are upcast on read, never rewritten. Gates: 1652 passed, mypy --strict, ruff check/format clean.


## d0568a6 Finalize acceptance artifacts for troupe-config-lineage-01M436R0

## 8c79856 Record acceptance commit for troupe-config-lineage-01M436R0

## 8d4739f Accept troupe-config-lineage-01M436R0

## e60b788 Record WP review cycles and status for troupe-config-lineage-01M436R0 (all WPs approved)

## c5a2749 chore: Capture baseline tests for WP05

## c109bd2 chore: Capture baseline tests for WP04

## 4f352a2 chore: Capture baseline tests for WP03

## 4027752 chore: Capture baseline tests for WP02

## d27ae66 chore: planning artifacts for troupe-config-lineage-01M436R0

Auto-committed by method before creating the lane worktree for WP02

## d70a700 chore: Capture baseline tests for WP01

## 1359dbf docs(record-analysis): record analysis report for mission troupe-config-lineage-01M436R0

## 403bdfa Add tasks for feature troupe-config-lineage-01M436R0

## f77b9e9 chore: Map requirements for WP01, WP02, WP03, WP04, WP05 on spec troupe

## cee0fda Add research (D-1..D-9), data model, CLI/history contract and quickstart for lineage: v2 events upcast on read, one Lineage per producer

## ab29dce Add plan for feature troupe-config-lineage-01M436R0

## a252fbb Record decision index for troupe-config-lineage specify

## af3c6d6 Record specify decision moments for troupe-config-lineage (legacy events, TROUPE_ACTOR check order, unknown login name)

## 0d0105e Add spec for troupe-config-lineage: actor, via, at, reason and change on every history event

## 6b71882 Add scaffold for feature troupe-config-lineage-01M436R0
