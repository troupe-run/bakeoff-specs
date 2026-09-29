<!-- checklists/README.md -->
# Owner one-time steps

1. In your own terminal (never in an agent session): `claude setup-token`, then
   `security add-generic-password -s bakeoff-claude-oauth -a "$USER" -w` and paste the token.
2. Confirm that the subscription terms allow this use (spike B open question 1).
3. For each pass: run the commands `uv run python -m runner github-plan <pass>` prints (private repos), create one
   fine-grained PAT per GitHub-tracker arm as it describes (**expiry 45 days**), store each under
   `bakeoff-gh-<pass>-<arm>`, then `uv run python -m runner github-verify <pass>` must pass.
4. Enable the results secret-scan hook once: `git config core.hooksPath .githooks` (Task 21).
5. Keep the machine otherwise idle during runs.
6. At the end of pass 1: revoke every pass-1 PAT (GitHub → Settings → Developer settings → Fine-grained tokens).
