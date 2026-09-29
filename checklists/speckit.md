# Setup checklist — speckit (github/spec-kit 1.0.12)

## Source
research/CANDIDATES.md §1.2; https://github.com/github/spec-kit#get-started,
https://github.github.io/spec-kit/guides/existing-projects.html, https://github.github.io/spec-kit/reference/integrations.html,
https://github.github.io/spec-kit/quickstart.html

## Pins
specify-cli 1.0.12, hash-locked (image bakeoff-arm-speckit:1); Claude Code 2.1.281; model claude-opus-5-5.

## Setup (what the runner runs)
1. `specify init --here --force --integration claude` — the existing-repo route (§1.2 item 3; the repo holds only its empty initial commit). Skills mode: `.claude/skills/speckit-*/`, plus `.specify/` (templates, scripts, `memory/constitution.md` as a template). Verified offline in the pinned image: no prompt without a TTY, exit 0.
2. `specify extension add bug` — the documented bug process (§1.2 item 4, used at step 6 — OD5): `.claude/skills/speckit-bug-{assess,fix,test}/`, registered in `.specify/extensions/.registry`.
3. Agent: `/speckit-constitution <project-principles.md>` (§1.2 item 5) — writes `.specify/memory/constitution.md`.
4. OD24 B with MCP only (§1.2 "Task/issue tracking"; probe P11): `home/.bk-mcp.json` (GitHub MCP server with the arm's Issues-only PAT) when `config/mcp/speckit.json` exists — it does not yet.
5. Commit `Set up github/spec-kit 1.0.12` (design §6: the setup is part of the arm repo's history).

## Machine-verified
Ids marked `(computed)` are omitted, never recorded ok, when they would check nothing; whether they exist is computed from the arm config and the plugin route (`checklist.host_check_ids`), and a computed id that should exist but did not run fails.

- `common.claude-version` — `claude --version` is 2.1.281
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude in the verify container's env, i.e. the image and runner-injected env; the env each arm session actually gets is verified elsewhere (credentials.session_env tests, `00-setup/model-overrides.json`)
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — no plugin installed or vendored
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `speckit.version` — the "CLI Version" row of `specify version` is 1.0.12
- `speckit.skills` — `.claude/skills/speckit-{constitution,specify,clarify,plan,tasks,analyze,implement,converge,taskstoissues}/SKILL.md` exist (§1.2 workflow stages, plus the OD24 export)
- `speckit.bug-skills` — `.claude/skills/speckit-bug-{assess,fix,test}/SKILL.md` exist and the `bug` extension is enabled in `.specify/extensions/.registry`
- `speckit.constitution` — `.specify/memory/constitution.md` is not empty and has no `[UPPER_CASE]` template placeholders (init writes the template, so this fails until the agent turn has run)
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `github.issues-access` — (host) the arm's PAT can list issues and labels of its repo
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds (preflight B4)
- (computed) `setup.agent-turns` — (host) present only when setup prompts are configured: every prompt's last turn ended ok
- (computed) `setup.manifest-matches-pass1` — (host) present only when the effective manifest list is not empty: pass 2's setup files equal pass 1's
- (computed) `speckit.entry-commands` — (host) present only when `[drive]` needs a slash command (entry, bug_entry, must_run, and for OD24 B `export_after` plus `/speckit-taskstoissues`): every one is installed

## Owner-verified
- [ ] OV1: The constitution reads as this project's principles (not the template), and nothing in it goes beyond project-principles.md.
- [ ] OV2: `specify init` printed no warnings about overwritten files (00-setup/shell/01.log).
- [ ] OV3: Telemetry: none documented, or disabled — per probe P9's record for specify-cli (offline scan of the pinned package found no telemetry code; P9 confirms).
- [ ] OV4: OD24: probe P11's finding on `/speckit-taskstoissues` (gh CLI or GitHub MCP) is applied as the owner decided.

## Known traps
- Re-running `specify init --here --force` (the documented upgrade path) **overwrites `.specify/memory/constitution.md`
  and customised templates**. The runner never re-runs init; `step` mode checks the version.
- Skills mode uses the hyphen form `/speckit-<cmd>`; the command reference page still shows `/speckit.<cmd>`. The bug
  extension registers `speckit.bug.<cmd>` and installs the skills `speckit-bug-<cmd>`.
- `specify init` warns that agent folders may hold credentials and suggests ignoring `.claude/`: the runner does not
  (setup files are part of the arm's history, design §6); the PAT lives in the arm's home, never in the repo.
- Four `.specify/` files carry an install timestamp, so pass 2's manifest always differs from pass 1's there, as does the model-written constitution: `setup.manifest-matches-pass1` shows the owner the difference to accept (review G6).
- Single active feature state in `.specify/feature.json`: step 5's two CRs may collide — record, do not intervene.
- `/speckit-taskstoissues` pushes to GitHub Issues **one way** (OD24).
- No project-wide canonical spec; later features can silently stale earlier ones (#620) — what step 3 probes.
