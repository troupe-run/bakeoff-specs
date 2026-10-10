# Agentic SDLC and Spec-Driven Development

method-command Spec-Driven Development on an agentic SDLC

## Project Context

### Paths
- Steering: `spec/steering/`
- Specs: `spec/spec/`

### Steering vs Specification

**Steering** (`spec/steering/`) - Guide AI with project-wide rules and context
**Specs** (`spec/spec/`) - Formalize development process for individual features

### Active Specifications
- Check `spec/spec/` for active specifications
- Use `/method-command [feature-name]` to check progress

## Development Guidelines
- Think in English, generate responses in English. All Markdown content written to project files (e.g., requirements.md, design.md, tasks.md, research.md, validation reports) MUST be written in the target language configured for this specification (see spec.json.language).

## Minimal Workflow
- Phase 0 (optional): `/method-command`, `/method-command`
- Discovery: `/method-command "idea"` — determines action path, writes brief.md + roadmap.md for multi-spec projects
- Phase 1 (Specification):
  - Single spec: `/method-command {feature} [--auto]` or step by step:
    - `/method-command "description"`
    - `/method-command {feature}`
    - `/method-command {feature}` (optional: for existing codebase)
    - `/method-command {feature} [-y]`
    - `/method-command {feature}` (optional: design review)
    - `/method-command {feature} [-y]`
  - Multi-spec: `/method-command` — creates all specs from roadmap.md in parallel by dependency wave
- Phase 2 (Implementation): `/method-command {feature} [tasks] [--review required|inline|off]`
  - Without task numbers: autonomous mode (subagent per task + independent review + final validation)
  - With task numbers: manual mode (selected tasks in main context, still reviewer-gated before completion)
  - `--review off` skips task-local review; use it intentionally and keep `/method-command {feature}` as the final quality gate
  - `/method-command {feature}` (standalone re-validation)
- Progress check: `/method-command {feature}` (use anytime)

## Skills Structure
Skills are located in `.claude/skills/method-*/SKILL.md`
- Each skill is a directory with a `SKILL.md` file
- Skills run inline with access to conversation context
- Skills may delegate parallel research to subagents for efficiency
- Additional files (templates, examples) can be added to skill directories
- `method-command` — task-local adversarial review protocol used by reviewer subagents
- `method-command` — root-cause-first debug protocol used by debugger subagents
- `method-command` — fresh-evidence gate before success or completion claims
- Use skills explicitly requested by the user and skills relevant to the task's domain, including design, accessibility, and UX.
- Select skills from their descriptions or metadata first, then read only the selected skills and the references needed for the task.
- Follow explicit host and project rules and retain required workflow checks. Do not skip relevant skills just because the task is small.

## Development Rules
- 3-phase approval workflow: Requirements → Design → Tasks → Implementation
- Human review required each phase; use `-y` only for intentional fast-track
- Keep steering current and verify alignment with `/method-command`
- Follow the user's instructions precisely, and within that scope act autonomously: gather the necessary context and complete the requested work end-to-end in this run, asking questions only when essential information is missing or the instructions are critically ambiguous.

## Steering Configuration
- For spec and implementation work, load the core steering files below from `spec/steering/`. Reuse current context rather than rereading unchanged files.
- Load additional steering only when required by project rules or relevant to the task.
- Default files: `product.md`, `tech.md`, `structure.md`
- Custom files are supported (managed via `/method-command`)
