# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN tracker INTEGRATION v:1 profile:minimal hash:46cd31e7 -->
## tracker Issue Tracker

This project uses **tracker-cli (tracker)** for issue tracking. Run `tracker-cli prime` to see full workflow context and commands.

### Quick Reference

```bash
tracker-cli ready              # Find available work
tracker-cli show <id>          # View issue details
tracker-cli update <id> --claim  # Claim work
tracker-cli close <id>         # Complete work
```

### Rules

- Use `tracker-cli` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `tracker-cli prime` for detailed command reference and session close protocol
- Use `tracker-cli remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local tracker DB; sync uses `refs/tracker/data` on your git remote; `tracker/issues.jsonl` is a passive export. See https://github.com/gastownhall/tracker/blob/main/docs/core-concepts/sync-concepts.md for details and anti-patterns.

## Agent Context Profiles

The managed tracker block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `tracker-cli` for task tracking. Do not run git commits, git pushes, or tracker remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `tracker-cli prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close tracker, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a tracker implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create tracker for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   tracker-cli tracker push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this tracker block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END tracker INTEGRATION -->


## Build & Test

_Add your build and test commands here_

```bash
# Example:
# npm install
# npm test
```

## Architecture Overview

_Add a brief overview of your project architecture_

## Conventions & Patterns

_Add your project-specific conventions here_
