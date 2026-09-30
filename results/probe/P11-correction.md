# P11 correction

`P11.json` records `"route": "unknown"` for Spec Kit 1.0.12's `speckit-taskstoissues` skill. That is a misread by
the probe, not a property of the skill: the skill uses **the GitHub MCP server** to create issues. The probe's
classifier did not recognise the skill's wording "the GitHub MCP server"; it was fixed in commit `b0c7e04` (runner:
probe P11 recognises 'the GitHub MCP server' phrasing), with a test. `P11.json` is left as the probe wrote it.

Consequence: with the export needing an arm-specific MCP server, the owner switched **OD24 to A** on 2026-09-30
(`export_after = ""` in `runner/config/arms/speckit.toml`; design §11): the runner no longer forces Spec Kit's
taskstoissues export, and no arm has an MCP server.
