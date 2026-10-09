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

## 2. First collect (Docker not needed)

3. `--stage collect --no-docker` writes `collected/<arm>/<NN>.json` (churn deferred). The re-measure stage picks its
   targets from these records, so this comes first.

## 3. Mutation re-measure (Docker, holds the runner lock)

4. `uv run pytest tests/runner/scoring/test_remeasure_docker.py --run-docker -k spike` proves the whole-suite-per-mutant
   path works on this machine. Do not continue if it fails.
5. `--stage remeasure` re-measures every step whose mutation run crashed, or that is unmeasured because under half
   its sampled mutants were checked, into the step's `quality/`. It holds the runner lock (refuses while a run is
   active) and refuses on a halted pass. Each step has a budget of `mutation_seconds`; mutants not reached are
   `not_checked`. Check: the stage prints one file per re-measured step. A result with no mutant killed is recorded
   as `crashed`, not a score.
6. **Owner choice: comparability.** After step 5 some arms' mutation scores come from mutmut and others from the
   whole suite per mutant, which are not like-for-like (once aggregated, `scores.json` flags "mutation methods mixed"
   and the report's bottom line says so). To score every arm by one method, run `--stage remeasure --all`: it re-measures every arm's
   scored steps by the whole-suite method (up to `mutation_seconds` per step, for every arm and step). Skip it to
   keep mutmut's scores where they exist; the flag then stays in the report.

## 4. Collect again, anonymise and leak check

7. `--stage collect` (Docker, for churn) rewrites `collected/` so it picks up the re-measures and churn. Check: the
   record count is arms x steps run; read `missing` entries in the records.
8. `--stage anonymise` (Docker, container git) writes `anon/` and then `anon-key.json`. **Re-run it whenever any
   `anon/` predates the judge changes** (the judges need `MISSING.json` and `stale-list.toml` in each step dir).
   Labels are the arms shuffled by a random salt stored in `anon-key.json`: **re-running anonymise keeps labels while
   the key exists** (its salt is reused, even after a crashed re-run, from `anon-key.json.prev`); a new salt is drawn
   only when there is no key. Extractions and both sheets record the key's sha256 and refuse on a mismatch, so a
   changed key can never silently re-map ratings or verdicts.
   Check: any `anon/<label>/<NN>/MISSING.md` and `UNSCRUBBED.txt` are expected, and are disclosed in the report.
9. `--stage leak-check` searches every file under `anon/` (contents and paths, `repo/` and `diff.patch` included)
   for every arm's names, aliases, tool folders and CLI forms, with a checker independent of the scrubber's regexes.
   It writes `leak-check.json` and exits non-zero naming each hit. Fix the scrub terms (or accept a hit as disclosed
   residue, with the owner) before judging; the report discloses the result.

## 5. Approval, then decisions and judging (spends model quota)

10. `--stage judge-estimate` prints calls (judge plus decision extract and align), input size and implied cost,
    and separately the upper bound if every call needed its one parse retry (`calls_with_parse_retries`, 2x; shown
    for the owner, not what approval is checked against). It needs no approval. **One approval number covers the judge and the decision calls**, so this comes
    *before* `decisions-extract`.
11. Owner approves: `echo "approved <YYYY-MM-DD> <calls>" > results/pass1/scoring/judge-approved`. Any stage that
    spends quota refuses if its current estimate exceeds the approved number.
12. `--stage decisions-extract`, then `--stage decisions-align`. Align refuses while extractions failed; fix with
    `--retry-failed` on extract, or accept with `--allow-failed` (those labels then show as unrated "no
    evidence", never "not considered").
12a. `--stage decisions-context` (Docker: wrap it in the docker lock) writes `decisions/context/<topic>.json`. Per
    topic it makes two judge calls: the first plans example commands and the second writes up their results. The
    examples run in every arm's final code in the tester sandbox. It is resumable, and a topic is redone when a
    re-alignment changed its routes. Run `--only T1 T5 T40` first and show the owner a few topics before the rest.
    Failed topics are final unless `--retry-failed`, and the sheet shows them as "no behaviour context".
13. `--stage decisions-sheet` writes `decisions/rating-sheet.md`. It refuses to write a sheet that names an arm or an
    arm letter. Ratings are 1–5 or n/a and the reason is optional (spec §8.4, amended 2026-10-09). The owner can rate
    in chat instead: `python -m runner.scoring.rate <pass> next | show T4 | set T4 4 2 5 n/a [--reason 2 "…"] |
    progress` reads and writes only the blind sheet. **The owner fills only that file.** Never open
    `decisions/.import/` (it maps routes back to arms and would unblind the ratings). Then
    `--stage decisions-import`.
14. `--stage judge`: resumable, so re-run after a crash. Failed items are final unless `--retry-failed`; items
    whose input was missing are re-checked automatically on every run. Check: the printed counts; unjudged items
    show as unmeasured, never as zero.

## 6. Owner review of judgements

15. `--stage aggregate` writes `scores.json` (and refuses on an unreviewed all-fail test).
16. `--stage review-sheet` writes `review/review-sheet.md`: every disputed item, every item that decides a
    top-two placing, and a seeded sample. **The owner fills only `review/review-sheet.md`; never open `review/.import/`** (it maps items back to arms and
    would unblind the review). It can be filled over several sittings: items with both fields blank are skipped; half-filled or invalid items block the import; re-import is
    idempotent.
17. `--stage review-import`, then `--stage aggregate` again so the verdicts count.

## 7. Report and publishing

18. `--stage report` writes `report.md`, `report.html` and `confidence.json` (refreshed with the report so they
    cannot disagree). It refuses while `results/pass1/scoring/anon-key.json` is tracked by git (see below).
19. The operator publishes `report.html` as a **private artifact** and gives the owner the link.
20. Commit `results/pass1/scoring/` with the report, **after** moving `anon-key.json` out of the tree:

    ```sh
    mkdir -p state/pass1-scoring && mv results/pass1/scoring/anon-key.json state/pass1-scoring/
    ```

    The key maps Arm A-F to arms; committed, it de-anonymises the judges' evidence and the owner's ratings. The
    `report` stage checks the harness repo (`git ls-files --error-unmatch`, never an arm repo) and refuses while
    the key is tracked; if it is only on disk, untracked, the report still runs. Moving it ends the scoring
    stages that read it (`judge`, `decisions-*`, `review-*`), so finish them first; to redo one, move it back.
    Do not `git add` `anon/` unless the owner wants the anonymised copies kept (they are scrubbed, but large).
    Never commit `anon-tmp/`: it holds UNSCRUBBED exports (anonymise removes it on every exit, and it is
    gitignored; if a killed run left one, delete it).

## What the report discloses about blinding

Blinding is **partial**, and the report's "Blinding disclosure" section says so (residual vocabulary, structural
tells, the egress difference by tracker, counts of `UNSCRUBBED.txt` and `MISSING.json` items, and the leak check's
result):

- **Residual method vocabulary** is not scrubbed (`anonymise.RESIDUAL_VOCABULARY`): steering, mission, WP (work
  package), claude-plugins-official, constitution, charter, proposal, delta spec, converge, brainstorming, "Spec-Driven
  Development" (the phrase), issue ids and tracker concepts that name no tracker (e.g. `troupe-12`, ready/blocked),
  skill and command names without a method prefix, and the plain-English use of "open specification".
- **Structural tells** survive scrubbing: directory shapes such as nested `spec/spec/` (a scrubbed tool folder inside
  another), the placeholder names `tracker` and `tracker-cli` (only one arm family has a tracker), file counts and
  artefact shapes. The owner noted these in review.
- **Leak check:** the whole written `anon/` tree, repo trees and diffs included, is checked by the `leak-check` stage
  (step 9); the in-suite test over the snapshot covers transcripts, questions, gates and setup records only. The
  Docker test `test_anonymise_docker.py` checks only that dry1's arm name is gone, not the whole vocabulary.
- Unscrubbed binaries are listed per step in `UNSCRUBBED.txt` (text files of any size are scrubbed).
- The stale lists, rubrics and all-fail verdicts were written after steps 1-5 were seen and before steps 6-7: they are
  not fully pre-registered.
