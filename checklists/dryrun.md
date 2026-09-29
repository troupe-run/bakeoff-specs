# Setup checklist — dryrun (the runner's own dry-run arm; not an arm under test)

## Source
Plan 2 Task 24: the dry run of the whole runner. The fake claude in `bakeoff-arm-dryrun:1` plays the arm (with the
reference implementation baked in at `/opt/reference`), the product owner and the teammate; the owner is the
scripted owner (`runner/config/dryrun-owner.toml`); the credential is the dummy. No model is called and GitHub is
never touched (tracker `dry`).

## Pins
Fake Claude Code reporting 2.1.281 and the pinned model (pins.toml); image `bakeoff-arm-dryrun:1` (images.lock.json).

## Setup (what the runner runs)
1. `repo.init`: a fresh repo with one empty commit, pushed to the local bare origin `/home/actor/origin.git`.
2. One shell step: `.claude/commands/dry-next.md` and `.claude/commands/dry-close.md`, the method's "commands" the
   dry run exercises (`next_command` at step 3, `must_run = ["/dry-close"]` at every step); committed by setup.

## Machine-verified
Ids marked `(computed)` are omitted, never recorded ok, when they would check nothing (`checklist.host_check_ids`).

- `common.claude-version` — `claude --version` is 2.1.281 (the fake reports it; expected value from pins.toml)
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — no plugin installed or vendored
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds
- (computed) `setup.manifest-matches-pass1` — (host) present only when the effective manifest list is not empty
  (the dry arms list none: setup runs once per arm, Task 23, so there is no pass-2 compare)
- (computed) `setup.agent-turns` — (host) present only when setup prompts are configured (none here)

## Owner-verified
- [ ] OV1: dry run (scripted owner).

## Known traps
- None.
