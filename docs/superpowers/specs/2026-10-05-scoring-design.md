# Plan 3 — scoring: design

Status: **draft for owner review** · 2026-10-05 · owner: Martin (hps.gd)

Turns pass 1's evidence into the recorded, defensible choice the bake-off exists for (design §1). Settles the
open items in design §8. Brainstormed with the owner 2026-10-05 19:46–20:15 AEST while pass 1 was at step 5.

## 1. Purpose and success criteria

- **Output:** a scorecard that supports the owner's decision, not a single verdict. Per-dimension raw scores and
  weights are shown with an explicit confidence check; the owner makes the call and records why (owner, Q1: B
  plus confidence).
- **Traceable:** every number in the report links to the evidence file it came from. Someone who was not present
  can re-run the scorer and get the same numbers.
- **Re-runnable (design decision "c"):** the scorer is part of the harness. A future pass, a new tool version or a
  second-model re-run is scored by the same code; scores are comparable across runs.
- **Built while pass 1 runs, offline.** Judge runs and the Docker suite wait until pass 1 is finished (machine
  and quota contention).

## 2. Changes to design §8 (owner decisions, 2026-10-05)

| Was | Now |
|---|---|
| Coping with change 30 · Correctness 20 · Traceability 15 · Human interaction 15 · Code and test quality 10 · Setup and ergonomics 10 | Coping with change **20** · Correctness 20 · Traceability 15 · Human interaction 15 · Code and test quality **15** · Setup and ergonomics 10 · **Time to outcome 5** |
| Cost reported, not scored | **Time to outcome is scored** (5). Cost stays reported alongside, with outliers either way flagged. Owner: "I'd score time taken to reach an outcome (cost is a proxy for that)"; "blow-outs one way or another are interesting data points." |
| "Number and value of questions" | **Value of questions.** Asking is never penalised for its own sake; only asks whose answer was within reach, or that were superfluous, lose points. The count is reported. |
| Owner review time scored under human interaction | **Removed from the score; reported.** The relay auto-continued uncontroversial reviews, so the measure reflects the relay, not the arm. |
| LLM judges, checked by the owner | **A panel of three lenses per judged part** (§6). Disagreement is reported, not averaged away. |

The design's headline ("judged on how each method copes with change over time") is **not** reworded. Owner:
correctness is implicit in coping with change; measuring change explicitly as well as the correctness of that
change is deliberate overlap. Six of seven steps are change steps.

## 3. Scorecard

| Weight | Dimension | Parts (points within the dimension) | Measured / judged |
|---|---|---|---|
| 20 | **Coping with change** | Regressions: earlier steps' hidden tests still green after each change step (7) · Stale artefacts updated: old requirements, tests and docs a change made wrong were found and changed, steps 3, 5, 7 (7) · Collateral churn: lines changed in files the step had no reason to touch (3) · Hand edit detected and reconciled, step 2 (3) | measured · judged · measured · judged |
| 20 | **Correctness** | Hidden tests passed per step, **all** tests at that step including earlier steps' (a regression deliberately costs twice) | measured |
| 15 | **Traceability** | Requirement → test → code · change → reason · fallback assumptions recorded as decisions · step 6's fix leaves a spec trace | judged |
| 15 | **Quality of human interaction** | Value of questions, N.a and N.b both counted · research before asking, informed-choice framing (design §8) · gates at sensible points | judged |
| 15 | **Code and test quality** | Mutation score · `mypy --strict` and lint · test names checked against what the tests assert | measured · measured · judged |
| 10 | **Setup and ergonomics** | Setup effort (4) · fit with Claude Code and the arm's tracker (4) · arm violations, deduction by severity (2) | judged · judged · measured |
| 5 | **Time to outcome** | Arm working time per hidden test passed | measured |

Internal splits not given above are equal. All weights live in one file, `scoring/weights.toml` (single source
of truth).

**Reported, not scored:** cost; time and cost by phase (§5); outliers in time or cost, by step and by arm; owner
review time; tracker quality (incl. step 6's tracker round trip); N.a runs in full; re-runs and harness faults;
the "your choice" sweep (§8).

## 4. Scales (owner, Q3: C)

- **Natural scale where one exists:** pass rates and mutation scores as they are.
- **Deductions with a floor:** mypy and lint error counts.
- **Control as the baseline where none exists:** time and collateral churn are scored on log(arm ÷ control) for the
  same step. Equal to control is the midpoint; the scale is capped at 10× worse and 10× better, so one bad control
  step or one blow-out cannot flatten everyone else.
- **Judged parts:** 0–4 on an anchored rubric (every level described concretely), median of the three lenses.
- **Across steps:** every step weighs the same. A part that applies only to some steps is averaged over those.

## 5. Time and phases (owner, Q2: A; Q6: C)

- **Arm working time** = wall-clock of the scored run's turns, minus waits on gates, the PO and the harness (hidden
  tests, restores). Time lost to harness faults is excluded. Scored per hidden test passed, so a fast failure is
  not "fast".
- **Phases, two views, side by side:**
  - **The method's own:** one turn is one phase, labelled from its prompt (`/speckit-plan`, `/kiro-impl`, …).
  - **Common phases**, so arms compare: Understand · Specify · Implement · Test · Rework · Review · Waiting. Each
    tool call in the stream is classified by what it did; the time to the next call goes to its phase. **Rework**
    = changes to code, tests or spec after a failed check or a review finding.
  - The classifier's rules live in one named table (tunable); its first version is hand-checked by the owner on a
    sample, stored as a fixture.
- Phases are reported, not scored separately.

## 6. Judging (owner, Q8: C)

- **Lenses:** each judged part has three lenses with different perspectives (e.g. traceability: maintainer,
  auditor, newcomer). Each scores 0–4 and cites evidence (paths, SHAs, transcript lines).
- **Model:** Opus 5.5, the arms' model, so any self-preference bias is shared by every arm.
- **Anonymised copies (design §8):** arms become Arm A–F in a fixed random order; repo names, tool folder names,
  commit trailers and URLs are scrubbed. The key is kept out of the judges' inputs. Blinding is partial and the
  report says so.
- **Disputed:** lenses differ by 2 or more. The owner reviews every disputed item, every judgement that decides a
  top-two placing, and a random ~10% of the rest. The owner's verdict is stored beside the judges', never instead.
- **Cost:** roughly 6 arms × 7 steps × ~7 parts × 3 lenses ≈ 900 calls. An estimate is given for go-ahead before
  the judge stage runs.

## 7. Gaps in the evidence (owner, Q5)

1. **Hidden tests every arm fails** (at step 4: three step-1 byte-surgical cases — `multi-line -> plain`,
   `null gains a child key`, `scalar -> mapping keeps EOL comment on the key line`). Each is reviewed before
   scoring: a test or contract defect is excluded for every arm and recorded; a genuinely hard test is kept.
2. **Mutation runs that crashed** (ccsdd and control: the arm's own tests pass, `baseline_rc 0`, but mutmut fails
   on their parametrised test IDs, `mutmut_run_rc 1`, 200 of 200 not checked). A harness problem, so try a
   different path: select tests by file rather than node ID, or another mutation runner. Only if every path fails
   is the score unmeasured; then the dimension's other parts are reweighted and the cell is flagged.
3. **Fallback-answered questions** are judged like any other question. Whether the arm recorded its assumption as
   the fallback asked counts under traceability.
4. **Harness faults and re-runs:** only the final valid run is scored; re-runs are listed.
5. **Owner review time:** removed from the score (§2).
6. **Arm violations:** listed, each judged, deducted under setup and ergonomics by severity. An arm-caused fault is
   never a harness fault (existing ruling).
7. **N.a runs:** not scored, reported. Their questions count toward human interaction.

Missing or unreadable evidence is never a zero: it is recorded as `missing` with its path and shown.

## 8. The "your choice" sweep (owner, 2026-10-04)

For each escalated or fallback answer that left a decision out of contract, the route each arm took — not just
the asker's — from its recorded decisions, code and hidden-test results. For discussion, not scored. Includes the
owner's note (2026-10-05): with `TROUPE_ACTOR` unset and no login name, the owner would rather the command fail
than record a null or unknown actor.

## 9. Architecture (owner: B, staged)

Run as `runner score <pass> [--stage S]`. Each stage reads the previous stage's files under
`results/<pass>/scoring/` and is resumable.

| Stage | Reads | Writes | LLM? |
|---|---|---|---|
| **collect** | `results/<pass>/` | `collected/<arm>/<NN>.json`: every measured value with its source path | no, deterministic |
| **anonymise** | arm repos at the scored SHAs, transcripts, question logs | `anon/` copies + `anon-key.json` (kept from judges) | no |
| **judge** | `anon/`, rubrics | `judged/<part>/<arm>/<NN>/<lens>.json`, written as each call finishes | yes |
| **aggregate** | `collected/`, `judged/`, owner verdicts, `weights.toml` | `scores.json` | no, deterministic |
| **report** | `scores.json` | `report.md`, the page | no |

Re-weighting re-runs aggregate and report only, at no cost.

**Inputs written before scoring,** from the scenario files only (step briefs, contract, PO brief), without opening
arm repos, and approved by the owner before steps 6–7's results are in:
- **"What goes stale" list per change step:** the requirements, tests, docs and code areas the change makes wrong,
  and the files the step has legitimate reason to touch. Drives "stale artefacts updated" and "collateral churn".
- **Rubrics:** one per judged part, three lens prompts each, 0–4 anchored.
- **The review of tests every arm fails** (§7.1).

**Disclosure:** these are written after steps 1–5's results were seen, before steps 6–7's, so they are not fully
pre-registered. The report says so.

## 10. Confidence check

Each reported as "does the order change?":
1. **Weights:** each dimension ±5, taken from or given to the others in proportion.
2. **Judges:** each disputed item rescored with each single lens's score instead of the median.
3. **Both together.**

Arms whose order flips under any of these are shown as **within noise** of each other, not ranked. Arms with
unmeasured parts are flagged.

## 11. Report: summary first, detail on demand

| Level | Content |
|---|---|
| 0 Bottom line | ranked arms, weighted totals, confidence, 3–5 key findings, on one screen |
| 1 Scorecard | arms × dimensions, one number per cell, outliers flagged; weight sliders here (page) |
| 2 Dimension detail | a cell's parts, per step |
| 3 Step detail | raw values, time and cost by phase, the three lens verdicts |
| 4 Evidence | links to files, commits, transcript lines |

- **`report.md` + `scores.json`** in the repo are the record: levels 0–2 in the body, 3–4 in a per-arm appendix.
- **The page** is a private artifact generated from the same `scores.json` (so the two cannot disagree): levels
  0–1 visible, the rest expands in place; weight sliders make the confidence check interactive.

## 12. Testing

- Built test-first against the dry-run evidence (dry1 complete, dry2 broken, dry4 edge) and the real steps 1–5.
- collect and aggregate are deterministic: two runs give byte-identical output, enforced by a test.
- Judges are tested with a fake judge; no LLM call in the test suite.
- No test name claims more than its body asserts.

## 13. Order of work

1. **Now, offline, while pass 1 runs:** the stale lists, rubrics and all-fail test review (for owner approval);
   collect, aggregate and report; the alternative mutation path, proven on stored commits; the phase classifier
   and its hand-checked sample.
2. **After pass 1:** full collect; anonymise; judge cost estimate → owner go-ahead → judge; owner review of
   disputed and sampled items; aggregate; report.
3. **Design doc:** amend §8 per §2 above, citing this spec.
