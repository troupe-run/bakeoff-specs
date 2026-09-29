# Setup checklist — speckitty (spec-kitty/spec-kitty 3.2.7 + beads 1.3.0)

## Source
research/CANDIDATES.md §1.4 (+ beads §2.1); https://github.com/spec-kitty/spec-kitty#quick-start,
https://github.com/spec-kitty/spec-kitty/blob/main/docs/api/cli-commands.md,
https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/2.x/2026-02-27-1-cli-tracker-surface-gated-by-saas-sync-flag.md,
https://github.com/gastownhall/beads#readme, https://github.com/gastownhall/beads/blob/main/docs/integrations/claude-code.md

## Pins
spec-kitty-cli 3.2.7 (hash-locked; never a 4.0 RC) and @beads/bd 1.3.0 (package-lock; binary SHA-256 in
images.lock.json) in bakeoff-arm-speckitty:1; Claude Code 2.1.281; model claude-opus-5-5.

## Setup (what the runner runs)
Every step was run offline against the pinned CLIs in bakeoff-arm-speckitty:1 (Task 11); none needs the network.

1. `spec-kitty init . --ai claude` (§1.4 item 2, existing repo; non-interactive without a TTY). Writes `.kittify/`, the repo's `.claude/{skills,agents,settings.json,CLAUDE.md}` (SessionStart `spec-kitty session-start`, Stop `spec-kitty session-stop`), `.gitignore` (which ignores `.claude/`), `.gitattributes`, `.claudeignore` — and the `/spec-kitty.*` commands and most skills **user-scope**, in `$CLAUDE_CONFIG_DIR/{commands,skills}`.
2. `spec-kitty verify-setup` (§1.4 item 3).
3. `bd metrics off` (design §6, telemetry off; beads §2.1): bd 1.3.0 sends anonymous usage metrics by default (its first-run notice, endpoint shown by `bd metrics`). The opt-out is user-scope (`~/.config/bd/config.yaml`), so it runs before any other `bd` command.
4. `bd init` (beads §2.1 install). In 1.3.0 this also installs the Claude integration (CLAUDE.md beads section, SessionStart `bd prime --hook-json` in `.claude/settings.json`, merged with spec-kitty's hooks), AGENTS.md and Codex/Cursor surfaces, git hooks (`core.hooksPath=.beads/hooks`), a Dolt remote on the local origin, and **commits** `bd init: initialize beads issue tracking` as the arm's identity.
5. `bd setup claude` (beads §2.1: "a SessionStart hook running `bd prime`"; review G2) — the documented step, run although `bd init` already registered the hook (it reports "Hook already registered").
6. `SPEC_KITTY_ENABLE_SAAS_SYNC=1 spec-kitty tracker bind --provider beads --workspace beads` (§1.4 "Task/issue tracking"; review G1). In 3.2.7 the `tracker` group only exists with that flag (the ADR above); a local provider needs `--provider` and `--workspace` (`beads` is the connector's own default workspace); no `--credential` (the connector then runs `bd` in the repo).
7. The egress decision (§1.4: local providers "require a recorded egress decision since 3.2.6rc1"; review G1): `tracker.egress: permitted` in `.kittify/config.yaml`, written through spec-kitty's own config loader/saver. No command writes it; spec-kitty's remedy text says "record `tracker.egress: permitted` in this project's own .kittify/config.yaml". It grants only the local subprocess (`bd`); the hosted service stays refused (no hosted-sync consent).
8. Agent: `/spec-kitty.charter <project-principles.md>` (§1.4 item 4) — writes `.kittify/charter/{charter.md,charter.yaml}` (its own command file).
9. Commit `Set up spec-kitty/spec-kitty 3.2.7` (design §6) — in the arm container, so beads' git hooks (`core.hooksPath=.beads/hooks`) run where `bd` exists (review S-1). Verified: this commit and `setup.origin-push` both succeed with the hooks active and bd's Dolt remote on the origin, under `--network none` and `GIT_CONFIG_GLOBAL=/dev/null` (test_verify_docker, Task 11 FR1).

## Machine-verified
Ids marked `(computed)` are omitted, never recorded ok, when they would check nothing; whether they exist is computed from the arm config and the plugin route (`checklist.host_check_ids`), and a computed id that should exist but did not run fails.

- `common.claude-version` — `claude --version` is 2.1.281
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude in the verify container's env, i.e. the image and runner-injected env; the env each arm session actually gets is verified elsewhere (credentials.session_env tests, `00-setup/model-overrides.json`)
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — no plugin installed or vendored
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `speckitty.version` — `spec-kitty --version` is exactly 3.2.7 (an rc suffix fails)
- `beads.version` — `bd version` is exactly 1.3.0
- `speckitty.verify-setup` — `spec-kitty verify-setup` exits 0 on the read-only mounts. Measured in 3.2.7: it fails when a `/spec-kitty.*` command file is missing (it tries to reinstall it and the read-only mount refuses); it does not notice a deleted managed skill or a changed managed file (no machine check here covers those in pass 1; in pass 2 the manifest comparison does)
- `speckitty.charter` — `.kittify/charter/charter.md` and `.kittify/charter/charter.yaml` exist and are not empty (fails until the agent turn has run)
- `speckitty.commands` — `$CLAUDE_CONFIG_DIR/commands/spec-kitty.{charter,specify,plan,tasks,implement,review,accept,merge}.md` exist (the §1.4 workflow stages)
- `speckitty.session-hook` — a SessionStart hook runs `spec-kitty session-start` (user or project settings): `bd`'s settings edits kept init's hook
- `speckitty.tracker-binding` — `spec-kitty tracker status` (with the SaaS-sync flag) reports `provider: beads` and `workspace: beads`
- `speckitty.tracker-egress` — `.kittify/config.yaml`'s `tracker.egress` is `permitted`, and spec-kitty's own verdict for the local subprocess destination is not refused
- `speckitty.hosted-egress-refused` — spec-kitty's own verdict for the hosted-service destination (its SaaS) is refused: no hosted-sync consent is recorded, so nothing goes to spec-kitty's service
- `beads.init` — `.beads/config.yaml` exists and `bd --readonly --sandbox list --all --json` succeeds (an initialised database)
- `beads.claude-hook` — a SessionStart hook running `bd prime` is in the arm's settings (user or project)
- `beads.metrics-off` — `bd metrics` reports "Anonymous usage metrics: OFF"
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds (preflight B4)
- (computed) `setup.agent-turns` — (host) present only when setup prompts are configured: every prompt's last turn ended ok
- (computed) `setup.manifest-matches-pass1` — (host) present only when the effective manifest list is not empty: pass 2's setup files equal pass 1's
- (computed) `speckitty.entry-commands` — (host) present only when `[drive]` needs a slash command (entry, bug_entry, must_run): every one is installed

## Owner-verified
- [ ] OV1: The tracker binding is beads and its egress decision is `permitted` (00-setup/shell/06.log and 07.log). The verdicts themselves — local subprocess permitted, hosted service refused — are machine-checked (`speckitty.tracker-egress`, `speckitty.hosted-egress-refused`).
- [ ] OV2: `spec-kitty dashboard` is not running (optional, off).
- [ ] OV3: The `bd setup claude` hook is as the beads docs describe (runs `bd prime` at session start), and spec-kitty's own SessionStart/Stop hooks are still there beside it.
- [ ] OV4: Telemetry: none documented, or disabled — per probe P9's record for spec-kitty and beads (beads metrics are machine-checked off; spec-kitty's upgrade-check notice and its SaaS sync paths are not telemetry but are recorded by P9).
- [ ] OV5: The charter reads as this project's principles, and nothing in it goes beyond project-principles.md.

## Known traps
- 4.0 RCs are on `main`; pin 3.2.7 exactly (design §2).
- Renames: `constitution` became `charter`; `--feature` was removed.
- **The tracker surface is behind `SPEC_KITTY_ENABLE_SAAS_SYNC=1` in 3.2.7.** Provisional ruling (the owner may flip
  it): the flag is OFF in arm sessions — `env` in `arms/speckitty.toml` sets it to `"0"`, one commented switch, so
  turning it on is a config change. Setup and the verify script set it to 1 only for their own `tracker` commands.
  **With the flag off, the spec-kitty→beads binding is inert during runs**: the arm's spec-kitty cannot see or use the
  `tracker` group, so nothing syncs work packages to beads through spec-kitty. The arm still gets beads through bd's
  own Claude integration — the SessionStart `bd prime` hook (`beads.claude-hook`), CLAUDE.md's beads section and the
  `bd` CLI — and the step-6 bug arrives as a beads issue either way (runner/tracker.py).
- `spec-kitty init`'s `.gitignore` ignores `.claude/`: the repo's `.claude/` (skills, agents, settings with the hooks)
  is never committed, so the arm's git history does not carry it; snapshots (home + work) do.
- `/spec-kitty.*` commands live in the arm's home (`$CLAUDE_CONFIG_DIR/commands`), not in the repo.
- `bd init` commits on its own and writes Codex/Cursor/AGENTS.md surfaces beside Claude's (1.3.0 defaults, left as-is);
  `spec-kitty init` also writes other agents' global surfaces into the arm's home (`~/.cursor`, `~/.gemini`, `~/.kiro`,
  …). Those home surfaces are not in the manifest; the repo's are.
- Four `.kittify` files carry per-run ids or timestamps and the charter is model-written: they are `volatile_paths`,
  left out of the pass-2 manifest comparison (each install stamp is proven to differ between two offline setups; the
  charter is OV5's). A trade-off: `.kittify/config.yaml`'s other keys are then not compared across passes — only its
  tracker keys are machine-checked.
- #4891: accept silently skips the acceptance gate when `lanes.json` is absent — evidence records whether `lanes.json` existed at accept.
- #4889: implement re-cuts deleted lane branches.
- **beads schema upgrades from one designated clone only**: this repo is the only clone; `bd migrate` is never run.
- beads installs git hooks that call `bd`: every commit the runner makes (setup, teammate) runs in the arm container (review S-1).
- `bd init` points a Dolt remote at the local origin (`git+file:///home/actor/origin.git`); nothing leaves the machine.
