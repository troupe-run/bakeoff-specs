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

Contract sections in force: General; Includes; show PATH (step 1 and 2); set PATH VALUE; history [PATH].


# Step 2 — keep files and configuration in sync

People edit `.troupe/` files directly, in their editor, while troupe is running. Add
`troupe config watch`, which picks up those edits as they happen, and make every command pick up edits made
while nothing was running. When troupe itself writes a change back to a file, that must not be picked up
again as a new change.

Contract sections added: Sync with files.


# Step 3 — `get` for values, `show` for anything

We are changing `show`. From now on:
- `troupe config get PATH` prints a single value — what `show` used to do.
- `troupe config show [PATH]` prints either a value or a whole section as YAML, and with `--sources` says
  which file each value comes from.

Contract sections added: get and show (replaces "show PATH (step 1 and 2)").


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


# Step 5 — two change requests (both arrived this week)

## CR-A: keep shared includes shared
Included files are shared between projects. Adding a new setting under an included section must no longer
modify the shared file: it should be added in the including file, as an override. Existing settings still
change where they live.

Contract sections added: Overrides (replaces rule 2 under "set PATH VALUE").

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.


Our troupe.yml shares settings between agents with a YAML anchor:

    defaults: &d
      model: opus
    coder:
      settings: *d
    reviewer:
      settings: *d

I ran `troupe config set coder.settings.model sonnet` and now `reviewer` uses sonnet too, and `defaults`
changed. I only meant to change coder.

Expected: changing `defaults.model` changes everyone (that's what the anchor is for). Changing
`coder.settings.model` should not silently change anyone else — refuse, and let me explicitly ask for coder's
copy to be expanded so I can override it.

Contract sections added: Aliases.


# Step 7 — remote includes and a schema

- Includes can now point at `https://` URLs (shared team configuration). They are read-only from troupe's
  point of view: refuse changes to their values, and tell the user which include line to change instead.
- The configuration is described by a JSON Schema at `.troupe/troupe.schema.json`. Some settings are URLs
  that must never be treated as includes; the schema marks those with `"format": "uri"`, and a `!literal` tag
  marks any other value that must be taken literally.

Contract sections added: Remote includes and schema.
