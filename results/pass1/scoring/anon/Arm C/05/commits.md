# Commits (35, newest first)

Each commit's short SHA and subject, then its message body.

## 103058d Record R-9: post-merge acceptance re-run on the feature branch (lenient for docs/ only); main gains bookkeeping only


## b4fcfcd Record acceptance commit for troupe-config-include-overrides-01M46FY4

## bb6b119 Accept troupe-config-include-overrides-01M46FY4

## b18a000 Record post-merge mission review for troupe-config-include-overrides: PASS WITH NOTES

All 13 FRs covered by real-CLI tests; no drift; two LOW risks (verifier defence in depth, tracker c22; nearest-include rule can write an intermediate included file, by PO decision DM 01M46FYYFFXXZE893KWDP2WJCW).


## ded0223 Merge feat/troupe-config-include-overrides: new keys under shared includes become overrides; set --in-include opts back into the shared file

Step 5 change requests CR-A (Overrides: mapping-form includes with $ref, deep merge, new keys written as overrides in the including file nearest the key's deepest existing ancestor; scalar-form includes converted keeping their end-of-line comment) and CR-B (In-include: set --in-include writes a new key into the included file, the step-1 rule). Existing values still change where they live; list appends and keys inside list items stay in the file holding the list.

Mission troupe-config-include-overrides-01M46FY4: WP01-WP05 implemented and independently reviewed, accepted (6f52139), 1848 tests passed, mypy --strict and ruff clean.


## 619b046 chore(troupe-config-include-overrides-01M46FY4): capture mission retrospective

## 7a0e938 chore(troupe-config-include-overrides-01M46FY4): flatten coordination metadata after branch deletion (#3086)

## 0afc642 chore(troupe-config-include-overrides-01M46FY4): record done transitions for merged WPs

## 36874e6 feat(method/mission-troupe-config-include-overrides-01M46FY4): squash merge of mission

## f99a8b2 Finalize acceptance artifacts for troupe-config-include-overrides-01M46FY4

## 4301613 Record acceptance commit for troupe-config-include-overrides-01M46FY4

## 6f52139 Accept troupe-config-include-overrides-01M46FY4

## 9dfc2bc docs(record-analysis): record analysis report for mission troupe-config-include-overrides-01M46FY4

## d20616e Record review cycles for troupe-config-include-overrides (WP04 cycle 2 approved, WP05 approved)


## 568cd68 Align spec, research and data model with the code as built (WP05 agreement check)

- spec D-4/D-5: name the next-line and whole-document conversion shapes and the flow-parent comment-column exception (analysis U1, I2)
- spec US2-5/US4-2: base.yaml resolves to agents/models/base.yaml
- data-model: holder is set on every $ref include; ConvertInclude carries parent/slot (analysis I1)
- research R-3/R-5: --in-include uses _on_base; verifier allowances _gains_override and recursive _orders (tracker c3z)


## af2108d chore: Capture baseline tests for WP05

## d577447 docs(record-analysis): record analysis report for mission troupe-config-include-overrides-01M46FY4

## c3ac01b Record review cycles and claim metadata for troupe-config-include-overrides (WP01-WP03 approved, WP04 cycle 1 changes requested)


## fbf4436 Spec: record that includes with anchors/tags never reach conversion (exit 4 at load) and that conversion refuses any preceding text (exit 3)

Found in the WP02 review (tracker repo); verified in WP04.


## cb07966 chore: Capture baseline tests for WP04

## 0d7d5a8 chore: Capture baseline tests for WP03

## 052adfe chore: Capture baseline tests for WP02

## 9e59f2c chore: planning artifacts for troupe-config-include-overrides-01M46FY4

Auto-committed by method before creating the lane worktree for WP02

## b369963 chore: Capture baseline tests for WP01

## 78e5adc docs(record-analysis): record analysis report for mission troupe-config-include-overrides-01M46FY4

## 82518a4 Assign agent profiles to troupe-config-include-overrides WPs (python-pedro, claude) and record task status bookkeeping


## c0a22dc Add tasks for feature troupe-config-include-overrides-01M46FY4

## 6072099 Refine R-1/R-3: merged sides kept as found; nearest include reference found by target file identity; writes use concrete parents only

Same behaviour as the approved alignment; made precise while writing work packages.


## 59f0c72 Record plan decision moment for troupe-config-include-overrides (engineering alignment approved)


## 186a484 Add research (R-1..R-8), data model, CLI contract and quickstart for include overrides: merged-view MergedMapping, placement in one module, verifier conversion allowance


## ef7dc7b Spec: record planning choices D-10 (partly overridden mapping replace exits 3), D-11 (multi-line include string conversion exits 3), D-7 correction (empty target stays an empty mapping as in step 1)

Found while planning against the loader and write-back code; out of contract, agent's choice, approved in DM 01M46GE1PATR2GJF9SGQ9NAWQ1.


## ccd2a6b Add plan for feature troupe-config-include-overrides-01M46FY4

## 1493d5e Record specify decision moments for troupe-config-include-overrides (nested include target, malformed $ref, --in-include on existing values)


## b221059 Add spec for troupe-config-include-overrides (step 5, CR-A + CR-B): new keys under shared includes become overrides in the including file; set --in-include opts back into the step-1 rule


## 879e62b Add scaffold for feature troupe-config-include-overrides-01M46FY4
