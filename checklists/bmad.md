# Setup checklist — bmad (bmad-code-org/BMAD-METHOD 6.12.0) — PARKED

## Source
research/CANDIDATES.md §1.5; https://docs.bmad-method.org/start/build-your-first-change/,
https://github.com/bmad-code-org/BMAD-METHOD#start-building. The arm is PARKED (preflight B2; arms/bmad.toml): no
image can be built, so setup refuses to start. See "Parked" below for what was checked against the sources.

## Pins
bmad-method and bmad-core-tools 6.12.0 at the verified commit (arms/bmad.toml `sha`, empty while parked); route
per OD9; Claude Code 2.1.281; model claude-opus-5-5. The base image carries the §1.5 item 1 prerequisites
(Node, Python 3, `uv`, Git).

## Setup (what the runner runs)
1. Plugins (§1.5 item 2, Claude Code plugin route): route B vendored at `/opt/plugins/{bmad-method,bmad-core-tools}` (pass 1 also runs the documented marketplace install into a scratch config as an ergonomics check); route A installs into the arm's home.
2. The arm's GitHub PAT and `GH_REPO` are in place before any setup prompt, since origin is local (design §6; preflight M4, B4).
3. Agent: "Use the bmad skill to run `bmad setup`." (§1.5 item 3) — creates `_bmad/` and `_bmad-output/`.
4. Agent: configure `bmad-preview-ticketing` with the `gh` store starter for this repository's GitHub Issues (§1.5 item 5; design §2 tracker column) — writes `_bmad/custom/ticketing-store-config.toml`.
5. Agent: the principles, with an instruction to record them where BMAD keeps project-level constraints and do nothing else with them (§1.5 "Change handling"; OD22, review F-7). `bmad-project-context` is skipped: §1.5 item 4 marks it optional.
6. Post-shell: `uv lock --script` for every `_bmad/scripts/*.py` and `_bmad/*/scripts/*.py` with PEP 723 metadata (§1.5 "Claude Code integration": skills shell out to `uv run`; review S-5).
7. Commit `Set up bmad-code-org/BMAD-METHOD 6.12.0` (design §6).

## Machine-verified
- `common.claude-version` — `claude --version` is 2.1.281
- `common.isolation-env` — CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 and CLAUDE_CONFIG_DIR=/home/actor/.claude
- `common.git-identity` — repo identity is the neutral `Developer`
- `common.no-foreign-plugins` — only `bmad-core-tools bmad-method`
- `common.origin` — `origin` is the local bare repo `/home/actor/origin.git` and its `main` resolves (preflight B4)
- `bmad.plugin-version` — both plugins' `plugin.json` versions start with 6.12
- `bmad.setup-done` — `_bmad/config.toml` (the team config `bmad setup` writes) and `_bmad-output/` exist
- `bmad.ticketing-gh` — `_bmad/custom/ticketing-store-config.toml` has `[tickets] store = "github"` (the gh starter's value), and its `repo`, if set, is this arm's `GH_REPO`
- `bmad.scripts-locked` — at least one `_bmad/scripts/*.py` exists, and every `_bmad/scripts/*.py` and `_bmad/*/scripts/*.py` with a `# /// script` block has a `.lock` beside it
- `common.no-foreign-model-ids` — (host) no installed file names a full non-pinned model ID
- `github.issues-access` — (host) the arm's PAT can list issues and labels of its repo
- `setup.manifest-matches-pass1` — (host) pass 2's setup files (`_bmad`) equal pass 1's
- `setup.origin-push` — (host) `git push origin main` to the local bare origin succeeds (preflight B4)
- `setup.agent-turns` — (host) each of the three setup prompts' last turn ended ok

## Owner-verified
- [ ] OV1: `bmad setup` completed without errors (read the setup turn in 00-setup/turns/).
- [ ] OV2: Ticketing points at this pass's GitHub repo: `repo` in the ticketing config is the slug, or empty with `GH_REPO` set — never the local origin path.
- [ ] OV3: The principles were recorded, and where (note the file) — nothing beyond the text was added.
- [ ] OV4: Telemetry: none documented, or disabled — per probe P9's record for BMAD.

## Known traps
- Skills refuse to run before `bmad setup` (§1.5 item 3; bmad-correct-course Step 4).
- Ticketing is a **preview** feature; internals change between minors, so the version is pinned (§1.5 "Maturity").
- Skills shell out to `uv run _bmad/scripts/*.py`; PEP 723 deps are locked at setup (PyPI stays on the run allowlist for the arm's own `uv add`).
- The process sizes itself to the work (trivial / one session / epic / project): record which path each step took.
- The gh ticketing starter's empty `repo` means "the repo of the current checkout (origin)"; here origin is the
  local bare repo (B4), so `gh` relies on `GH_REPO` (M4). OV2 checks the result.
- `_bmad-output/` is empty after setup and git does not track empty directories: it is checked in the work tree,
  not in the setup commit, and not listed in `manifest_paths`.

## Parked
Checked on 2026-09-29 against GitHub (not reachable from the arm; recorded for the unpark decision, B2):
- `bmad-code-org/bmad-plugins` has no tags. Its `main` marketplace lists `bmad-method` (`./plugins/method`) and
  `bmad-toolbox` (`./plugins/toolbox`) — not `bmad-core-tools` — at version `6.13.0-next`, with `strict: false`
  and no `.claude-plugin/plugin.json` inside either plugin dir. The image's `test -f .../plugin.json` and
  `bmad.plugin-version` both assume a plugin.json; the version would have to come from `marketplace.json`.
- `BMAD-METHOD` tag `v6.12.0` has no `bmad` hub skill (so no `bmad setup`) and no ticketing skill; both exist
  only on `main`, where the ticketing skill is now named `bmad-ticket` (CANDIDATES' `bmad-preview-ticketing`).
  The gh starter (`skills/bmad-ticket/config/gh-ticketing.toml` on `main`) writes `store = "github"`.
- `bmad setup` on `main` also writes `_bmad/<module>/scripts/` (setup.py), hence step 6's second glob.
So the pinned 6.12.0 and the documented setup (CANDIDATES §1.5) do not describe the same release. This checklist
follows §1.5 as written; the pins, plugin names and skill names need revisiting together when unparking.
