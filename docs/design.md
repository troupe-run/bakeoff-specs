# bakeoff-specs — design

Status: **approved by owner 2026-09-28** · 2026-09-28 · owner: Martin (hps.gd)

A bake-off to choose the spec-driven development methodology — and, where it ships one, the work tracking —
that troupe.run will be built with. Judged on how each method copes with **change over time**, not on a
day-one greenfield build.

## 1. Purpose and success criteria

**Outcome:** a recorded, defensible choice of methodology for troupe.run, with the evidence to back it.

**Built to be re-run (decision "c"):** the decision is made now, but the scenario, checklists, hidden tests,
rubric and runner are kept as a harness that can be re-run as the tools change, and that can later become a
troupe performance. We do not build that automation now; we structure the artefacts so it is possible.

**Success means:**
1. Every candidate was set up properly, per its own docs, and that setup was verified before step 1.
2. Every candidate went through the same seven-step evolution, answered by the same product-owner brief,
   against the same hidden acceptance tests.
3. Scores are traceable to recorded evidence for each step.
4. The owner has reviewed every candidate's key gates and every escalation.

**Priority:** quality of conclusion over cost. No cost cap; cost is recorded and reported, not scored.

## 2. Candidates

Research and citations: [`research/CANDIDATES.md`](../research/CANDIDATES.md) (2026-09-28).

| Arm | Tool | Version at research | Work tracking in the arm |
|---|---|---|---|
| openspec | Fission-AI/OpenSpec | v1.13.2 | GitHub Issues (baseline) |
| bmad | bmad-code-org/BMAD-METHOD | v6.12 | BMAD ticketing (preview), GitHub backend |
| speckit | github/spec-kit | v1.0.12 | Spec Kit export to GitHub Issues (the method's own optional, one-way step; not forced, OD24 A — §11) |
| speckitty | spec-kitty/spec-kitty | 3.2.7 (stable, not 4.0 RC) | beads |
| superpowers | obra/superpowers | v6.4.2 | GitHub Issues (baseline) |
| ccsdd | gotalab/cc-sdd | v3.1.0 | GitHub Issues (baseline) |
| control | plain Claude Code, no methodology | — | GitHub Issues (baseline) |

- **GSD dropped (owner, 2026-09-28).** The original `gsd-build/get-shit-done` is archived and described by
  its community fork as compromised or abandoned. The fork is young, and GSD's change model (requirements
  rebuilt per milestone) is weak on the axis that matters most here, so it does not justify the supply-chain risk.
- **Control** tells us whether a methodology adds anything over Claude Code on its own.
- **Tracking** uses what each tool ships with; tools that ship none get GitHub Issues as a common baseline.
  Tracker quality is recorded but scored separately, so a built-in board does not earn double credit.
  A dedicated tracker bake-off (`bakeoff-trackers-*`) is parked until this one concludes.
- **Excluded:** GSD (above), Kiro (not drivable from Claude Code), Tessl spec tile (too thin and stale).
- **bmad is parked (owner, 2026-09-29)** until BMAD 6.13: it keeps its setup checklist but is not run, has no
  repo or PAT, and is left out of the order (`parked = true`, `config.active_arms()`). Six arms run.

Versions are pinned at setup and recorded; an upgrade mid-bake-off is not allowed.

## 3. The subject: a real troupe slice

Every arm builds troupe's **configuration subsystem**. Spike A (`../spike-config-roundtrip/FINDINGS.md`)
showed the slice is feasible and hard in the right ways. Spike A's findings are **not** given to candidates;
the only shared input is the step briefs and the product-owner brief.

### 3.1 Fixed technical constraints (same for every arm)

Python ≥3.12 managed with `uv`; the `eventsourcing` library for the event store and projection; YAML config at
`<theatre>/.troupe/troupe.yml` (or `.yaml`). Library choices beyond that are the arm's to make.

### 3.2 The CLI contract

Hidden tests touch only this contract. Each arm must make it runnable as `uv run troupe config …` from the
repo root, operating on a theatre directory given by `--theatre <dir>` (default: current directory).

The exact contract — arguments, output format, exit codes, error text requirements — is written per step in
`scenario/contract.md` and handed to every arm with the step brief that introduces it. A step's contract
changes only where the scenario says it does (step 3).

## 4. The evolution sequence

Each step is handed to the arm as a user request, in the arm's own workflow. Hidden tests for a step include
every earlier step's still-valid tests, so regressions count.

| # | Step | What it probes |
|---|---|---|
| 1 | **Greenfield.** Load `troupe.yml` with local file includes (YAML embedded as a subtree; other files become a multi-line string); hold config as an event-sourced projection; `config show <path>` prints a setting's value; `config set <path> <value>` updates the projection and writes the change back surgically to the file the value lives in. | Initial spec quality, test design, the surgical write-back bar |
| 2 | **Bidirectional sync.** A file watcher reconciles hand edits into the projection; `set` write-backs must not loop. Includes a **hand edit made outside the method's workflow** (by the harness, directly to code/spec) before the step begins. | Added feature; drift detection |
| 3 | **Contradicting change — command behaviour.** New `config get <path>` prints a value (what `show` did). `config show <path>` now prints a value **or** a YAML subtree. Same subcommand, changed behaviour. | Does the method find and change the old requirement, tests and docs, rather than only adding? |
| 4 | **Cross-cutting: lineage.** Every config event records who made the change (human or agent, which one), via what (CLI or file edit), and when. | Where a cross-cutting concern lands; whether later steps honour it |
| 5 | **Contradicting change — data rule.** New keys under an included subtree now go to the *including* file as an override, not into the included file. Delivered as **two concurrent change requests touching the same requirement**. Override events must carry lineage. | Reversing a data rule; concurrent change handling |
| 6 | **Bug fix.** A reported defect arrives **as an issue in the arm's tracker**: setting a value through a YAML alias silently changes the anchor and every other alias. | Does the fix leave a spec trace? Tracker round trip |
| 7 | **Model change.** Remote `https:` includes, read-only (a set targeting one is refused, naming the local include reference); a JSON Schema for the config decides include-vs-literal-URL (`format: uri` fields are literal; `!literal` tag as an escape hatch). | Late requirement that changes the model; schema as source of truth |

## 5. People in the loop

**Product-owner agent.** Answers every clarifying question and approval request from a fixed brief
(`scenario/po-brief.md`) that the owner approves once before any run. Questions the brief does not cover are
**escalated to the owner**, logged, and the answer is added to the brief so later arms receive the same answer.
**Two runs per step (owner, 2026-09-29; replaces the whole-run two passes of 2026-09-28).** For each step N:
- **N.a (discovery):** each of the six arms, one at a time, starts step N and stops at the first approval
  request or the first edit to code outside its spec and docs paths, whichever comes first. Every escalated
  answer is added to the brief, recording which arm first raised it. The arm repo is then reset to its
  pre-step commit.
- **Consistency check:** before N.b, the answers escalated in N.a are compared with each other (the same or an
  overlapping question must get the same answer), so the same question always gets the same answer. Whether an
  answer is consistent with the brief's own standing text is the owner's call when confirming: the check itself
  compares escalated answers only.
- **N.b (scored):** each arm, one at a time, re-runs step N from the same starting commit, to completion, with
  the brief as it stands after the check. N.b is scored and is what step N+1 builds on.
- **Discovery tracker (owner, 2026-09-30):** a GitHub-tracker arm's N.a works against its own private discovery
  repo, `troupe-run/bakeoff-specs-<arm>-<pass>-disc` (its own `GH_REPO` and PAT, keychain
  `bakeoff-gh-<pass>-disc-<arm>`; the local origin is untouched), so nothing N.a files, comments on or closes
  reaches the tracker N.b starts from. Beads (speckitty) lives in git and is reset with the arm repo.

**Consistent, not identical (owner, 2026-09-29).** Arms get the same answer to the same question, but only
what they ask for: the product owner never volunteers brief content an arm did not ask about. Asking tougher or
more insightful questions is a strength the scoring must be able to see, and handing everyone the same
information would hide it. The question log records which arm first raised each escalation.

N.a is kept as evidence (notably of how each method handles ambiguity) and reported alongside.

Proposed brief defaults to confirm: `config get` on a subtree fails with an error pointing at `config show`;
`config show` renders the merged view (includes resolved), with `--sources` showing which file each value
came from.

**The owner** personally reviews each arm's key approval gates (e.g. spec sign-off, plan sign-off, as the
method defines them) and sees every escalation and every question the log marks significant.

This is not an unattended run: arms go **one at a time**, pausing at the owner's gates.

## 6. Setup and isolation

**One repo per arm**, `troupe/bakeoff-specs-<arm>/`, fresh, with clean history, never containing hidden tests
or harness code. Private during the bake-off (`troupe-run/bakeoff-specs-<arm>-<pass>`, and the N.a discovery repo);
at close-out the arm's history is published to `troupe-run/bakeoff-specs-<arm>`, created **private**; the owner
changes its visibility later (owner, 2026-09-30).

**Isolation per arm:**
- its own `CLAUDE_CONFIG_DIR`, so no plugin, skill, memory or setting from another arm (or from the
  owner's normal config — superpowers is installed there) leaks in;
- `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`;
- the same pinned Claude Code version and the same model for every arm, recorded in the run record;
- tool telemetry disabled where the tool supports it (OpenSpec sends telemetry by default);
- whether every arm runs in a container, for an identical environment, is decided by spike B's findings.

**Setup checklist per arm** (`checklists/<arm>.md`), derived from the tool's own docs in the research file,
e.g. Spec Kit's constitution step, BMAD's `bmad setup`, beads initialisation. Each item is verified by a
script where possible and by the owner where not. **No step 1 until the checklist is green.** Known traps from
research are listed in the relevant checklist (Spec Kit upgrades can overwrite `constitution.md`; beads
schema upgrades from one designated clone only).

## 7. Running and evidence

The runner (in this repo) prepares an arm, hands it each step brief, stands up the product-owner agent,
pauses for owner gates, and after each step runs the hidden tests from outside against the arm's CLI.

Evidence stored per arm per step, in this repo under `results/<pass>/<arm>/<NN>/` (N.b, the scored run), with
the step's N.a discovery run under `results/<pass>/<arm>/<NN>/a/`:
full session transcripts; cost with its unit and source, and wall-clock time; every question asked, who
answered, and whether it was escalated; hidden-test results; mutation score, `mypy --strict` and lint output;
the arm repo's git SHA at the end of the step.

**Watching a run live.** A turn's stream is stored gzipped, which cannot be followed while it is written, so each
turn also writes a plain, line-buffered feed — tool calls with a short argument summary, assistant text (trimmed),
subagent start and stop, retries, tool errors and the result with its outcome and cost — to
`state/<pass>/<arm>/live/NN-<run>-<turn>-<started>.log`, with `live/current.json` naming the running turn.
`runner watch [--pass P] [--arm A]` follows it from a second terminal (read-only: no lock, no writes), switching
to each new turn as it starts. The feed is state, not evidence: it is never committed or scored. It holds model
text and tool inputs, so every line has token shapes and the known credential values redacted before it is
written, and the feeds are secret-scanned with the step's evidence after every run (`secrets.scan_step`, also
`scan_arm`, the setup scan, close-out, and the dry-run report's scan of `state/`).

## 8. Scoring

| Weight | Dimension | Measured by |
|---|---|---|
| 30% | Coping with change | Hidden tests still green after each change step; amount of rework; whether spec, code and tests agree after steps 3 and 5; whether step 2's hand edit was detected |
| 20% | Correctness | Hidden acceptance tests passed per step |
| 15% | Traceability | Requirement → test → code, and change → reason, can be followed |
| 15% | Quality of human interaction | Number and value of questions; whether the arm researched before asking (see below); whether gates fall at sensible points; owner review time |
| 10% | Code and test quality | Mutation score, `mypy --strict`, lint, test names checked against what the tests assert |
| 10% | Setup and ergonomics | Setup effort; fit with Claude Code and with the arm's tracking |

Cost is reported alongside, not scored. Tracker quality is reported separately.

**Research before asking (owner, 2026-09-30).** Within *Quality of human interaction*, each question put to the
product owner is judged on whether the arm first used what it could reach (the repo, the scenario documents,
package docs, and for GitHub-tracker arms their issues) and whether the question arrived as an informed choice
(options, what was found, a recommendation) rather than a bare problem. Judged from the step transcripts and the
question log. The run-phase egress allowlist bounds what an arm can research, and it differs slightly by arm
(GitHub-tracker arms can reach `api.github.com`); the report says so. Weights are unchanged.

**Mutation score and CLI subprocess tests (2026-10-01).** mutmut 3 attributes coverage only to code a test
runs in-process. Code an arm's tests reach only by running its CLI as a subprocess (`uv run troupe …`, as the
CLI contract invites) is reported as "no tests": unmeasured, and left out of the score's denominator (killed ÷
(total − no tests − skipped)), not counted as surviving. The mutation containers set `UV_PROJECT_ENVIRONMENT` to
the copy's prepared `.venv` so that such a subprocess, launched from inside mutmut's `mutants/` working copy,
runs at all; it runs the unmutated install. An arm whose tests are all subprocess-based therefore gets an
unmeasurable (null) mutation score, not a crash and not zero. The report says so.

**Judging:** measured dimensions come from the evidence directly. Judgement dimensions (question quality,
traceability, test naming) are scored by LLM judges working on **anonymised copies** (repo name, tool-specific
folder names and commit trailers scrubbed), then checked by the owner. Blinding is partial — some methods are
recognisable by their artefact shapes — and the report says so.

## 9. Stop rules

- **Harness faults** (our setup error, a wrong brief, a flaky hidden test) are fixed and the step is re-run;
  they never count against an arm. **The same harness fault twice halts the whole bake-off** for review with
  the owner.
- **Resource exhaustion (owner, 2026-09-29):** an arm that exhausts memory, disk or process slots is re-run
  once; a repeat scores that step as all-failed. If two arms exhaust resources at the same step, it is treated
  as a harness fault (the suite, not the framework) and the bake-off halts for review.
- **Arm faults:** if an arm makes no progress on the hidden tests for three attempts at one step, the arm
  stops at that step and that is recorded as its result.
- **Owner stop mid-flight (owner, 2026-10-01):** the owner stopping a run (Ctrl-C in the runner's terminal, e.g.
  after seeing a turn go off the rails in `runner watch`) is a **harness** fault, not an arm fault. The step is
  left `interrupted`; the owner records it with `runner faults declare <pass> <arm> <step> <slug> --scope
  record` (ledgered as `manual:<slug>`; `record` supersedes nothing, so finished work is not re-run); resuming
  moves the interrupted attempt aside and re-runs it from the step's snapshot — except a stop during the scored
  run's tests phase, where the attempt is kept and only the tests resume on the same commit. The arm is not
  penalised. Like every harness fault, the same `manual:<slug>` twice halts the bake-off, and a declared stop
  appears in the step's N.b `harness_faults`, so a canary with one fails its no-harness-fault check: after an
  owner stop, run a fresh canary. A stop during setup (step 0) has no ledger entry (`faults declare` takes steps
  1-7); setup is attended, so the owner reruns the setup.

## 10. Repos and naming

`bakeoff-<topic>[-<arm>]`, so future bake-offs have their own namespace:
- `bakeoff-specs` — this harness: `docs/`, `research/`, `scenario/` (step briefs, contract, PO brief),
  `tests/hidden/`, `checklists/`, `runner/`, `results/`.
- `bakeoff-specs-<arm>` — one per arm, created private at close-out; the owner sets its visibility later.
- `bakeoff-specs-<arm>-<pass>` and `bakeoff-specs-<arm>-<pass>-disc` — the private per-pass repo and the N.a
  discovery tracker used during the bake-off.

All private during the bake-off (owner, 2026-09-30).

## 11. Open items

1. ~~GitHub org~~ — decided: repos under `troupe-run` (issue types Task/Bug/Feature are enabled there), private
   during the bake-off; published at close-out to `troupe-run/bakeoff-specs-<arm>`, created private, with the owner
   adjusting visibility later (owner, 2026-09-30).
2. ~~Containers for every arm~~ — decided: **yes**, every arm runs in the spike B container stage
   (see `../spike-claude-docker/FINDINGS.md`), with its own `CLAUDE_CONFIG_DIR` mounted in and the
   credential supplied the same way for every arm.

Decided 2026-09-30 (owner, OD24 A, after probe P11): the runner does not force Spec Kit's `/speckit-taskstoissues`
export. In 1.0.12 the skill needs the GitHub MCP server and refuses unless `remote.origin.url` is a GitHub URL (arm
origins are local bare repos). The export is one-way (tasks.md to issues; its only read is a dedup check, and no other
Spec Kit skill reads GitHub issues), so forcing it would add an arm-only MCP server and a remote workaround just to
fill a tracker column that is reported, not scored. The method may still choose the export itself; without MCP it
cannot create issues, and the transcript will show that.

Decided 2026-09-28: step 1 is held to the **byte-surgical** bar spike A achieved (only the changed value's bytes
differ), with files containing a tab before an end-of-line comment and multi-document files out of contract.
Every arm uses **Claude Opus 5.5** (`claude-opus-5-5`) and Claude Code **2.1.281**; a re-run of the top two arms
and the control on a second model may follow once there is a winner. The model is passed explicitly
(`--model`); an unpinned run was observed to default to a different model. **Pinning is verified, not
assumed:** the runner checks the `model` field of every assistant message in every transcript, including
subagents'; any model other than the pinned one is a harness fault and the step is re-run.

Decided 2026-09-28, step 1 write-back rules (go into `scenario/contract.md`):
- a changed paragraph of a folded (`>`) value is re-wrapped to the paragraph's previous width;
- a write that would add an indented line to a folded value is refused (folded style cannot represent it);
- new keys copy their neighbours' quoting (e.g. `"temperature": 0.2` in a JSON-style file);
- a list item appended to a list that ends with a comment goes **below** the comment;
- when a value's length changes, only that line's end-of-line comment is re-aligned to its old column, or
  one space where the column cannot be kept; other lines are untouched;
- **anchors and aliases** are out of step 1's contract, so step 6's bug is real; the owner's alias rule
  (refuse through an alias; expand only on confirmation; never write merge keys) is step 6's expected fix.
