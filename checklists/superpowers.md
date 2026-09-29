# Setup checklist — superpowers (obra/superpowers 6.4.2)

## Source
research/CANDIDATES.md §1.1; https://github.com/obra/superpowers#claude-code

## Pins
superpowers 6.4.2 at the tag's verified commit `8ca22dba9a94f28898bbce59f2537ff4d87c747d` (arms/superpowers.toml
`sha`); route per OD9 (`pins.toml [plugins] route`, currently `plugin-dir`); Claude Code 2.1.281; model claude-opus-5-5.

## Setup (what the runner runs)
1. Plugin (§1.1 item 1): route B (plugin-dir, default) — the plugin is vendored at `/opt/plugins/superpowers` in the arm image and loaded with `--plugin-dir`; in pass 1 the documented `claude plugin install superpowers@claude-plugins-official` also runs once into a scratch config as a recorded ergonomics check. Route A — the documented install into the arm's home.
2. No init, no constitution, no required config (§1.1 item 2): nothing is written into the repo, so `manifest_paths` is empty and there is no setup commit.
3. Smoke test (§1.1 item 3): a fresh session in `/work/smoke` receives "Let's make a react todo list" and must invoke `brainstorming`; its transcripts are moved out of the arm's home and `/work/smoke` is deleted.

## Machine-verified
- `common.claude-version` — `claude --version` is 2.1.281
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — only `superpowers`
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `superpowers.plugin-version` — the loaded plugin's `.claude-plugin/plugin.json` version is 6.4.2
- `superpowers.skills` — using-superpowers, brainstorming, writing-plans, subagent-driven-development, test-driven-development, finishing-a-development-branch SKILL.md present (§1.1 "Workflow stages", item 2)
- `superpowers.session-hook` — `hooks/hooks.json` registers a SessionStart hook running `hooks/session-start`, which exists (§1.1 item 2)
- `superpowers.smoke` — (host) the smoke stream invoked `brainstorming` (§1.1 item 3)
- `superpowers.entry-commands` — (host) every command in `[drive]` (its `must_run`) is installed
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID (aliases are remapped, OD2)
- `github.issues-access` — (host) the arm's PAT can list issues and labels of its repo
- `setup.manifest-matches-pass1` — (host) pass 2's setup files equal pass 1's (route A: the plugin cache in the arm's home)
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds (preflight B4)
- `setup.agent-turns` — (host) every configured setup prompt's last turn ended ok (superpowers configures none)

## Owner-verified
- [ ] OV1: The smoke session asked a brainstorming question before writing any code.
- [ ] OV2: Route B: `00-setup/marketplace-check.json` shows the documented install succeeded (pass 1). Route A: the installed version is 6.4.2.
- [ ] OV3: `00-setup/model-overrides.json` lists the method's own subagent model choices; they are reported as overridden (OD2).
- [ ] OV4: Telemetry: none documented, or disabled — per probe P9's record for superpowers.

## Known traps
- Brainstorming's *bounded* path writes no spec file, by design (§1.1 "Workflow stages") — not a setup fault.
- Worktrees are made beside the repo (hence the whole `/work` mount, and the PO's read-only `/work`, OD21).
- SDD dispatches cheaper subagent models; OD2 remaps them to the pin — recorded, reported.
- Reviewer subagents are token-heavy (#1930): cost will be high; cost is not scored.
- Plans record no completion status (#1075).
- superpowers is installed in the owner's own Claude config: `common.no-foreign-plugins` in every *other* arm is
  what catches a leak (CANDIDATES "Implications" 4).
