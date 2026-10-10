# Commits (48, newest first)

Each commit's short SHA and subject, then its message body.

## f439ef1 Finalize acceptance artifacts for troupe-config-remote-includes-01M4BMJ5

## c678f62 Record acceptance commit for troupe-config-remote-includes-01M4BMJ5

## 37b6cdc Accept troupe-config-remote-includes-01M4BMJ5

## f172d52 Merge fix/remote-fetch-limits: 1 MiB remote body limit, no https-to-http redirects (tracker 1j5.3, 1j5.4)

Agent choices S-14..S-16 recorded in the spec after the product owner ruled both questions
out of contract. Full suite 2682 passed; mypy --strict, ruff check, ruff format --check clean.


## f215865 Remote fetch: 1 MiB body limit and no https-to-http redirects (tracker 1j5.3, 1j5.4)

The product owner ruled both out of contract and the agent's choice (2026-10-08).
S-14: a body over 1 MiB is a failed fetch (exit 4); configurations are small (under 1,000
leaves in under 50 files), and reading an unbounded body could exhaust memory. The limit is
checked against Content-Length and again while reading, so a missing or false length cannot
pass it.
S-15: a redirect from https to http is a failed fetch; the owner asked for an encrypted
source and following the downgrade would silently drop it. http->https and same-scheme
redirects still work.
S-16: http:// includes stay first-class with no warning: the contract makes them includes, and
a warning would add stderr noise to every successful command with no contract basis.
Spec, contract and research updated in the same change.


## bc8d285 Merge feat/troupe-config-remote-includes: remote includes and a schema (step 7)

Includes may name https:// or http:// URLs; they are fetched at load (10 s total deadline,
verified TLS, http(s)-only redirects) and are read-only: changing a remote value exits 3 and
quotes the include line to change instead, while new keys become local overrides.
.troupe/troupe.schema.json (JSON Schema 2020-12) validates the configuration (exit 4 at load,
exit 3 for a set) and marks format: uri settings as literals; !literal marks any other string
as a literal; set writes include-looking strings as !literal unless --include is given.
Mission troupe-config-remote-includes-01M4BMJ5, feature tracker repo;
agent choices S-1..S-13 recorded in the spec.


## 961cbed Record post-merge mission review for troupe-config-remote-includes: PASS WITH NOTES

Spec S-1/S-2/FR-003 and research R-6 wording aligned with the delivered behaviour and the
contract (D-1, D-3, R-c); remaining low findings filed as tracker under the feature issue.


## fb28e7b chore(troupe-config-remote-includes-01M4BMJ5): capture mission retrospective

## dd06834 chore(troupe-config-remote-includes-01M4BMJ5): flatten coordination metadata after branch deletion (#3086)

## 65b11ed chore(troupe-config-remote-includes-01M4BMJ5): record done transitions for merged WPs

## eb4bc81 feat(method/mission-troupe-config-remote-includes-01M4BMJ5): squash merge of mission

## 3fe0d31 Finalize acceptance artifacts for troupe-config-remote-includes-01M4BMJ5

## 6ded1c8 Record acceptance commit for troupe-config-remote-includes-01M4BMJ5

## 6b81a2b Accept troupe-config-remote-includes-01M4BMJ5

## 6230d16 Record WP10 review cycle (approved) for troupe-config-remote-includes; all WPs approved


## ca25bba Docs sync from WP10 acceptance for troupe-config-remote-includes

contracts/cli.md: the redirect refusal reads 'refused (only http and https)' as the code
prints it; list the S-10 refusal of !literal on a mapping key (message and exit 4).
research R-9: the rationale example could not occur (text includes keep the step-1 rule,
YAML includes cannot be replaced whole); use the collection case WP10 verified via the CLI.
quickstart: wait for the server, stop it by PID (works without job control), say only the
webhook URL is not fetched, remove the temp dir.


## bbd21d8 chore: Capture baseline tests for WP10

## 36f57aa Record WP09 review cycle (approved) for troupe-config-remote-includes


## 9062e8f chore: Capture baseline tests for WP09

## 08970ff Record WP08 review cycles for troupe-config-remote-includes (cycle 1 rejected: remote check ran after renderers; cycle 2 approved)


## 3407449 WP09 prompt: correct test 9 — a text include set to its own string keeps the step-1 rule

WP08 implementation and review confirmed that S-11 and C-003 keep step-1 behaviour for local
text includes (VALUE is file text, never tagged); the original expectation (turn the include
into a !literal) contradicted the spec. Verified against step-6 main.


## 096706b chore: Capture baseline tests for WP08

## 2acad6c Record WP06/WP07 review cycles (approved) for troupe-config-remote-includes


## d959211 chore: Capture baseline tests for WP07

## f63ca3f chore: Capture baseline tests for WP06

## 964f7a6 Record WP05 review cycles for troupe-config-remote-includes (cycle 1 rejected: inline << remount changed anchor identity; cycle 2 approved)


## d9b3650 chore: Capture baseline tests for WP05

## 2dcbace Record WP04 review cycle (approved) for troupe-config-remote-includes


## 9524b96 chore: Capture baseline tests for WP04

## c47dc7a Record WP01/WP02 review cycles for troupe-config-remote-includes (WP01 cycle 1 rejected: deadline did not bound connect/DNS; cycle 2 approved; WP02 approved)


## aa12936 Record WP03 review cycles for troupe-config-remote-includes (cycle 1 rejected: empty Unresolvable reason; cycle 2 approved)


## cb4e8ba Record WP01 claim metadata for troupe-config-remote-includes (base branch and commit)


## 5effdde chore: Capture baseline tests for WP03

## 135d366 chore: Capture baseline tests for WP02

## d5a57a2 chore: planning artifacts for troupe-config-remote-includes-01M4BMJ5

Auto-committed by method before creating the lane worktree for WP02

## 6273750 chore: Capture baseline tests for WP01

## 1158302 docs(record-analysis): record analysis report for mission troupe-config-remote-includes-01M4BMJ5

## a064ccc Spec clarifications from the analysis report of troupe-config-remote-includes (U1, I1, U2, I3)

S-10: !literal on a mapping key is refused at load (keys are never includes).
S-6: while unloadable, watch keeps the step-3 retry-every-tick rule, so a failing remote
include is refetched on each retry (bounded by the deadline); no new polling behaviour.
S-12: --include removes an existing !literal tag from the replaced value.
Data model: Schema field is 'path', as in WP03. WP05/WP06 prompts carry the rules.


## 3e4ef47 docs(record-analysis): record analysis report for mission troupe-config-remote-includes-01M4BMJ5

## fcb3564 Record task status bookkeeping for troupe-config-remote-includes (10 WPs seeded, python-pedro profiles)


## b52e9dc Plan amendments found while writing work packages for troupe-config-remote-includes

R-1: keep SourceFile.path as the field name, retyped to Location (Url in the new
location.py), so mypy still finds every disk-only use without a ten-module rename that
would cross work-package ownership. R-8/R-9: an IncludeStr marker beside LiteralStr so
the no-op check can tell an include from a literal; scalar replacements keep, insert or
remove the !literal tag as a separate edit; alias copies keep the tag (a copied literal
must not become an include). Contract: other tags keep the step-6 message.


## 5558c76 Add tasks for feature troupe-config-remote-includes-01M4BMJ5

## 8992702 chore: Map requirements for WP01, WP02, WP03, WP04, WP05, WP06, WP07, WP08, WP09, WP10 on spec troupe

## 72281e4 Plan artifacts for troupe-config-remote-includes: research R-1..R-13 with supply-chain review, data model, CLI contract, quickstart; record the validator decision (jsonschema, the safest assumption per the product owner)


## 66d8e75 Add plan for feature troupe-config-remote-includes-01M4BMJ5

## edc9bbe Record specify decision moment and spec quality checklist for troupe-config-remote-includes (S-1: includes inside remote content resolve against the URL)


## b718e81 Add spec for troupe-config-remote-includes: step 7 Remote includes and schema, with agent choices S-1..S-12 confirmed by the product owner as out of contract

## 9d33331 Add scaffold for feature troupe-config-remote-includes-01M4BMJ5
