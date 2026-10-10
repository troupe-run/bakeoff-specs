# Step 5 — a change request

## CR-A: keep shared includes shared
Included files are shared between projects. Adding a new setting under an included section must no longer
modify the shared file: it should be added in the including file, as an override. Existing settings still
change where they live.

Contract sections added: Overrides (replaces rule 2 under "set PATH VALUE").
