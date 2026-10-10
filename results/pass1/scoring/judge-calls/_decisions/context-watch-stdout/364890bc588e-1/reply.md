```json
{
  "stakes": "`config watch` runs in the background and records hand edits to the config file. The question is what it prints while it runs: anything a script reads from its output depends on that line, and a user has to be able to tell when a broken edit was not recorded.",
  "examples": [
    {
      "input": "`config watch` (with TROUPE_ACTOR=human:owner), then three hand edits to .troupe/troupe.yml: `model: opus` -> `sonnet`, then `retry: [3` (broken YAML), then `retry: 5`; then Ctrl-C (SIGINT)",
      "before": "# troupe settings\nmodel: opus  # default model\nretry: 3\nagents:\n  coder:\n    temperature: 0.2\n",
      "results": {
        "1": "All four arms print one line on stdout, `watching /theatre` (the full directory path), and nothing else. The two good edits print nothing.",
        "2": "Both arms print one line on stdout, `watching .` (relative path, not the full directory), and nothing else. The two good edits print nothing."
      },
      "observed": true
    },
    {
      "input": "the broken edit `retry: [3` while watch is running",
      "before": "",
      "results": {
        "1": "Nothing on stdout. All four arms report it on stderr, each worded differently. One arm: `/theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence, expected ',' or ']', but got ':' (line 4, column 7)`. One arm: `troupe: .troupe/troupe.yml: invalid YAML (line 4, column 7): expected ',' or ']', but got ':'`. One arm: `troupe: cannot parse /theatre/.troupe/troupe.yml: expected ',' or ']', but got ':' at line 4`. One arm prints the parser's full multi-line dump, starting `troupe: error: /theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence` and pointing at `retry: [3` and `agents:` with carets.",
        "2": "Nothing on stdout. Both arms report it on stderr. One arm prints a single line with no location and no reason: `troupe: /theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence`. The other prints the full multi-line parser dump, starting `troupe: ./.troupe/troupe.yml: invalid YAML: while parsing a flow sequence`."
      },
      "observed": true
    },
    {
      "input": "Ctrl-C (SIGINT) to stop watch",
      "before": "",
      "results": {
        "1": "It stops in every arm. Three arms exit 0; one arm exits 137.",
        "2": "It stops in both arms. One arm exits 0; one arm exits 137."
      },
      "observed": true
    },
    {
      "input": "`config history` afterwards",
      "before": "",
      "results": {
        "1": "exit 0 in all arms. Three import entries, then `model` opus->sonnet and `retry` 3->5, both `via: file`. The broken edit left no entry. Actor is recorded as `unknown`, even though watch ran with TROUPE_ACTOR=human:owner.",
        "2": "Same in both arms: three import entries, then `model` opus->sonnet and `retry` 3->5 via file, no entry for the broken edit, actor `unknown`."
      },
      "observed": true
    }
  ],
  "in_practice": "On both routes, watch prints only its start line, so the only way to see what it recorded is `config history`. The routes differ mainly in that line: route 1 names the full directory, while route 2 prints `.`. On both routes the error for a broken edit appears only on stderr and its wording differs from arm to arm; one route-2 arm gives no line number or reason. On each route, one arm exits 137 instead of 0 on Ctrl-C.",
  "tradeoff": "Route 1: the start line names the full directory, but you have to run history to see what was recorded. Route 2: the same quiet output with a less informative `watching .` line, and in one arm a broken-edit error with no location."
}
```