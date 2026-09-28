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
