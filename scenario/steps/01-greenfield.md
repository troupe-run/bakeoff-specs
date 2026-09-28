# Step 1 — troupe configuration: load, show, set

troupe is an AI orchestration tool. Each project ("theatre") keeps its configuration in `.troupe/troupe.yml`,
which can be split across files with includes. Build the configuration subsystem:

- Load the configuration, following includes.
- Hold the configuration as an event-sourced projection, using the `eventsourcing` library, persisted under
  `.troupe/` so it survives between commands.
- `troupe config show PATH` prints a setting's value.
- `troupe config set PATH VALUE` changes a setting and writes the change back into whichever file it lives
  in. People edit these files by hand and review their diffs, so a write-back must change only the bytes of
  the value being changed — comments, formatting, quoting and layout elsewhere must be untouched.
- `troupe config history [PATH]` lists the changes.

Python 3.12+, managed with uv; the CLI must run as `uv run troupe config …` from the repository root.

The CLI contract sections in force are listed below; the full contract is attached.

Contract sections in force: General; Includes; show PATH (step 1 and 2); set PATH VALUE; history [PATH].
