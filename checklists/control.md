# Setup checklist — control (plain Claude Code 2.1.281, no methodology)

## Source
docs/design.md §2 (control arm: "plain Claude Code, no methodology", tracker "GitHub Issues (baseline)") and §6
(setup and isolation). There is no CANDIDATES.md section: the control has no tool of its own.

## Pins
Claude Code 2.1.281 (image `bakeoff-base:cc2.1.281`, pins.toml `[claude] version`); model claude-opus-5-5
(pins.toml `[claude] model`). No plugins, no generated files.

## Setup (what the runner runs)
1. `repo.init`: a fresh repo with one empty commit, pushed to the local bare origin `/home/actor/origin.git` (design §6; preflight B4).
2. The arm's GitHub PAT for the baseline tracker, installed into the arm's home only (design §2 tracker column; preflight M4).
3. Nothing else: no methodology, so no shell steps, no setup prompts, no setup commit (design §2 control arm).

## Machine-verified
- `common.claude-version` — `claude --version` is 2.1.281 (expected value from pins.toml)
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude (design §6)
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — no plugin installed or vendored
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `control.no-method` — no `.claude/`, `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md` or `.mcp.json` in the repo, and no `CLAUDE.md`, `skills/`, `commands/` or `agents/` in the arm's user-scope `~/.claude`
- `control.empty-repo` — the repo is exactly `repo.init`'s one empty commit: nothing tracked, untracked or ignored
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `github.issues-access` — (host) the arm's PAT can list issues and labels of its repo (n/a, never green, on a pass without a repo)
- `setup.manifest-matches-pass1` — (host) pass 2's setup files equal pass 1's (control lists none: setup creates nothing)
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds and `origin/main` is `main` (preflight B4)
- `setup.agent-turns` — (host) every configured setup prompt's last turn ended ok (control configures none)

## Owner-verified
- [ ] OV1: Telemetry: plain Claude Code with CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1; nothing else to disable (probe P9 evidence).

## Known traps
- None specific. The control must receive exactly the same harness text as every method arm.
- Anything a later step adds (a `CLAUDE.md` from `/init`, say) is the arm's own work, not setup: `control.no-method`
  and `control.empty-repo` run in `setup` mode only.
