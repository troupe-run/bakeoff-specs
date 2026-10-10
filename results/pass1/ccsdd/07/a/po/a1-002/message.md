Both step-7 specs are written, approved through the `-y` fast-track and committed on `main` (not pushed). No code is written yet, so step 7's contract isn't met until both specs are implemented.

| Spec | Requirements | Design components | Sub-tasks |
|---|---|---|---|
| config-remote-includes | 9 | 9 | 16 |
| config-schema-literals | 11 | 11 | 19 |

config-remote-includes went through two runs of its tasks phase:
- **First run:** the task review failed on both of its allowed passes, because of missing task dependencies.
- **Second run:** I ran the phase again with fresh reviewers. They found that requirement 5.4 wasn't covered: an error inside remote content would have shown an internal placeholder path instead of the URL. After that fix the review passed.

**Cross-spec review**
- **Round 1:** one important issue and six minor ones. The important one would have lost data: `set notes file:notes.txt` on an existing text include would have overwritten `notes.txt` with the literal text `file:notes.txt`. Now a VALUE equal to the include string already at that place leaves the file unchanged, with or without `--include`. That includes the `$ref` form without overrides.
- **Round 2:** all seven fixed. I then fixed three new minor issues myself:
  - Reworded when the new anchor/alias refusal runs, so the requirements match the design.
  - Recorded the reverse anchor/alias case as accepted (it fails safely with exit 3) and added a test for it.
  - Filled in two roadmap entries.

**Choices worth checking** (each is recorded in its spec's `research.md`):
- **Behaviour change:** `set` now writes include-looking strings as `!literal` even when the theatre has no schema. Tests that relied on the old behaviour get `--include`.
- **Include line refused:** running `set` on a remote include line itself (for example to point it at another URL) is refused, consistent with how `file:` includes already behave.
- **Existing URL settings:** theatres that already hold `https://` values, such as a webhook, will start fetching them. A schema `format: uri` entry or a `!literal` tag stops that.
- **Schema references:** the `jsonschema` library fetches a schema's remote `$ref` targets by default; the design turns that off.

The two step-7 boxes in the roadmap are still unchecked. Here `[x]` has meant "implemented", and each spec's task 5.2 ticks its own box. The notes owed to six existing specs (now including config-aliases) are written by task 5.2 of each spec, not by this batch.

**Commits:**
- `84ac84f`: config-remote-includes
- `72c76c0`: config-schema-literals and the cross-spec fixes

**Next:** `/kiro-impl config-remote-includes`, then `/kiro-impl config-schema-literals`.