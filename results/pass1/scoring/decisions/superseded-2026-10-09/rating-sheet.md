# Decision review: rating sheet

Rate every route, one-offs first. After `rating:` write one of good, acceptable, poor or out_of_scope (not a real choice, or does not matter); after `reason:` write one line - it becomes cited evidence. Leave the `##` and `### Route` headings as they are.

Routes are anonymous: which arm took which route is hidden. "not considered" is a route too: if the topic mattered, missing it is a weakness; if it did not, not considering it can be acceptable and deciding it may have been over-engineering. `proposed:` is the aligning judge's suggestion; your rating decides.

Extraction: every step's decisions were extracted.

# One-offs (3)

## T1

**Question:** How are VALUEs and reasons starting with '-' parsed?  
**Kind:** one-off

### Route 1

- Route: Override argparse's private _parse_optional so single-dash values are positional
- Reasoning given: Plain argparse rejects -1e3
- Outcome: kept; also applies to --reason
- proposed: acceptable - Depends on a private API

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Users can use '--'.

rating:
reason:

## T2

**Question:** What if a literal block would swallow the deeper-indented comments that follow it?  
**Kind:** one-off

### Route 1

- Route: Write the string double-quoted instead
- Reasoning given: Otherwise the comments would silently become part of the value
- Outcome: kept
- proposed: good - Avoids silent data change

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write would catch it.

rating:
reason:

## T3

**Question:** Are dependency builds hardened?  
**Kind:** one-off

### Route 1

- Route: no-build-package for rpds-py
- Reasoning given: Avoids running arbitrary build code
- Outcome: kept
- proposed: good - Security

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Wheels are default.

rating:
reason:

# Divergent (146)

## T4

**Question:** How are alias occurrences located?  
**Kind:** divergent

### Route 1

- Route: A PyYAML loader subclass recording *name tokens
- Reasoning given: PyYAML composes an alias to the anchored node
- Outcome: kept
- proposed: acceptable - Works

rating:
reason:

### Route 2

- Route: Compare positions (start mark before the key) and find the *name token
- Reasoning given: An alias points back at its anchor
- Outcome: kept
- proposed: acceptable - Heuristic

rating:
reason:

### Route 3

- Route: Own composer built from parser events
- Reasoning given: Avoids ruamel internals and text scanning
- Outcome: kept
- proposed: good - Robust

rating:
reason:

### Route 4

- Route: Shared node object, with the alias recorded on the holding entry
- Reasoning given: Every consumer reads it unchanged
- Outcome: kept
- proposed: good - Minimal change

rating:
reason:

### Route 5

- Route: Subclass the ruamel composer (compose_node hook or stand-in node)
- Reasoning given: Exact; text scanning is fragile
- Outcome: kept; A pins ruamel and checks spans
- proposed: acceptable - Relies on library internals

rating:
reason:

## T5

**Question:** Is exponential alias expansion (billion laughs) limited?  
**Kind:** divergent

### Route 1

- Route: No limit; noted
- Reasoning given: Configs are small and local
- Outcome: kept
- proposed: acceptable - Documented

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Local configs.

rating:
reason:

## T6

**Question:** What history events does a write at an anchor or an expansion record?  
**Kind:** divergent

### Route 1

- Route: One event per resolved leaf that changed, in one change; an expansion alone records nothing
- Reasoning given: Leaves are resolved paths
- Outcome: kept
- proposed: good - Accurate

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Follows from the leaf diff.

rating:
reason:

## T7

**Question:** Is a new key under an alias in an included file refused when an override would land elsewhere?  
**Kind:** divergent

### Route 1

- Route: Refused
- Reasoning given: Never writes through an anchor (C: owner ruling)
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T8

**Question:** Can PATH name the alias's own key?  
**Kind:** divergent

### Route 1

- Route: Allowed: replaces only the *name token (logged as an open question)
- Reasoning given: Changes nobody else
- Outcome: kept
- proposed: acceptable - Reasonable, but departs from the literal rule

rating:
reason:

### Route 2

- Route: Counts as through the alias: exit 3 unless --expand-alias
- Reasoning given: The literal reading is safer
- Outcome: kept
- proposed: good - Contract-literal

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T9

**Question:** Can VALUE contain anchors or aliases?  
**Kind:** divergent

### Route 1

- Route: No: exit 2
- Reasoning given: Would create sharing nobody asked for
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T10

**Question:** How are anchors, aliases and merge keys treated before step 6?  
**Kind:** divergent

### Route 1

- Route: Leave them undefined and untested (out of contract)
- Reasoning given: Listed as out-of-contract behaviour
- Outcome: step 6 found that a write through an alias silently changed other agents' settings
- proposed: poor - Led to silent corruption of shared values

rating:
reason:

### Route 2

- Route: Refuse them on load with exit 4 until step 6
- Reasoning given: Out of contract; a write through an alias could change other paths
- Outcome: reworked at step 6 to full support
- proposed: good - Safe until support exists

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - Writing through an unhandled alias could corrupt shared values.

rating:
reason:

## T11

**Question:** Can an include carry an anchor?  
**Kind:** divergent

### Route 1

- Route: Exit 4 on load
- Reasoning given: Undefined semantics
- Outcome: kept
- proposed: acceptable - Conservative

rating:
reason:

### Route 2

- Route: Loads; converting an anchored include is refused with exit 3
- Reasoning given: No rule says where the anchor goes
- Outcome: kept
- proposed: good - Supports more

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T12

**Question:** How are files written to disk?  
**Kind:** divergent

### Route 1

- Route: Sibling temp file, fsync, os.replace, copy permissions; only changed files
- Reasoning given: Never half-written; a temp file in .troupe/ is not atomic across filesystems
- Outcome: kept
- proposed: good - Protects user data

rating:
reason:

### Route 2

- Route: Write in place (newline='') after computing and verifying all files; no temp files
- Reasoning given: The only failure left is an OS error during the write itself
- Outcome: kept
- proposed: poor - A crash mid-write can corrupt the file

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - A crash could leave a half-written config.

rating:
reason:

## T13

**Question:** How is the chomping indicator chosen when writing block scalars?  
**Kind:** divergent

### Route 1

- Route: Keep the old indicator if it fits, otherwise choose strip, clip or keep by trailing newlines; keep-chomped trailing lines belong to the value
- Reasoning given: Exact read-back
- Outcome: kept
- proposed: good - Minimal change

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write covers it.

rating:
reason:

## T14

**Question:** Does setting a collection over an existing collection merge entries or rewrite the block?  
**Kind:** divergent

### Route 1

- Route: Entry-wise merge (keep, change, append, delete)
- Reasoning given: Unchanged entries keep their comments and bytes
- Outcome: kept
- proposed: good - Minimal diff

rating:
reason:

### Route 2

- Route: Replace the whole span, dropping comments inside it, and render in the old style
- Reasoning given: Those comments described the old entries
- Outcome: kept
- proposed: poor - Rewrites text the user did not ask to change

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - Rewriting loses comments in unchanged entries.

rating:
reason:

## T15

**Question:** What happens to an end-of-line comment when a value's length changes?  
**Kind:** divergent

### Route 1

- Route: Keep the comment's column, with at least one space before it
- Reasoning given: Contract rule
- Outcome: kept; test expectations corrected at step 7
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T16

**Question:** What concurrency is in contract?  
**Kind:** divergent

### Route 1

- Route: One watch plus one other command; concurrent sets, several watches and editor-vs-set races are out of contract
- Reasoning given: Carries over step 1
- Outcome: kept
- proposed: acceptable - Documented scope

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Implicitly handled by the lock.

rating:
reason:

## T17

**Question:** What happens if both troupe.yml and troupe.yaml exist, or neither does?  
**Kind:** divergent

### Route 1

- Route: Exit 4 in both cases
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Refuses ambiguity

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T18

**Question:** What may the config root be (empty file, non-mapping root)?  
**Kind:** divergent

### Route 1

- Route: An empty or comment-only file is an empty mapping and set can write into it
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Sensible

rating:
reason:

### Route 2

- Route: An empty or comment-only file is an empty mapping; a non-mapping root exits 4
- Reasoning given: Conservative and deterministic
- Outcome: kept
- proposed: good - Clear rules

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T19

**Question:** What happens on unknown or corrupt stored lineage values?  
**Kind:** divergent

### Route 1

- Route: Raise ValueError, reported as an unreadable store (exit 4)
- Reasoning given: A corrupted row should give exit 4, not a traceback
- Outcome: kept
- proposed: good - No traceback

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Hand-damaged stores only.

rating:
reason:

## T20

**Question:** Where are out-of-contract choices recorded?  
**Kind:** divergent

### Route 1

- Route: README decisions list
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Visible

rating:
reason:

### Route 2

- Route: Spec or research documents
- Reasoning given: Traceability
- Outcome: kept
- proposed: good - Traceable

rating:
reason:

### Route 3

- Route: docs/decisions.md or DECISIONS.md
- Reasoning given: Fallback asked for it
- Outcome: E started at step 5
- proposed: good - Visible

rating:
reason:

## T21

**Question:** How was work delivered?  
**Kind:** divergent

### Route 1

- Route: Commit on main, no push or PR
- Reasoning given: Owner rule
- Outcome: kept
- proposed: good - Owner rule

rating:
reason:

### Route 2

- Route: Feature or mission branch merged locally into main, no push
- Reasoning given: method would not commit to main
- Outcome: kept
- proposed: good - Owner rule

rating:
reason:

## T22

**Question:** How are duplicate keys and complex (non-scalar) keys handled on load?  
**Kind:** divergent

### Route 1

- Route: Complex keys are refused with exit 4 (no duplicate-key rule recorded)
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Partial coverage

rating:
reason:

### Route 2

- Route: Duplicate keys and complex keys are load errors (exit 4)
- Reasoning given: Ambiguous meaning; the writer cannot handle them
- Outcome: kept
- proposed: good - Refuses ambiguity

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Rare in hand-written configs.

rating:
reason:

## T23

**Question:** Does a command that records nothing create a change?  
**Kind:** divergent

### Route 1

- Route: No events means no change and no stamp
- Reasoning given: Requirement 4.4
- Outcome: kept
- proposed: good - Clean

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Implicit.

rating:
reason:

## T24

**Question:** What happens to an override mapping left empty?  
**Kind:** divergent

### Route 1

- Route: Prune it upward, never past $ref; a mapping that loses every key becomes {}
- Reasoning given: Leaves no empty override
- Outcome: kept
- proposed: good - Tidy

rating:
reason:

### Route 2

- Route: Remove it but keep mapping form
- Reasoning given: Changes only the lines it must
- Outcome: kept
- proposed: good - Minimal

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Cosmetic.

rating:
reason:

## T25

**Question:** Where is a value written into an empty 'key:'?  
**Kind:** divergent

### Route 1

- Route: Right after the colon/indicator, not at ruamel's mark
- Reasoning given: ruamel's mark is on the next line, which broke set
- Outcome: kept
- proposed: good - Fixes real refusals

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write refuses instead.

rating:
reason:

## T26

**Question:** How are errors mapped to exit codes and stdout?  
**Kind:** divergent

### Route 1

- Route: Typed error classes carry codes 2/3/4/5, the CLI alone converts them, and stdout is empty on any failure
- Reasoning given: One place for the mapping
- Outcome: kept
- proposed: good - Clean

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T27

**Question:** What about existing user mappings that hold $ref: file: as data?  
**Kind:** divergent

### Route 1

- Route: They now load as includes, documented or assumed intended
- Reasoning given: Unlikely in troupe configs
- Outcome: kept
- proposed: acceptable - Documented

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Unlikely.

rating:
reason:

## T28

**Question:** What does --expand-alias do with no alias on PATH?  
**Kind:** divergent

### Route 1

- Route: Nothing; a plain set
- Reasoning given: Same as --in-include
- Outcome: kept
- proposed: good - Consistent

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T29

**Question:** What does an --expand-alias copy contain?  
**Kind:** divergent

### Route 1

- Route: Rendered from the resolved value; nested aliases expanded (D also copies an aliased include's content)
- Reasoning given: The copy shares nothing; no repeated anchors
- Outcome: kept
- proposed: acceptable - Changes more than asked

rating:
reason:

### Route 2

- Route: The anchored node as written, without inner anchors or comments; inner aliases stay aliases; include strings and styles kept
- Reasoning given: Copying anchors rebinds aliases; resolving changes more than asked
- Outcome: kept
- proposed: good - Minimal and faithful

rating:
reason:

## T30

**Question:** What if an expansion and the following write land in different files?  
**Kind:** divergent

### Route 1

- Route: Refuse with exit 3
- Reasoning given: One write of one file
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T31

**Question:** What if the alias line already has a user comment?  
**Kind:** divergent

### Route 1

- Route: Keep the user comment and put the marker after it
- Reasoning given: Never lose a comment
- Outcome: kept
- proposed: acceptable - The marker is not at the end of the key

rating:
reason:

### Route 2

- Route: Put the marker before the user comment
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Keeps both, marker on the key line

rating:
reason:

### Route 3

- Route: Refuse with exit 3
- Reasoning given: Both alternatives alter the user's text
- Outcome: kept
- proposed: acceptable - Over-refuses

rating:
reason:

## T32

**Question:** How are explicit YAML tags in config files handled?  
**Kind:** divergent

### Route 1

- Route: Honour core tags (!!str etc.); refuse other tags with exit 4
- Reasoning given: Conservative for an out-of-contract feature
- Outcome: kept; !literal is added in step 7
- proposed: good - Supports valid YAML and refuses the unknown

rating:
reason:

### Route 2

- Route: Ignore tags: quoted and block scalars stay strings, and losing tags such as !!binary on write is not raised
- Reasoning given: Outside the contract
- Outcome: kept
- proposed: poor - Silently changes the typed meaning of tagged values

rating:
reason:

### Route 3

- Route: Refuse any tag on load (exit 4); kept for non-!literal tags in step 7
- Reasoning given: Ambiguous meaning; the writer cannot handle tags safely
- Outcome: kept; step 7 allows !literal only
- proposed: good - Conservative, and data can never be misread

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Out of contract; the risk is low for hand-written configs.

rating:
reason:

## T33

**Question:** Is fetched body size limited?  
**Kind:** divergent

### Route 1

- Route: No limit
- Reasoning given: Out of contract
- Outcome: kept
- proposed: acceptable - Memory risk

rating:
reason:

### Route 2

- Route: No limit at first; reworked to 1 MiB
- Reasoning given: An unbounded body could exhaust memory
- Outcome: reworked
- proposed: good - Safe

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Configs are small.

rating:
reason:

## T34

**Question:** Which redirects are followed?  
**Kind:** divergent

### Route 1

- Route: Follow redirects (urllib default)
- Reasoning given: Plainest choice
- Outcome: kept
- proposed: acceptable - Allows ftp redirects

rating:
reason:

### Route 2

- Route: Only http/https targets (C also refuses https-to-http downgrades)
- Reasoning given: Blocks file:/ftp: redirects
- Outcome: kept
- proposed: good - Secure

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Default urllib behaviour.

rating:
reason:

## T35

**Question:** What TLS, credential and proxy behaviour does fetching have?  
**Kind:** divergent

### Route 1

- Route: Verify TLS, no credentials, strict UTF-8, environment proxies; test environments drop proxy variables
- Reasoning given: An unverified response cannot corrupt anything
- Outcome: kept
- proposed: good - Secure

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Defaults apply.

rating:
reason:

## T36

**Question:** What fetch timeout is used?  
**Kind:** divergent

### Route 1

- Route: 10 s (C and F: a total deadline over DNS, connect and read)
- Reasoning given: Keeps a dead server from hanging commands
- Outcome: kept
- proposed: good - Responsive

rating:
reason:

### Route 2

- Route: 30 s
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Long waits

rating:
reason:

## T37

**Question:** How are file encoding and a BOM handled?  
**Kind:** divergent

### Route 1

- Route: Decode as plain utf-8 so a BOM stays in the text; detect a text include's encoding and CRLF from its bytes
- Reasoning given: ruamel marks count U+FEFF; the platform default encoding is non-deterministic
- Outcome: kept
- proposed: good - Preserves the BOM and keeps offsets right

rating:
reason:

### Route 2

- Route: Strict UTF-8; non-UTF-8 files exit 4
- Reasoning given: Decoding with replacement characters would corrupt data
- Outcome: kept
- proposed: good - Never alters bytes silently

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - UTF-8 is the de facto default.

rating:
reason:

## T38

**Question:** How is a file: include inside remote content treated?  
**Kind:** divergent

### Route 1

- Route: Exit 4
- Reasoning given: No local directory; the contract does not describe URL includes
- Outcome: kept
- proposed: acceptable - Conservative

rating:
reason:

### Route 2

- Route: Resolve against the URL (remote and read-only)
- Reasoning given: Keeps the relative meaning; never reads the user's disk
- Outcome: kept
- proposed: good - Secure and useful

rating:
reason:

## T39

**Question:** How is a write into a file included at several places handled?  
**Kind:** divergent

### Route 1

- Route: Allowed (tested at step 3; only override writes matched by reference)
- Reasoning given: Needed by step 1 and --in-include
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: Refused at first; reworked at step 5 so writes follow the placement rules everywhere (conflicting values exit 3)
- Reasoning given: PO: no contract rule refuses it
- Outcome: reworked at step 5
- proposed: good - Contract-faithful

rating:
reason:

### Route 3

- Route: Refused in step 1; overrides go into the shared nearest file at step 5
- Reasoning given: Cautious, then follows the PO's nesting answer
- Outcome: kept
- proposed: acceptable - Mixed

rating:
reason:

### Route 4

- Route: Refused with exit 3, including --in-include
- Reasoning given: It would alter every includer
- Outcome: kept
- proposed: acceptable - Conservative

rating:
reason:

### Route 5

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T40

**Question:** What does set do with a 'file:' VALUE before step 7?  
**Kind:** divergent

### Route 1

- Route: Verify a file: string as written text
- Reasoning given: Contract silent
- Outcome: reworked at step 7
- proposed: acceptable - Unclear include semantics

rating:
reason:

### Route 2

- Route: Write the string; it becomes an include and the read-back decides (missing or cyclic target exits 3)
- Reasoning given: Verification keeps it safe; refusing narrows the contract
- Outcome: A reworked from a blanket refusal; all became !literal by default at step 7
- proposed: good - Contract-faithful

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Superseded by step 7.

rating:
reason:

## T41

**Question:** How are floats spelled in show's YAML?  
**Kind:** divergent

### Route 1

- Route: .inf/.nan, plus '.0' before the 'e' in exponent floats (YAML-only)
- Reasoning given: YAML 1.1 readers need a '.'
- Outcome: kept
- proposed: good - Portable

rating:
reason:

### Route 2

- Route: repr when finite, .inf/-.inf/.nan otherwise
- Reasoning given: repr matches the core float pattern
- Outcome: kept
- proposed: good - Core schema

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T42

**Question:** How are ruamel's U+0007 fold markers in folded scalars handled?  
**Kind:** divergent

### Route 1

- Route: Strip the markers from folded values when reading (also for !literal folded scalars in step 7)
- Reasoning given: The ruamel composer inserts them; show was printing them
- Outcome: kept
- proposed: good - Fixes a real data artefact

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Only matters if the ruamel composer is used on folded text.

rating:
reason:

## T43

**Question:** How are folded values with more-indented lines handled?  
**Kind:** divergent

### Route 1

- Route: First refused any edit; reworked so existing more-indented runs are kept as opaque units and only newly added ones exit 3
- Reasoning given: Final validation: the contract only refuses adding such a line
- Outcome: reworked at final validation
- proposed: good - Exact contract reading

rating:
reason:

### Route 2

- Route: Refuse a change that would introduce a more-indented line
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Matches the contract

rating:
reason:

### Route 3

- Route: Refuse any change to a folded value that already has more-indented lines
- Reasoning given: Its paragraphs cannot be split reliably
- Outcome: kept
- proposed: acceptable - Refuses more than the contract requires

rating:
reason:

## T44

**Question:** Were randomized or property tests used?  
**Kind:** divergent

### Route 1

- Route: Fuzzing of random set sequences
- Reasoning given: Catch read-back and CRLF bugs
- Outcome: kept
- proposed: good - Strong

rating:
reason:

### Route 2

- Route: Property tests without hypothesis
- Reasoning given: No dependency
- Outcome: kept
- proposed: good - Strong

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Optional.

rating:
reason:

## T45

**Question:** How does history filter by PATH?  
**Kind:** divergent

### Route 1

- Route: A plain string prefix; an unknown path prints nothing and exits 0
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - 'agents' also matches 'agentsX'

rating:
reason:

### Route 2

- Route: A prefix filter; no matches print nothing and exit 0
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Semantics unclear

rating:
reason:

### Route 3

- Route: The path or its dotted prefix
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Segment-aware

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T46

**Question:** How are history JSON lines encoded (non-finite floats, ASCII)?  
**Kind:** divergent

### Route 1

- Route: Non-finite floats as '.inf'/'.nan' strings (allow_nan=False); ASCII escaping
- Reasoning given: Must be valid JSON Lines; null would lose the value
- Outcome: kept
- proposed: good - Valid, lossless JSON

rating:
reason:

### Route 2

- Route: Non-finite floats as YAML-style strings
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Valid JSON

rating:
reason:

### Route 3

- Route: ensure_ascii=False with keys in a fixed order
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Fine; non-finite floats are not addressed

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - An edge case for most labels.

rating:
reason:

## T47

**Question:** Where do the lineage keys go in history lines?  
**Kind:** divergent

### Route 1

- Route: After seq, op, path, old, new, in the order actor, via, at, reason, change, with actor as {kind, id}
- Reasoning given: Existing consumers are unaffected
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label decided this.

rating:
reason:

## T48

**Question:** Does history load the configuration once the theatre has been imported?  
**Kind:** divergent

### Route 1

- Route: An invalid configuration is a load error for every command, including history's first import
- Reasoning given: (none)
- Outcome: set at step 7
- proposed: acceptable - Consistent rule

rating:
reason:

### Route 2

- Route: Every command, history included, loads the config first (and later fetches and validates it)
- Reasoning given: Every command is treated the same way; history may import
- Outcome: kept; step 7 also validates the schema
- proposed: acceptable - Consistent, but history fails when the files are broken

rating:
reason:

### Route 3

- Route: Once state exists, history reads the events without loading the files
- Reasoning given: history needs no loadable files once something has been recorded
- Outcome: kept
- proposed: good - History stays readable while the files are broken

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T49

**Question:** Which file does --in-include write into?  
**Kind:** divergent

### Route 1

- Route: Always the included side, never the overrides
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - May invent sections in the shared file

rating:
reason:

### Route 2

- Route: The innermost included file holding the deepest ancestor (following base links)
- Reasoning given: The step-1 rule
- Outcome: C fixed chained includes in WP05; kept
- proposed: good - Contract

rating:
reason:

### Route 3

- Route: The innermost included file; an override-only ancestor stays in the override's file
- Reasoning given: Where the shared content lives
- Outcome: kept
- proposed: good - Precise

rating:
reason:

## T50

**Question:** How does set --include verify a new include, and what does a failed fetch do?  
**Kind:** divergent

### Route 1

- Route: A failed fetch exits 4 and nothing is written; the read-back faithfulness check is skipped when the value has include strings and the target resolves
- Reasoning given: The first condition was muddled
- Outcome: simplified during step 7
- proposed: poor - Skips the safety net

rating:
reason:

### Route 2

- Route: Verify by reading each string back as an include; a failed fetch is exit 4 (FetchError re-raised)
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Uses a load exit code for a refused write

rating:
reason:

### Route 3

- Route: Write it plain and fetch on read-back; a failed or unreadable fetch exits 3
- Reasoning given: Decision D's rule for unloadable targets
- Outcome: kept
- proposed: good - Verified write

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T51

**Question:** What does --include do at a format: uri path?  
**Kind:** divergent

### Route 1

- Route: Refuse with exit 3
- Reasoning given: Rather than silently write a literal
- Outcome: kept
- proposed: good - Clear

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T52

**Question:** Where does the include rule live?  
**Kind:** divergent

### Route 1

- Route: A new includes.py module
- Reasoning given: One place
- Outcome: kept
- proposed: out_of_scope - Internal

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: out_of_scope - Internal.

rating:
reason:

## T53

**Question:** How is an include string that is not on its key's line converted?  
**Kind:** divergent

### Route 1

- Route: Convert in place (C refuses multi-line strings; E re-renders them)
- Reasoning given: The item is itself the reference
- Outcome: kept
- proposed: acceptable - Handles more cases

rating:
reason:

### Route 2

- Route: Refuse with exit 3
- Reasoning given: Guessing could misplace the comment
- Outcome: kept
- proposed: good - Conservative

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T54

**Question:** How are include targets resolved and classified?  
**Kind:** divergent

### Route 1

- Route: Case-sensitive .yml/.yaml suffix means a YAML include, otherwise a text include; paths are relative to the including file; cycles (realpath) and missing targets exit 4
- Reasoning given: Follows the contract
- Outcome: kept; extended to URLs at step 7
- proposed: good - Matches the contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Mostly fixed by the contract.

rating:
reason:

## T55

**Question:** How is replacing a value that comes wholly from a YAML include handled?  
**Kind:** divergent

### Route 1

- Route: Refuse with exit 3 (including through an ancestor); only a YAML include root is affected, not a text include
- Reasoning given: Contract rule 4
- Outcome: kept; a mapping-form include is treated the same at step 5
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T56

**Question:** What does setting an include with overrides to its bare string, or replacing it whole, do?  
**Kind:** divergent

### Route 1

- Route: Refuse with exit 3; overrides are never dropped silently
- Reasoning given: Same as a scalar-form include
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Rule 4 covers it.

rating:
reason:

## T57

**Question:** How is the indentation step for new content detected?  
**Kind:** divergent

### Route 1

- Route: From the first nested block, default 2
- Reasoning given: Follows the file's own layout
- Outcome: kept; C fixed detection on anchored files at step 6
- proposed: good - Sensible

rating:
reason:

### Route 2

- Route: The smallest nesting difference found in the file, default 2
- Reasoning given: The contract does not define detection
- Outcome: kept
- proposed: good - Sensible

rating:
reason:

## T58

**Question:** How is content whose first line starts with a space written in a literal block?  
**Kind:** divergent

### Route 1

- Route: Add an explicit indentation indicator when the first content line starts with a space
- Reasoning given: YAML takes the indentation from the first non-blank line
- Outcome: F added it at step 3 (set previously refused with exit 3)
- proposed: good - Valid YAML

rating:
reason:

### Route 2

- Route: Double-quote such values instead
- Reasoning given: A literal block cannot hold them exactly
- Outcome: kept
- proposed: acceptable - Valid, but less readable

rating:
reason:

### Route 3

- Route: In show, always use indicator 2, relative to the owning key or dash
- Reasoning given: An experiment showed the literal reading breaks read-back
- Outcome: kept
- proposed: good - Tested

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write refuses instead.

rating:
reason:

## T59

**Question:** How was the reporter's issue handled?  
**Kind:** divergent

### Route 1

- Route: Leave the issue open with no public comment
- Reasoning given: A comment would be public; ask the owner
- Outcome: kept
- proposed: good - Respects the outward-action limits

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Optional.

rating:
reason:

## T60

**Question:** How are keys that would read back as non-strings written?  
**Kind:** divergent

### Route 1

- Route: Quote keys whose plain form would not read back as the same string (including <<)
- Reasoning given: A plain key would read back as a bool or number, or as a merge key
- Outcome: kept
- proposed: good - Read-back stays exact

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - A plain 'true' key would read back as a boolean.

rating:
reason:

## T61

**Question:** How are keys containing '.' handled?  
**Kind:** divergent

### Route 1

- Route: Declared out of contract
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Contract gap

rating:
reason:

### Route 2

- Route: Rebuild removed paths by raw split, without validation
- Reasoning given: The loader accepts such keys; validation would break every later reconcile
- Outcome: kept
- proposed: good - Robust

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Out of contract.

rating:
reason:

## T62

**Question:** How are pre-step-4 events shown?  
**Kind:** divergent

### Route 1

- Route: Out of contract: no migration and undefined behaviour
- Reasoning given: Any filled value would be a guess
- Outcome: kept
- proposed: poor - An upgrade can break existing histories

rating:
reason:

### Route 2

- Route: Upcast on read; via 'cli' (reworked from null after the PO's rejection); actor unknown; stored timestamp; legacy-import and legacy-<seq> ids
- Reasoning given: Stays within the contract vocabulary; the PO accepted 'cli'
- Outcome: reworked in discovery
- proposed: good - Contract-valid and keeps history readable

rating:
reason:

### Route 3

- Route: Upcast on read; via 'file' for set/remove; legacy-import and legacy-<seq> ids (by seq)
- Reasoning given: 'file' is the only via that pairs with an unknown actor
- Outcome: kept
- proposed: good - Contract-valid

rating:
reason:

### Route 4

- Route: Upcast on read; via null for old set/remove (E reworked from 'file'); per-event ids (C pre-lineage-<seq>; D change null; E unrecorded-*)
- Reasoning given: CLI and hand-edit origin cannot be told apart
- Outcome: kept
- proposed: poor - null is outside the contract's via vocabulary

rating:
reason:

## T63

**Question:** How is compatibility with old stores tested?  
**Kind:** divergent

### Route 1

- Route: A real database written by the step-3 code
- Reasoning given: Tests the real on-disk format
- Outcome: kept
- proposed: good - Realistic

rating:
reason:

### Route 2

- Route: Drop the automated test and verify by hand
- Reasoning given: Old event topics could not be faked in-process
- Outcome: kept
- proposed: poor - No regression guard

rating:
reason:

### Route 3

- Route: Strip lineage from stored rows, plus a manual check against the previous commit
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Partly synthetic

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - Untested upgrades break.

rating:
reason:

## T64

**Question:** Which line ending do new or rewritten lines use?  
**Kind:** divergent

### Route 1

- Route: CRLF if any CRLF appears in the file, else LF
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Mixed files may gain the wrong ending

rating:
reason:

### Route 2

- Route: Copy the preceding line's ending for mixed files
- Reasoning given: Follows the user's own layout
- Outcome: kept
- proposed: good - Locally faithful

rating:
reason:

### Route 3

- Route: Keep CRLF for text includes that used it
- Reasoning given: (none)
- Outcome: kept; the read-back check normalises CRLF
- proposed: acceptable - Covers text includes only

rating:
reason:

### Route 4

- Route: The file's first line break decides
- Reasoning given: Deterministic
- Outcome: kept
- proposed: good - Simple

rating:
reason:

## T65

**Question:** Where is lineage stored?  
**Kind:** divergent

### Route 1

- Route: A single nested lineage/meta field on each event
- Reasoning given: Survives restarts
- Outcome: kept
- proposed: good - Atomic

rating:
reason:

### Route 2

- Route: Flat lineage fields on every leaf event (class_version 2 or extra args)
- Reasoning given: One store and one seq; atomic with the event
- Outcome: kept
- proposed: good - Simple and atomic

rating:
reason:

## T66

**Question:** How are tests isolated from the developer's actor and login?  
**Kind:** divergent

### Route 1

- Route: Strip TROUPE_ACTOR in fixtures and child environments (B and F also pin LOGNAME/USER)
- Reasoning given: The developer's shell must not change results
- Outcome: kept
- proposed: good - Deterministic

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - Results would depend on the developer's shell.

rating:
reason:

## T67

**Question:** Where does the marker go for a list-item alias?  
**Kind:** divergent

### Route 1

- Route: On the dash line, with the copy below
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Sensible

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T68

**Question:** When is it decided whether a string is a literal or an include?  
**Kind:** divergent

### Route 1

- Route: While walking, before any fetch
- Reasoning given: Otherwise literal URLs would be fetched
- Outcome: kept
- proposed: good - Correct

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Implicit.

rating:
reason:

## T69

**Question:** What happens to an existing !literal tag when its value is replaced?  
**Kind:** divergent

### Route 1

- Route: Keep it for strings (B drops it for non-strings); --include removes it
- Reasoning given: Smallest diff; keeps intent
- Outcome: kept
- proposed: good - Minimal

rating:
reason:

### Route 2

- Route: Remove the tag
- Reasoning given: Keeping it would silently keep a literal
- Outcome: kept
- proposed: acceptable - Defensible

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T70

**Question:** What does !literal mean?  
**Kind:** divergent

### Route 1

- Route: On a scalar, its text as a string; on collections exit 4; other tags still exit 4
- Reasoning given: YAML's rule for tagged scalars
- Outcome: kept
- proposed: good - Clear

rating:
reason:

### Route 2

- Route: Only stops include-ness (!literal 3 stays 3); meaningless on collections
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Unusual

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label decided this.

rating:
reason:

## T71

**Question:** What happens when the lock cannot be taken?  
**Kind:** divergent

### Route 1

- Route: An OSError becomes exit 4 naming .troupe (or the lock file); a missing .troupe still reports the config file
- Reasoning given: Some filesystems do not support flock
- Outcome: kept
- proposed: good - No traceback

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Rare.

rating:
reason:

## T72

**Question:** How are implicit keys over 1024 characters handled?  
**Kind:** divergent

### Route 1

- Route: Left unhandled (documented risk or tracker issue)
- Reasoning given: Out of contract; configs are small
- Outcome: kept
- proposed: acceptable - Documented

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Unrealistic.

rating:
reason:

## T73

**Question:** How is a malformed PATH (empty segments) handled?  
**Kind:** divergent

### Route 1

- Route: Exit 2 before the theatre is opened; get and show parse PATH first
- Reasoning given: The argument is malformed, not missing; prevents empty-key creation
- Outcome: kept
- proposed: good - Creates no state on bad input

rating:
reason:

### Route 2

- Route: history validates PATH syntax too (a..b exits 2)
- Reasoning given: (none)
- Outcome: kept; contradicts its own B-10 wording
- proposed: acceptable - Reasonable, but it deviates from its own spec

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor edge case.

rating:
reason:

## T74

**Question:** Are << merge keys resolved when reading?  
**Kind:** divergent

### Route 1

- Route: Resolve them: own keys win, earlier sources first, merged keys at the << position; only a plain << is a merge key; bad values exit 4
- Reasoning given: Every YAML reader gives the file this meaning
- Outcome: kept
- proposed: good - Matches user expectation

rating:
reason:

### Route 2

- Route: Treat << as an ordinary key
- Reasoning given: YAML 1.2 core; the contract only forbids writing them
- Outcome: kept
- proposed: poor - get and show misreport merged configs

rating:
reason:

## T75

**Question:** What is the key order of a merged mapping?  
**Kind:** divergent

### Route 1

- Route: Included keys in their order (overridden keys keep their place), then override-only keys
- Reasoning given: show still reads like the shared file
- Outcome: kept
- proposed: good - Intuitive

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T76

**Question:** How is a set on a value supplied by a merge key handled?  
**Kind:** divergent

### Route 1

- Route: Refuse any PATH containing a << segment (merges not resolved)
- Reasoning given: Merge keys are never written
- Outcome: kept
- proposed: acceptable - Follows from not resolving merges

rating:
reason:

### Route 2

- Route: Refuse with exit 3, even with --expand-alias
- Reasoning given: Merges are shallow; a local key would shadow silently
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 3

- Route: Refused at first; reworked so --expand-alias writes an explicit key beside <<
- Reasoning given: Overrides without touching <<
- Outcome: reworked mid-implementation
- proposed: acceptable - Shallow-merge risk

rating:
reason:

## T77

**Question:** How is a set that touches several files carried out?  
**Kind:** divergent

### Route 1

- Route: Compute and verify all new texts before writing any
- Reasoning given: The only failure left is during the write
- Outcome: kept
- proposed: acceptable - No rollback if a later write fails

rating:
reason:

### Route 2

- Route: First refused; reworked to verify all, write each atomically, roll back on failure and record after all writes
- Reasoning given: Refusing contradicted the contract
- Outcome: reworked within step 1
- proposed: good - Complete and safe

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Covered implicitly by verifying before writing.

rating:
reason:

## T78

**Question:** What if PATH passes through several aliases?  
**Kind:** divergent

### Route 1

- Route: Expand each alias (outermost first, iterating with reload), each with its own comment
- Reasoning given: Otherwise the command could never succeed
- Outcome: kept
- proposed: good - Completes the request

rating:
reason:

### Route 2

- Route: Expand only the first shared value found
- Reasoning given: (none)
- Outcome: kept
- proposed: poor - Nested cases stay refused

rating:
reason:

## T79

**Question:** How is writing << avoided elsewhere (a new key named <<, replacing a mapping that holds <<, copies)?  
**Kind:** divergent

### Route 1

- Route: Quote a new key named <<; refuse replacing a mapping with << and copies containing <<
- Reasoning given: Plain << would read back as a merge key
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: Refuse a new key named <<, replacements of mappings holding <<, and copies containing <<
- Reasoning given: << is never written
- Outcome: kept
- proposed: good - Safe

rating:
reason:

## T80

**Question:** What style do newly written collections take (empty, flow parent, list items)?  
**Kind:** divergent

### Route 1

- Route: Collection list items in compact form; minimal separators
- Reasoning given: Follows the user's layout
- Outcome: kept
- proposed: good - Sensible

rating:
reason:

### Route 2

- Route: Empty collections as {} and []; compact '- k: v' in list items; flow style inside a flow parent
- Reasoning given: Block style cannot express empty collections or appear inside flow
- Outcome: kept; C writes a replaced flow collection under a block mapping in block style
- proposed: good - Valid and minimal

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T81

**Question:** Where do new entries go relative to trailing comments and blank lines?  
**Kind:** divergent

### Route 1

- Route: After trailing comments indented at least to the entry column; blank lines stay below
- Reasoning given: Only a less-indented comment ends a collection
- Outcome: kept
- proposed: good - Keeps grouping

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T82

**Question:** Which quoting style do new keys and items take?  
**Kind:** divergent

### Route 1

- Route: Copy the last remaining sibling's style, else minimal style
- Reasoning given: The contract's preceding-sibling rule
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T83

**Question:** How is a value made only of line breaks written?  
**Kind:** divergent

### Route 1

- Route: Double-quote a value of only line breaks
- Reasoning given: There is no content line to carry them
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: Render a lone '\n' as a |+ block
- Reasoning given: Probes showed it round-trips in every position
- Outcome: kept
- proposed: good - Verified

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T84

**Question:** How are non-string VALUEs spelled when written?  
**Kind:** divergent

### Route 1

- Route: Canonical plain form (true/false, null, decimal int, repr float)
- Reasoning given: Quoting a non-string would change its type
- Outcome: kept
- proposed: acceptable - Normalises user spelling

rating:
reason:

### Route 2

- Route: Keep VALUE's own spelling (floats otherwise repr; .inf/.nan)
- Reasoning given: Smallest surprise
- Outcome: kept
- proposed: good - Respects user input

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Both choices are valid.

rating:
reason:

## T85

**Question:** When is a set a no-op?  
**Kind:** divergent

### Route 1

- Route: Typed equality is a no-op, but replacing an include root exits 3 even when identical
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Inconsistent idempotence

rating:
reason:

### Route 2

- Route: Typed-equal value: no write, no event, exit 0; a no-op wins over a refusal, even at an include
- Reasoning given: A refusal changes nothing
- Outcome: kept
- proposed: good - Idempotent

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label decided this.

rating:
reason:

## T86

**Question:** Is an unchanged VALUE through an alias refused?  
**Kind:** divergent

### Route 1

- Route: No: a no-op comes before any refusal
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Idempotent

rating:
reason:

### Route 2

- Route: Yes, exit 3: the alias refusal comes before the no-op check
- Reasoning given: The rule has no exception
- Outcome: kept
- proposed: acceptable - Contract-literal

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T87

**Question:** What if the override position that should receive a new key is itself an include?  
**Kind:** divergent

### Route 1

- Route: Refuse with exit 3
- Reasoning given: Ambiguous target
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: The nearest include wins
- Reasoning given: It is the nearest include
- Outcome: kept
- proposed: acceptable - May write a shared file

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T88

**Question:** What if overrides target YAML content that is not a mapping?  
**Kind:** divergent

### Route 1

- Route: Exit 4 (including an empty file)
- Reasoning given: Deep merge is defined only for mappings
- Outcome: kept
- proposed: good - Loses nothing

rating:
reason:

### Route 2

- Route: Exit 4, but an empty included file counts as an empty mapping
- Reasoning given: The original spec broke a step-1 test
- Outcome: reworked at Gate 6
- proposed: good - Consistent with step 1

rating:
reason:

### Route 3

- Route: The overrides replace the content
- Reasoning given: Merge rule: anything but two mappings is replaced
- Outcome: kept
- proposed: poor - Silently drops included content

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T89

**Question:** Were open points escalated to the owner or decided autonomously?  
**Kind:** divergent

### Route 1

- Route: Asked the PO on key choices, with fallback assumptions
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Aligned

rating:
reason:

### Route 2

- Route: Mostly decided autonomously and recorded
- Reasoning given: Detailed brief, or fallback instructions
- Outcome: kept
- proposed: acceptable - Recorded

rating:
reason:

## T90

**Question:** How was work split into specs, changes or work packages?  
**Kind:** divergent

### Route 1

- Route: Direct implementation with a decisions file
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

### Route 2

- Route: Method changes per step with capability deltas, archived with spec sync
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

### Route 3

- Route: Missions with work packages on lanes
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

### Route 4

- Route: Numbered spec dirs with user stories and convergence tasks
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

### Route 5

- Route: Specs per step (two at step 1, one per later step, notes in earlier specs)
- Reasoning given: Risk isolation
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

## T91

**Question:** Which project tooling was set up?  
**Kind:** divergent

### Route 1

- Route: Hash-pinned uv.lock with deferred dependency review
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Tooling

rating:
reason:

### Route 2

- Route: uv package with pytest only
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Tooling

rating:
reason:

### Route 3

- Route: uv, src layout, ruff, mypy strict, Python 3.12
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Tooling

rating:
reason:

## T92

**Question:** How is the recorded configuration maintained and replayed?  
**Kind:** divergent

### Route 1

- Route: A leaves map on the aggregate; replay tolerates removes of unknown paths
- Reasoning given: Step-1 histories contain such removes
- Outcome: kept
- proposed: good - Robust

rating:
reason:

### Route 2

- Route: Computed per sync from a fold of history and never persisted; an import resets created_seq
- Reasoning given: Simplification
- Outcome: kept
- proposed: good - No extra state

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Internal.

rating:
reason:

## T93

**Question:** Do reconcile events stand if the command then fails?  
**Kind:** divergent

### Route 1

- Route: Yes: saved before the handler runs, kept on exit 3 or 5
- Reasoning given: The hand edit really happened
- Outcome: kept
- proposed: good - History stays true

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Implied by the session design.

rating:
reason:

## T94

**Question:** In what order are reconcile remove events recorded?  
**Kind:** divergent

### Route 1

- Route: sets in document order, then removes by the seq that created each leaf
- Reasoning given: Previous document order is unavailable
- Outcome: kept
- proposed: good - Stable

rating:
reason:

### Route 2

- Route: sets in document order, then removes in projection or recorded order
- Reasoning given: Nearest equivalent to the old document order
- Outcome: F reworded FR-114 to match; kept
- proposed: good - Stable

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Contract silent.

rating:
reason:

## T95

**Question:** Are events recorded before or after the file write, and how are failures handled?  
**Kind:** divergent

### Route 1

- Route: Record after all writes; if recording fails, restore the files and exit 4 naming the store
- Reasoning given: Undefined by the contract
- Outcome: kept
- proposed: good - Keeps files and history consistent

rating:
reason:

### Route 2

- Route: Record events after the files are written; a failed write records nothing (C: exit 3; F: unwritable target exit 3, store errors exit 4)
- Reasoning given: Never record a change that did not reach disk
- Outcome: kept
- proposed: good - History never lies

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - An implicit ordering may still be correct.

rating:
reason:

## T96

**Question:** How is a recursive alias handled?  
**Kind:** divergent

### Route 1

- Route: Exit 4
- Reasoning given: It would hang (D fixed a real hang)
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 2

- Route: Left unhandled
- Reasoning given: Already unsupported
- Outcome: kept
- proposed: poor - Possible hang

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: poor - It can hang.

rating:
reason:

## T97

**Question:** How is a $ref segment in PATH handled?  
**Kind:** divergent

### Route 1

- Route: get/show exit 5; set exit 3
- Reasoning given: Writing a $ref key would retarget an include
- Outcome: kept
- proposed: good - Explicit

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write refuses it.

rating:
reason:

## T98

**Question:** What is a $ref whose value is not a file: include string?  
**Kind:** divergent

### Route 1

- Route: An ordinary key
- Reasoning given: Files that load today keep loading
- Outcome: kept
- proposed: acceptable - Back-compatible but silent

rating:
reason:

### Route 2

- Route: Load error, exit 4
- Reasoning given: A typo must not silently become data
- Outcome: kept
- proposed: good - Loud

rating:
reason:

## T99

**Question:** How are server-side remote changes recorded?  
**Kind:** divergent

### Route 1

- Route: At the next reconcile, as file edits (unknown actor)
- Reasoning given: Reuses the reconcile rule
- Outcome: kept
- proposed: good - History stays complete

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Implicit.

rating:
reason:

## T100

**Question:** Where do new keys under remote includes go?  
**Kind:** divergent

### Route 1

- Route: As local overrides in the nearest locally written include
- Reasoning given: Keeps the step-5 overrides
- Outcome: kept
- proposed: good - Useful

rating:
reason:

### Route 2

- Route: Refuse when the nearest including file is remote
- Reasoning given: Step 5 D-40 points at a remote file
- Outcome: kept
- proposed: acceptable - Conservative

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label decided this.

rating:
reason:

## T101

**Question:** Are --in-include, --expand-alias and deletes into remote content refused?  
**Kind:** divergent

### Route 1

- Route: Yes: exit 3 (D: a no-op set of the same value exits 0)
- Reasoning given: They would write the remote file
- Outcome: kept
- proposed: good - Read-only

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label decided this.

rating:
reason:

## T102

**Question:** Where is the read-only guard for remote content enforced?  
**Kind:** divergent

### Route 1

- Route: At the edit and planning sites (A: _Planner._add; B: apply._apply; C: two checkpoints plus a write assertion), with a backstop in the file writer
- Reasoning given: Checking where edits are made cannot miss a case
- Outcome: kept
- proposed: good - Robust

rating:
reason:

### Route 2

- Route: Remote URLs as str vs local Path, told apart by type
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Implicit

rating:
reason:

### Route 3

- Route: Type-level: SourceFile.path is Path | str and every write goes through local_path
- Reasoning given: mypy enforces it at every write site
- Outcome: kept
- proposed: good - Robust

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label decided this.

rating:
reason:

## T103

**Question:** How is a remote source modelled in code?  
**Kind:** divergent

### Route 1

- Route: A SourceFile with url, or Path | Url/str
- Reasoning given: Smallest change
- Outcome: kept
- proposed: out_of_scope - Internal

rating:
reason:

### Route 2

- Route: A separate Config.remote dict
- Reasoning given: Avoids 'but not remote' filters
- Outcome: kept
- proposed: out_of_scope - Internal

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: out_of_scope - Internal.

rating:
reason:

## T104

**Question:** How are keys removed that sit in both the included file and an override?  
**Kind:** divergent

### Route 1

- Route: Refuse with exit 3
- Reasoning given: Writing only the override lets the keys reappear; writing the shared file defeats CR-A
- Outcome: kept
- proposed: good - Protects shared files

rating:
reason:

### Route 2

- Route: Remove the key from every layer
- Reasoning given: Overrides cannot delete; the result is what was asked
- Outcome: kept
- proposed: acceptable - Modifies the shared file

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T105

**Question:** How is removing an anchored node still used by aliases handled?  
**Kind:** divergent

### Route 1

- Route: Refuse explicitly, naming the anchor
- Reasoning given: The read-back message would not name the anchor
- Outcome: kept
- proposed: good - Clear

rating:
reason:

### Route 2

- Route: Rely on the reload failure, giving exit 3
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Vague message

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Read-back catches it.

rating:
reason:

## T106

**Question:** When a scalar with an end-of-line comment becomes a block collection, where does the comment go?  
**Kind:** divergent

### Route 1

- Route: Keep the comment on the key or dash line; the collection goes below
- Reasoning given: Matches the rule for keys
- Outcome: kept
- proposed: good - No comment lost

rating:
reason:

### Route 2

- Route: Refuse a kind-changing replacement that would lose a comment
- Reasoning given: Contract silent
- Outcome: kept
- proposed: acceptable - Over-refuses

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write catches loss.

rating:
reason:

## T107

**Question:** What if $schema names another dialect?  
**Kind:** divergent

### Route 1

- Route: Exit 4
- Reasoning given: Draft-07 items mean something else
- Outcome: kept
- proposed: good - No silent misvalidation

rating:
reason:

### Route 2

- Route: Ignore $schema; always 2020-12
- Reasoning given: The contract names 2020-12
- Outcome: kept
- proposed: acceptable - Silent

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T108

**Question:** Which schema violation is reported?  
**Kind:** divergent

### Route 1

- Route: One, chosen by jsonschema's best_match, with its dotted path
- Reasoning given: A full list would be long
- Outcome: kept
- proposed: good - Readable

rating:
reason:

### Route 2

- Route: The first by deterministic path ordering
- Reasoning given: Deterministic
- Outcome: kept
- proposed: good - Stable

rating:
reason:

## T109

**Question:** At which path are aliased or merged strings judged against the schema?  
**Kind:** divergent

### Route 1

- Route: The position where it appears
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - One node could be judged two ways

rating:
reason:

### Route 2

- Route: Where the value is written (the anchor path or merge source)
- Reasoning given: That is where the string is written
- Outcome: kept
- proposed: good - Consistent

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T110

**Question:** How does set enforce the schema?  
**Kind:** divergent

### Route 1

- Route: A set that would break the schema exits 3
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Mechanism unrecorded

rating:
reason:

### Route 2

- Route: Through the read-back load, reworded as exit 3
- Reasoning given: Intended trees lack include content
- Outcome: kept
- proposed: good - Complete

rating:
reason:

### Route 3

- Route: Validate the final result once, or in a separate entry point (exit 3)
- Reasoning given: Intermediate states may be invalid; set needs a different exit code
- Outcome: kept
- proposed: good - Clear

rating:
reason:

## T111

**Question:** Which keywords are followed when looking up format: uri for a path?  
**Kind:** divergent

### Route 1

- Route: Also patternProperties, prefixItems, local $ref and combinators (depth-capped)
- Reasoning given: Schemas factor URIs into $defs
- Outcome: kept
- proposed: acceptable - Goes beyond the contract

rating:
reason:

### Route 2

- Route: Only properties, additionalProperties and items
- Reasoning given: The contract names exactly these
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T112

**Question:** How is the history seq numbered?  
**Kind:** divergent

### Route 1

- Route: seq = aggregate version - 1; the Created event is hidden from history
- Reasoning given: Gapless and starts at 1 by construction
- Outcome: kept
- proposed: good - No counter to maintain

rating:
reason:

### Route 2

- Route: seq is the position in a history log kept in the aggregate state
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Works, but the reason is unrecorded

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Any gapless scheme works.

rating:
reason:

## T113

**Question:** In what order are one set's events recorded?  
**Kind:** divergent

### Route 1

- Route: remove events (old order) before set events (new order)
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Deterministic but unexplained

rating:
reason:

### Route 2

- Route: set events in new document order, then remove events in old document order
- Reasoning given: Deterministic
- Outcome: kept
- proposed: good - Deterministic

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Contract silent.

rating:
reason:

## T114

**Question:** How does set create missing path segments?  
**Kind:** divergent

### Route 1

- Route: A missing parent with index 0 creates a new list; other indices exit 5
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Invents behaviour

rating:
reason:

### Route 2

- Route: Create only mapping keys; a digit segment needing creation, a scalar or null parent, or an index past the end exits 5 (append only at index == len)
- Reasoning given: Digit-only keys are out of contract
- Outcome: kept
- proposed: good - Conservative

rating:
reason:

## T115

**Question:** How does show print include-looking literal strings?  
**Kind:** divergent

### Route 1

- Route: Prefix them with !literal
- Reasoning given: The output reads back the same
- Outcome: kept
- proposed: good - Round-trips

rating:
reason:

### Route 2

- Route: Print as plain strings
- Reasoning given: show prints resolved values
- Outcome: kept
- proposed: acceptable - Reads back as an include

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T116

**Question:** Which quoting rules does show use?  
**Kind:** divergent

### Route 1

- Route: Reuse set's quoting and literal rules from one place
- Reasoning given: One decision in one place
- Outcome: kept
- proposed: good - No drift

rating:
reason:

### Route 2

- Route: set's rules plus quoting anything a YAML 1.1 or 1.2 reader would misread (probe), applied to show only
- Reasoning given: Reviewer found 2001-12-14, yes and 1_000 misread
- Outcome: kept
- proposed: good - Portable output

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Any read-back-safe rule works.

rating:
reason:

## T117

**Question:** How is show's read-back verified?  
**Kind:** divergent

### Route 1

- Route: Parse-back under both YAML 1.1 and 1.2; no runtime self-check
- Reasoning given: D-10
- Outcome: kept
- proposed: good - Strong

rating:
reason:

### Route 2

- Route: Tests load the output with the project's own loader
- Reasoning given: ruamel's resolver departs from the 1.2 core schema
- Outcome: kept
- proposed: good - Same semantics

rating:
reason:

### Route 3

- Route: Tests use ruamel's safe loader with type-exact compare
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Library typing differs

rating:
reason:

## T118

**Question:** How does step-1 show print values?  
**Kind:** divergent

### Route 1

- Route: Lowercase null/true/false, repr floats, trailing newline; a collection exits 5
- Reasoning given: (none)
- Outcome: becomes get at step 3
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T119

**Question:** How are source file labels computed?  
**Kind:** divergent

### Route 1

- Route: Lexical at first; reworked to real paths with symlinks resolved
- Reasoning given: Names the file a set would write; the loader identifies files by real path
- Outcome: reworked during step-3 planning
- proposed: acceptable - Defensible, but less recognisable

rating:
reason:

### Route 2

- Route: Lexical relpath to the theatre with '/' separators, symlinks not resolved, '../' for files outside; a text include names the included file
- Reasoning given: Users recognise the paths they wrote; avoids /private/var on macOS
- Outcome: kept
- proposed: good - User-facing paths

rating:
reason:

## T120

**Question:** Which subcommand accepts --sources?  
**Kind:** divergent

### Route 1

- Route: show only, before or after PATH; get --sources exits 2
- Reasoning given: argparse treats it as unknown
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T121

**Question:** Which file does --sources name for a value reached through an alias?  
**Kind:** divergent

### Route 1

- Route: The file holding the anchor
- Reasoning given: Aliases are file-local
- Outcome: kept
- proposed: good - Correct

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T122

**Question:** How are NEL, U+2028/2029 and U+FEFF written?  
**Kind:** divergent

### Route 1

- Route: Leave U+FEFF strings plain or single-quoted
- Reasoning given: Existing write-back behaviour; set's bytes must not change
- Outcome: kept
- proposed: acceptable - A known risk is left in place

rating:
reason:

### Route 2

- Route: Never write them literally outside double quotes; use a YAML 1.2 printable check
- Reasoning given: ruamel's scanner treats them as line breaks
- Outcome: kept
- proposed: good - Read-back stays exact

rating:
reason:

### Route 3

- Route: Write U+2028/2029 literally inside double quotes
- Reasoning given: The contract requires it; they read back correctly
- Outcome: kept; the U+2028 mismatch with ruamel at step 3 is left to the owner
- proposed: acceptable - Valid, but other readers may differ

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Rare characters.

rating:
reason:

## T123

**Question:** How was the step-6 alias issue framed?  
**Kind:** divergent

### Route 1

- Route: Bug reproduced (silent change with exit 0); fixed as a bug
- Reasoning given: Reproduced the silent change
- Outcome: kept
- proposed: good - Verified first

rating:
reason:

### Route 2

- Route: The bug cannot happen on main (anchors exit 4), so implement full step-6 support
- Reasoning given: Reproduced exit 4 on main
- Outcome: kept
- proposed: good - Verified first

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Every label implemented the feature.

rating:
reason:

## T124

**Question:** Is the process environment kept out of eventsourcing's configuration?  
**Kind:** divergent

### Route 1

- Route: Configure the store explicitly and ignore the process environment
- Reasoning given: eventsourcing reads the user's environment variables
- Outcome: kept
- proposed: good - Prevents stray configuration

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Low risk.

rating:
reason:

## T125

**Question:** How long does a history store stay open?  
**Kind:** divergent

### Route 1

- Route: Close at the end of each command and open per sync inside the lock in watch
- Reasoning given: No -wal/-shm files left; no stale caches
- Outcome: kept
- proposed: good - Clean end state

rating:
reason:

### Route 2

- Route: Keep one store open for watch's whole life
- Reasoning given: repository.get rebuilds from events, so other processes' events are seen
- Outcome: kept
- proposed: acceptable - Leaves WAL files during watch

rating:
reason:

### Route 3

- Route: One store per command, closed explicitly
- Reasoning given: Dropping the last reference closes the pool
- Outcome: kept
- proposed: good - Explicit

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T126

**Question:** What happens to tests of superseded behaviour?  
**Kind:** divergent

### Route 1

- Route: Rename and rewrite them, not delete
- Reasoning given: Behaviour changes must stay visible
- Outcome: kept
- proposed: good - Traceable

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Implicit.

rating:
reason:

## T127

**Question:** How is a string containing a TAB quoted?  
**Kind:** divergent

### Route 1

- Route: Single quotes, not a double-quoted escape
- Reasoning given: Single quotes come before double in the fallback order
- Outcome: kept
- proposed: good - Contract order

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Follows from the general rule.

rating:
reason:

## T128

**Question:** How is the !literal tag recorded?  
**Kind:** divergent

### Route 1

- Route: As a span outside the value span
- Reasoning given: Writers do not see the tag
- Outcome: kept
- proposed: good - Clean

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: out_of_scope - Internal.

rating:
reason:

## T129

**Question:** Were tests checked by deliberately breaking code?  
**Kind:** divergent

### Route 1

- Route: Tests written first and seen failing
- Reasoning given: (none)
- Outcome: at step 6
- proposed: good - TDD

rating:
reason:

### Route 2

- Route: Yes, mutation or break checks
- Reasoning given: Prove tests can fail
- Outcome: kept
- proposed: good - Strong tests

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Optional.

rating:
reason:

## T130

**Question:** Can a text include carry overrides?  
**Kind:** divergent

### Route 1

- Route: No: exit 4; a bare $ref text include behaves like the scalar form
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Clear

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T131

**Question:** What VALUEs may be written into a text include?  
**Kind:** divergent

### Route 1

- Route: First refused mappings and lists; reworked so any VALUE is accepted on an LF target and non-strings are refused only for CRLF
- Reasoning given: PO: the contract gives no such refusal
- Outcome: reworked in step 1
- proposed: acceptable - Follows the owner's ruling

rating:
reason:

### Route 2

- Route: Strings only (else exit 3); CRLF preserved
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Safe

rating:
reason:

### Route 3

- Route: Verify against CRLF-converted text
- Reasoning given: Verification failed for CRLF targets
- Outcome: kept
- proposed: acceptable - Fix only

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Verify-before-write covers it.

rating:
reason:

## T132

**Question:** How does show print a text include that a literal block cannot hold (CRLF, control characters)?  
**Kind:** divergent

### Route 1

- Route: Always a literal block, with CRLF turned into LF; read-back exception documented
- Reasoning given: The contract says text includes are literal blocks; get keeps the exact bytes
- Outcome: kept
- proposed: good - Follows the contract wording

rating:
reason:

### Route 2

- Route: Double-quoted first; reworked so every text include is a literal block with the file's exact text
- Reasoning given: The owner rejected the fallback: no exception in the contract
- Outcome: reworked at step 3
- proposed: good - Follows the owner's ruling

rating:
reason:

### Route 3

- Route: Fall back to a double-quoted string
- Reasoning given: A literal block cannot keep CR; data is never altered
- Outcome: kept
- proposed: acceptable - Exact, but deviates from the 'text includes as literal blocks' wording

rating:
reason:

## T133

**Question:** How are concurrent commands serialised?  
**Kind:** divergent

### Route 1

- Route: Blocking fcntl.flock on the .troupe/ directory fd (no lock file); locate the config before locking; set holds the lock through reconcile, write and record; history takes it too
- Reasoning given: Creates no file; the kernel releases it on death; SQLite cannot cover the file writes
- Outcome: kept
- proposed: good - Robust and leaves nothing behind

rating:
reason:

### Route 2

- Route: flock on a lock file in .troupe/ (events.lock / events.sqlite3.lock)
- Reasoning given: Whoever comes second sees a matching projection
- Outcome: kept
- proposed: good - Works; state is allowed in .troupe/

rating:
reason:

## T134

**Question:** Where is --theatre accepted, and what is its default?  
**Kind:** divergent

### Route 1

- Route: Added before the subcommand as an extra, then removed
- Reasoning given: Requirements must not be invented
- Outcome: reworked in step 1
- proposed: good - Self-corrected

rating:
reason:

### Route 2

- Route: After the subcommand only, defaulting to the current directory
- Reasoning given: Contract form
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 3

- Route: At both the config and the subcommand level
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Invents an extra form

rating:
reason:

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T135

**Question:** How were workflow-tool failures handled?  
**Kind:** divergent

### Route 1

- Route: Manual merges and copies, --lenient acceptance, forced statuses, no retries
- Reasoning given: Retries would fail the same way
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

### Route 2

- Route: Respected review stop limits at first; continued after a second failure at step 5
- Reasoning given: The fix was prescribed
- Outcome: kept
- proposed: out_of_scope - Process

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: out_of_scope - Process.

rating:
reason:

## T136

**Question:** How are values compared?  
**Kind:** divergent

### Route 1

- Route: Key-order-insensitive tree verification
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Ignores order changes

rating:
reason:

### Route 2

- Route: Type-strict: 1, 1.0, true and '1' differ; NaN equals NaN
- Reasoning given: A type change is a change
- Outcome: kept
- proposed: good - Exact

rating:
reason:

## T137

**Question:** Are breaking changes documented?  
**Kind:** divergent

### Route 1

- Route: README notes (https strings become includes, rollback limits)
- Reasoning given: (none)
- Outcome: kept
- proposed: good - User-friendly

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Optional.

rating:
reason:

## T138

**Question:** How is the CLI VALUE parsed?  
**Kind:** divergent

### Route 1

- Route: Compose as a single flow-sequence item; empty becomes null
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Lenient

rating:
reason:

### Route 2

- Route: Exactly one scalar or flow node; empty, block, multi-document, tag or anchor input exits 2
- Reasoning given: The contract says a single flow node
- Outcome: kept
- proposed: good - Strict

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Fixed by the contract.

rating:
reason:

## T139

**Question:** What does watch do when the files stop loading while it runs?  
**Kind:** divergent

### Route 1

- Route: Print errors to stderr and continue
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - May flood stderr

rating:
reason:

### Route 2

- Route: Report each distinct error once on stderr, record nothing, retry every tick, and resume
- Reasoning given: Editors save partial files; nothing is lost
- Outcome: kept
- proposed: good - Robust and readable

rating:
reason:

## T140

**Question:** How does watch write its line mid-run in the CLI architecture?  
**Kind:** divergent

### Route 1

- Route: A streaming or callback path from the CLI (stream_handler, announce or report callbacks)
- Reasoning given: Buffered handlers cannot print and keep running
- Outcome: kept
- proposed: out_of_scope - Internal plumbing

rating:
reason:

### Route 2

- Route: watch writes its own line and run returns ''
- Reasoning given: (none)
- Outcome: kept
- proposed: out_of_scope - Internal plumbing

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: out_of_scope - Internal design.

rating:
reason:

## T141

**Question:** How does watch treat remote includes?  
**Kind:** divergent

### Route 1

- Route: URLs not polled; a failing fetch is retried every tick
- Reasoning given: Existing retry behaviour
- Outcome: kept
- proposed: acceptable - Can block up to 10 s per tick

rating:
reason:

### Route 2

- Route: URLs not polled; changes are picked up at the next command or local change
- Reasoning given: Polling every 100 ms would be unkind to the server
- Outcome: kept
- proposed: good - Kind to servers

rating:
reason:

### Route 3

- Route: URLs not polled; re-fetched only when a local or schema file changes
- Reasoning given: Polling URLs is not in the contract
- Outcome: F fixed this in convergence
- proposed: good - Kind to servers

rating:
reason:

## T142

**Question:** Does watch wait for a file to settle before reconciling?  
**Kind:** divergent

### Route 1

- Route: Reconcile immediately; quick edits may record their net difference
- Reasoning given: A diff against the recorded state is naturally net
- Outcome: kept
- proposed: acceptable - May record a transient half-save

rating:
reason:

### Route 2

- Route: Settle before syncing (B: same bytes on two polls; E: up to 20 checks 0.05 s apart)
- Reasoning given: Avoid recording a file emptied mid-save
- Outcome: kept
- proposed: good - Avoids phantom events

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Broken saves are reported, not recorded.

rating:
reason:

## T143

**Question:** What does watch do if the config cannot load at startup?  
**Kind:** divergent

### Route 1

- Route: Exit 4 without printing the watching line
- Reasoning given: Same as every other command
- Outcome: kept
- proposed: good - Consistent

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T144

**Question:** What does watch print to stdout?  
**Kind:** divergent

### Route 1

- Route: Only the watching line; diagnostics go to stderr; no events printed; no files written
- Reasoning given: The contract asks only for that line
- Outcome: kept
- proposed: good - Contract

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T145

**Question:** Is the watching line printed if a stop arrives during startup?  
**Kind:** divergent

### Route 1

- Route: Skip the line if stop was requested
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - Fine

rating:
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Edge case.

rating:
reason:

## T146

**Question:** How are history-store errors during watch handled?  
**Kind:** divergent

### Route 1

- Route: Report and retry like load errors
- Reasoning given: No hand edit is lost
- Outcome: kept
- proposed: good - Resilient

rating:
reason:

### Route 2

- Route: Unexpected (non-LoadError) exceptions end watch
- Reasoning given: Stop rather than record silently
- Outcome: kept
- proposed: acceptable - Conservative

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Rare.

rating:
reason:

## T147

**Question:** What is <dir> in 'watching <dir>'?  
**Kind:** divergent

### Route 1

- Route: --theatre as given, else TROUPE_THEATRE, else the absolute cwd; never resolved
- Reasoning given: Resolving changes /var to /private/var
- Outcome: kept
- proposed: good - Matches user input

rating:
reason:

### Route 2

- Route: As passed, else TROUPE_THEATRE or '.'
- Reasoning given: (none)
- Outcome: kept
- proposed: acceptable - A bare '.' tells the user little

rating:
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: acceptable - Minor.

rating:
reason:

## T148

**Question:** How is a write checked before it reaches disk?  
**Kind:** divergent

### Route 1

- Route: Re-load the whole edited config in memory and compare it with the intended config; any mismatch exits 3 with nothing written
- Reasoning given: Turns renderer bugs into refusals instead of corruption
- Outcome: kept and extended in later steps
- proposed: good - A strong safety net

rating:
reason:

### Route 2

- Route: Re-parse the edited text and compare only the value at PATH with VALUE
- Reasoning given: A formatting bug becomes a refused write
- Outcome: kept
- proposed: acceptable - Misses unintended changes elsewhere

rating:
reason:

## T149

**Question:** Which YAML parsing approach supports byte-surgical write-back?  
**Kind:** divergent

### Route 1

- Route: Use PyYAML compose for node positions, with text splices
- Reasoning given: PyYAML follows YAML 1.1, so plain scalars are resolved by custom 1.2 rules
- Outcome: kept; step 6 needed a loader subclass to find alias positions
- proposed: acceptable - Works, but the YAML 1.1 parser needs extra workarounds

rating:
reason:

### Route 2

- Route: Use the ruamel.yaml composer only for node positions, apply edits as text splices, and never re-dump the file
- Reasoning given: A ruamel round-trip dump reformats untouched text, PyYAML is YAML 1.1, and a hand-written parser is too risky
- Outcome: kept through step 7
- proposed: good - Exact spans with no reformatting is the right basis for byte-surgical writes

rating:
reason:

# Unanimous (42)

## T150

**Question:** What TROUPE_ACTOR values are valid?  
**Kind:** unanimous

### Route 1

- Route: Lowercase human: or agent: plus a non-empty id kept verbatim after the first ':'; set-but-empty is invalid
- Reasoning given: 'anything else' is exit 2; a mistyped actor in an audit trail is worse than a refusal
- Outcome: kept
- proposed: good - Strict and auditable

rating:
reason:

## T151

**Question:** With TROUPE_ACTOR unset and no login name, what actor is recorded?  
**Kind:** unanimous

### Route 1

- Route: {kind: human, id: null} and the command still runs (login name from getpass.getuser)
- Reasoning given: State the unknown rather than guess; refusing would block the user
- Outcome: kept
- proposed: poor - Owner preference (2026-10-05): fail rather than record a null actor

rating:
reason:

## T152

**Question:** Which commands reject an invalid TROUPE_ACTOR, and when?  
**Kind:** unanimous

### Route 1

- Route: Every subcommand rejects it with exit 2, parsed once right after argument parsing, before anything is loaded or recorded
- Reasoning given: A misconfigured agent learns on its first command; nothing is recorded under a bad actor
- Outcome: E first validated only in set and reworked after the owner's answer; kept
- proposed: good - Predictable and safe

rating:
reason:

## T153

**Question:** Can an alias inside a flow collection be expanded?  
**Kind:** unanimous

### Route 1

- Route: No: exit 3
- Reasoning given: A block copy cannot go inside a flow collection
- Outcome: kept
- proposed: good - Safe

rating:
reason:

## T154

**Question:** How are anchored node spans handled so writes keep '&name'?  
**Kind:** unanimous

### Route 1

- Route: The span starts after &name, so a replacement keeps the anchor on the new value
- Reasoning given: Every edit path keeps the anchor without per-rule changes
- Outcome: kept
- proposed: good - Correct

rating:
reason:

## T155

**Question:** How is 'at' formatted?  
**Kind:** unanimous

### Route 1

- Route: UTC with microseconds and 'Z', one function; not eventsourcing's per-event timestamp
- Reasoning given: Fixed width, sorts lexically, TZ-proof
- Outcome: kept
- proposed: good - RFC 3339

rating:
reason:

## T156

**Question:** How is history persisted with eventsourcing?  
**Kind:** unanimous

### Route 1

- Route: One aggregate per theatre with a fixed id, in eventsourcing SQLite under .troupe/
- Reasoning given: Gives a total order, gapless versions and atomic batches
- Outcome: kept; event classes upcast at step 4
- proposed: good - A simple, atomic, durable single stream

rating:
reason:

## T157

**Question:** How often is a URL fetched within one command?  
**Kind:** unanimous

### Route 1

- Route: Once per command; reused by reloads and read-back
- Reasoning given: A second response could refuse correct writes at random
- Outcome: kept
- proposed: good - Consistent

rating:
reason:

## T158

**Question:** How is a changed folded scalar re-wrapped?  
**Kind:** unanimous

### Route 1

- Route: Align paragraphs with difflib; unchanged paragraphs keep their bytes; changed ones re-wrap at the old width (default 80)
- Reasoning given: Unchanged paragraphs keep their bytes; the contract requires re-wrapping
- Outcome: kept; C fixed re-wrapping of reordered paragraphs in rework
- proposed: good - Minimal diff

rating:
reason:

## T159

**Question:** How are get and show split at step 3?  
**Kind:** unanimous

### Route 1

- Route: get keeps step-1 scalar show (a collection exits 5 with a hint naming config show); show prints any value as YAML and prints a scalar exactly like get
- Reasoning given: Scripts keep working; the contract requires it
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T160

**Question:** What lineage do imports and hand edits get, and is a set's reconcile its own change?  
**Kind:** unanimous

### Route 1

- Route: actor unknown/null, null reason; the reconcile before a set is a separate change from the set's own cli change
- Reasoning given: Never credit a hand edit to the CLI user
- Outcome: kept
- proposed: good - Honest attribution

rating:
reason:

## T161

**Question:** Does history import a never-imported theatre?  
**Kind:** unanimous

### Route 1

- Route: history imports on first use but never reconciles
- Reasoning given: Importing is not reconciling
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T162

**Question:** Which HTTP client fetches remote includes?  
**Kind:** unanimous

### Route 1

- Route: Stdlib urllib
- Reasoning given: No dependency for a single GET
- Outcome: kept
- proposed: good - Lean

rating:
reason:

## T163

**Question:** When does the first import happen, and does it persist if the command then fails?  
**Kind:** unanimous

### Route 1

- Route: Import on the first command whose config loads; it stands if that command then exits 2, 3 or 5; a load failure creates no state
- Reasoning given: 'The first command imports'; nothing is created when the load fails
- Outcome: kept
- proposed: good - Conservative reading of the contract

rating:
reason:

## T164

**Question:** What does --in-include affect?  
**Kind:** unanimous

### Route 1

- Route: Only where new keys go; a store_true flag on set only; a no-op when no include is involved
- Reasoning given: The contract scopes it to new keys
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T165

**Question:** How is a scalar-form include converted to mapping form?  
**Kind:** unanimous

### Route 1

- Route: Follow the contract example ('coder: # c', $ref first, original bytes kept), with compact '- $ref:' for list items and inline {$ref: ...} in flow
- Reasoning given: Matches the contract; smallest diff
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T166

**Question:** How is one actor, at and change shared within a change?  
**Kind:** unanimous

### Route 1

- Route: One lineage per producer or batch (import, reconcile, set), stamped once with a uuid4 change id and one UTC instant
- Reasoning given: A shared change id and at hold by construction
- Outcome: kept; E stamps at record time inside the lock so at follows seq
- proposed: good - Correct by construction

rating:
reason:

## T167

**Question:** Where does a literal block's source comment go?  
**Kind:** unanimous

### Route 1

- Route: On the '|' header line; content lines and {}/[] lines get no comment
- Reasoning given: A comment on a content line becomes part of the value
- Outcome: kept
- proposed: good - Correct

rating:
reason:

## T168

**Question:** How do include-looking VALUE strings become !literal?  
**Kind:** unanimous

### Route 1

- Route: Mark every include-looking string, nested ones included, once before planning (str-subclass markers), unless the schema says uri; text include content is never tagged
- Reasoning given: A nested string would otherwise be fetched
- Outcome: kept
- proposed: good - Complete

rating:
reason:

## T169

**Question:** How does the loader represent $ref overrides?  
**Kind:** unanimous

### Route 1

- Route: A merged tree whose nodes keep their layers or base (provenance), so readers need no change
- Reasoning given: Readers would drift; provenance travels with the node
- Outcome: kept
- proposed: good - One truth

rating:
reason:

## T170

**Question:** How are multi-line strings written?  
**Kind:** unanimous

### Route 1

- Route: Literal block in block context when it can hold the value exactly; otherwise double-quoted
- Reasoning given: Literal blocks cannot appear in flow context or hold CR and control characters
- Outcome: kept; E fixed literal_ok so a newline is allowed
- proposed: good - Readable and exact

rating:
reason:

## T171

**Question:** With nested includes, which file receives a new key's override?  
**Kind:** unanimous

### Route 1

- Route: The nearest file holding the include reference, even if it is itself included
- Reasoning given: Literal contract wording
- Outcome: A reworked its placement walk to the innermost include after validation; kept
- proposed: good - Contract

rating:
reason:

## T172

**Question:** Where are existing (possibly overridden) values changed?  
**Kind:** unanimous

### Route 1

- Route: In the override if there is one, otherwise where they live; list appends and list-item keys stay in the list's file
- Reasoning given: Overrides cannot address list items
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T173

**Question:** How does --reason behave?  
**Kind:** unanimous

### Route 1

- Route: set only (other subcommands exit 2), last one wins, '' stored as '', null when absent, only on the set's own events
- Reasoning given: 'The text given'
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T174

**Question:** What does reconcile compare the files against?  
**Kind:** unanimous

### Route 1

- Route: The recorded configuration (projection of the events), diffed per leaf with set's typed rule
- Reasoning given: Idempotent; a set's write-back finds nothing new, so no self-write bookkeeping
- Outcome: kept
- proposed: good - Removes the double-recording risk by construction

rating:
reason:

## T175

**Question:** Which commands reconcile, and how is that wired?  
**Kind:** unanimous

### Route 1

- Route: Every command except history; one session or open function decides (flag, command-name set, or required keyword)
- Reasoning given: A new command cannot forget to reconcile; history reports only what is recorded
- Outcome: kept; get added at step 3
- proposed: good - Contract with one decision point

rating:
reason:

## T176

**Question:** Which include line does a remote-write refusal name?  
**Kind:** unanimous

### Route 1

- Route: The outermost local include, as written, with its file and line
- Reasoning given: The only line the user can change
- Outcome: kept
- proposed: good - Actionable

rating:
reason:

## T177

**Question:** How does --sources label remote values?  
**Kind:** unanimous

### Route 1

- Route: With the URL
- Reasoning given: (none)
- Outcome: kept
- proposed: good - Clear

rating:
reason:

## T178

**Question:** How is a URL's YAML or text format decided?  
**Kind:** unanimous

### Route 1

- Route: The URL path's .yml/.yaml suffix, ignoring query and fragment
- Reasoning given: Same rule as file:
- Outcome: kept
- proposed: good - Consistent

rating:
reason:

## T179

**Question:** Resolve plain scalars with the library's resolver or with an own YAML 1.2 core-schema resolver?  
**Kind:** unanimous

### Route 1

- Route: Own YAML 1.2 core-schema resolver
- Reasoning given: ruamel reads 1_000 as an int and dates as timestamps; PyYAML is 1.1
- Outcome: kept
- proposed: good - Exact core-schema typing, and it is defined in one place

rating:
reason:

## T180

**Question:** What does 'show PATH --sources' print for a scalar?  
**Kind:** unanimous

### Route 1

- Route: The scalar as a one-node YAML document with the '# from' comment
- Reasoning given: The contract promises a source for every scalar line
- Outcome: kept
- proposed: good - Consistent YAML

rating:
reason:

## T181

**Question:** How are the schema file's errors and watch tracking handled?  
**Kind:** unanimous

### Route 1

- Route: Unreadable, invalid or non-object schemas exit 4 naming the file; watch tracks the schema file whether present or absent
- Reasoning given: Avoids endless reconciles and races
- Outcome: kept
- proposed: good - Robust

rating:
reason:

## T182

**Question:** How is JSON Schema 2020-12 validation done?  
**Kind:** unanimous

### Route 1

- Route: The jsonschema library (Draft202012Validator), format not asserted, no remote $ref retrieval (types-jsonschema for mypy)
- Reasoning given: A hand-written validator would be subtly wrong
- Outcome: kept
- proposed: good - Reference implementation

rating:
reason:

## T183

**Question:** Does set write include-looking strings as !literal by default?  
**Kind:** unanimous

### Route 1

- Route: Yes: a breaking change; --include restores includes; old tests updated
- Reasoning given: The contract says such strings are literal
- Outcome: kept
- proposed: good - Contract

rating:
reason:

## T184

**Question:** What layout does show's YAML use?  
**Kind:** unanimous

### Route 1

- Route: 2-space indent, lists indented under their key, compact list items, {} and [] for empties (empty config prints {}), no document markers, one space before '#'
- Reasoning given: Common hand-written style; block style has no empty form
- Outcome: kept
- proposed: good - Readable and valid

rating:
reason:

## T185

**Question:** How is show's YAML produced?  
**Kind:** unanimous

### Route 1

- Route: Own line emitter over the source-mapped tree that tags each line with its source; --sources only appends comments
- Reasoning given: A dumper cannot say which line holds which scalar, and decides quoting itself
- Outcome: kept
- proposed: good - Exact control; the two outputs differ only by comments

rating:
reason:

## T186

**Question:** Are the files or the event projection the source of truth for current values?  
**Kind:** unanimous

### Route 1

- Route: Files are authoritative; show and set read the files, and hand edits are not recorded in step 1
- Reasoning given: Importing is not reconciling; a projection would show stale values after a hand edit
- Outcome: reworked at step 2: hand edits are reconciled into events
- proposed: good - Never hides a user's edit

rating:
reason:

## T187

**Question:** How is a written string quoted?  
**Kind:** unanimous

### Route 1

- Route: Keep the existing style if it can hold the value, else plain, then single, then double
- Reasoning given: The contract's fallback order
- Outcome: kept; shared with show at step 3
- proposed: good - Follows the contract

rating:
reason:

## T188

**Question:** How are tests run?  
**Kind:** unanimous

### Route 1

- Route: Real CLI subprocesses or in-process main with byte-exact files, a real SQLite store and a uv run smoke test
- Reasoning given: Real behaviour
- Outcome: kept
- proposed: good - Realistic

rating:
reason:

## T189

**Question:** How does watch detect file changes?  
**Kind:** unanimous

### Route 1

- Route: Stdlib polling of file bytes every 0.1 to 0.25 s; no watchdog, no mtime
- Reasoning given: No dependency; catches save-by-rename and same-size edits
- Outcome: kept
- proposed: good - Simple and reliable within 2 s

rating:
reason:

## T190

**Question:** Which files does watch track, and against what baseline?  
**Kind:** unanimous

### Route 1

- Route: Every loaded file plus both root candidates, recomputed after each load; the baseline is the bytes the load actually read
- Reasoning given: No edit can slip between load and announce; new includes are followed
- Outcome: A reworked its baseline from a pre-load snapshot after review; kept
- proposed: good - Makes the readiness line a true promise

rating:
reason:

## T191

**Question:** How does watch stop on SIGINT or SIGTERM?  
**Kind:** unanimous

### Route 1

- Route: Handlers only set a flag; a sync in progress finishes; exit 0; previous handlers are restored
- Reasoning given: No partial transaction and no traceback
- Outcome: kept
- proposed: good - Clean shutdown

rating:
reason:
