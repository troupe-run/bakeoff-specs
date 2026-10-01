# Bake-off candidates: spec-driven methodologies and work trackers

Research date: 2026-09-28. Stats pulled from the GitHub API (`gh api repos/...`) on that date unless noted.
Anything not confirmed against a primary source is marked [UNVERIFIED].

## Part 1 — Spec/methodology tools

### 1.1 superpowers (obra/superpowers)

**What it is.** "A complete software development methodology for your coding agents, built on top of a set of composable skills and some initial instructions that make sure your agent uses them." Built by Jesse Vincent / Prime Radiant. Skills auto-trigger; there are no slash-command stages to run by hand. <https://github.com/obra/superpowers#readme>

**Maturity.** 292,339 stars, MIT, 270 open issues, last push 2026-09-27. Latest release **v6.4.2 (2026-09-25)**. Cadence: v6.0.0 2026-06-16, v6.1.0 06-30, v6.2.0 07-24, v6.3.0 08-12, v6.4.1 09-19, v6.4.2 09-25, so roughly a minor release a month. Very active maintainer; issues are triaged by an agent posting from @obra's account with Jesse's sign-off. <https://api.github.com/repos/obra/superpowers>, <https://github.com/obra/superpowers/releases>, <https://github.com/obra/superpowers/issues/2249>

**Install/bootstrap (Claude Code), exactly as documented.** <https://github.com/obra/superpowers#claude-code>
1. Official marketplace: `/plugin install superpowers@claude-plugins-official`
   - or: `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers@superpowers-marketplace`
2. No init command, no constitution, no required config. A SessionStart hook injects the `using-superpowers` bootstrap.
3. Documented smoke test (in the Muse section, but it applies to any harness): start a fresh session and send `Let's make a react todo list`. A working install auto-triggers `brainstorming` before any code is written.
4. Optional: spec location can be changed by user preference ("User preferences for spec location override this default"). <https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md>

**Artefacts.**
- Design/spec: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, committed. (brainstorming SKILL.md)
- Plan: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`, made of 2-5 minute tasks with exact paths, code and verification steps. <https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md>
- A git worktree and branch for each piece of work. Everything else lives in code and tests.

**Workflow stages.** brainstorming → using-git-worktrees → writing-plans → subagent-driven-development or executing-plans → test-driven-development (throughout) → requesting-code-review (between tasks) → finishing-a-development-branch. The README says: "Mandatory workflows, not suggestions." Brainstorming sorts each request onto one of three paths. **Spike** gets no spec. **Bounded** (a change to existing code) gets a short design in chat, and "No spec file, no implementation plan document". **Architectural** gets the full spec and plan. There is a HARD-GATE: nothing is implemented before the human approves each stage. (README; brainstorming SKILL.md)

**Change handling (key axis): weak.**
- Specs are dated, point-in-time design docs. There is no living/canonical spec, no delta format and no drift detection.
- A change to existing code usually takes the *bounded* path, which by design writes no spec file. So requirement changes leave no durable spec trail unless they are big enough to count as "architectural". In that case a *new* dated spec is written and the old one is not updated. (brainstorming SKILL.md)
- Open issue #921, "Iteration skill for post-execution plan refinement", asks for a structured way to iterate after an execution cycle. A user request for spec-drift support (#2249) was closed as a duplicate of #921, which is still open. #1075 reports that "Plans and specs have no completion status after execution"; the maintainer is testing ticking checkboxes (draft #2395). #2332: there is no durable QA/acceptance artefact layer. <https://github.com/obra/superpowers/issues/921>, <https://github.com/obra/superpowers/issues/2249>, <https://github.com/obra/superpowers/issues/1075>, <https://github.com/obra/superpowers/issues/2332>
- A third-party plugin, `quziyan/spec-drift-mngr`, adds reconciliation gates around superpowers. <https://github.com/quziyan/spec-drift-mngr> (from a comment on #2249)

**Claude Code integration.** Native, and the first-class target: it is in the official plugin marketplace, uses a SessionStart hook, and uses subagents for SDD and review. Also supports around 15 other harnesses. (README)

**Task/issue tracking.** None built in. Plans are markdown checklists. The session TodoWrite/task tools are used when available (#2183 "handle unavailable task tracking"). An earlier community request to integrate Beads (#611) was closed. <https://github.com/obra/superpowers/issues/2183>, <https://github.com/obra/superpowers/issues/611>

**Known weaknesses.** Spec drift and iteration as above. Plans don't record completion. Brainstorming has no design-doc template (#2378). Subagent-driven development misses product-level gaps (#766). Reviewer subagents are verbose and expensive in tokens (#1930). Contributions of new skills are generally not accepted (README). <https://github.com/obra/superpowers/issues/2378>, <https://github.com/obra/superpowers/issues/766>, <https://github.com/obra/superpowers/issues/1930>

### 1.2 GitHub Spec Kit (github/spec-kit)

**What it is.** "An open source toolkit that gives AI coding agents structured processes, reusable templates, and documented outcomes." It is a Python CLI (`specify`) that installs agent skills and templates. It ships three processes that you can enter independently: SDD (core), bug fixing (extension) and idea assessment (extension). <https://github.com/github/spec-kit#readme>

**Maturity.** 139,217 stars, MIT, 282 open issues, last push 2026-09-25. Latest release **v1.0.12 (2026-09-25)**. It reached 1.0 in August 2026 and has shipped 12 patch releases in about 5 weeks (v1.0.1 2026-08-21 … v1.0.12 2026-09-25), with 100+ releases in total. <https://github.com/github/spec-kit/releases>

**Install/bootstrap, exactly as documented.** <https://github.com/github/spec-kit#get-started>, <https://github.github.io/spec-kit/reference/integrations.html>
1. Prerequisites: Python 3.11+, `uv`, a supported agent.
2. `uv tool install specify-cli`
3. Greenfield: `specify init <project> --integration claude`. Claude Code's integration key is `claude`, and it is "Skills-based; installs skills in `.claude/skills`".
   Existing repo: commit, create an adoption branch, then `specify init --here --force --integration claude`. `--force` "may overwrite files at conflicting managed paths". <https://github.github.io/spec-kit/guides/existing-projects.html>
4. Optional: `specify extension add git` gives numbered feature branches. It is opt-in; features are tracked through `.specify/feature.json`, not by branch. `specify extension add bug` and `specify extension add assess` add the other processes. <https://github.github.io/spec-kit/quickstart.html>
5. In the agent: `/speckit-constitution <principles>`, which writes `.specify/memory/constitution.md`.
6. Upgrading: re-run `specify init --here --force --integration <key>`, but **back up `.specify/memory/constitution.md` and any customised templates first** because they can be overwritten. <https://github.github.io/spec-kit/guides/evolving-specs.html>
- Naming note: the README and quickstart use `/speckit-<cmd>` (skills mode), while the command reference page still writes `/speckit.<cmd>`. In Claude Code (skills mode), use the hyphen form.

**Artefacts.** `specs/NNN-<slug>/` containing `spec.md`, `checklists/requirements.md`, `plan.md`, `tasks.md` and custom `checklists/*`. The repo-level `specs/` dir is set in `scripts/bash/create-new-feature.sh`: `SPECS_DIR="$REPO_ROOT/specs"`, `FEATURE_DIR="$SPECS_DIR/$BRANCH_NAME"`. The constitution is at `.specify/memory/constitution.md`. Bug reports go under `.specify/bugs/<slug>/` and assessments under `.specify/assessments/<slug>/`. <https://github.github.io/spec-kit/reference/agentic-sdd.html>, <https://github.com/github/spec-kit/blob/main/scripts/bash/create-new-feature.sh>

**Workflow stages.** constitution (once) → specify → clarify (optional) → plan → checklist (optional) → tasks → analyze (optional, read-only) → implement → **converge**. Repeat implement → converge "until convergence reports Converged"; converge appends missing tasks to `tasks.md`. `/speckit-taskstoissues` optionally turns tasks into GitHub issues. Bug flow: `/speckit-bug-assess` → `/speckit-bug-fix` → `/speckit-bug-test`, with verdicts verified/partial/failed. (agentic-sdd reference; README)

**Change handling (key axis): documented, but left to the team.** The "Evolving specs" guide names three models and leaves the choice to you: <https://github.github.io/spec-kit/guides/evolving-specs.html>
- **Flow-forward**: each substantial change gets a new `specs/NNN-*` directory, and old ones stay as an audit trail.
- **Living spec**: `spec.md` is the authoritative contract. Revise it first (manually or with `/speckit-clarify`), then regenerate `plan.md` and `tasks.md`.
- **Flow-back**: edit at any level, then realign the artefacts and run `/speckit-analyze`.
- There is no delta/merge mechanism and no project-wide canonical spec. Specs are per feature, so a later feature silently makes an earlier one stale. Issue #620, "How to keep specs consistent and up-to-date with spec-kit?", is still open (example: feature 009 2FA outdates feature 001 login). Issue #1100, "Module-Level Persistent Specifications", is also open. <https://github.com/github/spec-kit/issues/620>, <https://github.com/github/spec-kit/issues/1100>
- Brownfield: `init` "does not rewrite your application or infer specifications for existing behavior". (existing-projects guide)

**Claude Code integration.** A first-class integration key (`claude`) that installs skills into `.claude/skills`. It supports many other agents as well. There is no Claude Code plugin/marketplace package; it is installed per project by the CLI. (integrations reference)

**Task/issue tracking.** `tasks.md` inside the repo, plus `/speckit-taskstoissues`, which pushes tasks to GitHub Issues one way. There are extensions and presets for customisation, and a community catalogue. <https://github.github.io/spec-kit/community/overview.html> [UNVERIFIED whether a community extension syncs with beads or Backlog.md]

**Known weaknesses.** #75, "SpecKit creates the illusion of work, generating a bunch of text" (closed, 26 comments): over-engineering and ignoring existing structure on incremental work. Per-feature spec staleness (#620). Upgrades overwrite customisations (#1210, "Update procedure for already Specify Init-ed repositories"). Single active feature state in `.specify/feature.json` makes parallel features awkward. <https://github.com/github/spec-kit/issues/75>, <https://github.com/github/spec-kit/issues/1210>

### 1.3 OpenSpec (Fission-AI/OpenSpec)

**What it is.** "Spec-driven development (SDD) for AI coding assistants", distributed as a Node CLI (`openspec`) plus generated agent skills and commands. Its stated philosophy is "fluid not rigid … built for brownfield not just greenfield". <https://github.com/Fission-AI/OpenSpec#readme>

**Maturity.** 70,548 stars, MIT, 228 open issues, last push 2026-09-28. Latest release **v1.13.2 (2026-09-23)**. Cadence is about weekly minors: v1.6.0 07-10, v1.7.0 07-29, v1.8.0 08-05, v1.9.0 08-13, v1.10.0 08-19, v1.11.0 08-26, v1.12.0 09-03, v1.13.0 09-09. It collects anonymous telemetry by default; opt out with `openspec config set telemetry.enabled false` or `OPENSPEC_TELEMETRY=0`. <https://github.com/Fission-AI/OpenSpec/releases>, README "Telemetry"

**Install/bootstrap, exactly as documented.** <https://github.com/Fission-AI/OpenSpec#quick-start>, <https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md>
1. Requires Node.js ≥ 20.19.0.
2. `npm install -g @fission-ai/openspec@latest` (or `brew install openspec`)
3. `cd your-project && openspec init`. Non-interactive: `openspec init --tools claude`. The default profile is `core`, with delivery `both` and workflows `propose, explore, apply, update, sync, archive`.
4. Optional expanded workflow: `openspec config profile` (select `new`, `continue`, `ff`, `verify`, `bulk-archive`, `onboard`), then `openspec update`.
5. Optional project context goes in `openspec/config.yaml` (the `context` field; `--language` for new configs). There is no constitution step.
6. After each upgrade: `openspec update` in each project.
7. Claude Code files: `.claude/skills/openspec-*/SKILL.md` and `.claude/commands/opsx/<id>.md`, invoked as `/opsx:<id>`. <https://github.com/Fission-AI/OpenSpec/blob/main/docs/supported-tools.md>

**Artefacts.** <https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md>
```
openspec/
├── specs/<domain>/spec.md                       # source of truth: current behaviour
├── changes/<change>/{proposal,design,tasks}.md
│   └── specs/<domain>/spec.md                   # DELTA specs
├── changes/archive/YYYY-MM-DD-<change>/         # after archive
└── config.yaml
```
Requirements are written as `### Requirement:` headings using SHALL, with `#### Scenario:` WHEN/THEN. (README)

**Workflow stages.** Core: `/opsx:explore` (optional) → `/opsx:propose` → `/opsx:apply` → `/opsx:archive`, plus `/opsx:update` (revise planning artefacts coherently; "never edits code") and `/opsx:sync` (merge deltas without archiving). Expanded: `/opsx:new` → `/opsx:ff` or `/opsx:continue` → `/opsx:apply` → `/opsx:verify` → `/opsx:archive`. "There is no locked 'planning phase,' no approval gate." <https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md>, <https://github.com/Fission-AI/OpenSpec/blob/main/docs/editing-changes.md>

**Change handling (key axis): the strongest model in the field.** <https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md>
- There are two trees: `specs/` holds current truth, and `changes/` holds proposals. Each change carries **delta specs** with `## ADDED`, `## MODIFIED`, `## REMOVED Requirements` (and `## Purpose` for new capabilities). On archive, ADDED is appended, MODIFIED replaces the existing requirement, and REMOVED deletes it (the capability is retired with `retire_capabilities: true`).
- `openspec validate` checks "a change's MODIFIED requirements against the main specs they would replace", so a contradicting requirement change is an explicit, validated operation. <https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md>
- Parallel changes: "Two changes can touch the same spec file without conflicting, as long as they modify different requirements." If both change the *same* requirement, the docs don't describe the conflict behaviour. [UNVERIFIED — needs a scenario step]
- Drift: `/opsx:verify` reports completeness, correctness and coherence between the artefacts and the code. The editing guide covers reconciling hand edits in both directions ("The spec should match reality before you archive"). There is still an open proposal (#880) for `/opsx:validate` to check code against the *living* specs, so drift checking against archived truth is not built in. <https://github.com/Fission-AI/OpenSpec/issues/880>
- Brownfield: specs accumulate one change at a time, with no need to document the whole codebase first. Reverse-engineering specs from code is an open request (#724). <https://github.com/Fission-AI/OpenSpec/blob/main/docs/existing-projects.md>, <https://github.com/Fission-AI/OpenSpec/issues/724>
- Multi-repo: **Stores** (beta) keep planning in a separate repo shared by git across code repos (`openspec store setup|register|…`). (README; cli.md)

**Claude Code integration.** A first-class `--tools claude` option that generates skills and namespaced slash commands. It is not a Claude Code plugin; files are generated per project and refreshed with `openspec update`. A request to ship OpenSpec as a superpowers skill pack (#780) is the top-voted open issue (50 reactions). <https://github.com/Fission-AI/OpenSpec/issues/780>

**Task/issue tracking.** `tasks.md` checklists. Several CLI commands take `--json` for agents (`list`, `show`, `validate`, `status`, `instructions`). Custom schemas let a community "spec-driven-with-beads" schema route tasks to beads (#1232, open docs PR). A Beads integration feature request (#245) was closed. There is no built-in GitHub Issues sync. <https://github.com/Fission-AI/OpenSpec/issues/1232>, <https://github.com/Fission-AI/OpenSpec/issues/245>

**Known weaknesses.** The `openspec/` directory path is not configurable (#697, 29 reactions; #664). Multi-repo/microservices is only partly covered by beta Stores (#725). There is no code-first reverse engineering (#724) and no TDD/test-generation step (#900). Lighter gates mean less enforced rigour; for example, human approval is not a hard gate. <https://github.com/Fission-AI/OpenSpec/issues/697>, <https://github.com/Fission-AI/OpenSpec/issues/725>, <https://github.com/Fission-AI/OpenSpec/issues/900>

### 1.4 Spec Kitty (spec-kitty/spec-kitty, formerly Priivacy-ai/spec-kitty)

**What it is.** "Spec-driven development for AI coding agents, multi-agent workflows, and governed software factories." It is a Python CLI and runtime that began as a Spec Kit derivative. It adds repo-native mission state, work-package (WP) lanes, git-worktree isolation, a local kanban dashboard, governance/charter, review/accept/merge gates and retrospectives. The repo has moved from `Priivacy-ai/spec-kitty` to `spec-kitty/spec-kitty` (the GitHub API redirects). <https://github.com/spec-kitty/spec-kitty#readme>

**Maturity.** 1,647 stars, MIT, **861 open issues**, last push 2026-09-28. Latest stable release **v3.2.7 (2026-09-09)**. The 4.x line is in release candidates (v4.0.0rc1 2026-09-13 → rc4 2026-09-21); `main` carries 4.x and "stable launch acceptance remains pending". Release churn is very high: 45 RCs before 3.2.0 and a changelog of about 10k lines. <https://github.com/spec-kitty/spec-kitty/releases>, <https://github.com/spec-kitty/spec-kitty/blob/main/docs/changelog/CHANGELOG.md>

**Install/bootstrap, exactly as documented.** <https://github.com/spec-kitty/spec-kitty#quick-start>
1. `pipx install spec-kitty-cli` (preferred), or `uv tool install spec-kitty-cli`, or `python -m pip install spec-kitty-cli`. Python 3.11+.
2. `spec-kitty init my-project --ai claude` (existing repo: `spec-kitty init . --ai claude`)
3. `spec-kitty verify-setup`
4. In the agent: `/spec-kitty.charter` (the governance doc; this was renamed from `constitution` and the old command "no longer exists"). <https://github.com/spec-kitty/spec-kitty/blob/main/docs/architecture/mission-system.md>
5. Optional configuration: `.kittify/config.yaml` (e.g. `#retrospective`). Optional dashboard: `spec-kitty dashboard`.
6. After a CLI upgrade: `spec-kitty upgrade`.

**Artefacts.** `kitty-specs/<NNN-mission-slug>/` holds `meta.json`, `spec.md`, `plan.md`, `tasks.md`, `tasks/WP01.md…`, `wps.yaml` and `retrospective.yaml`. Worktrees live in `.worktrees/<mission>-lane-x/` and config in `.kittify/`. (mission-system.md; README)

**Workflow stages.** charter → specify → plan → tasks (or tasks-outline → tasks-packages → tasks-finalize) → `spec-kitty next --agent claude --mission <slug>` loop (implement → review per WP) → accept → consolidate/merge (`/spec-kitty.merge --push`) → `/spec-kitty-mission-review` and retrospective. WP lanes: `planned`, `in_progress`, `for_review`, `approved`, `done`. Mission types: software-dev, research, planning, documentation. <https://github.com/spec-kitty/spec-kitty/blob/main/docs/api/slash-commands.md>

**Change handling (key axis): per-mission like Spec Kit, with no delta model.** Each mission is its own spec folder. Neither the docs nor the slash-command reference describe a living spec or a delta/merge mechanism. The SDD architecture doc lists "Requirements drift as understanding evolves" as a problem, but I found no dedicated amend/change command. There is a "living glossary" (ADR 2026-02-23) for terminology, and `/spec-kitty-mission-review` "confirms spec→code fidelity" after merge. The absence of a delta model is [UNVERIFIED], since I did not read every doc page; the bake-off should exercise it with a scenario. <https://github.com/spec-kitty/spec-kitty/blob/main/docs/architecture/spec-driven-development.md>, <https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/2.x/2026-02-23-2-living-glossary-context-and-curation-model.md>

**Claude Code integration.** `--ai claude` installs slash commands (`/spec-kitty.<name>`) and skills. `spec-kitty next --agent claude` drives the loop. An open request asks for a Claude Code statusline (#1185). <https://github.com/spec-kitty/spec-kitty/issues/1185>

**Task/issue tracking.** It has the most tracker integration of any candidate:
- A built-in WP kanban (lanes) plus a local dashboard.
- A `spec-kitty tracker` command group. Local providers **`beads`/`fp`** require a recorded egress decision since 3.2.6rc1. Hosted providers (Jira, Linear, GitHub, GitLab) run through the SaaS path: `spec-kitty mission create --from-ticket linear:PRI-42`.
- An epic "3.3.0 Beads-backed Spec Kitty state backend" (#1168) is closed as *completed*, but no 3.3.0 release exists; it may have been folded into 4.x [UNVERIFIED].
- GitHub Issues as a tracker provider: SaaS-only. In spec-kitty 3.2.7, GitHub (with Linear, Jira and GitLab) is a SaaS tracker provider — `SAAS_PROVIDERS = {"linear","jira","github","gitlab"}` in `specify_cli/tracker/config.py:21`, handled by `saas_service.py`; the local providers are `beads` and `fp` (checked in the `bakeoff-arm-speckitty:1` image, 2026-10-01). The owner kept beads for speckitty (2026-10-01): a native local tracker, no third-party service in the loop.
<https://github.com/spec-kitty/spec-kitty/blob/main/docs/api/cli-commands.md>, <https://github.com/spec-kitty/spec-kitty/issues/1168>, CHANGELOG lines on `beads`/`fp` egress

**Known weaknesses.** It is heavy and fast-moving: 861 open issues and breaking renames across minor versions (`--feature` removed, `constitution` became `charter`). Its own issues report silent-failure bugs, e.g. #4891 "accept silently skips the entire acceptance-matrix gate when lanes.json is absent", #4889 "implement WP## silently re-cuts a deleted lane branch". Hosted features are coupled to their SaaS (`SPEC_KITTY_ENABLE_SAAS_SYNC`). The README says it is "probably overkill for one-off edits". <https://github.com/spec-kitty/spec-kitty/issues/4891>, <https://github.com/spec-kitty/spec-kitty/issues/4889>, <https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/2.x/2026-02-27-1-cli-tracker-surface-gated-by-saas-sync-flag.md>

### 1.5 BMAD-METHOD (bmad-code-org/BMAD-METHOD)

**What it is.** "Agile AI Driven Development — turn an idea or change request into working software without giving up the thinking." It is a skills-based method with persona agents (analyst, PM, architect, UX, dev) and a process that sizes itself to the work: trivial / one session / epic-sized / project-sized. Since the "all-is-skills" refactor (#1834) it is delivered purely as agent skills. <https://github.com/bmad-code-org/BMAD-METHOD#readme>, <https://docs.bmad-method.org/plan/choose-a-planning-path/>

**Maturity.** 53,582 stars, 54 open issues (well triaged), last push 2026-09-28. The licence shows as NOASSERTION on GitHub; the README says MIT, and "BMad" is a trademark of BMad Code, LLC. Latest release **v6.12.0 (2026-09-04)**. Cadence is roughly monthly: v6.8.0 05-25, v6.9.0 06-22, v6.10.0 07-03, v6.11.0 08-10, v6.12.0 09-04. The architecture changes substantially between minors (a new ticketing preview landed 2026-09-18, PR #2884). <https://github.com/bmad-code-org/BMAD-METHOD/releases>, <https://github.com/bmad-code-org/BMAD-METHOD/pull/2884>

**Install/bootstrap, exactly as documented.** <https://github.com/bmad-code-org/BMAD-METHOD#start-building>, <https://docs.bmad-method.org/start/build-your-first-change/>
1. Prerequisites: macOS or Linux, Node.js 20.12+, Python 3, `uv`, Git.
2. Pick one route:
   - Claude Code plugin: `/plugin marketplace add bmad-code-org/bmad-plugins`, then install the plugins **`bmad-method`** (delivery workflows) and **`bmad-core-tools`** (standalone skills, including the `bmad` hub).
   - Skills CLI: `npx skills add bmad-code-org/BMAD-METHOD`, selecting `bmad`, `bmod-method`, `bmod-core-tools`. By name: `npx skills add bmad-code-org/BMAD-METHOD --skill bmad --skill bmod-core-tools --skill bmod-method --skill bmad-build`.
3. In the agent, "ask the `bmad` skill to run `bmad setup`". This creates `_bmad/` (config and scripts) and the output folder `_bmad-output/` by default. Skills refuse to run until setup has happened (bmad-correct-course SKILL.md Step 4).
4. Optional: `bmad-project-context` writes agent instructions into `AGENTS.md` (skip it if the repo already maintains CLAUDE.md/AGENTS.md). <https://docs.bmad-method.org/existing-codebases/start-in-an-existing-codebase/>
5. Optional: configure ticketing at first use of `bmad-preview-ticketing`. This writes `_bmad/custom/ticketing-store-config.toml` from a starter (see tracking below).
6. Updates: `npx skills update` or the marketplace, then `bmad setup` again. `bmad status` shows versions and what to run next.
7. Customisation: `_bmad/custom/<skill>.toml` for the team and `<skill>.user.toml` for personal overrides. <https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-correct-course/SKILL.md>

**Artefacts.** Documents go in `<type>-<slug>/` folders inside the active *initiative* folder, or directly in `_bmad-output/`: `brief-<slug>.md`, `prfaq-<slug>.md`, `prd-<slug>.md` + `addendum.md` + `.memlog.md` (an append-only decision log), `ux-<slug>.md`/`DESIGN.md`/`EXPERIENCE.md`, `spec-<slug>.md`, `architecture-<slug>.md`, and ticket trees (`tickets.toml` for each container, plus `<type>-<slug>.md` leaves and `-plan.md` files). (choose-a-planning-path)

**Workflow stages.** These depend on the path. Trivial: change → edit → verify. One session: `bmad-build`. Epic: `bmad-spec` → `bmad-ticket`/`bmad-preview-ticketing` stories → `bmad-build` for each story (or `bmad-build-auto`; the BMad Loop module builds a whole epic unattended) → integrate → `bmad-retrospective`. Project: brief/PRD/UX/architecture → epics → as for an epic. Review happens through `bmad-code-review`/`bmad-review`. Multi-agent discussion happens through `bmad-party-mode`. (choose-a-planning-path; skills list in <https://github.com/bmad-code-org/BMAD-METHOD/tree/main/skills>)

**Change handling (key axis): explicit, document-level, no delta format.**
- `bmad-correct-course`: "Assess the impact of a significant change during sprint execution across the PRD, epics, architecture, and UX documents, and produce a sprint change proposal." A contradicting requirement becomes a first-class *Sprint Change Proposal* artefact. <https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-correct-course/SKILL.md>
- `bmad-prd` has an **Update** intent: "Reconcile the PRD with a change signal … Surface conflicts with prior decisions before applying". It works against the `.memlog.md` decision log and reverse-engineers one if it is missing. It also has a **Validate** intent. <https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-prd/SKILL.md>
- In ticketing, each container ticket "is the spec at its altitude" with stable requirement ids, and children reference them. (bmad-preview-ticketing SKILL.md)
- Brownfield: "treats existing codebases as the primary knowledge source". There is no automated spec↔code drift check. (existing-codebase guide)

**Claude Code integration.** A Claude Code plugin marketplace (`bmad-code-org/bmad-plugins`) or the `npx skills` CLI. Skills shell out to `uv run _bmad/scripts/*.py`. <https://github.com/bmad-code-org/bmad-plugins>

**Task/issue tracking.** Built-in, and the richest mapping to external trackers. `bmad-preview-ticketing` is a ticket tree (initiative → epic → story/spike/bug) with prerequisites (`after`) and states planned/backlog/in-progress/review/done/dropped. Its store starters are `repo` (git files; the default), `gh`, `jira`, `linear`, `notion`, `trello`. "A tracker, when configured, is a remote: `write` pushes a ticket to it, `query` reads it back." It is labelled **preview**. No beads integration was found (0 issue hits). <https://github.com/bmad-code-org/BMAD-METHOD/tree/main/skills/bmad-preview-ticketing/config>, <https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-preview-ticketing/references/store-setup.md>

**Known weaknesses.** Heavyweight and persona-heavy. Fast-moving internals (workflow.xml → workflow.md → skills; v7 planning lane, #2672). Ticketing is a preview. It depends on Python/uv scripts inside `_bmad/`. Its ceremony can be excessive for small changes, although the "right-sized" paths try to address this. I found no public issue documenting spec drift in v6.12 [UNVERIFIED — sparse issue signal because the issue count is low].

### 1.6 GSD, "Get Shit Done" (now **open-gsd/gsd-core**)

**Provenance warning (important).** The original `gsd-build/get-shit-done` (by TÂCHES) is **archived**: 64,443 stars, last release v1.42.3 on 2026-05-16, and its README now reads "GSD Has Moved … continues as **GSD Core**" at `open-gsd/gsd-core`. The fork announcement says the upstream "appears compromised or abandoned", with "no contact with the original maintainer (TÂCHES) since 2026-04-01", and "the `$GSD` token was publicly linked to a rug-pull". Migration took place on 2026-05-22: branches, tags and 77 issues were mirrored and the code was left unchanged. GSD 2 (`gsd-build/gsd-2`, a standalone Pi-based agent) likewise moved to `open-gsd/gsd-pi`. **For the bake-off, evaluate `@opengsd/gsd-core` and do not install `get-shit-done-cc`.** <https://github.com/gsd-build/get-shit-done>, <https://github.com/open-gsd/gsd-core/discussions/109>, <https://github.com/gsd-build/gsd-2>, <https://github.com/open-gsd/gsd-pi>

**What it is.** "A light-weight meta-prompting, context engineering, and spec-driven development system". Each milestone runs a phase loop: **Discuss → Plan → Execute → Verify → Ship**. Heavy work runs in fresh-context subagents to avoid "context rot". <https://github.com/open-gsd/gsd-core#readme>

**Maturity.** 9,910 stars (the fork restarted the count), MIT, 188 open issues, last push 2026-09-28. Latest release **v1.15.0 (2026-09-26)**. Cadence is about weekly to fortnightly minors: v1.9.0 07-31, v1.10.0 08-08, v1.11.0 08-19, v1.12.0 08-30, v1.13.0 09-06, v1.14.0 09-14, v1.15.0 09-26. The feature surface is large: around 86 skills behind six namespace routers. (Note: the fork restarted version numbers, but docs still cite upstream versions such as "v1.40".) <https://github.com/open-gsd/gsd-core/releases>, <https://github.com/open-gsd/gsd-core/blob/next/docs/COMMANDS.md>

**Install/bootstrap, exactly as documented.** <https://github.com/open-gsd/gsd-core#quickstart>
1. `npx @opengsd/gsd-core@latest`. The installer prompts for the runtime (choose Claude Code) and for global or local install. "Do not copy files from `agents/` or `commands/` directly."
2. Greenfield: `/gsd-new-project` (or `/gsd-new-project --auto @prd.md`). This produces `.planning/PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `config.json`, `research/` and `CLAUDE.md`.
3. Brownfield: `/gsd-onboard` (runs `/gsd-map-codebase` → `.planning/codebase/`, optional `/gsd-ingest-docs`, then new-project → `.planning/onboarding/SUMMARY.md`).
4. Configuration: `/gsd-settings`, `/gsd-config`, or `gsd config-set <key> <value>` (e.g. `workflow.windows_enforce`). <https://github.com/open-gsd/gsd-core/blob/next/docs/CONFIGURATION.md>
5. Updates: `/gsd-update`.

**Artefacts.** Everything is under `.planning/`: `PROJECT.md`, `REQUIREMENTS.md` (REQ-IDs), `ROADMAP.md` (phases), `STATE.md`, `MILESTONES.md`, `phases/NN-name/{NN-SPEC.md, CONTEXT.md, RESEARCH.md, NN-M-PLAN.md, NN-M-SUMMARY.md, VERIFICATION.md, UAT.md}`, `WINDOWS.md` (a broken-windows ledger), and `quick/`, `debug/`, `threads/`. (COMMANDS.md)

**Workflow stages.** new-project/onboard → per phase: [`/gsd-spec-phase N`] → `/gsd-discuss-phase N` → `/gsd-plan-phase N` (with a requirements coverage gate: "Uncovered requirements MUST block planning completion") → `/gsd-execute-phase N` (parallel waves) → `/gsd-verify-work` → `/gsd-ship` (PR) → next phase. When all phases are done: `/gsd-complete-milestone` → `/gsd-new-milestone`. Other entry points: `/gsd-autonomous`, `/gsd-manager` (dashboard), `/gsd-quick`/`/gsd-fast` for small tasks. <https://github.com/open-gsd/gsd-core/blob/next/docs/features/requirements-coverage-gate.md>

**Change handling (key axis): roadmap-centric, plus milestone resets.**
- `/gsd-phase` does CRUD on ROADMAP phases: append; `--insert N` for urgent decimal phases (e.g. 3.1); `--remove N` with renumbering; `--edit N` (`--force` for in-progress or completed phases).
- `/gsd-new-milestone` produces "Updated `PROJECT.md`, new `REQUIREMENTS.md`, new `ROADMAP.md`". Requirements are therefore versioned per milestone rather than kept as a living delta-merged spec.
- There is no delta-spec format. A contradicting requirement change mid-milestone would mean editing REQUIREMENTS.md or a phase by hand; I found no dedicated impact-analysis command [UNVERIFIED].
- Drift guards: scope-reduction detection, scope-conformance warnings, verification being "disk-strict" (a passing `VERIFICATION.md` decides completion, not checkboxes), and the broken-windows ledger. <https://github.com/open-gsd/gsd-core/tree/next/docs/features>

**Claude Code integration.** Claude Code was the original first-class target. It is installed as skills and commands (`/gsd-*`; formerly `/gsd:*`) and uses subagents heavily. `/gsd-ultraplan-phase` (beta) offloads planning to Claude Code's ultraplan cloud.

**Task/issue tracking.** Built-in: phases, plans and STATE in `.planning/`. Trackers: a documented recipe, "drive GSD from a tracker issue" (GitHub/Linear/Jira), maps an issue to a phase manually, "with no custom scripts or tracker integrations". There is also a pluggable **task-content resolver seam**: plan tasks can carry `tracker-id="beads:GSD-42"`, and `gsd-tools task resolve-content` pulls the task body from the tracker through an installed capability (ADR-3646). `/gsd-ship` creates GitHub PRs. <https://github.com/open-gsd/gsd-core/blob/next/docs/how-to/drive-gsd-from-a-tracker-issue.md>, <https://github.com/open-gsd/gsd-core/blob/next/docs/how-to/develop-a-task-content-resolver-capability.md>

**Known weaknesses.** Governance and provenance risk (the upstream was abandoned or compromised, and the fork is community-run and only about four months old). A very large command surface. Requirements are rebuilt per milestone rather than accumulated. Planning state lives in `.planning/`, which can pollute PRs; `planning.pr_strict` exists for this reason. (COMMANDS.md)

### 1.7 Additional contenders

#### 1.7a cc-sdd (gotalab/cc-sdd): Kiro-style SDD for Claude Code — **recommended to include**

- **What it is.** "Turn approved specs into long-running autonomous implementation. A minimal, adaptable SDD harness with Agent Skills." It is "Kiro-inspired … Existing Kiro specs remain compatible and portable." It installs 17 skills, and Claude Code and Codex support is marked **stable**. <https://github.com/gotalab/cc-sdd#readme>
- **Maturity.** 3,688 stars, last push 2026-09-23. Latest release **v3.1.0 (2026-09-23)**; before that v3.0.0 2026-04-09 and v2.1.x 2026-02. Releases are infrequent but substantive. <https://github.com/gotalab/cc-sdd/releases>
- **Install/bootstrap.** `npx cc-sdd@latest`, which by default installs Claude Code Skills with English docs (explicitly: `npx cc-sdd@latest --claude-skills`). Options: `--lang ja|zh-TW|es…`, `--dry-run`, `--kiro-dir docs` to change the spec directory. The legacy `/kiro:*` command mode (`--claude`) is deprecated. Then run `/kiro-steering` to capture project memory into `.kiro/steering/*.md` (the constitution equivalent). (README; <https://github.com/gotalab/cc-sdd/blob/main/docs/guides/skill-reference.md>)
- **Artefacts.** Kiro layout: `.kiro/specs/<feature>/{requirements.md, design.md, tasks.md}` (design includes a File Structure Plan; tasks carry `_Boundary:_`/`_Depends:_`), plus `brief.md`/`roadmap.md` from discovery and `.kiro/steering/`. The exact paths come from the `{{KIRO_DIR}}` default and Kiro compatibility [partly UNVERIFIED].
- **Workflow.** New work: `/kiro-discovery` → `/kiro-spec-init` → `/kiro-spec-requirements` → `/kiro-spec-design` → `/kiro-spec-tasks` → `/kiro-impl` (autonomous; a fresh implementer does TDD behind a feature flag, then an independent reviewer and auto-debug) → `/kiro-validate-impl` (GO/NO-GO/MANUAL_VERIFY_REQUIRED). **Extend an existing system:** `/kiro-steering` → `/kiro-discovery` or `/kiro-spec-init` → optional **`/kiro-validate-gap`** → design → tasks → impl. Multi-spec: `/kiro-spec-batch`, with cross-spec review "to catch contradictions". (README)
- **Change handling.** Discovery explicitly routes work to "extend an existing spec" or to "implement directly with no spec". `validate-gap` analyses the gap between existing code and new requirements. Cross-spec review looks for contradictions. There is no delta/archive model; specs are living per-feature docs edited in place [UNVERIFIED beyond the README and skill reference].
- **Tracking.** None beyond `tasks.md`, which records task state for resumption.
- **Why include it.** It is the most credible "Kiro-style spec workflow usable from Claude Code". It also uses the same artefact format as Kiro, which provides an exit path.

#### 1.7b Kiro (AWS) — reference point only; not a Claude Code tool

Kiro is AWS's spec-driven IDE and CLI. Specs are `requirements.md` (or `bugfix.md` for bugfix specs), `design.md` and `tasks.md`, produced in three phases (requirements/bug analysis → design → tasks), and independent tasks run in parallel. "Specs work in CLI alongside IDE and Web." It runs its own agent, so it cannot be driven by Claude Code directly. cc-sdd is the practical way to use Kiro-format specs from Claude Code. <https://kiro.dev/docs/specs/> [Detailed Kiro change-handling was not documented on that page, so it is UNVERIFIED]

#### 1.7c Tessl spec-driven-development tile — lightweight option, low maturity

- A Tessl "methodology tile" (skills and rules). Install with `tessl init` then `tessl install tessl-labs/spec-driven-development`, or `npx @tessl/cli install tessl-labs/spec-driven-development`. It is activated by saying "use spec-driven development" in the prompt. <https://github.com/tesslio/spec-driven-development-tile>
- Specs are `specs/*.spec.md`, with YAML frontmatter `targets:` (code globs) and **`[@test]` links** to test files. This makes the spec↔code↔test link explicit and machine-checkable (`scripts/check-spec-links.sh`, `validate-specs.sh`). The `spec-verification` skill "Verify[ies] implementation and tests remain synchronized with specs". The tile's evals cover "Spec drift detection after file refactoring" and "Extending an existing spec with new requirements". (tile README)
- Maturity: the repo has 55 stars and was last pushed 2026-03-30 (the registry shows 2.0.1). Tessl as a company has repositioned as an "Agent Enablement Platform" (a skills registry, code review, MCP gateway). Account/pricing requirements [UNVERIFIED]. <https://tessl.io/>, <https://tessl.io/registry/tessl-labs/spec-driven-development>, <https://docs.tessl.io/sitemap.md>
- Verdict: the `targets`/`[@test]` idea is worth borrowing, but the tool itself is too thin and stale to be a primary candidate.

(Considered and not included: `Pimzino/claude-code-spec-workflow` was last pushed 2025-09 and is stale; `Pimzino/spec-workflow-mcp` (4.3k stars, last pushed 2026-07) is an MCP server with a dashboard, not a methodology; `eyaltoledano/claude-task-master` (28k stars) is a task manager rather than SDD, with its last release 2026-03-31. <https://api.github.com/repos/Pimzino/claude-code-spec-workflow>, <https://api.github.com/repos/Pimzino/spec-workflow-mcp>, <https://github.com/eyaltoledano/claude-task-master/releases>)

### 1.8 Part 1 comparison table

| Tool | Latest (date) | Stars | Install surface | Canonical spec model | Change-to-existing-spec mechanism | Human gates | Built-in tracking / tracker links | Claude Code fit |
|---|---|---|---|---|---|---|---|---|
| superpowers | v6.4.2 (2026-09-25) | 292k | CC plugin marketplace; no init | Dated design docs + plans (`docs/superpowers/`) | **None**: bounded changes write no spec; iteration issue #921 is open | Hard gates at every stage | None (plan checklists; TodoWrite) | Native plugin, hooks, subagents |
| Spec Kit | v1.0.12 (2026-09-25) | 139k | `uv tool install specify-cli`; `specify init --integration claude` | Per-feature `specs/NNN-*/` + constitution | Doc'd choice: flow-forward / living / flow-back; `analyze`, `converge`; no delta | Manual, one skill at a time | `tasks.md`; one-way `taskstoissues` → GitHub | Skills in `.claude/skills` |
| OpenSpec | v1.13.2 (2026-09-23) | 70.5k | `npm i -g @fission-ai/openspec`; `openspec init --tools claude` | **Living `openspec/specs/` + change folders** | **Delta specs ADDED/MODIFIED/REMOVED, validated, merged on archive**; `/opsx:verify` | Soft (no gates) | `tasks.md`; community beads schema; `--json` CLI | Generated skills + `/opsx:*` commands |
| Spec Kitty | v3.2.7 (2026-09-09); 4.0 RC | 1.6k | `pipx install spec-kitty-cli`; `spec-kitty init . --ai claude` | Per-mission `kitty-specs/NNN-*/` + charter | Per-mission, no delta found [UNVERIFIED]; mission review | review/accept/merge gates | **WP kanban lanes + dashboard; tracker cmds (beads/fp local; Jira/Linear/GitHub/GitLab via SaaS)** | Slash cmds + `next --agent claude` runtime |
| BMAD | v6.12.0 (2026-09-04) | 53.6k | CC plugin (`bmad-code-org/bmad-plugins`) or `npx skills add`; `bmad setup` | PRD/spec/architecture docs per initiative in `_bmad-output/` | **`bmad-correct-course` → Sprint Change Proposal; PRD Update intent with decision memlog** | Facilitated, per stage | **Ticket tree (preview) with stores: repo, gh, jira, linear, notion, trello** | Plugin + skills; uv scripts |
| GSD Core | v1.15.0 (2026-09-26) | 9.9k (fork) | `npx @opengsd/gsd-core@latest`; `/gsd-new-project` or `/gsd-onboard` | `.planning/` REQUIREMENTS + ROADMAP phases, per milestone | `/gsd-phase --insert/--edit/--remove`; new milestone = new REQUIREMENTS; coverage gate | discuss/verify gates; autonomous mode | `.planning` state; **tracker-id resolver seam (beads)**; manual GH/Linear/Jira recipe | Original CC-first; commands + subagents |
| cc-sdd | v3.1.0 (2026-09-23) | 3.7k | `npx cc-sdd@latest` | Kiro `.kiro/specs/<f>/` + steering | Discovery routes to "extend existing spec"; `validate-gap`; cross-spec contradiction review | Approval of requirements/design/tasks | `tasks.md` only | Skills (stable for CC) |
| Tessl SDD tile | 2.0.1 (registry) | 55 | `tessl init; tessl install tessl-labs/spec-driven-development` | `specs/*.spec.md` with `targets` + `[@test]` | `spec-verification` sync skill; link-check scripts | spec-before-code rule | None | Skills/rules via Tessl |



## Part 2 — Work trackers

### 2.1 Candidate notes

**GitHub Issues + Projects (hosted).**
- Sub-issues, issue types, advanced search and higher Projects limits reached GA after the Jan 2025 preview. There can be up to 100 sub-issues per parent. <https://github.blog/changelog/2025-04-09-evolving-github-issues-and-projects/>
- Dependencies ("blocked by"/"blocking") are GA, with up to 50 per relationship type. <https://github.blog/changelog/2025-08-21-dependencies-on-issues/>
- **Issue fields** (typed org-wide custom fields: single-select, text, number, date; up to 25 per org; Priority/Effort/Start/Target preconfigured) went GA on 2026-07-02. Multi-select fields went GA in Aug 2026, alongside a "Relates to" relationship in preview. <https://github.blog/changelog/2026-07-02-issue-fields-are-now-generally-available/>, <https://github.blog/changelog/2026-08-07-connecting-issues-and-multi-select-field-support/>
- **Caveat:** issue types and issue fields are *organisation* features. Issue types are removed if a repo moves to a personal account, so troupe.run must live in an org (e.g. hps-gd) to get them. <https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization>
- Projects: table, board and roadmap views, plus custom fields (date, number, single-select, text, iteration). They are user- or org-owned and can hold issues and PRs from any repository, up to 50,000 items. <https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects>, <https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-items-in-your-project/adding-items-to-your-project>
- Agent drivability: `gh` ≥ v2.94.0 adds `--type`, `--parent`, `--set-parent`/`--remove-parent` and `--blocked-by`/`--blocking` to `gh issue create/edit`. This was confirmed in local `gh issue create --help` on gh 2.101.0. <https://github.blog/changelog/2026-06-10-manage-sub-issues-types-and-dependencies-from-github-cli/>
- The official **GitHub MCP server** (33k stars, v1.12.2 2026-09-16) has `sub_issue_write`, `get_sub_issues`, issue `type`, `list_issue_types`, `projects_get`/`projects_list`, and issue-field read/write (since 2026-06-18). <https://github.com/github/github-mcp-server>, <https://github.blog/changelog/2026-06-18-duplicate-detection-and-issue-fields-mcp-support-for-github-issues/>
- Note: the GitHub MCP plugin failed to connect in this session (a 400 auth-header error), so the troupe team will need to fix its auth if the bake-off uses it.

**git-bug (git-bug/git-bug).**
- "Distributed, offline-first bug tracker integrated in git". Entities are stored in git refs, and "no files are added in your project". It has CLI, TUI and web UIs plus a GraphQL API.
- **Bridges** import and export to GitHub, GitLab and Jira (Launchpad import only), incrementally. They carry bugs, comments, labels, status and title, but **not assignee or milestone**, and there is no board.
- Its own feature matrix shows Assignee ❌, Milestone ❌, Board 🟠 (core and CLI partial), Project Config ❌. Relationships (#949) and milestones (#639) are open issues.
- `git bug bug --format json` gives JSON output.
- Maturity: 10.6k stars, GPL-3.0. v0.11.0 was released 2026-09-22 after a 16-month gap (v0.10.1 2025-05-19).
<https://github.com/git-bug/git-bug#readme>, <https://github.com/git-bug/git-bug/blob/trunk/doc/feature-matrix.md>, <https://github.com/git-bug/git-bug/issues/949>, <https://github.com/git-bug/git-bug/issues/639>, <https://github.com/git-bug/git-bug/blob/trunk/doc/md/git-bug_bug.md>

**Backlog.md (MrLesk/Backlog.md).**
- "Markdown-native Task Manager & Kanban visualizer for any Git repository", explicitly built for AI agents with three human review checkpoints (spec, plan, code). Tasks are `.md` files under `backlog/`, alongside docs and decisions.
- Install: `npm i -g backlog.md` (or brew/bun/nix), then `backlog init "Name"`. The init wizard offers CLI instructions (recommended) or MCP; manual MCP: `claude mcp add backlog --scope user -- backlog mcp start`.
- Features: parent/subtasks (`--parent`), labels, priority, milestones (`backlog milestone add`, with due dates), dependencies (`--dep`) with derived `isReady` and a `dependencyGraph`, configurable `statuses`/`labels`/`types`/`priorities`, a monorepo `projects` attribute, a terminal board and a local web Kanban. It is local-first: "no server, no account, no telemetry"; `remoteOperations: false` for offline use; `checkActiveBranches` reads task state across branches.
- Output is stable, versioned JSON (`--json`, `schemaVersion`), with `--watch` for streaming.
- I found no GitHub Issues sync.
- Maturity: 6.9k stars, MIT, **v1.53.0 (2026-09-24)**, releases about every 1–2 weeks, dogfooded.
<https://github.com/MrLesk/Backlog.md#readme>, <https://github.com/MrLesk/Backlog.md/blob/main/CLI-INSTRUCTIONS.md>, <https://github.com/MrLesk/Backlog.md/blob/main/ADVANCED-CONFIG.md>

**beads / bd (gastownhall/beads, formerly steveyegge/beads).**
- "Distributed graph issue tracker for AI agents, powered by Dolt". The source of truth is a Dolt DB in `.beads/`, synced via `bd dolt push/pull` to `refs/dolt/data` on the git remote. `.beads/issues.jsonl` is an *export*, "not the source of truth".
- Install: `brew install beads` or `npm i -g @beads/bd`, then `bd init` and `bd setup claude` (a SessionStart hook running `bd prime`); a Claude Code plugin also exists. MCP: `uv tool install beads-mcp`, although the docs say "Prefer CLI + hooks when shell is available".
- Features: hierarchical IDs (epic `bd-a3f8` → `bd-a3f8.1` → `.1.1`), deps (`blocks`, `parent-child`, `related`), `bd ready`, atomic `--claim`, graph links (`relates-to`, `duplicates`, `supersedes`), labels, priorities, and core types (bug, task, feature, chore, epic, decision) plus `types.custom`. The **arbitrary JSON `metadata`** field is the extension point for custom fields. Memory is kept via `bd remember`/`bd prime`, with compaction.
- It has **no first-class milestones**; they are modelled as epics (#3184 asks for Linear milestone reconstruction).
- **Bidirectional GitHub sync**: `bd github sync [--pull-only|--push-only] [--prefer-local|--prefer-github|--prefer-newer]`. Syncing epic/child and blocks relationships *to GitHub* is still an open PR (#6804, 2026-09-27). Jira, Linear, GitLab and Azure DevOps integrations also exist.
- Multi-repo routing (`bd repo add`, contributor/maintainer roles) and federation are available.
- Maturity: 27.5k stars, MIT, **v1.3.0 (2026-09-15)** with v1.3.1-rc.1 on 2026-09-21. It has **1,281 open issues**, and schema migrations need a coordinated `bd migrate` (the upgrade guide describes this). Board views come from community tools such as `beads_viewer` (1.7k stars; kanban, DAG, robot-mode JSON).
<https://github.com/gastownhall/beads#readme>, <https://github.com/gastownhall/beads/blob/main/docs/cli-reference/github.md>, <https://github.com/gastownhall/beads/blob/main/docs/cli-reference/types.md>, <https://github.com/gastownhall/beads/blob/main/docs/core-concepts/metadata.md>, <https://github.com/gastownhall/beads/blob/main/docs/multi-agent/routing.md>, <https://github.com/gastownhall/beads/blob/main/docs/integrations/claude-code.md>, <https://github.com/gastownhall/beads/blob/main/docs/integrations/mcp-server.md>, <https://github.com/gastownhall/beads/pull/6804>, <https://github.com/gastownhall/beads/issues/3184>, <https://github.com/Dicklesworthstone/beads_viewer>

**ticket / tk (wedow/ticket): added contender.**
- "Git-backed issue tracker for AI agents … written as a full replacement for beads". It is a single bash script, and tickets are markdown with YAML frontmatter in `.tickets/`.
- Features: types (bug, feature, task, epic, chore), `--parent`, `dep`/`dep tree`/`dep cycle`, `ready`/`blocked`, tags, priority, `--external-ref gh-123`, and `query` JSON via jq. It has plugins but no GitHub sync, milestones or board.
- Maturity: 903 stars; v0.3.2 2026-02-03; last push 2026-03-16, so it is quiet.
<https://github.com/wedow/ticket#readme>

**Radicle issues: added contender (considered, weak fit).** Radicle issues are git-native Collaborative Objects and are local-first ("can be created even when offline"). They support comments, assignees, labels and state, but the guide doesn't mention milestones, hierarchy, dependencies, GitHub sync or JSON output. They also require the Radicle P2P network rather than GitHub. <https://radicle.dev/guides/user>

### 2.2 Capability matrix

Legend: **Y** yes · **P** partial · **N** no · **?** unverified.

| Capability | GitHub Issues + Projects | git-bug | Backlog.md | beads (bd) | ticket (tk) |
|---|---|---|---|---|---|
| Themes/epics / hierarchy | **Y**: sub-issues, up to 100 per parent [cl-2025-04] | **N**: relationships open issue #949 [fm] | **Y**: parent/subtasks `--parent` [cli] | **Y**: hierarchical IDs epic→task→subtask; `parent-child` dep [rd] | **Y**: `--parent`; `epic` type [tk] |
| Labels | **Y** | **Y** [fm] | **Y** `-l` [cli] | **Y** `bd label` [lbl] | **Y** `--tags` [tk] |
| Milestones | **Y** (repo milestones; `gh issue create -m`) [gh help] | **N** (#639) [fm] | **Y** `backlog milestone add`, due dates [cli] | **N**: use epics (#3184) | **N** |
| Issue types | **Y**, org-only, up to 25 [types-doc] | **N** [fm] | **Y**: configurable `types` [adv] | **Y**: 6 core + `types.custom` [types] | **Y**: fixed 5 [tk] |
| Dependencies / blocking | **Y**: blocked-by/blocking GA, up to 50 [cl-2025-08] | **N** | **Y**: `--dep`, `isReady`, dependency graph [cli] | **Y**: `blocks`, `bd ready`, graph links [rd] | **Y**: `dep`, `ready`, `blocked`, cycle check [tk] |
| Custom fields | **Y**: issue fields GA 2026-07 (org) + Project fields [cl-fields] | **N** | **P**: configurable enums (statuses/labels/types/priorities/projects); no arbitrary fields [adv] | **P**: arbitrary JSON `metadata` (no UI/schema) [meta] | **N** (plugins only) |
| Board / roadmap views | **Y**: table, board, roadmap [projects] | **P**: board partial (core/CLI), web UI list [fm] | **Y**: terminal + web Kanban; Gantt **?** (PR #669) | **P**: community TUIs (beads_viewer kanban/DAG) [bv] | **N** |
| Offline / local-first | **N** (hosted) | **Y**: offline-first, git refs [rd-gb] | **Y**: plain files; `remoteOperations: false` [adv] | **Y**: embedded Dolt; push/pull [rd] | **Y**: plain files |
| Sync with GitHub | **n/a** (native) | **Y**: bridge import/export; no assignee/milestone [fm] | **N** (none found) | **Y**: bidirectional `bd github sync`; relationship sync pending #6804 | **N** (`--external-ref` only) |
| Agent-drivable CLI/API | **Y**: `gh` flags for type/parent/deps; REST/GraphQL | **Y**: CLI `--format json`, GraphQL [gb-cli] | **Y**: versioned `--json`, `--watch` [cli] | **Y**: `--json` everywhere, `--claim`, `bd prime` [rd] | **P**: bash; `query` JSON needs jq [tk] |
| MCP server | **Y**: official github-mcp-server (sub-issues, types, projects, fields) | **N** (none found) | **Y**: `backlog mcp start` [rd-bl] | **Y**: `beads-mcp` (CLI+hook preferred) [mcp] | **N** |
| Multi-repo | **Y**: Projects span repos/orgs [add-items] | **N**: per repo | **P**: `projects` attr for monorepos; one MCP server follows workspace [adv, rd-bl] | **Y**: routing + federation (some open bugs, e.g. #6351) [routing] | **P**: `TICKETS_DIR` |
| Maturity | GA platform; features GA 2025–26 | 10.6k stars; v0.11.0 2026-09-22 after 16-month gap | 6.9k stars; v1.53.0 2026-09-24; releases every 1–2 weeks | 27.5k stars; v1.3.0 2026-09-15; 1,281 open issues; schema migrations | 903 stars; v0.3.2 2026-02; quiet |

Citation keys: [cl-2025-04] <https://github.blog/changelog/2025-04-09-evolving-github-issues-and-projects/> · [cl-2025-08] <https://github.blog/changelog/2025-08-21-dependencies-on-issues/> · [cl-fields] <https://github.blog/changelog/2026-07-02-issue-fields-are-now-generally-available/> · [types-doc] <https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization> · [projects] <https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects> · [add-items] <https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-items-in-your-project/adding-items-to-your-project> · [gh help] `gh issue create --help` (gh 2.101.0) and <https://github.blog/changelog/2026-06-10-manage-sub-issues-types-and-dependencies-from-github-cli/> · [fm] <https://github.com/git-bug/git-bug/blob/trunk/doc/feature-matrix.md> · [rd-gb] <https://github.com/git-bug/git-bug#readme> · [gb-cli] <https://github.com/git-bug/git-bug/blob/trunk/doc/md/git-bug_bug.md> · [cli] <https://github.com/MrLesk/Backlog.md/blob/main/CLI-INSTRUCTIONS.md> · [adv] <https://github.com/MrLesk/Backlog.md/blob/main/ADVANCED-CONFIG.md> · [rd-bl] <https://github.com/MrLesk/Backlog.md#readme> · [rd] <https://github.com/gastownhall/beads#readme> · [lbl] <https://github.com/gastownhall/beads/blob/main/docs/cli-reference/label.md> · [types] <https://github.com/gastownhall/beads/blob/main/docs/cli-reference/types.md> · [meta] <https://github.com/gastownhall/beads/blob/main/docs/core-concepts/metadata.md> · [mcp] <https://github.com/gastownhall/beads/blob/main/docs/integrations/mcp-server.md> · [routing] <https://github.com/gastownhall/beads/blob/main/docs/multi-agent/routing.md> · [bv] <https://github.com/Dicklesworthstone/beads_viewer> · [tk] <https://github.com/wedow/ticket#readme>

(Radicle is left out of the matrix. It has labels, assignees and offline support; everything else is N or unverified per <https://radicle.dev/guides/user>.)

## Implications for bake-off design

**1. Shortlist hygiene.**
- Use **GSD Core (`@opengsd/gsd-core`)**, not the archived `get-shit-done-cc`. Record the provenance risk as a scored criterion rather than silently excluding it.
- **Spec Kitty** is mid-transition (stable 3.2.7 versus 4.0 RC), so pin the stable version and note the churn.
- **Tessl** and **Kiro** are reference points, not contestants: Tessl is thin and stale, and Kiro cannot be driven by Claude Code. **cc-sdd** stands in for "Kiro-style from Claude Code".

**2. Natural methodology ↔ tracker pairings** (each is a documented integration, not a guess):

| Methodology | Pairs naturally with | Evidence |
|---|---|---|
| Spec Kit | GitHub Issues (one-way `/speckit-taskstoissues`) | agentic-sdd reference |
| BMAD | GitHub Issues (`gh` store), or its own repo store; also Jira/Linear/Notion/Trello | ticketing `config/` starters |
| Spec Kitty | beads (local tracker provider) or its own WP lanes/dashboard; Jira/Linear/GitHub/GitLab via SaaS | CHANGELOG, cli-commands |
| GSD Core | beads (`tracker-id="beads:…"` resolver seam); GitHub/Linear/Jira via manual recipe | COMMANDS.md, how-to |
| OpenSpec | beads (community schema, #1232); otherwise only `tasks.md` | #1232 |
| superpowers | none (TodoWrite, plan checklists); any tracker has to be bolted on via CLAUDE.md | README, #2183 |
| cc-sdd | none (`tasks.md`) | README |

Consequences:
- **beads** is the tracker most integrated with methodologies (Spec Kitty, GSD, OpenSpec schema) and has bidirectional GitHub sync.
- **GitHub Issues** is the most integrated with *humans* (roadmap views, issue fields, MCP).
- **Backlog.md** is a self-contained agent-first alternative that doesn't depend on any methodology.

Treat the tracker as a separate factor and test at least one combination per tracker. Otherwise a methodology with a built-in board (Spec Kitty, BMAD) gets double credit.

**3. Change-handling has to be exercised by scenario, not by reading docs.** Each tool's change mechanism is different, so each needs a scenario step designed to trigger it:
- **Contradicting requirement (e.g. "R3 now forbids what R1 required").**
  - OpenSpec: a MODIFIED/REMOVED delta; check that `openspec validate` flags it and that archive updates `openspec/specs/`.
  - BMAD: `bmad-correct-course`, which should produce a Sprint Change Proposal; the PRD Update intent should surface the conflict against `.memlog.md`.
  - Spec Kit: the team must *choose* living vs flow-forward. Score whether the old `specs/NNN/spec.md` is left stale (#620).
  - GSD: `/gsd-phase --edit` or `--insert`, plus a hand edit of REQUIREMENTS.md; check the coverage gate.
  - superpowers: expect the bounded path to produce no spec. Score whether the earlier spec is silently contradicted.
  - cc-sdd: `/kiro-discovery` should route to "extend existing spec"; then run `/kiro-validate-gap`.
- **Two concurrent changes touching the same requirement.** Only OpenSpec claims delta merging, and the case where both touch the *same* requirement is undocumented [UNVERIFIED]. This is the sharpest test of its model. For Spec Kit, the single `.specify/feature.json` active-feature state makes parallel features awkward, so test it.
- **Cross-cutting concern** (e.g. event-sourcing audit metadata on every command). Test where it lands:
  - the constitution or charter (Spec Kit, Spec Kitty)
  - steering (cc-sdd)
  - PROJECT.md or the milestone (GSD)
  - architecture (BMAD)
  - a spec domain (OpenSpec)
  - nowhere durable (superpowers)
  
  Then check whether later features pick it up.
- **Bug fix.** Spec Kit has a dedicated bug extension (`specify extension add bug`; verdicts verified/partial/failed). Kiro/cc-sdd have bugfix specs, GSD has `/gsd-debug`, and superpowers has systematic-debugging. Check whether each fix leaves a spec trace.
- **Drift after hand edits.** Edit code by hand, then run each tool's check: OpenSpec `/opsx:verify`, Spec Kit `/speckit-analyze` + `/speckit-converge`, GSD verify-work, Spec Kitty mission-review, BMAD PRD Validate. Score whether each detects the edit.

**4. Setup-checklist gotchas to bake into the harness.**
- Spec Kit's upgrade (`specify init --here --force`) can overwrite `.specify/memory/constitution.md`, so back it up.
- OpenSpec sends telemetry by default; set `OPENSPEC_TELEMETRY=0`.
- BMAD needs `uv` plus `bmad setup` before any skill runs.
- beads needs `bd setup claude`, and its schema migrations need a designated clone.
- GitHub issue types and issue fields need the repo in an **organisation**.
- superpowers and BMAD install as Claude Code plugins, while Spec Kit, OpenSpec, Spec Kitty, GSD and cc-sdd generate per-project files. This affects isolation between bake-off arms: use a fresh repo per arm and make sure no globally installed plugin (e.g. superpowers, which is already installed in this environment) leaks into the other arms.

**5. Event-sourced fit (troupe.run specific, a judgement call).**
- The tools with an **append-only change history** fit best with an event-sourced mindset: OpenSpec's archived change folders, BMAD's `.memlog.md`, beads' Dolt history with `supersedes` links, and Spec Kitty's event-log runtime state.
- superpowers' dated specs are also append-only, but they are never reconciled into a current-truth view, so there is no "projection".
- It is worth scoring this explicitly as "can we reconstruct why requirement X is what it is today?".
