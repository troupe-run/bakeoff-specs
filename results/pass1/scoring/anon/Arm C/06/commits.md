# Commits (35, newest first)

Each commit's short SHA and subject, then its message body.

## cd1330d Finalize acceptance artifacts for troupe-config-anchor-aliases-01M48SQ8

## 0b48788 Record acceptance commit for troupe-config-anchor-aliases-01M48SQ8

## 32c6d58 Accept troupe-config-anchor-aliases-01M48SQ8

## 4a1ca69 Spec C6: record the product owner's ruling that a new key under an alias in an included file stays refused

The Aliases rule (exit 3, stderr mentions --expand-alias) does not depend on which file the
write would land in; the Overrides section only says where a new key is written. Behaviour
is unchanged (already covered by the C6 tests); this records why.


## 9a638fb Merge fix/troupe-config-anchor-aliases: anchors and aliases stay honest (bug repo)

Step 6, contract section Aliases. Setting a value at an anchor changes it everywhere;
setting a path reached through an alias exits 3 (stderr mentions --expand-alias) and changes
nothing; set --expand-alias replaces that alias with a block-style copy marked
'# expanded from *<name> by troupe' and sets the value in the copy; merge keys are never
written. Out-of-contract choices A-0, C1-C14 are recorded in the mission spec.


## 77fa884 chore(troupe-config-anchor-aliases-01M48SQ8): capture mission retrospective

## 4fccf9e chore(troupe-config-anchor-aliases-01M48SQ8): flatten coordination metadata after branch deletion (#3086)

## 7e446c4 chore(troupe-config-anchor-aliases-01M48SQ8): record done transitions for merged WPs

## ed006c7 feat(method/mission-troupe-config-anchor-aliases-01M48SQ8): squash merge of mission

## ec4e835 Finalize acceptance artifacts for troupe-config-anchor-aliases-01M48SQ8

## b553a81 Record acceptance commit for troupe-config-anchor-aliases-01M48SQ8

## 18704f1 Accept troupe-config-anchor-aliases-01M48SQ8

## 9d74448 Record WP06 review cycle (approved) for troupe-config-anchor-aliases; all WPs approved


## 3d65c5a Escape '|' in '|+' inside Markdown table cells of spec, contract and data model


## 7f13314 Data model: list the write refusals found during implementation (A-0, C9)


## 8e58114 Spec agreement for troupe-config-anchor-aliases: record refusals found during implementation

Keeps spec, contract and code in agreement (TROUPE-009; analysis I1, I2, U1-U3; WP06 table):
A-0/FR-007 (new '<<' key, replacing a '<<' mapping, copy containing '<<' -> exit 3),
C5 (anchor off its key line -> exit 3), C9/FR-006 (|+ copy, redefined anchor in copy,
expansion and key in different files -> exit 3; comment spacing on expanded lines),
FR-002 (recursive alias), FR-004 (refusal before no-op), --in-include edge case, and the
matching CLI messages.


## 58e207f chore: Capture baseline tests for WP06

## 4e6fa2f Record WP05 review cycle (approved) for troupe-config-anchor-aliases


## 73be11c chore: Capture baseline tests for WP05

## 5f66b26 Record WP03/WP04 review cycles (approved) for troupe-config-anchor-aliases


## ccfe6f1 chore: Capture baseline tests for WP04

## 2cb810d chore: Capture baseline tests for WP03

## 7a67922 Record WP02 review cycle (approved) for troupe-config-anchor-aliases


## 55e78fb Record WP01 review cycle (approved) and WP02 claim bookkeeping for troupe-config-anchor-aliases


## 3ed483a chore: Capture baseline tests for WP02

## da4fb6d Record WP01 claim metadata for troupe-config-anchor-aliases (vcs lock, agent/profile)


## 8a43211 chore: Capture baseline tests for WP01

## 8f59671 docs(record-analysis): record analysis report for mission troupe-config-anchor-aliases-01M48SQ8

## 297995b Record task status bookkeeping for troupe-config-anchor-aliases (6 WPs seeded, python-pedro profiles)


## 5c06c23 Add tasks for feature troupe-config-anchor-aliases-01M48SQ8

## 34643be Plan artifacts for troupe-config-anchor-aliases: research R-1..R-10, data model, CLI contract, quickstart

Spec amended with the product owner's planning answers (DM 01M48T5X483RCHEXYJ60R4N35P):
C9 also refuses expanding an alias not on its key's or dash's line, C13 makes << beside $ref
unloadable, C14/FR-010 keep anchors and aliases out of a set VALUE (exit 2).


## 2a2999b Add plan for feature troupe-config-anchor-aliases-01M48SQ8

## 88e2578 Record specify decision moment for troupe-config-anchor-aliases (merge keys: agent choice A-0)


## c20e4d1 Add spec for troupe-config-anchor-aliases: step 6 Aliases (bug qht) with agent choices A-0, C1-C12 confirmed by the product owner

## 9bdfcea Add scaffold for feature troupe-config-anchor-aliases-01M48SQ8
