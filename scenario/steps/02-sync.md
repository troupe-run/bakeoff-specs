# Step 2 — keep files and configuration in sync

People edit `.troupe/` files directly, in their editor, while troupe is running. Add
`troupe config watch`, which picks up those edits as they happen, and make every command pick up edits made
while nothing was running. When troupe itself writes a change back to a file, that must not be picked up
again as a new change.

The CLI contract sections in force are listed below; the full contract is attached.

Contract sections in force: General; Includes; show PATH (step 1 and 2); set PATH VALUE; history [PATH]; Sync with files.
