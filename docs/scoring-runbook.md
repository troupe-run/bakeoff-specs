# Scoring a pass: run book (Plan 3)

Run after pass 1 has finished, **in the main checkout, on the landed `scoring` branch, against `results/pass1`**
(nothing is copied; the worktree snapshot was only for building the scorer). Design: [design §8](design.md),
spec: [superpowers/specs/2026-10-05-scoring-design.md](superpowers/specs/2026-10-05-scoring-design.md).
Every stage is `uv run runner score pass1 --stage <S>` and prints what it wrote or why it refused.
Stages that need Docker or quota say so. Order matters: the stages are listed in dependency order.

Re-running is safe: every stage reads the previous stage's files under `results/pass1/scoring/` and is
resumable or idempotent unless noted.

## 1. Before anything: tests every arm fails (owner)

1. `--stage all-fail` lists hidden tests every arm failed. Any test not in `scoring/excluded-tests.toml` is
   reviewed by the owner first and added there.
2. Every entry's `decided` must read `owner <date>`. A `draft` verdict still applies but `aggregate` flags it in
   `scores.json`; do not publish a report that carries that flag.

## 2. Mutation re-measure (Docker, holds the runner lock)

3. `uv run pytest tests/runner/scoring/test_remeasure_docker.py --run-docker -k spike` proves the whole-suite-per-mutant
   path works on this machine. Do not continue if it fails.
4. `--stage remeasure` re-measures every crashed mutation run into the step's `quality/`. It holds the runner
   lock (refuses while a run is active) and refuses on a halted pass. Each step has a budget of
   `mutation_seconds`; mutants not reached are `not_checked`. Check: the stage prints one file per re-measured
   step. A result with no mutant killed is recorded as `crashed`, not a score.

## 3. Collect and anonymise

5. `--stage collect` (Docker, for churn; `--no-docker` defers churn) writes `collected/<arm>/<NN>.json`. Check: the
   record count is arms x steps run; read `missing` entries in the records.
6. `--stage anonymise` (Docker, container git) writes `anon/` and then `anon-key.json`. **Re-run it whenever any
   `anon/` predates the judge changes** (the judges need `MISSING.json` and `stale-list.toml` in each step dir).
   Labels are seeded by the pass name, so re-running anonymise after ratings exist is safe (same labels).
   Check: any `anon/<label>/<NN>/MISSING.md` and `UNSCRUBBED.txt` are expected, and are disclosed in the report.
7. `--stage leak-check` searches every file under `anon/` (contents and paths, `repo/` and `diff.patch` included)
   for every arm's names, aliases, tool folders and CLI forms, with a checker independent of the scrubber's regexes.
   It writes `leak-check.json` and exits non-zero naming each hit. Fix the scrub terms (or accept a hit as disclosed
   residue, with the owner) before judging; the report discloses the result.

## 4. Approval, then decisions and judging (spends model quota)

8. `--stage judge-estimate` prints calls (judge plus decision extract and align), input size and implied cost.
   It needs no approval. **One approval number covers the judge and the decision calls**, so this comes
   *before* `decisions-extract`.
9. Owner approves: `echo "approved <YYYY-MM-DD> <calls>" > results/pass1/scoring/judge-approved`. Any stage that
   spends quota refuses if its current estimate exceeds the approved number.
10. `--stage decisions-extract`, then `--stage decisions-align`. Align refuses while extractions failed; fix with
    `--retry-failed` on extract, or accept with `--allow-failed` (those labels then show as unrated "no
    evidence", never "not considered").
11. `--stage decisions-sheet` writes `decisions/rating-sheet.md`. **The owner fills only that file.** Never open
    `decisions/.import/` (it maps routes back to arms and would unblind the ratings). Then
    `--stage decisions-import`.
12. `--stage judge`: resumable, so re-run after a crash. Failed items are final unless `--retry-failed`; items
    whose input was missing are re-checked automatically on every run. Check: the printed counts; unjudged items
    show as unmeasured, never as zero.

## 5. Owner review of judgements

13. `--stage aggregate` writes `scores.json` (and refuses on an unreviewed all-fail test).
14. `--stage review-sheet` writes `review/review-sheet.md`: every disputed item, every item that decides a
    top-two placing, and a seeded sample. **The owner fills only `review/review-sheet.md`; never open `review/.import/`** (it maps items back to arms and
    would unblind the review). It can be filled over several sittings: items with both fields blank are skipped; half-filled or invalid items block the import; re-import is
    idempotent.
15. `--stage review-import`, then `--stage aggregate` again so the verdicts count.

## 6. Report and publishing

16. `--stage report` writes `report.md`, `report.html` and `confidence.json` (refreshed with the report so they
    cannot disagree). It refuses while `results/pass1/scoring/anon-key.json` is tracked by git (see below).
17. The operator publishes `report.html` as a **private artifact** and gives the owner the link.
18. Commit `results/pass1/scoring/` with the report, **after** moving `anon-key.json` out of the tree:

    ```sh
    mkdir -p state/pass1-scoring && mv results/pass1/scoring/anon-key.json state/pass1-scoring/
    ```

    The key maps Arm A-F to arms; committed, it de-anonymises the judges' evidence and the owner's ratings. The
    `report` stage checks the harness repo (`git ls-files --error-unmatch`, never an arm repo) and refuses while
    the key is tracked; if it is only on disk, untracked, the report still runs. Moving it ends the scoring
    stages that read it (`judge`, `decisions-*`, `review-*`), so finish them first; to redo one, move it back.
    Do not `git add` `anon/` unless the owner wants the anonymised copies kept (they are scrubbed, but large).

## What the report discloses about blinding

Blinding is **partial**, and the report says so:

- **Residual method vocabulary** is not scrubbed (`anonymise.RESIDUAL_VOCABULARY`): steering, mission, WP (work
  package), claude-plugins-official, constitution, charter, proposal, delta spec, converge, brainstorming, "Spec-Driven
  Development" (the phrase), issue ids and tracker concepts that name no tracker (e.g. `troupe-12`, ready/blocked),
  skill and command names without a method prefix, and the plain-English use of "open specification".
- **Structural tells** survive scrubbing: directory shapes such as nested `spec/spec/` (a scrubbed tool folder inside
  another), the placeholder names `tracker` and `tracker-cli` (only one arm family has a tracker), file counts and
  artefact shapes. The owner noted these in review.
- **Leak check:** the whole written `anon/` tree, repo trees and diffs included, is checked by the `leak-check` stage
  (step 7); the in-suite test over the snapshot covers transcripts, questions, gates and setup records only. The
  Docker test `test_anonymise_docker.py` checks only that dry1's arm name is gone, not the whole vocabulary.
- Unscrubbed binaries are listed per step in `UNSCRUBBED.txt` (text files of any size are scrubbed).
- The stale lists, rubrics and all-fail verdicts were written after steps 1-5 were seen and before steps 6-7: they are
  not fully pre-registered.
