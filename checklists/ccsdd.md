# Setup checklist — ccsdd (gotalab/cc-sdd 3.1.0)

## Source
research/CANDIDATES.md §1.7a; https://github.com/gotalab/cc-sdd#readme,
https://github.com/gotalab/cc-sdd/blob/main/docs/guides/skill-reference.md

## Pins
cc-sdd 3.1.0 from a committed package-lock (image bakeoff-arm-ccsdd:1; `npx cc-sdd@3.1.0` runs this same bin);
Claude Code 2.1.281; model claude-opus-5-5.

## Setup (what the runner runs)
1. `cc-sdd --claude-skills` (§1.7a install: the explicit form of the documented `npx cc-sdd@latest`, English docs, Claude Code Skills). Verified offline in the pinned image: no prompt without a TTY, "50/50 files written" — 33 files in `.claude/skills/` (17 skills), `CLAUDE.md` (project memory), 16 in `.kiro/settings/` — byte-identical across runs.
2. Agent: `/kiro-steering` with `<project-principles.md>` (§1.7a: "run `/kiro-steering` to capture project memory into `.kiro/steering/*.md`").
3. Commit `Set up gotalab/cc-sdd 3.1.0` (design §6: the setup is part of the arm repo's history).

## Machine-verified
Ids marked `(computed)` are omitted, never recorded ok, when they would check nothing; whether they exist is computed from the arm config and the plugin route (`checklist.host_check_ids`), and a computed id that should exist but did not run fails.

- `common.claude-version` — `claude --version` is 2.1.281
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude in the verify container's env, i.e. the image and runner-injected env; the env each arm session actually gets is verified elsewhere (credentials.session_env tests, `00-setup/model-overrides.json`)
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — no plugin installed or vendored
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `ccsdd.version` — `cc-sdd --version` (the bin on PATH) is 3.1.0
- `ccsdd.skills` — exactly the 17 skills 3.1.0 installs: `.claude/skills/kiro-{debug,discovery,impl,review,spec-batch,spec-design,spec-init,spec-quick,spec-requirements,spec-status,spec-tasks,steering,steering-custom,validate-design,validate-gap,validate-impl,verify-completion}/SKILL.md`
- `ccsdd.settings` — `.kiro/settings/templates/{specs,steering,steering-custom}/` hold their templates
- `ccsdd.project-memory` — `CLAUDE.md` names `.kiro/steering/` and `.kiro/specs/`
- `ccsdd.steering` — at least one `.kiro/steering/*.md`, none empty (fails until the agent turn has run)
- `ccsdd.no-legacy` — no `.claude/commands/kiro/` (the deprecated `--claude` mode)
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `github.issues-access` — (host) the arm's PAT can list issues and labels of its repo
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds (preflight B4)
- (computed) `setup.agent-turns` — (host) present only when setup prompts are configured: every prompt's last turn ended ok
- (computed) `setup.manifest-matches-pass1` — (host) present only when the effective manifest list is not empty: pass 2's setup files equal pass 1's
- (computed) `ccsdd.entry-commands` — (host) present only when `[drive]` needs a slash command (entry, bug_entry, must_run): every one is installed

## Owner-verified
- [ ] OV1: The installer reported version 3.1.0 and English docs (00-setup/shell/01.log).
- [ ] OV2: The steering files hold the principles and nothing invented beyond them.
- [ ] OV3: Telemetry: none documented, or disabled — per probe P9's record for cc-sdd (offline scan of the pinned package found no telemetry code; P9 confirms).

## Known traps
- The legacy `/kiro:*` command mode is deprecated — skills only.
- `--kiro-dir` is left at its default (`.kiro`).
- Without a TTY the installer's overwrite policy falls back to `skip` (existing files are kept); the repo holds only its
  empty initial commit, so nothing is skipped.
- The installer prints "Recommended models" (Opus/Sonnet 4.6): advice only; every session runs the pinned model (OD2).
- `/kiro-impl` works "behind a feature flag" — evidence records whether the flag was removed by each step's end.
