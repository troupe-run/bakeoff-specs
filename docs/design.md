# bakeoff-specs — design

Status: **draft for owner review** · 2026-09-28 · owner: Martin (hps.gd)

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
| speckit | github/spec-kit | v1.0.12 | Spec Kit export to GitHub Issues |
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
Because the brief grows, arms that ran earlier are re-checked against any answer added later that would have
changed what they were told; the log records which arm first raised each question.

Proposed brief defaults to confirm: `config get` on a subtree fails with an error pointing at `config show`;
`config show` renders the merged view (includes resolved), with `--sources` showing which file each value
came from.

**The owner** personally reviews each arm's key approval gates (e.g. spec sign-off, plan sign-off, as the
method defines them) and sees every escalation and every question the log marks significant.

This is not an unattended run: arms go **one at a time**, pausing at the owner's gates.

## 6. Setup and isolation

**One repo per arm**, `troupe/bakeoff-specs-<arm>/`, fresh, with clean history, never containing hidden tests
or harness code. Pushed public to GitHub when complete.

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

Evidence stored per arm per step, in this repo under `results/<arm>/<step>/`:
full session transcripts; cost with its unit and source, and wall-clock time; every question asked, who
answered, and whether it was escalated; hidden-test results; mutation score, `mypy --strict` and lint output;
the arm repo's git SHA at the end of the step.

## 8. Scoring

| Weight | Dimension | Measured by |
|---|---|---|
| 30% | Coping with change | Hidden tests still green after each change step; amount of rework; whether spec, code and tests agree after steps 3 and 5; whether step 2's hand edit was detected |
| 20% | Correctness | Hidden acceptance tests passed per step |
| 15% | Traceability | Requirement → test → code, and change → reason, can be followed |
| 15% | Quality of human interaction | Number and value of questions; whether gates fall at sensible points; owner review time |
| 10% | Code and test quality | Mutation score, `mypy --strict`, lint, test names checked against what the tests assert |
| 10% | Setup and ergonomics | Setup effort; fit with Claude Code and with the arm's tracking |

Cost is reported alongside, not scored. Tracker quality is reported separately.

**Judging:** measured dimensions come from the evidence directly. Judgement dimensions (question quality,
traceability, test naming) are scored by LLM judges working on **anonymised copies** (repo name, tool-specific
folder names and commit trailers scrubbed), then checked by the owner. Blinding is partial — some methods are
recognisable by their artefact shapes — and the report says so.

## 9. Stop rules

- **Harness faults** (our setup error, a wrong brief, a flaky hidden test) are fixed and the step is re-run;
  they never count against an arm. **The same harness fault twice halts the whole bake-off** for review with
  the owner.
- **Arm faults:** if an arm makes no progress on the hidden tests for three attempts at one step, the arm
  stops at that step and that is recorded as its result.

## 10. Repos and naming

`bakeoff-<topic>[-<arm>]`, so future bake-offs have their own namespace:
- `bakeoff-specs` — this harness: `docs/`, `research/`, `scenario/` (step briefs, contract, PO brief),
  `tests/hidden/`, `checklists/`, `runner/`, `results/`.
- `bakeoff-specs-<arm>` — one per arm.

All public.

## 11. Open items

1. ~~GitHub org~~ — decided: public repos under `troupe-run` (issue types Task/Bug/Feature are enabled there).
2. **Containers for every arm?** Decided on spike B's findings (Claude Code in Docker, including sign-in).

Decided 2026-09-28: step 1 is held to the **byte-surgical** bar spike A achieved (only the changed value's bytes
differ), with files containing a tab before an end-of-line comment and multi-document files out of contract.
Every arm uses **Claude Opus 5.5** (`claude-opus-5-5`) and Claude Code **2.1.281**; a re-run of the top two arms
and the control on a second model may follow once there is a winner. The model is passed explicitly
(`--model`); an unpinned run was observed to default to a different model.

Decided 2026-09-28, step 1 write-back rules (go into `scenario/contract.md`):
- a changed paragraph of a folded (`>`) value is re-wrapped to the paragraph's previous width;
- a write that would add an indented line to a folded value is refused (folded style cannot represent it);
- new keys copy their neighbours' quoting (e.g. `"temperature": 0.2` in a JSON-style file);
- a list item appended to a list that ends with a comment goes **below** the comment;
- when a value's length changes, only that line's end-of-line comment is re-aligned to its old column, or
  one space where the column cannot be kept; other lines are untouched;
- **anchors and aliases:** setting the anchor's own path changes every alias (expected). Setting a path
  reached through an alias is **refused by default**; on explicit user confirmation (it is not surgical) the
  alias is expanded into a local copy, with a comment saying why, and the value overridden. Merge keys
  (`<<`) are not used or introduced.
