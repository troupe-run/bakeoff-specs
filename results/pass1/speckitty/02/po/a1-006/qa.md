Q1: **Discovery question 1: what should `watch` do when a hand edit breaks the configuration?**

**Scenario:** `troupe config watch` is running and someone saves a file that troupe can't load. It might be half-typed YAML, an include pointing at a file that doesn't exist yet, an include cycle, or both `troupe.yml` and `troupe.yaml` present. Editors often save in this kind of in-between state.

**What I found:**
- The contract only says `watch` stops on SIGINT/SIGTERM and exits 0.
- In step 1, every command exits 4 and names the file when the configuration can't be loaded. That still applies to the reconcile‑first step of `show`/`set`.
- `watch` is different because it runs for a long time. If it stops at the first broken save, it would stop during normal editing.

**Options:**
- **(A) Keep watching (recommended).** Write one stderr line that names the offending file and record nothing. When the files load again, reconcile against the last recorded configuration. The edits made in between then show up as normal `set`/`remove` events, and no data is lost or guessed.
- **(B) Stop.** Exit 4 and name the file, the same as other commands. The person has to restart `watch` after fixing it. Edits are still picked up later by the next command's reconcile.
- **(C) Something else.**

**Choices I'll make unless you object** (each one fills a gap in the contract, and I'll record why in the spec):
- `watch` writes nothing to stdout except `watching <dir>`.
- On a theatre that has never been imported, `watch` imports first, as every step‑1 command does.
- If the configuration can't load when `watch` starts, it exits 4 before printing `watching`.
- `history` still imports a never-imported theatre but never reconciles.
- Reconcile events use the existing `set`/`remove` ops. Sets come in document order, then removes, the same as a `set` command.

WAITING_FOR_DISCOVERY_INPUT
A1 (po+fallback): On “When `troupe config watch` is running and a hand edit leaves the configuration unloadable (bad YAML, missing include target, include cycle, or both troupe.yml and troupe.yaml present), should watch keep watching and report the file on stderr, or exit 4?”: The brief doesn't cover this. Make the safest assumption (the one least likely to lose or corrupt a user's data or to contradict the contract), record it as a decision with your reason, and carry on.

On “Do you object to the listed default choices: watch's stdout carries only `watching <dir>`; watch imports a never-imported theatre first; watch exits 4 before printing `watching` if the configuration cannot load at startup; history imports but never reconciles; reconcile events use set/remove ops, with sets in document order and then removes?”: No objection. Using only `watching <dir>` on stdout is your choice, and the brief says this is out of contract (Escalated answers, watch stdout). Importing first follows from 'The first command run against a theatre imports it' (history). Exiting 4 at startup with nothing on stdout follows from the General exit codes and from 'the line is a promise'. History importing but never reconciling is stated in history and in Sync with files. Reconcile emitting set/remove events is stated in Sync with files (Reconcile). The contract does not state an order for events within one reconcile, so the order you proposed is acceptable. Record what you chose in the spec.

Q2: The spec for step 2 is written and committed on `feat/troupe-config-sync-files` (commit `2941e03`), and the quality checklist passes on the first try. It isn't on `main` yet. Delivery means merging that branch into `main` after implementation, the same way step 1 landed. Nothing pushed, no PR.

- **Mission:** `troupe-config-sync-files-01M3ZT6R` (id `01M3ZT6RJENXK1D5FZYETB4V72`)
- **Spec:** `kitty-specs/troupe-config-sync-files-01M3ZT6R/spec.md`
- **Checklist:** `kitty-specs/troupe-config-sync-files-01M3ZT6R/checklists/requirements.md`

**What the spec says:**
- **Change to step 1:** step 1 said hand edits never create history events (FR‑008/FR‑022 and its confirmed decision). That rule is replaced: reconcile now records hand edits as `set`/`remove` events. The files on disk are still the source of truth, and reconcile never writes to a file.
- **The rule that must always hold:** after any reconcile, the history matches the files on disk, and each difference is recorded exactly once. FR‑015 and FR‑016 apply this to a `set` while `watch` is running, so its write-back isn't recorded a second time.
- **Your answer on the open question (D‑1):** if a hand edit breaks the configuration while `watch` is running, `watch` keeps running. It writes one stderr line naming the file, records nothing, and reconciles once the files load again. Why: the contract says `watch` runs until SIGINT/SIGTERM and then exits 0, and recording nothing loses no edits and can't corrupt the history.
- **Recorded choices D‑2 to D‑7:** the ones you accepted (stdout is only `watching <dir>`, import before the line, exit 4 at startup, `history` doesn't reconcile, event order). Plus one I made where the contract is silent: if a command reconciles and then fails with exit 3 or 5, the reconcile's events are kept.
- **Size:** 16 functional requirements, 7 non-functional ones (including the 2‑second reaction time and no missed changes after the `watching` line), and 5 constraints. One `watch` plus one other command at a time is supported; several `watch` processes on one theatre, or two `set` commands at once, are not.

`setup-plan` has already created an empty `plan.md`. `status.events.jsonl` has an uncommitted bookkeeping change from spec-kitty. How a `set`'s write-back is kept from being picked up again is deliberately left for the plan.

Next step: `/spec-kitty.plan`.
A2 (po): /spec-kitty.plan

Q3: **Planning question 1: how should a `set`'s write-back be kept out of `watch`'s events, and each edit recorded exactly once?**

**What the code already gives us:**
- `set` writes files atomically (temp file plus rename), then records its events.
- The history is an eventsourcing aggregate in `.troupe/history.sqlite`. Its version check makes a second concurrent save fail instead of silently interleaving.
- `leaves.diff` already produces the ordering in D‑6.

**Options:**
- **(A) Theatre lock plus compare (recommended).** Every reconcile, and every `set` (from its reconcile through writing files and recording events), runs under an exclusive `flock` on `.troupe/lock`. A reconcile records only the leaves that differ from the recorded configuration, which is the history replayed into a path→value map kept on the aggregate.
  - A write-back is recorded by `set` before the lock is released, so when `watch` next reconciles it finds no difference and records nothing.
  - A hand edit is recorded by whichever reconcile takes the lock first. The next one finds it already recorded.
  - There is no bookkeeping that can drift: the "exactly once" rule follows directly from the invariant.
- **(B) Fingerprint ignore list.** `set` writes the hashes of the files it wrote, and `watch` skips matching bytes. This is fragile: a hand edit saved between the write and `watch`'s check is lost or double-counted, and a hand edit that happens to restore earlier bytes is suppressed.
- **(C) Something else.**

**Engineering Alignment (please confirm with your answer):**
1. **How `watch` observes files: stdlib polling, no new dependency.** About every 250 ms, `watch` reads the bytes of the watched files plus both root-file names. Any difference triggers a reconcile.
   - Comparing bytes rather than mtimes catches editors that save by renaming a new file over the old one, and same-second edits.
   - The baseline is taken before reconciling, and `watching <dir>` is printed afterwards. So any edit made after the line appears is detected within about 0.5 s, well under 2 s.
   - The alternative was adding `watchdog`, which brings a supply-chain dependency and platform-specific backends, so I rejected it.
2. **The watched set** is the set of files the loader actually read; the loader will report it. While the configuration can't load, `watch` retries loading every tick. It prints one `troupe: …` stderr line when it becomes unloadable, and another only if the error changes.
3. **Recorded configuration:** the `ConfigHistory` aggregate keeps a `leaves` map that its import, set and remove events update. Existing step‑1 databases replay into it unchanged, so no migration is needed.
4. **Reconcile** is one function, `reconcile(theatre)`: lock, load, import if needed, diff against the recorded leaves, record. `show`, `set` and `watch` call it. `history` keeps its current path (it imports but never reconciles).
5. **Signals:** SIGINT/SIGTERM set a stop flag. The loop finishes any reconcile in progress (each one is a single atomic save), then exits 0.
6. **A contract-fidelity change to the spec:** `watching <dir>` will echo the theatre directory as you gave it, whether that came from `--theatre`, `$TROUPE_THEATRE` or the current directory. It will not print the resolved path. The contract writes `--theatre <dir>` → `watching <dir>`. Resolving would turn macOS `/var/…` into `/private/var/…` and break that match. I'd update FR‑009 to say this.

WAITING_FOR_PLANNING_INPUT
A3 (po): On “Which mechanism should keep a `set`'s write-back out of `watch`'s events and record each edit exactly once: (A) a theatre lock plus comparing against the recorded configuration, (B) a fingerprint ignore list, or (C) something else?”: The contract fixes the outcome, not the mechanism, so the mechanism is your engineering choice. The outcome it requires: a `set` while `watch` runs emits exactly the `set`'s own events and its write-back produces no further events; every hand edit made after `watching <dir>` is reconciled within 2 seconds; a formatting-only or comment-only edit emits nothing; and state lives only under `<dir>/.troupe/`. (A) is consistent with all of that, and a lock file under `.troupe/` is allowed state. (B) as you describe it would lose or suppress some hand edits, which contradicts 'Within 2 seconds of any change … it reconciles', so it is not acceptable as described. Proceed with (A).

On “Is it acceptable for `watch` to observe files by polling their bytes with the stdlib about every 250 ms, with no new dependency?”: Yes. The contract only requires a reconcile within 2 seconds of any change made after the `watching <dir>` line, and that line may be printed only once `watch` can observe changes. Taking the baseline before printing meets that promise. The brief sets no performance targets (configurations are small), and only macOS and Linux need to be supported.

On “Is it acceptable for the watched set to be the files the loader actually read, with `watch` retrying the load every tick while the configuration can't load, and printing one stderr line when it becomes unloadable and another only when the error changes?”: Yes. Watching the config file plus every included file is what Sync with files requires, and that includes includes added by a hand edit. How often to write to stderr while the configuration can't load is your choice, because the contract doesn't specify it. Each message must name the path or file involved.

On “Is it acceptable for the history aggregate to keep a path→value `leaves` map, rebuilt by replaying existing events, with no migration?”: Yes. That is internal state under `.troupe/`, which the contract allows. Existing histories must keep being reported by `history` exactly as before.

On “Is it acceptable for a single `reconcile(theatre)` to be called by `show`, `set` and `watch`, while `history` imports but never reconciles?”: Yes. That matches the contract: every command other than `history` reconciles first, and `history` imports a theatre that has never been imported but never reconciles.

On “Is it acceptable for SIGINT/SIGTERM to set a stop flag, so that the loop finishes any reconcile in progress and then exits 0?”: Yes. The contract says `watch` runs until SIGINT or SIGTERM and then exits 0. Finishing an atomic reconcile before exiting is consistent with that.

On “Should `watching <dir>` echo the theatre directory as given (from `--theatre`, `$TROUPE_THEATRE` or the current directory) instead of the resolved path, with FR-009 updated to say so?”: Yes. The contract writes `--theatre <dir>` and then `watching <dir>`, so with `--theatre` the line must show the same `<dir>` that was given, not a resolved path. When the directory comes from the environment variable or defaults to the current directory, what to print is out of contract. Echoing it as given is acceptable; record that choice in FR-009.

Q4: The plan for step 2 is written and committed on `feat/troupe-config-sync-files` (commits `c340ce1` and `be613e5`), and `setup-plan` reports the plan phase complete. Nothing is implemented yet.

**Branch:** current, planning base and merge target are all `feat/troupe-config-sync-files`, and `branch_matches_target` is true. That branch goes into `main` at delivery. No push, no PR.

**Design, as you confirmed it:**
- **No double recording:** every reconcile and every `set` (from its reconcile through writing files and recording events) runs under one exclusive lock on the `.troupe` directory. A reconcile records only what differs from the recorded configuration. A write-back is already recorded before `watch` can see it, so `watch` finds no difference and records nothing.
- **No new file in the theatre:** the lock is taken on the `.troupe` directory itself, so the existing test that commands create only history files (`test_history.py:154`) still holds.
- **Recorded configuration:** a path→value map on the history aggregate, rebuilt by replaying events. Existing step‑1 histories need no migration and print exactly as before.
- **`watch`:**
  - It compares the bytes of the watched files and both root-file names every 0.25 s, with no new dependency.
  - The baseline is taken before `watching <dir>` is printed, so an edit made after the line is never missed.
  - While the configuration can't load, it retries every tick and prints one stderr line per distinct error.
  - SIGINT/SIGTERM let any reconcile in progress finish, then it exits 0.
- **One place for reconcile:** `open_session(theatre_dir, reconcile=…)` does lock → locate → load → import or reconcile. `show` and `set` pass `True`, `history` passes `False`.
- **Spec change:** FR‑009 now says `watching <dir>` echoes the directory as given (new decision D‑8).
- **Step‑1 tests to rewrite:** two of them encode the old "hand edits never produce events" rule. They'll be rewritten alongside the reconcile code, not deleted.

**One risk the plan leaves alone:** a hand edit saved during a `set`'s locked section is two writers on the same file at once. That is out of contract (C‑003), so it's documented rather than handled.

All 9 charter rules pass, the dependency checks (directive 051) had nothing to review, and the decision check is clean. `status.events.jsonl` has an uncommitted bookkeeping change from spec-kitty.

Files are in `kitty-specs/troupe-config-sync-files-01M3ZT6R/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli-watch.md`
- `quickstart.md`

Next step: `/spec-kitty.tasks`.
A4 (po): /spec-kitty.tasks

Q5: The tasks are written and finalized: 4 work packages with 22 subtasks, committed on `feat/troupe-config-sync-files` (finalize commit `4e9d42e`, data-model fix `5102e12`). Validation passed, all 16 functional requirements are mapped, and no two WPs own the same file. Nothing is implemented yet.

| WP | Goal | Subtasks | Prompt size | Depends on |
|---|---|---|---|---|
| WP01 | History keeps a path→value map of what it has recorded, plus the theatre lock | T001–T004 (4) | 213 lines | – |
| WP02 | `reconcile`; `show`/`set` reconcile first, `history` never; rewrite the step‑1 tests this supersedes | T005–T010 (6) | 267 lines | WP01 |
| WP03 | `troupe config watch` (CLI, polling, unloadable handling, signals, test harness, tests) | T011–T017 (7) | 290 lines | WP02 |
| WP04 | Tests for includes, write-backs not re-detected and exactly-once recording; fix anything they expose; quickstart and all gates | T018–T022 (5) | 179 lines | WP03 |

- **Size:** about 240 lines per WP on average. Every WP is within limits (≤7 subtasks, under 700 lines) and starts with the "Do This First" profile-load section.
- **Profiles:** all four use `python-pedro` as implementer, `agent: claude`.
- **Parallelism:** none between WPs, because the dependency chain is linear. `lanes.json` puts each WP in its own lane (`lane-a` to `lane-d`), but they still run one after another. Inside WP01 the history work and the lock work are independent.
- **MVP:** WP01 + WP02 already deliver "edits made while nothing was running are picked up".

Two things in the prompts are worth knowing about:
- **Old histories:** WP01's replay tolerates step‑1 histories that record a `remove` for a path that was never recorded, as found during tasks.
- **Superseded tests:** WP02 names the two step‑1 tests that change and says exactly how. They are rewritten, not deleted.

**Branch:** planning base and merge target are both `feat/troupe-config-sync-files`, and `branch_matches_target` is true. That branch then goes into `main` by local merge. No push, no PR.

`status.events.jsonl` (modified) and `status.json` (new) are uncommitted spec-kitty bookkeeping. I've deliberately not committed `status.json`, because a project memory notes that committing it trips spec-kitty's lane guards.

**Should I use the `/spec-kitty-implement-review` skill to fully implement all WPs until completion?** It dispatches implementing and reviewing agents for each WP, handles rejections, and merges the lanes when done. `/spec-kitty.analyze` must run first, because the implement step won't start until its `analysis-report.md` exists. I'd run it as the first step if you say yes.
A5 (po): /spec-kitty-implement-review