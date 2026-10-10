# Commits (60, newest first)

Each commit's short SHA and subject, then its message body.

## 0291201 fix(config-set-writeback): follow the contract for folded more-indented lines and sibling styles

Feature validation found two contract deviations. Any change to a folded value
that already held more-indented lines was refused; the contract only refuses
changes that would put such a line in, so unchanged runs are now kept
byte-for-byte. New keys added by a merge copied the style of an entry the same
set deletes; the preceding sibling is now the last remaining entry. Requirements
7.1/7.2 and 10.6/10.7, design and research are updated with the code and tests.


## 7bf1ba5 chore(config-set-writeback): mark task groups complete


## e41a5d1 feat(config-set-writeback): run full quality gate and fix test-to-requirement traceability


## b26755d feat(config-set-writeback): validate the history of sets


## 8441cfc feat(config-set-writeback): validate write safety, no-ops and refusals


## 7c9fb00 feat(config-set-writeback): validate byte preservation, line endings, encoding and file identity


## a19efe0 feat(config-set-writeback): validate merges, deletions and kind changes


## 30d989c feat(config-set-writeback): validate end-of-line comment columns


## 1b7426c feat(config-set-writeback): validate literal and folded block scalars


## b381fd6 feat(config-set-writeback): validate new collections, indentation and placement


## 193c04a feat(config-set-writeback): validate scalar quoting and sibling styles


## 5fa2c5f feat(config-set-writeback): validate where the change is written, including new includes


## c4f203f chore: add pytest-xdist for parallel test runs

The end-to-end suite runs the real CLI in subprocesses and takes ~2 minutes
serially; -n auto brings it to ~40s on this machine.


## cc7ea6b feat(config-set-writeback): validate invocation, VALUE parsing, import and error reporting


## 2ec52ed feat(config-set-writeback): register and handle the set subcommand


## e18253a feat(config-set-writeback): implement the set use case


## bc51eba feat(config-set-writeback): write user files atomically


## 42a3692 feat(config-set-writeback): derive leaf changes for the history


## d12bb62 feat(config-set-writeback): verify a patch by re-loading the configuration in memory


## c00dba8 feat(config-set-writeback): plan includes inside replaced collections and multi-file patches


## 1d2ad74 feat(config-set-writeback): plan entry-wise merges and deletions


## fddb3b2 feat(config-set-writeback): plan replacements that change kind or block form


## 236eddc feat(config-set-writeback): plan new keys, intermediate mappings and list appends


## 42d4e69 feat(config-set-writeback): plan in-place changes of existing values


## 12e1965 feat(config-set-writeback): resolve write targets, path errors and the intended configuration


## 7ddfa7c feat(config-set-writeback): render new collections and entries in block and flow style


## 11f7e5f feat(config-set-writeback): rewrite existing literal and folded block scalars


## b9df3a9 feat(config-set-writeback): render literal blocks, chomping and greedy word wrapping


## f24eea5 feat(config-set-writeback): decide scalar style and render quoted/plain scalars and keys


## 7469133 feat(config-set-writeback): apply edits and keep end-of-line comment columns


## 13d4c7f feat(config-set-writeback): analyse comments, value slots, content ends, extents and insertion points


## 3e3494d feat(config-set-writeback): analyse file text: lines, columns, line breaks, indent step, dash offset


## fc47c3c feat(config-set-writeback): provide plain trees, include directives, typed equality and splicing


## f4463a7 feat(config-set-writeback): parse VALUE into a typed value tree


## a77a9be feat(config-set-writeback): create writeback package skeleton, value types and set-test support


## e6b848b docs(config-set-writeback): carry foundation validation notes into tasks


## 8fbd54c chore(config-foundation): mark task groups complete


## 0502077 feat(config-foundation): validate read-only safety and state location


## cd93a5b feat(config-foundation): validate history and import behaviour end to end


## f78b324 feat(config-foundation): validate show output and path errors end to end


## d7d0b9f feat(config-foundation): validate includes end to end


## 087470b feat(config-foundation): validate locating and loading errors end to end


## 11a9274 feat(config-foundation): wire CLI parsing, dispatch, error mapping and buffered output


## e453c25 feat(config-foundation): render show output and history lines


## a6e609b feat(config-foundation): implement the theatre session use cases


## de431a2 feat(config-foundation): provide the change-recording API for set


## 0d5d73c feat(config-foundation): persist history under .troupe and import once


## 24ce7ff feat(config-foundation): add the event-sourced history aggregate and event types


## 1d324c5 feat(config-foundation): walk and resolve paths and flatten leaves


## f8011f7 feat(config-foundation): resolve file: includes recursively


## 42baa9f feat(config-foundation): load a single YAML file into the source-mapped model


## 0b8e8f6 feat(config-foundation): locate the root configuration file


## 3385de6 feat(config-foundation): define the source-mapped configuration model


## 2fae65c feat(config-foundation): parse, format and prefix-match dotted paths


## f57d719 feat(config-foundation): type plain scalars by the YAML 1.2 core schema


## 6ce25cd feat(config-foundation): define constants, error types and exit-code mapping


## e6d5ee7 feat(config-foundation): set up uv project, console script and quality tooling


## 8c0725b Record product owner decisions in config specs

Files are authoritative and history-only projection is confirmed; multi-file
sets are now carried out all-or-nothing instead of refused, because the
contract's write-back rules can legitimately change more than one file.
Delegated gaps are resolved conservatively and recorded with reasons.


## 5e1501e Add specs for config-foundation and config-set-writeback

Requirements, design and tasks for step 1 of the config subsystem, generated
by spec-batch and reconciled by cross-spec review (shared CLI shell module,
handler protocol, model key styles, span semantics, folded-scalar fix) so the
two specs can be implemented in order without interface drift.


## 7455822 Add discovery roadmap and briefs for config step 1

Split step 1 into a read-side foundation and a byte-surgical set spec so the
rule-dense write-back can be specified and reviewed on its own.

