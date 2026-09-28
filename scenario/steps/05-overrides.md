# Step 5 — two change requests (both arrived this week)

## CR-A: keep shared includes shared
Included files are shared between projects. Adding a new setting under an included section must no longer
modify the shared file: it should be added in the including file, as an override. Existing settings still
change where they live.

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

The CLI contract sections in force are listed below; the full contract is attached.

Contract sections in force: General; Includes; set PATH VALUE; history [PATH]; Sync with files; get and show; Lineage; Overrides (replaces rule 2 under "set PATH VALUE").
