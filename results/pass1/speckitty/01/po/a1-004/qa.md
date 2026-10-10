Q1: The mission scaffold is created, and nothing substantive has been written or committed yet.

**Branch contract**
- **Starting branch:** `chore/project-charter`.
- **Mission branch:** `feat/troupe-config-load-show-set`. It is the planning branch, the base branch and the Spec Kitty merge target. It was created from your current branch, so it includes the charter and the Spec Kitty setup.
- **Final landing:** I'll merge it into `main` locally at the end, as your delivery note asks. No push and no PR.
- **Mission:** `troupe-config-load-show-set-01M3XGPG`, type software-dev.

**Proposed scope (step 1)**
- **Who and when:** a theatre owner, or an automated test harness, runs `uv run troupe config show|set|history --theatre <dir>` against a project whose config lives in `.troupe/troupe.yml` or `.troupe/troupe.yaml`.
- **Desired outcome:** settings can be read and changed, and every change is recorded, without disturbing the hand-edited files.
- **Main rule:** after `set`, the only bytes that change in any file are the ones the contract requires.
- **Main exceptions:** each failure has a fixed exit code (2 usage error, 3 write refused, 4 config can't be loaded, 5 path not found or wrong kind of node). On failure, stdout is empty and stderr names the path or file.

**Extracted requirements:** about 22 functional rows, each taken from your contract with nothing added:

| Area | Requirements |
|---|---|
| CLI and general | `--theatre` defaults to the current directory; finding the config file (neither or both → exit 4); state kept only under `.troupe/`; dotted paths where digit segments index lists; `VALUE` parsed as a YAML 1.2 flow node; scalar printing rules; exit codes and messages |
| Includes | `file:` YAML includes are embedded in place; other targets become text values; recursive; missing target or cycle → exit 4 |
| `show` | Prints a scalar; a mapping or list → exit 5 |
| `set` placement | Existing values change in the file that holds them; text includes keep CRLF line endings; new keys go to the deepest existing ancestor mapping; appending at `index == length`; replacing a whole include → exit 3 |
| `set` formatting | Quoting style; double-quote escaping; block vs flow collections; literal blocks; folded re-wrapping; new entries placed below trailing comments; end-of-line comment columns |
| `history` | Per-leaf events as JSON Lines; first command imports; `set` and `remove` events; optional path prefix filter |

**Constraints:** Python 3.12+ with uv; the `eventsourcing` library, persisted under `.troupe/`; Linux/macOS; atomic writes.

**Out of contract (not built):** anchors, aliases and merge keys; multi-document files; a TAB before an end-of-line comment; concurrent writers.

**Non-functional:** a regression test proves untouched bytes are identical in 100% of `set` cases, and the strict quality gates from the charter (pytest, mypy, ruff) pass.

**One open question.** The contract says "importing is not reconciling" but doesn't say what happens when someone hand-edits the files after the import.

- **(A) Recommended:** the files on disk are the source of truth. `show` reads the current files, and `set` compares the current files with the result to produce its `set`/`remove` events. Hand edits are never back-filled into history. This matches "importing is not reconciling" and can't hide a user's edit.
- **(B)** The stored projection is the source of truth, and `show` ignores hand edits.
- **(C)** Something else.

Reply with A, B or C, plus any corrections to the summary above. Once you confirm, I'll write and commit `spec.md` and the checklist.

WAITING_FOR_DISCOVERY_INPUT
A1 (po): On “When files are hand-edited after the initial import, which is the source of truth for show and set: (A) the files on disk, (B) the stored projection, or (C) something else?”: A. The files are the source of truth. `show` and `set` always read the files as they are on disk. The stored projection is only the change history, so a hand edit appears in `show` but produces no history event. A later `set` records its `old` value as whatever was in the file.

On “Are there any corrections to the proposed scope summary?”: No corrections. The summary matches the contract sections in force for this step (General; Includes; show PATH; set PATH VALUE; history [PATH]) and the step brief.

Q2: The spec for `troupe-config-load-show-set-01M3XGPG` is written and committed, and it is ready for `/spec-kitty.plan`. No code has been written yet, and nothing is on `main` yet.

**Where it is**
- **Branch:** `feat/troupe-config-load-show-set`, created from `chore/project-charter`.
- **Commits:** `60bc3ec` adds the spec, meta and quality checklist. `849d23b` adds the record of your answer.
- **Delivery:** after implementation, the branch will be merged into `main` locally, with no push and no PR.
- **Uncommitted:** `status.events.jsonl`, Spec Kitty's own event log, has one new line from the last commit. It will go in with the next commit.

**What the spec contains**
- **Intent Summary:** the confirmed summary, including your answer: the files on disk are the source of truth. `show` and `set` always read the current files, hand edits produce no history event, and a later `set` records the on-disk value as `old`. This is requirement FR-008.
- **Domain Language:** a short glossary (theatre, root file, YAML vs text include, path, leaf, import, byte-surgical write-back).
- **User stories:** three, with concrete acceptance scenarios: P1 read a setting, P1 change a setting without disturbing the file, P2 review the history. Edge cases cover every exit-3, exit-4 and exit-5 condition.
- **Requirements:**
  - 24 functional requirements, taken directly from the contract sections in force.
  - 5 non-functional requirements with measurable thresholds: every byte of every file checked before and after `set`, no partial writes, state kept only under `.troupe/`, quality gates passing, and every error naming its path or file.
  - 6 constraints: Python 3.12+ with uv, the `eventsourcing` library, macOS/Linux only, the out-of-contract list, step-1 scope only, and delivery on `main`.
- **Assumptions I added**, which aren't in the contract:
  - A `set` that is refused or fails writes nothing and records no event.
  - The first command imports the theatre if the configuration loads, even if that command then exits 5.

**Checks**
- Every item in the quality checklist passes, with no clarification markers left.
- The decision check is clean (no findings).
- The prerequisites check reports the mission as valid.
A2 (po): /spec-kitty.plan

Q3: I've loaded the charter's plan context. The riskiest scenario is User Story 2: after `set`, the only bytes that change are the ones the contract requires (FR-014 to FR-020). How we write back decides almost everything else, so I'm asking this first.

**What I found:** the charter (TROUPE-001) mentions "format-preserving YAML round-tripping". But a ruamel.yaml load-modify-dump is only *mostly* format-preserving. It normalises indentation, can re-flow long lines and folded scalars, and rewrites quoting, spacing in flow collections and comment spacing. Several contract rules can't be met that way: folded paragraphs keeping their bytes, comments moved back to their previous column, and new entries placed below trailing comments.

**Options:**
- **(A) Recommended: find the node, then replace only its text.**
  - A parser locates the exact character span of the target node (start/end marks, block or flow, quoting style, indicator, end-of-line comment column).
  - A small set of edit rules builds only the replacement text: one rule each for quoting, block/flow collections, literal/folded blocks, entry placement and comment columns.
  - That text is spliced into the original file text, and the file is written atomically (temp file + rename).
  - The document is never re-serialised, so untouched bytes are identical by construction.
  - This still meets TROUPE-001's intent, and I'd record the reasoning in `research.md`.
- **(B) ruamel.yaml round-trip dump.** Less code, but it predictably breaks NFR-001 on real files and would need fix-ups that amount to (A) anyway.
- **(C) Something else.**

Reply A, B or C. After that I have one more question, about how history is stored under `.troupe/`, then I'll give you an Engineering Alignment summary to confirm.

WAITING_FOR_PLANNING_INPUT
A3 (po): A. The contract requires byte-surgical write-back: after a successful `set`, the only bytes that differ in any file are the ones the `set` section requires to change. Users hand-edit these files and review the diffs, so byte-surgical write-back matters more than speed. You may pick any technique that guarantees this. A round-trip dump that normalises indentation, quoting, flow spacing, folded scalars or comment spacing would break that rule.