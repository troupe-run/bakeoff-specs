The spec for `troupe-config-load-show-set-01M3XGPG` is written and committed, and it is ready for `/spec-kitty.plan`. No code has been written yet, and nothing is on `main` yet.

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