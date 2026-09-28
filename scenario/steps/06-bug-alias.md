# Setting one agent's model changed another agent's model

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

The CLI contract sections in force are listed below; the full contract is attached.

Contract sections in force: General; Includes; set PATH VALUE; history [PATH]; Sync with files; get and show; Lineage; Overrides; Aliases (from step 6).
