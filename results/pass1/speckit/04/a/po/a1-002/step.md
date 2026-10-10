# Step 4 — lineage

Configuration changes in troupe are made by people and by AI agents. We need a history we can audit: for any
setting, we must be able to answer:

- **Who changed it?** A human or an agent, and which one.
- **How?** Through the CLI, by editing a file, or by the first import.
- **When?** A UTC timestamp.
- **Why?** An optional reason given with the change (`troupe config set --reason "…"`).
- **What else changed with it?** Every change one command makes shares one change id, so a multi-value change
  can be seen as a unit.

Where something is genuinely unknown — an edit made in a text editor has no known author — say so explicitly
rather than guessing. Lineage must survive restarts and be readable through `troupe config history`.

Contract sections added: Lineage.
