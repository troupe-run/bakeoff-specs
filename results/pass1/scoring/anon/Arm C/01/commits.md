# Commits (38, newest first)

Each commit's short SHA and subject, then its message body.

## b5c81f9 Record R-20: WP08 marked done after method merge failure (code merged in e0d74f9)

## d0fa8b6 op(reviewer-renata): audit [01M3XV5M]

## 81fb62a Record acceptance commit for troupe-config-load-show-set-01M3XGPG

## de013b8 Accept troupe-config-load-show-set-01M3XGPG

## 772a741 chore: record method Op for mission acceptance re-run


## 5426abb chore: ignore Python build artefacts

Untracked __pycache__ directories blocked method move-task during the
troupe-config mission; ignore them and the tool caches/venv explicitly.


## e0d74f9 feat(troupe-config): load, show, set and history for troupe configuration

Squash-merge of mission troupe-config-load-show-set-01M3XGPG (WP01-WP08,
each independently reviewed and approved):

- CLI `troupe config show|set|history --theatre DIR` with contracted exit
  codes (2/3/4/5), empty stdout on failure, errors naming path or file.
- Loader with recursive `file:` includes (YAML embedded, other text exact),
  missing/cycle -> exit 4; YAML 1.2 core-schema scalar resolution.
- Byte-surgical `set`: parse-and-splice write-back (never re-serialised),
  quoting rules, comment columns, block/folded scalars, new entries below
  trailing comments, flow appends, verify-before-write, atomic writes.
- Event-sourced per-leaf history (eventsourcing + SQLite under .troupe/),
  import on first command, set/remove events, JSON Lines output.

Spec merge done by hand because method's automatic squash treated
planning artifacts absent from the coordination branch as deletions;
planning files were kept from this branch, status/acceptance/review
records taken from the mission branch.

Gates: pytest 1185 passed; mypy --strict, ruff check, ruff format clean.


## 7b2ffdd Finalize acceptance artifacts for troupe-config-load-show-set-01M3XGPG

## f5ad876 Record acceptance commit for troupe-config-load-show-set-01M3XGPG

## 34ec14a Accept troupe-config-load-show-set-01M3XGPG

## 7c1b226 chore: commit method WP01 frontmatter and status bookkeeping

## de33d92 chore: Capture baseline tests for WP08

## c75e82c chore: planning artifacts for troupe-config-load-show-set-01M3XGPG

Auto-committed by method before creating the lane worktree for WP08

## 886bdf3 chore: Capture baseline tests for WP07

## c2a5d76 chore: planning artifacts for troupe-config-load-show-set-01M3XGPG

Auto-committed by method before creating the lane worktree for WP07

## bbf9d14 chore: Capture baseline tests for WP06

## 77d9e48 chore: planning artifacts for troupe-config-load-show-set-01M3XGPG

Auto-committed by method before creating the lane worktree for WP06

## 9cc2fdd chore: Capture baseline tests for WP04

## 1f1310d chore: Capture baseline tests for WP05

## 5dbbf80 chore: Capture baseline tests for WP03

## 3631a65 chore: Capture baseline tests for WP02

## bc992ca chore: planning artifacts for troupe-config-load-show-set-01M3XGPG

Auto-committed by method before creating the lane worktree for WP02

## 15ffafd chore: Capture baseline tests for WP01

## 9f862b9 chore: charter synthesis artifacts

method agent action implement requires the synthesized doctrine
graph; this is the generated fresh-project minimal set (no charter
content changes).


## a4a3c27 docs(record-analysis): record analysis report for mission troupe-config-load-show-set-01M3XGPG

## 3e1c242 Align spec, plan and data model with recorded decisions (analysis findings I1-I4, U1, U2); record R-19

## 4182ee4 docs(record-analysis): record analysis report for mission troupe-config-load-show-set-01M3XGPG

## 014888d Revise R-16 per product owner (LF text include accepts any VALUE, written as typed); record R-18 implementation handoff decision

## 4ba6222 Assign python-pedro profile to all WPs; record research R-13..R-17 (YAML 1.2 core resolver, BOM, eventsourcing app lifetime, text-include non-string VALUE, verify-before-write) and align plan source layout with WP ownership

## cc97760 Add tasks for feature troupe-config-load-show-set-01M3XGPG

## 4f345c4 chore: Map requirements for WP01, WP02, WP03, WP04, WP05, WP06, WP07, WP08 on spec troupe

## 5b77847 Add plan research, data model, contracts and quickstart; record plan decisions (span-splice write-back, SQLite history)

## 3687095 Add plan for feature troupe-config-load-show-set-01M3XGPG

## 849d23b Record specify decision moment (files on disk are source of truth)

## 60bc3ec Add spec for troupe-config-load-show-set: step-1 config load/show/set/history contract

## 455285c Add scaffold for feature troupe-config-load-show-set-01M3XGPG

## 901fd5d Set up method/method 3.2.7

## c13279d chore: generate project charter for troupe config subsystem

Encodes the product owner's principles as governance: byte-for-byte
preservation of hand-edited YAML, conservative data-safe defaults,
path-naming errors, real-shape tests, verified quality gates (pytest,
mypy --strict, ruff), one decision per named place, and the
product-owner question protocol. Narrows activated doctrine to the
directives that match; records doctrine gaps as TROUPE-001..009.
config.yaml is included because it carries the charter: pointer.

