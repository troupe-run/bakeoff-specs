# Setup checklist — openspec (Fission-AI/OpenSpec 1.13.2)

## Source
research/CANDIDATES.md §1.3; https://github.com/Fission-AI/OpenSpec#quick-start,
https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md, https://github.com/Fission-AI/OpenSpec/blob/main/docs/supported-tools.md

## Pins
@fission-ai/openspec 1.13.2 from a committed package-lock (image bakeoff-arm-openspec:1, which also satisfies
§1.3 item 1, Node ≥ 20.19.0, with Node 22); Claude Code 2.1.281; model claude-opus-5-5.

## Setup (what the runner runs)
1. `openspec init --tools claude` — the documented non-interactive form, default profile `core` (§1.3 item 3). Creates `.claude/skills/openspec-*/`, `.claude/commands/opsx/` (§1.3 item 7) and `openspec/` with `config.yaml`.
2. `openspec config set telemetry.enabled false` — writes the global config in the arm's home, `~/.config/openspec/config.json` (§1.3 "Maturity" telemetry opt-out; design §6); the env var `OPENSPEC_TELEMETRY=0` is also set (arm env and base image).
3. Project context (§1.3 item 5; OD22): `openspec/config.yaml` gets a `context: |` block holding `project-principles.md` verbatim; the step refuses a config that already has a context.
4. Commit `Set up Fission-AI/OpenSpec 1.13.2` (design §6: the setup is part of the arm repo's history).

## Machine-verified
Ids marked `(computed)` are omitted, never recorded ok, when they would check nothing; whether they exist is computed from the arm config and the plugin route (`checklist.host_check_ids`), and a computed id that should exist but did not run fails.

- `common.claude-version` — `claude --version` is 2.1.281
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude in the verify container's env, i.e. the image and runner-injected env; the env each arm session actually gets is verified elsewhere (credentials.session_env tests, `00-setup/model-overrides.json`)
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — no plugin installed or vendored
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `openspec.version` — `openspec --version` is 1.13.2
- `openspec.skills` — the `core` profile's six skills: `.claude/skills/openspec-{propose,explore,apply-change,update-change,sync-specs,archive-change}/SKILL.md`
- `openspec.commands` — `.claude/commands/opsx/{propose,apply,archive,update,sync,explore}.md` exist
- `openspec.tree` — `openspec/specs/` and `openspec/changes/` exist and `openspec/config.yaml` has `schema: spec-driven`
- `openspec.telemetry-off` — `openspec config get telemetry.enabled` prints false, and OPENSPEC_TELEMETRY=0 in the verify container's env (the image and runner-injected env; the env each arm session gets is verified elsewhere, via `credentials.session_env` and the arm's `env`)
- `openspec.context` — `openspec/config.yaml`'s `context`, parsed with OpenSpec's own YAML library, is exactly `project-principles.md`
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `github.issues-access` — (host) the arm's PAT can list issues and labels of its repo
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds (preflight B4)
- (computed) `setup.agent-turns` — (host) present only when setup prompts are configured: every prompt's last turn ended ok
- (computed) `setup.manifest-matches-pass1` — (host) present only when the effective manifest list (`manifest_paths`, plus `~/.claude/plugins/cache` on route A) is not empty: pass 2's setup files equal pass 1's
- (computed) `openspec.entry-commands` — (host) present only when `[drive]` needs a slash command (entry, bug_entry, must_run): every one is installed

## Owner-verified
- [ ] OV1: `openspec/config.yaml` differs from the `openspec init` template only by the appended `context` block.
- [ ] OV2: `openspec init` printed no errors (00-setup/shell/01.log).

## Known traps
- Telemetry is on by default — must be off (§1.3 "Maturity"; design §6).
- The `openspec/` path is not configurable (#697).
- `openspec update` is needed after upgrades (§1.3 item 6) — none are allowed mid-bake-off (design §2).
- The optional expanded workflow (`openspec config profile`, §1.3 item 4) is not set up: the documented default is `core`.
- Behaviour when two changes touch the same requirement is undocumented [UNVERIFIED] — step 5 exercises it (OD6).
