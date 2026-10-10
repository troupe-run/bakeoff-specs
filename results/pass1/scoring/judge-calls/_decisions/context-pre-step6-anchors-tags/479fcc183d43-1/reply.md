```json
{
  "stakes": "This is about config files that use YAML anchors, aliases, merge keys (`<<: *d`) or explicit tags (`!!str`, `!!bool`, `!!float`). Depending on the route, a user is blocked from reading the file at all, reads values with the wrong type, or edits one key and changes other keys that share it without being told.",
  "examples": [
    {
      "input": "`config show`",
      "before": "defaults: &d\n  model: opus\n  port: !!str 8080\ncoder:\n  settings: *d\nreviewer:\n  <<: *d\n  model: sonnet\nflags:\n  enabled: !!bool \"true\"\n  ratio: !!float 1",
      "results": {
        "1": "exit 4, prints nothing. The file cannot be read at all. One arm: `defaults.port: explicit tag '!!str' is not supported`; one arm: `cannot parse ...: tags are not supported at line 3`. Every other command (`history`, `set`) fails the same way.",
        "2": "exit 0; the tags are honoured and the merge is resolved:\nport: '8080'\n...\nreviewer:\n  port: '8080'\n  model: sonnet\nflags:\n  enabled: true\n  ratio: 1.0",
        "3": "exit 0; the tags are ignored (port becomes a number, enabled becomes a string) and `<<` is shown as an ordinary key:\nport: 8080\n...\nreviewer:\n  <<:\n    model: opus\n    port: 8080\n  model: sonnet\nflags:\n  enabled: 'true'\n  ratio: 1",
        "4": "exit 0; the tags are honoured, but `<<` is shown as an ordinary key:\nport: '8080'\n...\nreviewer:\n  <<:\n    model: opus\n    port: '8080'\n  model: sonnet\nflags:\n  enabled: true\n  ratio: 1.0",
        "5": "exit 0; the tags are ignored but the merge is resolved:\nport: 8080\n...\nreviewer:\n  port: 8080\n  model: sonnet\nflags:\n  enabled: 'true'\n  ratio: 1"
      },
      "observed": true
    },
    {
      "input": "`config set reviewer.port 9090` (reviewer gets port only through `<<: *d`)",
      "before": "",
      "results": {
        "1": "exit 4, same parse error as above; file unchanged",
        "2": "exit 3: `reviewer.port is supplied by the merge key reviewer.<<; troupe never writes merge keys (--expand-alias cannot help), so edit the file by hand`; file unchanged",
        "3": "exit 0; the file now reads:\nreviewer:\n  <<: *d\n  model: sonnet\n  port: 9090",
        "4": "exit 0; the file now reads:\nreviewer:\n  <<: *d\n  model: sonnet\n  port: 9090",
        "5": "exit 3: `write refused: reviewer.port comes from a merge key (<<: *d), and merge keys are never written. Set it at the anchor, or use --expand-alias to give it its own key here`; file unchanged"
      },
      "observed": true
    },
    {
      "input": "`config set defaults.port '\"9091\"'` (the anchored key, shared by coder and reviewer)",
      "before": "",
      "results": {
        "1": "exit 4, same parse error; file unchanged",
        "2": "exit 3: `defaults.port: cannot rewrite this value safely (unsupported tag or block layout)`; file unchanged",
        "3": "exit 0, no warning; the `!!str` tag is dropped and the file now reads:\ndefaults: &d\n  model: opus\n  port: '9091'\nHistory records this one command as three changes: defaults.port, coder.settings.port and reviewer.<<.port, all 8080 -> \"9091\"",
        "4": "exit 0, no warning; the `!!str` tag is dropped and the file now reads:\ndefaults: &d\n  model: opus\n  port: '9091'\nHistory records three changes: defaults.port, coder.settings.port and reviewer.<<.port, all \"8080\" -> \"9091\"",
        "5": "exit 0, no warning; the tag is kept and the file now reads:\ndefaults: &d\n  model: opus\n  port: !!str '9091'\nHistory records three changes: defaults.port, coder.settings.port and reviewer.port, all 8080 -> \"9091\""
      },
      "observed": true
    }
  ],
  "in_practice": "On routes 3, 4 and 5, changing an anchored key also changes every key that points to it. The command exits 0 and prints nothing about it; you only see it in `history`. Routes 3 and 5 also read `port: !!str 8080` as the number 8080 and `enabled: !!bool \"true\"` as the string 'true', so a value's type can differ from what the file says. Routes 3 and 4 show `<<` in `show` and in history paths as if it were a real key.",
  "tradeoff": "Route 1 locks you out of any file that uses these features, even for reading. Route 2 reads correctly but refuses both edits. Routes 3 and 4 accept every edit and silently change shared keys, and route 3 also gets types wrong. Route 5 keeps the tags and refuses edits to merged keys, but still gets types wrong on read and silently changes shared keys when you edit an anchor."
}
```