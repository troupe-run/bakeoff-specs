# Go / no-go before pass 1 (plan Task 27)

Prepared 2026-10-01 by Claude with the owner. Each item lists the evidence for it. **The owner signs at the end.**

## Checklist

- [x] **Owner decisions.**
  - OD1–OD25 are all answered (plan, "Owner answers").
  - The spec-change ODs are approved and recorded in `docs/design.md`.
  - OD24 was switched from B to A on 2026-10-01, after probe P11 (design §2, §11).
  - The parameters are set to the answers.
- [x] **Harness texts approved by the owner (2026-10-01).**
  - `po-protocol.md`, `teammate-prompt.md` and `scenario.toml`.
  - `project-principles.md`, expanded and approved the same day (c460d54).
- [x] **Tests are green.**
  - Offline suite: 1814 passed.
  - `-m docker`: 216 passed, 0 failed, at 04c2233.
  - `-m "docker and network"`: 6 passed (2026-10-01).
  - `results/dryrun-validation.md`: **PASS**, all 9 gates.
- [x] **Probe.** `results/probe/probe.md` is reviewed and its corrections are committed (b0c7e04, plus the P11
  correction note).
  - P7 isolation passed: the PO and teammate in safe mode ignore `CLAUDE.md`.
  - P10 passed: no token on disk.
  - All 10 pass-1 tokens can write issues.
- [x] **Canary.** `results/canary/canary.md` shows **PASS**, 27 of 27 (7102238).
- [x] **Images.** These are the tested images, not a rebuild (owner, 2026-10-01).
  - All 11 locked image IDs match `images.lock.json`.
  - 10 are saved to `state/images/*.tar` (`runner images load` restores them).
  - *Deviation from the plan:* the plan's final `--rebuild` was skipped, because it would produce images that the
    dry run and canary never tested.
- [x] **Credentials.** Keychain item `bakeoff-claude-oauth` is present. The owner confirmed the subscription terms
  cover this use.
- [x] **GitHub.**
  - One token per GitHub-tracker arm is stored (pass-1 and discovery).
  - `runner github-verify pass1` passes: every repo is private, has issues on and is empty, and no `troupe-run` repo
    is public. `spike-claude-docker` was made private by the owner on 2026-10-01.
  - *Deviation:* the tokens expire in **60 days**, not the 45 the checklist asks for. The owner accepted this.
- [x] **Secret-scan hook enabled:** `git config core.hooksPath .githooks`.
- [x] **Order recorded:** `results/pass1/order.json`, seed 3124107815. The order is ccsdd → superpowers → speckit →
  speckitty → openspec → control. bmad is parked.
- [x] **The machine is otherwise idle** when pass 1 starts. The owner checks this at the time.

## Open findings from the canary (decide before `run-pass pass1`)

1. **The mutation score can't be measured for arms that test through the CLI.**
   - What happened: control's `test_entry_point` runs `uv run troupe …` from the repo root. Inside mutmut's
     `mutants/` copy that exits 2, so mutmut checks 0 of 200 mutants, the score is null, and the run is recorded as
     crashed.
   - Who it affects: likely most arms, since the contract is a CLI. It puts the 10% code-and-test-quality dimension
     at risk.
   - Options:
     - (a) find out why `uv run` fails inside `mutants/` and fix the harness;
     - (b) leave subprocess tests out of the mutation run;
     - (c) record the mutation score as unmeasurable and re-weight.
   - *Recommendation:* (a) first. The cause is not yet known, and it is a harness problem, not the arm's.
   - **Owner, 2026-10-01: accepted.** Fix it before `run-pass pass1`.
   - **Fixed, 2026-10-01 (8a985df, b3a3375).**
     - The root cause: with `UV_NO_SYNC=1`, uv saw `mutants/` as a separate project, made an empty venv there, and
       the run failed to spawn the CLI with exit 2.
     - The fix: the mutation containers now set `UV_PROJECT_ENVIRONMENT` to the prepared `.venv`.
     - What's left: code reached only through CLI subprocesses is reported as "no tests". It is unmeasured and left
       out of the denominator, because mutmut 3 cannot attribute coverage that runs in a subprocess.
     - A run where every mutant is "no tests" shows as "unmeasured", not crashed.
     - Evidence: a regression Docker test; the Docker suite at b3a3375 passed 217 with 0 failed; the dry run passed.
       Owner option B, putting mutants/src on PYTHONPATH, was tested and breaks the run.
2. **Discovery costs a whole turn for arms without gates.**
   - What happened: control wrote its whole step-1 implementation in one 17-minute turn during N.a, then discarded
     it.
   - Effect: roughly double the cost per step for gate-less arms, and no questions surfaced.
   - *Recommendation:* accept it. Cost is reported, not scored (design §1: quality over cost).
   - **Owner, 2026-10-01: accepted.**

## Sign-off

- [x] Owner: go for `run-pass pass1`; finding 1 is now fixed (above). Ticked by the owner on 2026-10-01.
