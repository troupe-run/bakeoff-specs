# Step 2 — keep files and configuration in sync

People edit `.troupe/` files directly, in their editor, while troupe is running. Add
`troupe config watch`, which picks up those edits as they happen, and make every command pick up edits made
while nothing was running. When troupe itself writes a change back to a file, that must not be picked up
again as a new change.

Contract sections added: Sync with files.
