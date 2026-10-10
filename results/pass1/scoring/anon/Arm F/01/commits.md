# Commits (13, newest first)

Each commit's short SHA and subject, then its message body.

## e3de0dd Insert new entries below a keep-chomped block's blank lines

With |+ or >+ chomping the blank lines after a block scalar belong to its value,
so placing a new key or list item above them changed that value and the write
was refused. Entries after such a block now end at its last block line
(research B-18); other blocks keep blank separators below the new entry.


## 2edf0e9 Append convergence task: insert after keep-chomped blocks

Converge found new keys after a |+ block scalar are refused, because insertion
lands inside the block's trailing blank lines, which belong to its value.


## 46421cc Allow setting a value to a file: include string

A file: string is a valid VALUE and becomes an include once written, but
verification compared the literal string with the resolved include and refused
it with a misleading message. Verify by the written value instead (the loaded
value still counts for text-include writes); a missing or cyclic target is
still refused, naming the target (research B-17).


## e2cfcd3 Append convergence task: setting a value to a file: include

Converge found set refuses a valid file: string value with a misleading
message, because verification compares the literal string with the resolved
include.


## 330dc2f Refuse unwritable targets and fail cleanly on store errors

Convergence found two Principle I breaches: the atomic rename silently replaced
read-only files, and event-store failures escaped as tracebacks with exit 1 and
no file named. set now checks the target file, its directory and the event
store before writing (exit 3, nothing changed), and store failures are load
errors naming the store file. Also drops the unrequested --theatre-before-
subcommand form so the CLI matches the contract exactly (Principle V).


## ca25f94 Append convergence tasks for step 1

Converge found that storage/write failures escape as tracebacks (exit 1, no
file named) and that set replaces read-only files, both against Principle I,
plus one unrequested CLI convenience to justify or remove.


## 2a41167 Polish: README, error-message coverage, --theatre before subcommand

Users and reviewers need one place describing the commands and exit codes, and
every failure must name its path or file (FR-008), so add a README and a test
sweeping each failure kind. Accept --theatre before the subcommand too, since
people naturally type it there; tasks.md now records all tasks complete with
pytest, mypy --strict and ruff passing.


## 6a3cd34 Test config history end to end

History is the audit trail reviewers rely on, so pin its contract: one import
event per leaf on first use, set/remove events per leaf in a fixed order,
nothing for no-op or failed sets, prefix filtering that does not match
siblings like bb for b, no reconciliation of hand edits, and contiguous seq
numbers across processes.


## 0c455a2 Add byte-surgical config set

People review these files as diffs, so set must change only the bytes of the
value: scalar styles kept or minimally changed, comments held at their column,
new keys and items placed below trailing comments, literal/folded blocks
rewritten in place, flow collections extended on the last entry's line, and
writes routed into the included file that holds the value. Every edit is
re-loaded and verified before an atomic write, refusing (exit 3) rather than
risking a wrong file.

Also fixes empty values (whose end mark points at the next token) and records
the design choices made while implementing (research B-13..B-15).


## 568a103 Add troupe config foundation and show command

Users need to read settings across included files before anything else; this
lands loading with file: includes (cycle and missing-target detection), YAML 1.2
core-schema typing owned in one place, the eventsourcing-backed store with
import on first use, the CLI with its exit-code mapping, and show.

The byte-surgical set modules are included because commands wire them in; their
behaviour tests follow in the next commits.


## 08854fb Add step 1 task list

Breaks the plan into test-first, story-ordered tasks so implementation can
proceed in small verified commits, with every behaviour mapped to a test as
the constitution requires.


## 7d5054e Add step 1 implementation plan and design artifacts

Records the technical approach (span-based splicing verified by re-load,
eventsourcing over SQLite) and the design-level choices the contract leaves
open, so tasks and implementation can trace each decision to a reason.


## 70df9f2 Add step 1 spec for troupe config load/show/set/history

Captures the product owner's contract as testable requirements and records the
conservative choices made where the contract leaves room (D-1..D-9), so planning
can start from an agreed statement of behaviour.

