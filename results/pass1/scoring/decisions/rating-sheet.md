# Decision review: rating sheet

Rate every route, one-offs first. Read the whole topic - every route - before rating any of it. After `rating:` write 1-5 (half steps such as 3.5 allowed) or n/a; after `reason:` you may write one line (optional) - it becomes cited evidence. Leave the `##` and `### Route` headings as they are.

| Rating | Meaning |
|---|---|
| 5 | what you'd want; nothing better was available |
| 4 | sound, with a minor cost or a missed nicety |
| 3 | works, but with a real cost or risk you'd want fixed |
| 2 | a problem: wrong for some realistic case |
| 1 | wrong or harmful: loses data, misleads, or breaks a stated preference |
| n/a | not a real choice, or it does not matter |

Routes are anonymous: which arm took which route is hidden. "not considered" is a route too: if the topic mattered, missing it is a weakness; if it did not, not considering it can be acceptable and deciding it may have been over-engineering. `proposed:` is the aligning judge's suggestion; your rating decides.

Extraction: every step's decisions were extracted.

# One-offs (8)

## T1

**Question:** How a UTF-8 BOM is handled  
**Kind:** one-off

**What's at stake:** Some config files start with an invisible byte-order mark (BOM), which Windows editors often add. When a file like that is read and edited, the user can lose the mark, get the first key read wrongly (for example as "\ufeffmodel" instead of "model"), or see the edit land in the wrong place in the file.

**What each route does** (run against every arm's final code):

**Example 1:** `config get model` _(observed)_

Starting file:

~~~
.troupe/troupe.yml (starts with a BOM):
﻿model: opus  # main model
retry: 3
coder: file:agents/coder.yaml
~~~

- Route 1: exit 0; prints `opus`. The first key is read correctly despite the BOM.
- Route 2: All five arms: exit 0; prints `opus`.

**Example 2:** `config set model sonnet-4` _(observed)_

Starting file:

~~~
.troupe/troupe.yml (starts with a BOM):
﻿model: opus  # main model
retry: 3
coder: file:agents/coder.yaml
~~~

- Route 1: exit 0, no output; the file still starts with the BOM and now reads:

  ~~~
  ﻿model: sonnet-4 # main model
  retry: 3
  coder: file:agents/coder.yaml
  (the comment is kept, but the two spaces before it become one)
  ~~~

- Route 2: All five arms: exit 0, no output; the file still starts with the BOM and now reads:

  ~~~
  ﻿model: sonnet-4 # main model
  retry: 3
  coder: file:agents/coder.yaml
  (the comment is kept, but the two spaces before it become one)
  ~~~


**Example 3:** `config set coder.temperature 0.55` (the value lives in an included file that also starts with a BOM) _(observed)_

Starting file:

~~~
.troupe/agents/coder.yaml (starts with a BOM):
﻿temperature: 0.2  # sampling
name: coder
~~~

- Route 1: exit 0, no output; the BOM is kept and .troupe/agents/coder.yaml now reads:

  ~~~
  ﻿temperature: 0.55 # sampling
  name: coder
  ~~~

- Route 2: All five arms: exit 0, no output; the BOM is kept and .troupe/agents/coder.yaml now reads:

  ~~~
  ﻿temperature: 0.55 # sampling
  name: coder
  ~~~


**Example 4:** `config show --sources` (after both sets) _(observed)_

- Route 1: exit 0; prints:

  ~~~
  model: sonnet-4 # from .troupe/troupe.yml
  retry: 3 # from .troupe/troupe.yml
  coder:
    temperature: 0.55 # from .troupe/agents/coder.yaml
    name: coder # from .troupe/agents/coder.yaml
  ~~~

- Route 2: All five arms: exit 0; same output as route 1.

**Example 5:** `config history model` _(observed)_

- Route 1: exit 0; two entries: the import of `opus`, then a set from `opus` to `sonnet-4` by human:owner via the CLI.
- Route 2: All five arms: exit 0; same two entries (only the timestamps and IDs differ).

**In practice:** Nothing in these tests tells the two routes apart. Every implementation on both routes reads the first key correctly, keeps the BOM when it writes the file back, and makes the same edits. All of them also turn the two spaces before an end-of-line comment into one. Route 2 never considered the BOM, but it still handled it the same way.

**Trade-off:** Route 1 deliberately keeps the BOM in the text, so where comments and edits land in the file stays correct. Route 2 never addressed the BOM and costs nothing extra; it behaved the same in this run, but nothing in it guarantees that.

### Route 1

- Route: Decode as plain UTF-8 so the BOM stays in the text and is written back unchanged
- Reasoning given: ruamel mark indices count a leading U+FEFF
- Outcome: Kept
- proposed: 5 - Byte-exact

rating: 5
reason: Deliberately preserves the file beyond its config values (BOM, comments, layout), which matters

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - utf-8-sig shifts offsets by one character

rating: 4
reason: Preserved the BOM in practice, but by luck rather than design; file fidelity (BOM, comments, layout) matters

## T2

**Question:** Can a VALUE starting with '-' (e.g. -1e3) be passed without --  
**Kind:** one-off

**What's at stake:** This decides whether a user can set a negative or dash-leading value directly, e.g. `config set retry -1e3`, or must remember to insert `--`. Without that, the command fails with a message that says the value is missing, even though the user typed it.

**What each route does** (run against every arm's final code):

**Example 1:** `config set retry -1e3` _(observed)_

Starting file:

~~~
retry: 3  # attempts
limit: 10
name: alpha
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  retry: -1e3 # attempts
  limit: 10
  name: alpha
  The history records the new value as -1000.0.
  ~~~

- Route 2: All five arms: exit 2, file unchanged. The error says the value is missing, worded differently per arm, e.g. `troupe: troupe config set: the following arguments are required: value`. Two arms also print the full usage block first.

**Example 2:** `config set limit -.inf` _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
  limit: -.inf
  The history records the new value as the string "-.inf".
  ~~~

- Route 2: All five arms: exit 2, file unchanged, same 'required: value' error as above.

**Example 3:** `config set name -beta --reason -x` _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
  name: -beta
  The history records reason "-x".
  ~~~

- Route 2: All five arms: exit 2, file unchanged. Error: `argument --reason: expected one argument` (wording varies slightly by arm).

**Example 4:** `config set -- retry -5` _(observed)_

Starting file:

~~~
retry: 3  # attempts
limit: 10
name: alpha
~~~

- Route 1: exit 0; the retry line now reads (earlier commands had already changed it):

  ~~~
  retry: -5   # attempts
  ~~~

- Route 2: All five arms: exit 2 → no, exit 0; the file now reads:

  ~~~
  retry: -5 # attempts
  limit: 10
  name: alpha
  ~~~


**In practice:** On route 1, any single-dash word after the key is taken as the value, and `--reason` accepts a dash-leading reason. Long `--` options still work as options. On route 2, the only way to set a dash-leading value is to type `--` before the key. A dash-leading reason cannot be given at all in these runs. On route 1, `-1e3` and `-.inf` are stored as typed. The history logs `-1e3` as the number -1000.0 but logs `-.inf` as the text "-.inf".

**Trade-off:** Route 1 accepts dash values directly but relies on overriding a private part of the argument parser, which could break in a future version. Route 2 uses the parser as it comes, but users must know to add `--`, and the error message doesn't tell them.

### Route 1

- Route: Override argparse's private _parse_optional (via a parser subclass) so single-dash VALUEs are positional
- Reasoning given: Plain argparse exits 2 on -1e3/-.inf; long options stay options
- Outcome: Kept; also governs --reason -x at step 4
- proposed: 4 - Usable; relies on a private argparse API

rating: 2
reason: Departs from the CLI convention that a dash-leading argument is an option unless after --; consistency beats flexibility

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Plain argparse exits 2 on negative numbers

rating: 4
reason: Matches the standard CLI convention (dash-leading values need --); consistency beats flexibility

## T3

**Question:** What deleting entries removes  
**Kind:** one-off

**What's at stake:** When a `config set` replaces a value with a smaller one, the entries it drops can take nearby comments with them. Depending on the route, the user's notes in troupe.yml are kept, silently lost, or the command refuses to run and leaves the file unchanged.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder '{model: opus}'` (drops temperature and max_tokens) _(observed)_

Starting file:

~~~
  coder:
    model: opus  # m
    # about temperature
    temperature: 0.2
    # about tokens
    max_tokens: 100
    # trailing comment of coder
~~~

- Route 1: exit 0; the block now reads:

  ~~~
    coder:
      model: opus  # m
      # about temperature
      # about tokens
      # trailing comment of coder
  ~~~

- Route 2: two arms: exactly as route 1, with every comment kept; two arms: exit 0, three comments lost:

  ~~~
    coder:
      model: opus
      # trailing comment of coder
  one arm: exit 0, "# about tokens" lost:
    coder:
      model: opus  # m
      # about temperature
      # trailing comment of coder
  ~~~


**Example 2:** `config set steps '[lint]'` (drops test and deploy) _(observed)_

Starting file:

~~~
steps:
  - lint
  # before test
  - test
  - deploy
  # after list
~~~

- Route 1: exit 0; the list now reads:

  ~~~
  steps:
    - lint
    # before test
    # after list
  ~~~

- Route 2: three arms: exactly as route 1; two arms: exit 0, "# before test" lost:

  ~~~
  steps:
    - lint
    # after list
  ~~~


**Example 3:** `config set agents.reviewer '{model: haiku}'` (one-line flow mapping, drops temperature) _(observed)_

Starting file:

~~~
  reviewer: {model: haiku, temperature: 0.1}  # rv
~~~

- Route 1: exit 0; the line now reads:

  ~~~
    reviewer: {model: haiku}                    # rv
  ~~~

- Route 2: three arms: exactly as route 1; one arm: exit 0, comment pulled in:

  ~~~
    reviewer: {model: haiku}  # rv
  one arm: exit 0, rewritten as a block:
    reviewer:                                   # rv
      model: haiku
  ~~~


**Example 4:** `config set tools '{a: 1}'` (multi-line flow mapping, drops b) _(observed)_

Starting file:

~~~
tools: {
  a: 1,  # comment a
  b: 2
}
~~~

- Route 1: exit 3; the file is unchanged; stderr: `/theatre/.troupe/troupe.yml: tools: the value's layout cannot be written (no ',' before the entry at index 257)`. `config show` still lists b: 2
- Route 2: three arms: exit 0, "# comment a" lost:

  ~~~
  tools: {
    a: 1
  }
  one arm: exit 0, collapsed onto one line and the comment lost:
  tools: {a: 1}
  one arm: exit 3, the file is unchanged; stderr: `troupe: cannot replace tools in /theatre/.troupe/troupe.yml: removing its old value would drop a comment`
  ~~~


**In practice:** Route 1 never lost a comment in these runs. Its description says interior comments go, but in the runs the comments between deleted entries all stayed. The cost is that it refuses to shrink a flow mapping written over several lines: the user gets exit 3 and an error about "layout" and an "index", not about comments. On route 2, the five arms disagree. Only one arm refused, and its error names the lost comment as the reason; the other four went ahead and silently deleted comments in at least one case.

**Trade-off:** Route 1: comments are safe, but some valid edits to flow mappings written over several lines fail with an unclear exit 3. Route 2: what happens to comments depends on the arm, and most arms delete them without saying so.

### Route 1

- Route: Whole block lines (interior comments go, trailing ones stay); a flow deletion only on one line, otherwise exit 3
- Reasoning given: Avoids deleting comments in multi-line flow text
- Outcome: Kept
- proposed: 5 - Careful

rating: 5
reason: Consistent and predictable: comments never lost, and it refuses rather than guesses

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 2
reason: Behaviour varied by arm, with comments silently lost; consistency and predictability are critical

## T4

**Question:** Add a source field to tell hand edits from sets  
**Kind:** one-off

**What's at stake:** When a config value changes, the user needs to know whether someone set it through the command or edited the file by hand. Without that, the history can't say who changed what or how.

**What each route does** (run against every arm's final code):

**Example 1:** `config set retry 5 --reason "bump retries"` (as human:owner) _(observed)_

Starting file:

~~~
# troupe config
model: opus  # default model
retry: 3
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  # troupe config
  model: opus  # default model
  retry: 5
  ~~~

- Route 2: all five arms: exit 0, no output; the file now reads:

  ~~~
  # troupe config
  model: opus  # default model
  retry: 5
  ~~~


**Example 2:** hand edit of .troupe/troupe.yml (model changed to sonnet), then `config show` (as agent:bot) _(observed)_

Starting file:

~~~
# troupe config
model: opus  # default model
retry: 5
~~~

- Route 1: exit 0; prints:

  ~~~
  model: sonnet
  retry: 5
  ~~~

- Route 2: all five arms: exit 0; prints:

  ~~~
  model: sonnet
  retry: 5
  ~~~


**Example 3:** `config history` (as human:owner) after the set and the hand edit _(observed)_

- Route 1: exit 0; four entries. Entries 1–2 are the original values, with "via": "import" and actor unknown. Entry 3 is retry 3→5 with "via": "cli", actor human/owner, reason "bump retries". Entry 4 is the hand edit, model opus→sonnet, with "via": "file", actor unknown, no reason. There is no separate "source" field.
- Route 2: all five arms: the same as route 1. Four entries: import, import, retry 3→5 with "via": "cli" and actor human/owner, then model opus→sonnet with "via": "file" and actor unknown. There is no separate "source" field.

**In practice:** The two routes behave the same. On both, the history marks hand edits apart from command sets with an existing "via" field: "file" for hand edits, "cli" for sets, "import" for the starting values. A hand edit is recorded on the next command, with the actor unknown and no reason. Apart from timestamps and IDs, all six runs produced identical output.

**Trade-off:** Route 1 deliberately adds no source field and relies on "via"; route 2 never considered one and ends up with the same "via" marking. Neither adds anything beyond "via".

### Route 1

- Route: No source field
- Reasoning given: Not asked for
- Outcome: Superseded at step 4 by via
- proposed: n/a - Superseded

rating: n/a
reason: Not a real choice: every route records hand edits the same way (via: file); some justified it, one didn't, same effect.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Superseded

rating: n/a
reason: Not a real choice: same behaviour as route 1.

## T5

**Question:** Refusing unusual layouts at load  
**Kind:** one-off

**What's at stake:** A config file with an unusual but valid layout (nested dash lists, a dash alone on its line with the value below it, a comment right after the dash) must either be read and edited correctly or be refused. A silent misedit would damage the user's file. In this test both routes read and edited it correctly, and neither refused it.

**What each route does** (run against every arm's final code):

**Example 1:** `config show` _(observed)_

Starting file:

~~~
# agents and their tools
tools:
- - read
  - write
- - shell
steps:
  -
    plain
  - # note
    second
  - third
retry: 3  # attempts
~~~

- Route 1: exit 0; it loads the file and prints it with normal layout:

  ~~~
  tools:
    - - read
      - write
    - - shell
  steps:
    - plain
    - second
    - third
  retry: 3
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, identical output.

**Example 2:** `config get tools.1.0` _(observed)_

- Route 1: exit 0; prints `shell`
- Route 2: exit 0; prints `shell` (all five arms)

**Example 3:** `config set tools.0.1 edit` _(observed)_

- Route 1: exit 0; only that item changes, and the comments and odd layout stay as they were:

  ~~~
  # agents and their tools
  tools:
  - - read
    - edit
  - - shell
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, identical file.

**Example 4:** `config set steps.0 first` (this step has a dash alone on its line with the value on the next line) _(observed)_

- Route 1: exit 0; the value is replaced in place and the layout is kept:

  ~~~
  steps:
    -
      first
    - # note
      second
    - third
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, identical file.

**Example 5:** `config set steps.3 fourth` (adds a new item to the list) _(observed)_

- Route 1: exit 0; the new item goes at the end of the list, and `retry` and its comment are kept:

  ~~~
    - third
    - fourth
  retry: 3  # attempts
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, identical file.

**In practice:** Route 1 is supposed to refuse a file with exit 4 when the dash layout doesn't match the parsed items. This file has nested dashes, a dash alone on its line, and a comment after a dash, and route 1 still did not refuse it. Both routes gave the same result on every command, so this test never triggered the refusal.

**Trade-off:** Route 1 adds a load-time check that can refuse a file with exit 4, but nothing here triggered it. Route 2 has no such check, and it handled every layout tested correctly.

### Route 1

- Route: Block sequences whose dash layout does not match the parsed items exit 4
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Safe, slightly strict

rating: 3.5
reason: Edge case; every arm handled these layouts correctly, and the extra refusal check was never triggered

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 3
reason: Edge case; handled every unusual layout correctly without a dedicated check

## T6

**Question:** How existing literal blocks are edited  
**Kind:** one-off

**What's at stake:** Editing a multi-line block value (a prompt, notes, code) rewrites part of the hand-written config file. What differs is whether the file keeps its exact bytes and layout, or whether a block with an explicit indent marker gets edited, refused, or turned into a one-line quoted string.

**What each route does** (run against every arm's final code):

**Example 1:** `config set prompt "You are a reviewer.\n\nBe terse.\n"` _(observed)_

Starting file:

~~~
prompt: |  # system prompt, keep short
    You are a coder.
    
    Be terse.
(the blank line inside the block holds four spaces)
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  prompt: |  # system prompt, keep short
      You are a reviewer.
      
      Be terse.
  Only the changed line differs. The blank line keeps its four spaces, and the comment and the rest of the file are untouched.
  ~~~

- Route 2: All five arms: exit 0; the file now reads:

  ~~~
  prompt: |  # system prompt, keep short
      You are a reviewer.
  
      Be terse.
  The comment is kept, but the blank line loses its four spaces and is now truly empty. The stored value is the same.
  ~~~


**Example 2:** `config set notes "alpha\ngamma\nbeta"`, then `config set notes "alpha\ngamma\nbeta\n"` _(observed)_

Starting file:

~~~
notes: |-
  alpha
  beta
# end of notes
~~~

- Route 1: Both commands exit 0. After the first, the file reads:

  ~~~
  notes: |-
    alpha
    gamma
    beta
  # end of notes
  After the second, the header becomes `notes: |` because the value now ends with a newline. The `# end of notes` comment stays.
  ~~~

- Route 2: All five arms: the same as route 1. Both commands exit 0, gamma is inserted, `|-` becomes `|` after the second command, and the comment stays.

**Example 3:** `config set code " indented first\nchanged\n"` _(observed)_

Starting file:

~~~
code: |2
    indented first
  normal
after: 1  # sentinel
~~~

- Route 1: exit 3, stderr `troupe: code: value cannot be written back faithfully`. The file is not changed.
- Route 2: Two arms: exit 0; the block is replaced by a quoted string, and the file now reads:

  ~~~
  code: "  indented first\nchanged\n"
  after: 1  # sentinel
  Three arms: exit 0; the block stays in place, and the file now reads:
  code: |2
      indented first
    changed
  after: 1  # sentinel
  ~~~


**Example 4:** `config get prompt` (after the edits above) _(observed)_

- Route 1: exit 0, prints:

  ~~~
  You are a reviewer.
  
  Be terse.
  ~~~

- Route 2: All five arms: exit 0, the same output.

**In practice:** For ordinary edits, both routes store the same value and keep comments and the lines around the block. Route 1 also leaves unchanged lines byte-for-byte as they were, including stray whitespace. Route 2 normalises blank lines inside the block. The two routes split on a block with an explicit indent marker (`|2`): route 1 refuses the edit and leaves the file alone, and on route 2 the arms disagree (two turn the block into a quoted one-liner, three edit it in place).

**Trade-off:** Route 1 keeps the file exact but refuses some edits it can't write back safely. On route 2 every edit goes through, but whitespace gets reformatted and, depending on the arm, a `|2` block may become a quoted string.

### Route 1

- Route: Line diff with difflib so unchanged lines keep their bytes
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 5 - Minimal diff

rating: 4
reason: Two questions, averaged. Reproduces a valid file: 3 (refuses some edits it could make). Detects a fidelity problem when writing: 5.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 5
reason: Two questions, averaged. Reproduces a valid file: 5. Detects a fidelity problem when writing: n/a, so not counted.

## T7

**Question:** Replaying old remove events for unknown paths  
**Kind:** one-off

**What's at stake:** This is about rebuilding config history from old "remove" records, including removes for paths that were never recorded (such as keys inside a block that started empty, or a key that a parent overwrite wiped out). If a route handles this badly, `config set` could crash, or the change history could be wrong or out of order. In this run nobody hit either problem: every implementation on both routes finished every command with exit 0 and produced the same file.

**What each route does** (run against every arm's final code):

**Example 1:** `config set empty.model sonnet` (the `empty` block starts as `{}`, so nothing is recorded under it) _(observed)_

Starting file:

~~~
name: demo
empty: {}
tools: []
agents:
  coder:
    model: opus  # main model
    tags: [a, b]
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  empty: {model: sonnet}
  ~~~

- Route 2: all five arms: exit 0, no output; the file now reads:

  ~~~
  empty: {model: sonnet}
  ~~~


**Example 2:** `config set agents.coder.tags []`, then `config set agents.coder solo` (replaces the whole coder block) _(observed)_

Starting file:

~~~
agents:
  coder:
    model: opus  # main model
    tags: [a, b]
~~~

- Route 1: both commands exit 0, no output; the file now reads:

  ~~~
  name: demo
  empty: {model: sonnet}
  tools: []
  agents:
    coder: solo
  ~~~

- Route 2: all five arms: both commands exit 0, no output; the file now reads:

  ~~~
  name: demo
  empty: {model: sonnet}
  tools: []
  agents:
    coder: solo
  ~~~


**Example 3:** `config set tools.0 hammer` (on an empty list) _(observed)_

Starting file:

~~~
tools: []
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  tools: [hammer]
  ~~~

- Route 2: all five arms: exit 0; the file now reads:

  ~~~
  tools: [hammer]
  ~~~


**Example 4:** `config history` after the commands above _(observed)_

- Route 1: exit 0; 10 entries: 4 imports (name, agents.coder.model, tags.0, tags.1), set empty.model, remove tags.0, remove tags.1, then entry 8 `set agents.coder` = "solo", entry 9 `remove agents.coder.model` (old "opus"), then set tools.0. None of the entries is flagged as an error.
- Route 2: four arms: exactly the same 10 entries in the same order as route 1. One arm: the same 10 entries, but entries 8 and 9 are swapped. `remove agents.coder.model` is logged first, then `set agents.coder` = "solo" (both still belong to one change).

**In practice:** In what was run, the two routes produced the same results: every exit code, every output and every file was identical. The only difference was in the history log, from one of the five arms on route 2. When one block replaced another, that arm recorded the removal of the old key before the new value was set. Every other arm recorded the set first. This test never replayed a remove for a path that history doesn't know about in a way that made one route crash and the other survive.

**Trade-off:** Route 1 quietly ignores removes for paths it doesn't know about, so a corrupted or out-of-order history would be accepted without any warning. Route 2 adds no such guard, so it could crash on old logs this test didn't produce, and its arms differed on the order of history entries.

### Route 1

- Route: pop(path, None)
- Reasoning given: Step-1 removes may name unrecorded paths
- Outcome: Kept
- proposed: 5 - Robust

rating: 5
reason: Removing something that doesn't exist should replay as no effect, and it does.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 5
reason: RESLICE placeholder: unknown removes replay as no effect (5), but one arm swaps history order on a block replacement (2). See decisions/reslice.md.

## T8

**Question:** Strings starting with file: in show  
**Kind:** one-off

**What's at stake:** Some config values are plain text that happens to start with `file:`. The file marks these `!literal` so they are not read as a pointer to another file. The question is whether `config show` keeps that mark. Without it, the output looks the same as a real file reference, so anyone who copies it back into the config would turn plain text into a file include.

**What each route does** (run against every arm's final code):

**Example 1:** `config show agents` _(observed)_

Starting file:

~~~
agents:
  coder:
    model: opus
    prompt: !literal file:prompts/coder.md
    system: file:sys.md
~~~

- Route 1: exit 0; prints the text without its mark:

  ~~~
  coder:
    model: opus
    prompt: file:prompts/coder.md
    system: |
      You are a coder.
  ~~~

- Route 2: three arms: same as route 1 (`prompt: file:prompts/coder.md`); two arms: exit 0, keeps the mark:

  ~~~
  coder:
    model: opus
    prompt: !literal file:prompts/coder.md
    system: |
      You are a coder.
  ~~~


**Example 2:** `config show agents --sources` _(observed)_

- Route 1: exit 0; `prompt: file:prompts/coder.md # from .troupe/troupe.yml` (no mark). The real include shows as `system: | # from .troupe/sys.md` followed by its content
- Route 2: three arms: same as route 1; two arms: `prompt: !literal file:prompts/coder.md # from .troupe/troupe.yml`

**Example 3:** `config set agents.coder.notes file:notes.txt`, then `config show` _(observed)_

- Route 1: set: exit 0, and the file gains ` notes: !literal file:notes.txt`. Then show prints ` notes: file:notes.txt` (no mark)
- Route 2: set: exit 0, same file change in all five arms. Then show: three arms print ` notes: file:notes.txt`; two arms print ` notes: !literal file:notes.txt`

**Example 4:** `config get agents.coder.notes` _(observed)_

- Route 1: exit 0; prints `file:notes.txt`
- Route 2: exit 0; prints `file:notes.txt` (all arms)

**In practice:** Every arm stores the mark correctly in the file, and `config get` returns the bare text in every arm. Only `config show` differs. Route 1, and three of the five arms on route 2, print `prompt: file:prompts/coder.md`, which looks exactly like a file reference such as `system: file:sys.md` would if it weren't expanded. The other two arms on route 2 print the `!literal` mark, so the output can be pasted back as-is.

**Trade-off:** Route 1 gives clean, readable output but drops the mark that separates plain text from a file reference. Route 2 is inconsistent: most arms do the same as route 1, and a minority keep the mark.

### Route 1

- Route: Print plain
- Reasoning given: Not in contract
- Outcome: Kept
- proposed: 3 - Reads back wrong

rating: 2
reason: Drops the !literal mark in show, so the output reads back wrong. Behaviour rating: keeps full fidelity = 5, doesn't = 2.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Step 7

rating: 3
reason: RESLICE placeholder: two arms keep the mark (5), three drop it (2). See decisions/reslice.md.

# Divergent (83)

## T9

**Question:** How changed files are written to disk  
**Kind:** divergent

**What's at stake:** If the program is interrupted while saving a changed file (crash, Ctrl-C, power loss, full disk), the user may end up with a file that is cut off partway through and has lost content, or with a file that is either fully old or fully new.

**What each route does** (run against every arm's final code):

**Example 1:** the program is killed halfway through saving a changed file _(inferred, not run)_

- Route 1: the file holds either the complete old text or the complete new text, never a mix; a leftover temporary file may stay in the same folder
- Route 2: the file can be left cut off partway, with only part of the new text and the rest missing
- Route 3: no decision was made here, so what happens depends on however the file happens to be written

**In practice:** Both routes leave a file alone if its text did not change, so its timestamp and contents stay as they were. Route 1 writes the new text to a temporary file next to the original, forces it onto the disk, gives it the original's permissions, and then swaps it into place in one step. A save is therefore all or nothing. Because the original file is replaced rather than edited, anything tied to that exact file, such as hard links or some editor and file-watcher setups, may see it as a new file. Route 2 overwrites the original file directly and keeps line endings exactly as computed. It relies on every new text being worked out and checked before anything is written, so only a disk or system error during the write can cause damage, but if that happens the file is left corrupted. Route 3 never considered the question.

**Trade-off:** Route 1 costs extra code, a brief temporary file and replacing the file instead of editing it, and in return a save can never leave a half-written file; route 2 is simpler and edits the file itself, but a failure during the write can leave a file damaged; route 3 makes no deliberate choice.

### Route 1

- Route: Temp file in the same directory, fsync, copy permissions, os.replace; only changed files are touched
- Reasoning given: A file is never half-written; a temp file in .troupe/ would not be atomic across filesystems
- Outcome: Kept
- proposed: 5 - Protects user data

rating: 5
reason: Atomic write: a save is all or nothing. A crash between files in a multi-file save can still leave a mix, but that's an edge case and hard to avoid.

### Route 2

- Route: Write in place with newline='' only when the text changed, no temp files
- Reasoning given: All texts are computed and verified first, so only an OS error during the write remains
- Outcome: Kept
- proposed: 3 - A crash mid-write can leave a truncated config file

rating: 3
reason: A crash mid-write can leave a truncated config.

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - A crash during an in-place write can truncate a user's config

rating: 3
reason: Not considered; same risk as an in-place write.

## T10

**Question:** Both troupe.yml and troupe.yaml exist (or neither)  
**Kind:** divergent

**What's at stake:** If a project ends up with both `.troupe/troupe.yml` and `.troupe/troupe.yaml`, the user either gets a clear refusal or has one file silently override the other. In the run, every implementation on both routes refused every config command, including read-only ones, until one of the files is removed.

**What each route does** (run against every arm's final code):

**Example 1:** `config get model` (with `.troupe/troupe.yml` and `.troupe/troupe.yaml` both present) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: from-yml  # yml file
retry: 1

.troupe/troupe.yaml:
model: from-yaml  # yaml file
retry: 2
~~~

- Route 1: exit 4, prints nothing. The two arms' error messages differ only in wording. One arm: `troupe: .troupe: both troupe.yml and troupe.yaml exist`. One arm: `troupe: ./.troupe/troupe.yml: both troupe.yml and troupe.yaml exist`
- Route 2: exit 4, prints nothing. Each of the four arms words the error differently. One arm: `/theatre/.troupe/troupe.yml: both troupe.yml and /theatre/.troupe/troupe.yaml exist` (no `troupe:` prefix). One arm: `troupe: .troupe/troupe.yml and .troupe/troupe.yaml: both exist; keep only one`. One arm: `troupe: both /theatre/.troupe/troupe.yml and /theatre/.troupe/troupe.yaml exist; remove one`. One arm: `troupe: error: ambiguous configuration: both .troupe/troupe.yml and .troupe/troupe.yaml exist`

**Example 2:** `config set retry 5` (same two files) _(observed)_

- Route 1: exit 4, same error as above. Neither file is changed (retry stays 1 in .yml and 2 in .yaml)
- Route 2: exit 4, same error as above in all four arms. Neither file is changed

**Example 3:** `config show`, `config history`, `config show --sources` (same two files) _(observed)_

- Route 1: each gives exit 4 with the same error and no output, in both arms
- Route 2: each gives exit 4 with the same error and no output, in all four arms

**In practice:** In practice the two routes behave the same: any config command, even just reading a value, fails with exit 4 and changes nothing. The only difference is the error text. Only two arms on route 2 tell the user what to do next ("keep only one" / "remove one"). The case where neither file exists was not tested.

**Trade-off:** Both routes cost the same: config is unusable until the user deletes one file. Route 1 reached this as a deliberate choice; route 2 reached the same behavior without considering the question, and its error messages vary more from arm to arm.

### Route 1

- Route: Exit 4 in both cases
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 5 - Unambiguous

rating: 4
reason: Refuses correctly, but the error states the problem without the fix (behaviour group B = 4).

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Silently picking one could edit the wrong file

rating: 4.5
reason: RESLICE placeholder: two arms say what to do (5), two state the problem only (4). See decisions/reslice.md.

## T11

**Question:** Block-scalar indicators when a block value changes  
**Kind:** divergent

**What's at stake:** When a multi-line value is replaced, the `|`, `|-` or `|+` marker in front of it decides whether trailing newlines survive the next read. If the marker is wrong, the value quietly gains or loses newlines. A value that is just a single newline is the hard case: it can be written as `|+`, written in quotes, or refused.

**What each route does** (run against every arm's final code):

**Example 1:** `config set a "x\ny"` (no trailing newline) _(observed)_

Starting file:

~~~
a: |
  one
  two
~~~

- Route 1: exit 0; all five arms gave the same result; the file now reads:

  ~~~
  a: |-
    x
    y
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  a: |-
    x
    y
  ~~~


**Example 2:** `config set b "p\nq\n\n"` (two trailing newlines) _(observed)_

Starting file:

~~~
b: |-
  one
c: |+
~~~

- Route 1: exit 0; all five arms gave the same result; the file now reads (the blank line belongs to b):

  ~~~
  b: |+
    p
    q
  
  c: |+
  ~~~

- Route 2: exit 0; the file now reads (the blank line belongs to b):

  ~~~
  b: |+
    p
    q
  
  c: |+
  ~~~


**Example 3:** `config set c "z\n"` (one trailing newline, old marker `|+`) _(observed)_

Starting file:

~~~
c: |+
  one

e: |
~~~

- Route 1: exit 0; all five arms gave the same result; `|+` is kept and the old blank line is gone:

  ~~~
  c: |+
    z
  e: |
  `config show` then prints it as `c: |`
  ~~~

- Route 2: exit 0; `|+` is kept and the old blank line is gone:

  ~~~
  c: |+
    z
  e: |
  `config show` then prints it as `c: |`
  ~~~


**Example 4:** `config set e "\n"` (the value is a single newline), then `config show` _(observed)_

Starting file:

~~~
e: |
  last
f: plain  # end
~~~

- Route 1: The arms on this route did different things. Two arms: exit 0; the file now reads:

  ~~~
  e: |+
  
  f: plain  # end
  `config show` prints the same `e: |+` and a blank line. One arm: exit 0; the file now reads:
  e: "\n"
  f: plain  # end
  `config show` prints `e: "\n"`. One arm: also exit 0 and writes the same quoted `e: "\n"` to the file, but `config show` prints `e: |+` and a blank line, so the file and show disagree. One arm: exit 3, stderr `troupe: write refused: e: cannot write this change faithfully`; the file is unchanged and show still prints `e: |` and `last`.
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  e: |+
  
  f: plain  # end
  `config show` prints the same `e: |+` and a blank line.
  ~~~


**In practice:** Both routes did the same for ordinary values. When the old marker couldn't fit the new value, both switched it: `|` became `|-`, and `|-` became `|+`. When it could fit, they kept it (`|+` stayed for c). They differ only on a value that is a single newline. Route 2 always writes it as `|+`. Route 1's arms split between `|+`, a quoted "\n", and refusing the write.

**Trade-off:** Route 1 doesn't settle the single-newline case, so its arms ranged from a quoted value to a refusal (and in one arm the file and `config show` disagreed); route 2 always writes that value as `|+` plus a bare blank line, which is easy to misread or break when editing by hand.

### Route 1

- Route: Keep the old indicator if it can represent the value, otherwise choose strip/clip/keep from trailing newlines; keep-chomped trailing blank lines count as part of the value
- Reasoning given: Contract silent; the result must read back, and trailing lines must not silently join the value
- Outcome: Kept
- proposed: 5 - Exact and minimal

rating: 3.5
reason: RESLICE placeholder: two arms round-trip with |+ (4.5), one quotes it (4), one quotes it but show disagrees (2), one refuses a valid value (3). See decisions/reslice.md.

### Route 2

- Route: Render a lone newline value as |+ instead of refusing it
- Reasoning given: Probes showed it round-trips in every position
- Outcome: Kept
- proposed: 5 - Removes a needless refusal

rating: 4.5
reason: Round-trips the single-newline value as |+ (4.5). Natural vs quoted is mostly style.

## T12

**Question:** Setting a mapping or list onto an existing collection: merge entry-wise or replace the block  
**Kind:** divergent

**What's at stake:** When you `config set` a whole mapping or list over one that already exists, the question is whether the comments in your hand-edited troupe.yml survive. That includes comments on entries whose values did not change.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder "{model: opus, temperature: 0.5, max_tokens: 4096}"` _(observed)_

Starting file:

~~~
# troupe settings
agents:
  coder:
    model: opus  # the best one
    # tuned low for code
    temperature: 0.2
    retries: 3   # flaky network
limits:
  ...
~~~

- Route 1: all four arms: exit 0, prints nothing; the block now reads:

  ~~~
    coder:
      model: opus  # the best one
      # tuned low for code
      temperature: 0.5
      max_tokens: 4096
  (the unchanged `model` line and the `# tuned low for code` comment are kept; `retries` and its comment are gone)
  ~~~

- Route 2: exit 0, prints nothing; the block now reads:

  ~~~
    coder:
      model: opus
      temperature: 0.5
      max_tokens: 4096
  (all three comments are gone, including the one on the unchanged `model` line)
  ~~~

- Route 3: same as route 2: exit 0; the block now reads:

  ~~~
    coder:
      model: opus
      temperature: 0.5
      max_tokens: 4096
  ~~~


**Example 2:** `config set tools "[git, shell, web]"` _(observed)_

Starting file:

~~~
tools:
  - git   # version control
  # shell is sandboxed
  - shell
name: demo
~~~

- Route 1: all four arms: exit 0; the list now reads:

  ~~~
  tools:
    - git   # version control
    # shell is sandboxed
    - shell
    - web
  ~~~

- Route 2: exit 0; the list now reads:

  ~~~
  tools:
    - git
    - shell
    - web
  ~~~

- Route 3: same as route 2: exit 0; the list now reads:

  ~~~
  tools:
    - git
    - shell
    - web
  ~~~


**Example 3:** `config set limits "{tokens: 1000, calls: 50}"` (the same values it already has) _(observed)_

Starting file:

~~~
limits:
  # per-run cap
  tokens: 1000  # soft limit
  calls: 50
~~~

- Route 1: all four arms: exit 0; the file is not touched and the comments stay
- Route 2: exit 0; the file is not touched and the comments stay
- Route 3: exit 0; the file is not touched and the comments stay

**Example 4:** `config history agents.coder` after the first command _(observed)_

- Route 1: all four arms: exit 0 and record the same three changes: temperature 0.2→0.5, max_tokens added as 4096, retries 3 removed. Three arms log them in that order. One arm logs the removal of retries first, then the two sets.
- Route 2: exit 0; records the same three changes in the order set temperature, set max_tokens, remove retries
- Route 3: exit 0; same as route 2

**In practice:** Your values come out the same on every route: `config show` printed identical settings everywhere. The only difference is the file you edit by hand. On route 1, setting a block deletes only the comments on entries you removed. On routes 2 and 3, setting a block deletes every comment inside it, including comments on entries you kept unchanged. Comments outside the block survive on all routes. If the new value equals the current one, no route rewrites anything.

**Trade-off:** Route 1 keeps your comments but can leave behind a comment that no longer matches what it sits next to. Routes 2 and 3 always produce a clean block but silently throw away every comment inside it.

### Route 1

- Route: Merge entry-wise (keep, change, append, delete); unchanged entries keep their bytes and comments
- Reasoning given: Never rewrite what the user did not ask to change
- Outcome: Kept
- proposed: 5 - Minimal diff

rating: 3
reason: Mixed: keeps comments, but a comment tied to a changed value (temperature 0.2 'tuned low for code' -> 0.5) goes stale. Value and comment should move as a unit; not always the case. (One arm also logs the removal first in history.)

### Route 2

- Route: Replace the collection's whole span in the old style; comments inside it go with it
- Reasoning given: Those comments described the old entries
- Outcome: Kept
- proposed: 3 - Loses comments and formatting on entries whose values did not change

rating: 3
reason: Mixed: a clean block, but it drops comments on unchanged entries too.

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - A wholesale rewrite drops comments in unchanged entries

rating: 3
reason: Same as route 2.

## T13

**Question:** Where an end-of-line comment goes when a value's length changes  
**Kind:** divergent

**What's at stake:** Hand-written YAML often lines up its end-of-line comments in a column. When a `config set` changes a value's length, the user either keeps that alignment or gets comments that drift out of line with their neighbours.

**What each route does** (run against every arm's final code):

**Example 1:** `config set model sonnet` (value grows from 5 to 6 characters, with room before the comment) _(observed)_

Starting file:

~~~
model: opus        # main model
name: abcdefgh  # shrinks
~~~

- Route 1: all five arms: exit 0, no output; the file now reads:

  ~~~
  model: sonnet      # main model
  name: abcdefgh  # shrinks
  ~~~

- Route 2: exit 0, no output; the file now reads:

  ~~~
  model: sonnet      # main model
  name: abcdefgh  # shrinks
  ~~~


**Example 2:** `config set name ab` (value shrinks from 8 to 2 characters) _(observed)_

Starting file:

~~~
name: abcdefgh  # shrinks
~~~

- Route 1: all five arms: exit 0; the file now reads:

  ~~~
  name: ab        # shrinks
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  name: ab        # shrinks
  ~~~


**Example 3:** `config set retry 123456789` (value too long for the comment's old column) _(observed)_

Starting file:

~~~
retry: 3   # tries
~~~

- Route 1: all five arms: exit 0; the file now reads:

  ~~~
  retry: 123456789 # tries
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  retry: 123456789 # tries
  ~~~


**Example 4:** `config set tags.2 c` (flow list grows, with room before the comment) _(observed)_

Starting file:

~~~
tags: [a, b]      # roomy flow list
~~~

- Route 1: four arms: exit 0; the file now reads:

  ~~~
  tags: [a, b, c]   # roomy flow list
  one arm: exit 0, but the comment is pushed 3 columns right, out of its column:
  tags: [a, b, c]      # roomy flow list
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  tags: [a, b, c]   # roomy flow list
  ~~~


**Example 5:** `config set ports.2 3` (flow list grows, with no room before the comment) _(observed)_

Starting file:

~~~
ports: [1, 2] # tight flow list
~~~

- Route 1: all five arms: exit 0; the file now reads:

  ~~~
  ports: [1, 2, 3] # tight flow list
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  ports: [1, 2, 3] # tight flow list
  ~~~


**In practice:** Both routes keep a comment in its column when there is room and leave one space before `#` when there isn't. The routes differ in only one place: on route 1, one of five arms did not keep the column when a flow list like `[a, b]` grew, and it shifted the comment right by the added width. Route 2's single arm behaved like route 1's other four arms in every case.

**Trade-off:** Route 1 states the column rule outright and also applies it to growing flow lists, but one arm still missed that case. Route 2 never addressed the rule, yet its one arm produced the aligned result anyway.

### Route 1

- Route: Keep its column if possible, else one space before #; also when a flow collection grows
- Reasoning given: Contract rule; test expectations were corrected to match in several steps
- Outcome: Kept
- proposed: 5 - Contract rule

rating: 4
reason: RESLICE placeholder: four arms keep the comment column everywhere (5); one lets it drift when a flow list grows (1). Contract rule. See decisions/reslice.md.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - The contract states the rule

rating: 5
reason: Keeps the comment column in every case (5).

## T14

**Question:** Spacing of `# from` comments  
**Kind:** divergent

**What's at stake:** When `config show --sources` labels each value with the file it came from, the spacing decides whether those `# from` notes line up in a column or sit right after each value. That affects how easy the output is to scan. On these tests both routes printed exactly the same output, so a user would see no difference.

**What each route does** (run against every arm's final code):

**Example 1:** `config show --sources` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: opus
max_retries: 3
agents:
  coder: file:agents/coder.yaml
  reviewer:
    name: rev
    a_much_longer_setting_name: "a fairly long string value here"
    tags:
      - a
      - bbbbbbbbbbbb
prompt: file:prompt.txt
empty: ""
~~~

- Route 1: exit 0; prints (all 4 arms the same):

  ~~~
  model: opus # from .troupe/troupe.yml
  max_retries: 3 # from .troupe/troupe.yml
  agents:
    coder:
      temperature: 0.2 # from .troupe/agents/coder.yaml
      model: sonnet # from .troupe/agents/coder.yaml
    reviewer:
      name: rev # from .troupe/troupe.yml
      a_much_longer_setting_name: a fairly long string value here # from .troupe/troupe.yml
      tags:
        - a # from .troupe/troupe.yml
        - bbbbbbbbbbbb # from .troupe/troupe.yml
  prompt: | # from .troupe/prompt.txt
    line one
    line two is longer
  empty: '' # from .troupe/troupe.yml
  ~~~

- Route 2: exit 0; prints exactly the same output as route 1 (both arms): one space before each `# from`, nothing lined up in a column

**Example 2:** `config show agents.reviewer.tags --sources` _(observed)_

- Route 1: exit 0; prints:

  ~~~
  - a # from .troupe/troupe.yml
  - bbbbbbbbbbbb # from .troupe/troupe.yml
  ~~~

- Route 2: exit 0; same output as route 1

**Example 3:** `config show agents.coder.temperature --sources` _(observed)_

Starting file:

~~~
.troupe/agents/coder.yaml:
temperature: 0.2
model: sonnet
~~~

- Route 1: exit 0; prints `0.2 # from .troupe/agents/coder.yaml`
- Route 2: exit 0; same output as route 1

**In practice:** Every arm on both routes printed exactly the same thing for all four commands, with one space before `# from` and no column alignment. Route 2 says it never considered this question, but in practice its output is the same as route 1's.

**Trade-off:** Route 1 chose plain one-space notes that are predictable but don't line up when values have different lengths. Route 2 gives the same output without having made that choice on purpose.

### Route 1

- Route: One space before #, no alignment
- Reasoning given: Predictable
- Outcome: Kept
- proposed: 5 - Fine

rating: n/a
reason: Doesn't matter: every arm prints identical output.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Minor

rating: n/a
reason: Doesn't matter: identical output.

## T15

**Question:** Deleting the first key of a compact `- key: v` item  
**Kind:** divergent

**What's at stake:** When a list entry is replaced and its old first key (`name`) has to go, the user either gets the change refused, with the file left alone, or gets it written, in which case the comments in that entry may or may not survive.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.0 "{model: opus, temp: 0.2}"` _(observed)_

Starting file:

~~~
# agents roster
agents:
  - name: coder   # first key
    model: opus   # model
    temp: 0.2
  - name: reviewer
    model: sonnet  # keep me
retry: 3
~~~

- Route 1: exit 3; the file is unchanged. stderr: `/theatre/.troupe/troupe.yml: agents.0: this change cannot be written: an entry to remove shares its first line with content that remains`
- Route 2: exit 0; the file now reads:

  ~~~
  agents:
    - model: opus   # model
      temp: 0.2
    - name: reviewer
      model: sonnet  # keep me
  ~~~

- Route 3: two arms: exit 0; the file now reads:

  ~~~
  agents:
    - model: opus   # model
      temp: 0.2
    - name: reviewer
      model: sonnet  # keep me
  one arm: the same, but the `# model` comment is dropped as well:
  agents:
    - model: opus
      temp: 0.2
    - name: reviewer
      model: sonnet  # keep me
  one more arm: the same as that one (exit 0, `# model` dropped). So two arms keep `# model` and two drop it.
  ~~~


**Example 2:** then `config set agents.1 "{model: haiku}"` _(observed)_

- Route 1: exit 3; the file is unchanged. stderr: `/theatre/.troupe/troupe.yml: agents.1: this change cannot be written: an entry to remove shares its first line with content that remains`
- Route 2: exit 0; the file now reads:

  ~~~
  agents:
    - model: opus   # model
      temp: 0.2
    - model: haiku   # keep me
  retry: 3
  ~~~

- Route 3: two arms: exit 0, with the same file as route 2 (` - model: haiku # keep me`); two arms: exit 0, but every comment in the list is gone:

  ~~~
  agents:
    - model: opus
      temp: 0.2
    - model: haiku
  retry: 3
  ~~~


**Example 3:** then `config show agents` and `config history agents` _(observed)_

- Route 1: `show` prints the original list (coder/opus/0.2, reviewer/sonnet). `history` lists only the 5 import entries; no change is recorded.
- Route 2: `show` prints:

  ~~~
  - model: opus
    temp: 0.2
  - model: haiku
  `history` adds three entries after the imports: remove agents.0.name "coder", remove agents.1.name "reviewer", and set agents.1.model sonnet -> haiku, all with actor human:owner.
  ~~~

- Route 3: all four arms: `show` gives the same output as route 2. `history` records the same three changes, but lists the set of agents.1.model before the remove of agents.1.name.

**In practice:** On every route that writes the file, the `# first key` comment disappears along with the `name:` line it was on. On routes 2 and 3, the old second line's comment moves up onto the dash line, so `# keep me` ends up next to `haiku` even though it was written for `sonnet`. On route 1, the user can't make this change through the command at all and has to edit the file by hand.

**Trade-off:** Route 1 never touches the file but refuses an ordinary replace. Route 2 makes the change and keeps the remaining comments, though one of them can end up on a line it wasn't written for. Route 3 also makes the change, but whether the comments survive depends on the implementation (half of its arms strip them).

### Route 1

- Route: Exit 3
- Reasoning given: Conservative
- Outcome: Kept
- proposed: 4 - Safe refusal

rating: 4
reason: Safe refusal, but the edit has to be done by hand (4).

### Route 2

- Route: Pull the next entry up into the dash line
- Reasoning given: Removing up to the next entry's key keeps the column
- Outcome: Kept
- proposed: 5 - Supports the edit safely

rating: 5
reason: Supports the edit and keeps the remaining comments (5), though one can end up beside a value it wasn't written for.

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Edge case

rating: 5
reason: RESLICE placeholder: two arms behave like route 2 (5); two strip every comment in the list (n/a as proposed). See decisions/reslice.md.

## T16

**Question:** Complex (non-scalar) mapping keys  
**Kind:** divergent

**What's at stake:** If the config file has a key that is a list or a map (YAML's `? [a, b]` form), the user can't use any config command at all, even to read the plain `name` key. On both routes every command refuses with exit 4 and the file is left untouched. The routes differ only in how the error message points to the problem.

**What each route does** (run against every arm's final code):

**Example 1:** `config get name` _(observed)_

Starting file:

~~~
name: demo
retry: 3  # attempts
? [a, b]
: pair
matrix:
  ? {os: linux}
  : fast
~~~

- Route 1: exit 4, prints nothing to stdout. The error wording differs between the three arms. One arm: `/theatre/.troupe/troupe.yml: mapping key is not a scalar (complex keys are not supported)`. One arm: `troupe: /theatre/.troupe/troupe.yml: complex mapping keys are not supported`. One arm: `troupe: complex mapping keys are not supported`, which doesn't name the file.
- Route 2: exit 4, prints nothing to stdout. The error wording differs between the three arms. One arm: `troupe: .troupe/troupe.yml (line 3, column 3): only scalar mapping keys are supported`. One arm: `troupe: cannot load /theatre/.troupe/troupe.yml: mapping key at line 3 under (root) is not a scalar`. One arm: `troupe: error: /theatre/.troupe/troupe.yml: only scalar mapping keys are supported`, which gives no line number.

**Example 2:** `config show` _(observed)_

- Route 1: exit 4. Shows nothing and prints the same error as for `config get name` (on every arm).
- Route 2: exit 4. Shows nothing and prints the same error as for `config get name` (on every arm).

**Example 3:** `config set retry 5` _(observed)_

- Route 1: exit 4, same error. The file is unchanged and `retry` stays 3.
- Route 2: exit 4, same error. The file is unchanged and `retry` stays 3.

**Example 4:** `config set matrix.extra on` _(observed)_

- Route 1: exit 4, same error, and the file is unchanged.
- Route 2: exit 4, same error, and the file is unchanged.

**Example 5:** `config history` _(observed)_

- Route 1: exit 4, same error, and no history is shown.
- Route 2: exit 4, same error, and no history is shown.

**In practice:** The two routes act the same: every config command, whether it reads, writes or shows history, refuses with exit 4 and never touches the file. The only difference is the error text. Two of the three arms on route 2 give the line number of the bad key (line 3). None of the three arms on route 1 gives a line number, and one of them doesn't name the file either.

**Trade-off:** Route 1 locks the user out of all config commands with an error that names the file in two of its three arms but never gives a line. Route 2 has the same lockout, and two of its three arms also point to the line that caused it.

### Route 1

- Route: Exit 4
- Reasoning given: Conservative
- Outcome: Kept
- proposed: 5 - Safe

rating: 3.5
reason: RESLICE placeholder: all refusals are good; being more explicit about the origin is better. Two arms name the file (4), one names neither file nor line (3).

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Rare; out of contract

rating: 4.5
reason: RESLICE placeholder: two arms name the file and line (5), one names the file only (4).

## T17

**Question:** Which concurrency is in contract  
**Kind:** divergent

**What's at stake:** This decides which simultaneous uses of the config file are promised to work. Picture a watcher running while someone runs a set, or an editor saving while a set is in progress. Outside the promised cases, a change can be silently lost or a watcher can show a half-written state, and the user gets no warning.

**In practice:** Route 1 promises exactly one case: a single watch running alongside one other command, such as one set. That case is expected to behave correctly. Everything else is declared unsupported: saving the file from an editor while a set is running, two sets at once, or two watches at once. If any of those goes wrong, for example the editor's save overwrites the set's change or the set overwrites the editor's, it counts as misuse rather than a bug. Users and maintainers get a clear rule about what they can rely on. Route 2 never addressed concurrency. No combination is promised and none is ruled out, so nobody can tell whether a watcher plus a set, or two sets, is meant to work. Bug reports about clashing writes have no agreed answer.

**Trade-off:** Route 1 costs users the editor-during-set and multiple-writer cases, which are explicitly unsupported, but it gives them a clear promise. Route 2 costs nothing up front but leaves every simultaneous use unspecified, so behaviour and expectations are unknown.

### Route 1

- Route: One watch plus one other command; editor saves during a set and multiple watches/sets are out of contract
- Reasoning given: Carries over step 1
- Outcome: Kept
- proposed: 4 - Reasonable

rating: 4
reason: A clear, reasonable promise: one watch plus one other command.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Scope

rating: n/a
reason: Not addressed; scope.

## T18

**Question:** How show prints a text include a literal block cannot hold exactly  
**Kind:** divergent

**What's at stake:** When an included prompt file has Windows line endings (CRLF), `config show` has to pick one: print the text so it reads as plain lines, or keep it exact. Depending on the route, a user sees the text with invisible carriage returns, as an escaped string with \r\n, or with the CRs quietly removed from what is shown.

**What each route does** (run against every arm's final code):

**Example 1:** `config show agents.coder` _(observed)_

Starting file:

~~~
.troupe/prompts/coder.txt holds "Line one\r\nLine two\r\n" (CRLF endings); troupe.yml has `prompt: file:prompts/coder.txt`
~~~

- Route 1: exit 0; the prompt prints as a literal block, and each line still ends in a raw, invisible carriage-return byte:

  ~~~
  prompt: |
    Line one
    Line two
  ~~~

- Route 2: exit 0; the prompt prints as an escaped string on one line (all three arms):

  ~~~
  prompt: "Line one\r\nLine two\r\n"
  ~~~

- Route 3: exit 0; the prompt prints as a literal block with the CRs dropped (plain LF lines):

  ~~~
  prompt: |
    Line one
    Line two
  ~~~


**Example 2:** `config show agents.coder` (the notes field) _(observed)_

Starting file:

~~~
.troupe/prompts/notes.txt holds "  indented first line\nlast line, no final newline"
~~~

- Route 1: exit 0;

  ~~~
  notes: |2-
      indented first line
    last line, no final newline
  ~~~

- Route 2: two arms: exit 0;

  ~~~
  notes: |2-
      indented first line
    last line, no final newline
  one arm: exit 0; it is double-quoted instead:
  notes: "  indented first line\nlast line, no final newline"
  ~~~

- Route 3: exit 0;

  ~~~
  notes: |2-
      indented first line
    last line, no final newline
  ~~~


**Example 3:** `config show agents.coder --sources` _(observed)_

Starting file:

~~~
same files as above
~~~

- Route 1: exit 0; `prompt: | # from .troupe/prompts/coder.txt`, followed by the two lines with raw CRs still in them
- Route 2: exit 0; `prompt: "Line one\r\nLine two\r\n" # from .troupe/prompts/coder.txt` (one arm also double-quotes notes)
- Route 3: exit 0; `prompt: | # from .troupe/prompts/coder.txt`, followed by the two lines with no CRs

**Example 4:** `config get agents.coder.prompt` _(observed)_

Starting file:

~~~
coder.txt with CRLF endings
~~~

- Route 1: exit 0; prints the exact bytes "Line one\r\nLine two\r\n"
- Route 2: exit 0; prints the exact bytes "Line one\r\nLine two\r\n"
- Route 3: exit 0; prints the exact bytes "Line one\r\nLine two\r\n"

**In practice:** `get` returns the exact file bytes on every route. Only `show` differs. Route 1 looks clean in a terminal, but the stray CR bytes sit inside the block, and a YAML reader treats a bare CR as a line break, so its output does not read back as the original text. Route 2 is the only one whose `show` output reads back to exactly the file's bytes, but you see `\r\n` escapes instead of lines. Route 3 shows clean lines, but `show` no longer matches the file: the CRs vanish from the display, and only `get` reveals them. Files without CRs (plain.txt, and notes.txt on most arms) print as literal blocks on every route.

**Trade-off:** Route 1: always a literal block, but raw CRs are hidden inside the output. Route 2: exact text, shown as an escaped one-line string. Route 3: readable block that silently differs from the file, which only `get` shows exactly.

### Route 1

- Route: Double-quoted at first; reworked so every text include is a literal block of the exact text
- Reasoning given: The owner said there is no exception
- Outcome: Reworked at step 3
- proposed: 4 - Owner-aligned; read-back excused

rating: 3
reason: Competing requirements (block shape vs fidelity). Keeps the block shape but hides raw CRs, so show doesn't read back. +1 for raising the conflict.

### Route 2

- Route: Double-quoted with escapes
- Reasoning given: A literal block cannot keep CR; data must never be altered
- Outcome: Kept
- proposed: 2 - The contract says text includes are literal blocks; one owner explicitly rejected this fallback

rating: 4
reason: Quoting is valid here, and the only way to preserve fidelity. Marked down because one arm over-quotes values that don't need it.

### Route 3

- Route: Literal block with CRLF turned into LF; get keeps the bytes
- Reasoning given: The contract requires literal blocks; get stays exact
- Outcome: Kept
- proposed: 4 - Contract shape; line endings differ

rating: 2
reason: Block shape, but silently drops the CRs from show.

## T19

**Question:** Missing digit-only PATH segments and list appends  
**Kind:** divergent

**What's at stake:** Whether a user can start a brand-new list by setting index 0 under a key that doesn't exist yet. On route 1 that works. On route 2 it is refused, and the user has to create the list some other way first. Both routes append to an existing list when the index equals its length.

**What each route does** (run against every arm's final code):

**Example 1:** `config set newlist.0 alpha` _(observed)_

Starting file:

~~~
name: demo
items:
  - a
  - b
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  name: demo
  items:
    - a
    - b
  newlist:
    - alpha
  ~~~

- Route 2: All five arms: exit 5, file unchanged. The messages differ: `troupe: newlist.0: not found (newlist does not exist)`; `troupe: path not found: newlist.0 (no (root).newlist; a missing list index '0' cannot be created)`; `troupe: path not found: newlist.0`; `troupe: error: newlist.0: path not found`; and one message gives the full file path, then `newlist.0: not found: key '0' would have to be created, but a key of digits only cannot be created (it reads as a list index)`

**Example 2:** `config set other.1 beta` _(observed)_

- Route 1: exit 5, file unchanged: `troupe: other.1: index 1 out of range`
- Route 2: All five arms: exit 5, file unchanged, with the same kind of "not found" message as above (e.g. `troupe: path not found: other.1`)

**Example 3:** `config set deep.inner.0 x` _(observed)_

- Route 1: exit 0; both missing levels are created and the file gains:

  ~~~
  deep:
    inner:
      - x
  ~~~

- Route 2: All five arms: exit 5, file unchanged (e.g. `troupe: deep.inner.0: not found (deep does not exist)`)

**Example 4:** `config set items.2 c` (items holds a, b) _(observed)_

Starting file:

~~~
name: demo
items:
  - a
  - b
~~~

- Route 1: exit 0; c is appended:

  ~~~
  items:
    - a
    - b
    - c
  (the file also still holds the newlist and deep entries from the earlier commands)
  ~~~

- Route 2: All five arms: exit 0; the file now reads:

  ~~~
  name: demo
  items:
    - a
    - b
    - c
  ~~~


**In practice:** On route 1, `.0` under a key that doesn't exist yet creates a one-item list, and that works at any depth. Any other index under a missing key fails. On route 2, a digit-only segment can never create anything, so a new list can't be started with `config set`. Both routes append when the index equals the current length.

**Trade-off:** Route 1 lets a user start a list with `config set`, but `.0` quietly gets the extra meaning "create a list". Route 2 keeps path creation to plain keys only, but a user cannot start a new list from the command line.

### Route 1

- Route: A `0` segment under a missing parent creates a new list; any other index exits 5
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 3 - Invents list-creation behaviour the contract does not define

rating: 5
reason: Creating the list when .0 is addressed is what I'd expect.

### Route 2

- Route: Missing segments are created only as mapping keys; a missing digit segment exits 5; index == length appends, larger indexes exit 5
- Reasoning given: Digit-only keys are out of contract and the contract describes no new lists
- Outcome: Kept
- proposed: 5 - Conservative and contract-bounded

rating: 3
reason: Refuses an obvious request; supporting it only through other, less obvious syntax is confusing.

## T20

**Question:** Duplicate mapping keys at load  
**Kind:** divergent

**What's at stake:** A hand-edited config file can end up with the same key twice (here `model: opus` and later `model: sonnet`). The user either gets told about it, or the tool quietly picks one of the two values, and that may not be the one it later edits or shows.

**What each route does** (run against every arm's final code):

**Example 1:** `config get model` _(observed)_

Starting file:

~~~
# duplicate key below
model: opus  # first
retry: 3
model: sonnet  # second
agents:
  coder:
    temperature: 0.2
~~~

- Route 1: Both arms: exit 4, nothing printed. One arm's message is `/theatre/.troupe/troupe.yml: model: duplicate key in mapping`. The other arm's is `troupe: cannot load /theatre/.troupe/troupe.yml: duplicate key model at line 4`. Every other command in this run (`set`, `show`, `history`) fails the same way, and the file is never touched.
- Route 2: The four arms split three ways. One arm: exit 4, `troupe: .troupe/troupe.yml (line 4, column 1): duplicate key 'model'`, and every later command fails the same way with the file untouched. Two arms: exit 0, prints `sonnet` (the second value). One arm: exit 0, prints `opus` (the first value).

**Example 2:** `config set model haiku` _(observed)_

Starting file:

~~~
# duplicate key below
model: opus  # first
retry: 3
model: sonnet  # second
agents:
  coder:
    temperature: 0.2
~~~

- Route 1: Both arms: exit 4 with the duplicate-key error; the file is unchanged.
- Route 2: One arm: exit 4 with the duplicate-key error; the file is unchanged.

  ~~~
  Two arms: exit 0; the file now reads:
  # duplicate key below
  model: opus  # first
  retry: 3
  model: haiku   # second
  One arm: exit 0; it edits the first `model` line instead, so the file now reads:
  # duplicate key below
  model: haiku # first
  retry: 3
  model: sonnet  # second
  ~~~


**Example 3:** `config set retry 5`, then `config show` _(observed)_

- Route 1: Both arms: both commands exit 4 with the duplicate-key error.
- Route 2: One arm: both commands exit 4. Two arms: exit 0. The file keeps both `model` lines, and only the `retry: 3` line becomes `retry: 5`. `show` prints:

  ~~~
  model: haiku
  retry: 5
  agents:
    coder:
      temperature: 0.2
  One arm: exit 0. `show` prints both keys:
  model: haiku
  retry: 5
  model: sonnet
  agents:
    coder:
      temperature: 0.2
  ~~~


**Example 4:** `config history` (after the two sets above) _(observed)_

- Route 1: Both arms: exit 4 with the duplicate-key error.
- Route 2: One arm: exit 4. Two arms: exit 0. The history shows the import of `model` as "sonnet", then `set model` sonnet -> haiku and `set retry` 3 -> 5 by human:owner. One arm: exit 0. The import also records `model` as "sonnet", but there is no entry for the `model` change at all. The only set listed is `retry` 3 -> 5, even though this arm had read `opus` and rewritten the `opus` line.

**In practice:** On route 1, a config file with a repeated key stops every command, including read-only ones like `get`, `show` and `history`, until the user removes the duplicate. On route 2, three of the four arms accept the file silently, with no warning, and the user's duplicate stays in the file. Two of them consistently use the last value. The third reads and edits the first value but records the second in history, so `get`, `show` and the history disagree with each other.

**Trade-off:** Route 1 blocks all use, even reading, until the file is fixed. Route 2 usually keeps working with no warning, picks a value inconsistently from arm to arm, and in one arm leaves a history that doesn't match the file.

### Route 1

- Route: Exit 4 (load error)
- Reasoning given: Ambiguous meaning; the byte-surgical writer cannot handle them
- Outcome: Kept
- proposed: 5 - Safe

rating: 5
reason: Raising the duplicate key is correct.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Last-wins hides which value is real and breaks splicing

rating: 2.5
reason: RESLICE placeholder: one arm raises it (5); two silently take the last value (2, arbitrary; a warning would be better than silence); one takes the first value and contradicts itself across get/show/history (1). See decisions/reslice.md.

## T21

**Question:** Saving when nothing changed  
**Kind:** divergent

**What's at stake:** When someone sets a config key to the value it already has, should the tool leave the file and the history alone, or rewrite the file and log a change that changed nothing? If it logs one, the audit trail fills up with fake changes credited to whoever ran the command. If it rewrites the file, the hand-written comments and quoting are at risk.

**What each route does** (run against every arm's final code):

**Example 1:** `config set model opus --reason no-op` (as human:owner; model is already `opus`) _(observed)_

Starting file:

~~~
# team config
name: "coder"   # quoted on purpose
temperature: 0.2  # tuned
model: opus
retries: 3
~~~

- Route 1: exit 0, no output; the file is untouched (all four arms)
- Route 2: exit 0, no output; the file is untouched (both arms)

**Example 2:** `config set name coder` (as agent:bot; the file has `name: "coder"`, quoted) _(observed)_

- Route 1: exit 0, no output; the file is untouched and its quotes and comment are kept (all four arms)
- Route 2: exit 0, no output; the file is untouched and its quotes and comment are kept (both arms)

**Example 3:** `config set temperature 0.20` (as agent:bot; the file has `temperature: 0.2`) _(observed)_

- Route 1: exit 0, no output; 0.20 is treated as the same value and the file is untouched (all four arms)
- Route 2: exit 0, no output; 0.20 is treated as the same value and the file is untouched (both arms)

**Example 4:** `config set retries 4 --reason "real change"` (as human:owner) _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
  # team config
  name: "coder"   # quoted on purpose
  temperature: 0.2  # tuned
  model: opus
  retries: 4
  (all four arms)
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  # team config
  name: "coder"   # quoted on purpose
  temperature: 0.2  # tuned
  model: opus
  retries: 4
  (both arms)
  ~~~


**Example 5:** `config history` (after all four commands above) _(observed)_

- Route 1: exit 0; 5 entries. Entries 1–4 are `import` records of the starting values (actor unknown). Entry 5 is `set retries 3 -> 4` by human:owner with the reason "real change". The three no-op commands left no entry: no "no-op" reason, and nothing from agent:bot (all four arms)
- Route 2: exit 0; 5 entries. Entries 1–4 are `import` records of the starting values (actor unknown). Entry 5 is `set retries 3 -> 4` by human:owner with the reason "real change". The three no-op commands left no entry: no "no-op" reason, and nothing from agent:bot (both arms)

**In practice:** There is no visible difference between the routes. Every arm on both routes skipped saving and logging for the no-op commands. Only the timestamps and change IDs in the history differ.

**Trade-off:** Route 1 makes 'no change, no save, no history entry' a deliberate rule. Route 2 did not consider the case, yet behaved the same in this run, so the behavior depends on nothing in its design keeping it that way.

### Route 1

- Route: Save and stamp nothing when there are no events
- Reasoning given: A command with no events records no change
- Outcome: Kept
- proposed: 5 - Clean

rating: n/a
reason: Doesn't matter: every arm behaves identically.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: n/a
reason: Doesn't matter: identical behaviour.

## T22

**Question:** Writing an empty collection  
**Kind:** divergent

**What's at stake:** Whether setting a key to an empty list or map (`[]`, `{}`) writes a valid file that keeps your comments and layout, and whether that key can be filled in later. In every test, both routes did exactly the same thing.

**What each route does** (run against every arm's final code):

**Example 1:** `config set tools []` _(observed)_

Starting file:

~~~
# troupe config
model: opus
agents:
  coder:
    opts: none  # coder options
    temperature: 0.2
~~~

- Route 1: exit 0, no output; the file now ends with:

  ~~~
  tools: []
  ~~~

- Route 2: exit 0, no output; the file now ends with:

  ~~~
  tools: []
  ~~~


**Example 2:** `config set agents.coder.opts {}` _(observed)_

Starting file:

~~~
# troupe config
model: opus
agents:
  coder:
    opts: none  # coder options
    temperature: 0.2
tools: []
~~~

- Route 1: exit 0, no output; the line now reads (the comment stays in its column):

  ~~~
      opts: {}    # coder options
  ~~~

- Route 2: exit 0, no output; the line now reads (the comment stays in its column):

  ~~~
      opts: {}    # coder options
  ~~~


**Example 3:** `config set extra "{a: [], b: {}, c: 1}"` _(observed)_

- Route 1: exit 0, no output; the file now ends with:

  ~~~
  extra:
    a: []
    b: {}
    c: 1
  ~~~

- Route 2: exit 0, no output; the file now ends with:

  ~~~
  extra:
    a: []
    b: {}
    c: 1
  ~~~


**Example 4:** `config set tools.0 search` (tools was `[]`) _(observed)_

- Route 1: exit 0, no output; the line now reads:

  ~~~
  tools: [search]
  ~~~

- Route 2: exit 0, no output; the line now reads:

  ~~~
  tools: [search]
  ~~~


**Example 5:** `config show` _(observed)_

- Route 1: exit 0; prints the config without comments, with tools as a block list:

  ~~~
  model: opus
  agents:
    coder:
      opts: {}
      temperature: 0.2
  tools:
    - search
  extra:
    a: []
    b: {}
    c: 1
  ~~~

- Route 2: exit 0; same output as route 1

**In practice:** Both routes write empty values as `[]` / `{}`, keep the comments and their alignment, and let you add items afterwards. A list that started empty stays on one line in the file (`tools: [search]`), but `config show` prints it as a block list. Route 2 never considered the issue, yet it behaved the same as route 1 in every test.

**Trade-off:** Route 1 handles empty values explicitly. Route 2 never considered them but got the same results in these tests, so it's untested on cases outside them.

### Route 1

- Route: Write {} or [] in flow form
- Reasoning given: Block style cannot represent an empty collection
- Outcome: Kept
- proposed: 5 - Only option

rating: n/a
reason: Nothing to choose between: every arm behaves identically, and YAML forces [] and {}.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Forced by YAML

rating: n/a
reason: Identical behaviour.

## T23

**Question:** An empty text include  
**Kind:** divergent

**What's at stake:** When a prompt file included with `file:` is empty, or a prompt is set to empty, the user needs `config show` and `config get` to say clearly that the prompt is empty. The output should not look broken or like it lost the value.

**What each route does** (run against every arm's final code):

**Example 1:** `config show` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
agents:
  coder:
    model: opus
    prompt: file:prompts/coder.txt  # empty prompt
  reviewer:
    model: sonnet
    prompt: file:prompts/reviewer.txt

.troupe/prompts/coder.txt is empty; .troupe/prompts/reviewer.txt reads:
Review carefully.
Be brief.
~~~

- Route 1: exit 0; prints:

  ~~~
  agents:
    coder:
      model: opus
      prompt: |-
    reviewer:
      model: sonnet
      prompt: |
        Review carefully.
        Be brief.
  ~~~

- Route 2: Same as route 1. Exit 0, and the empty coder prompt is shown as a bare `prompt: |-`.

**Example 2:** `config show agents --sources` _(observed)_

- Route 1: exit 0; prints:

  ~~~
  coder:
    model: opus # from .troupe/troupe.yml
    prompt: |- # from .troupe/prompts/coder.txt
  reviewer:
    model: sonnet # from .troupe/troupe.yml
    prompt: | # from .troupe/prompts/reviewer.txt
      Review carefully.
      Be brief.
  ~~~

- Route 2: Same as route 1. The empty prompt is shown as `prompt: |- # from .troupe/prompts/coder.txt`.

**Example 3:** `config get agents.coder.prompt` _(observed)_

- Route 1: exit 0; prints a single empty line
- Route 2: exit 0; prints a single empty line

**Example 4:** `config set agents.reviewer.prompt '""'`, then `config show agents.reviewer` _(observed)_

- Route 1: The set exits 0 and prints nothing. .troupe/prompts/reviewer.txt is now empty, and troupe.yml is not changed. The show then exits 0 and prints:

  ~~~
  model: sonnet
  prompt: |-
  ~~~

- Route 2: Same as route 1. reviewer.txt is emptied, troupe.yml is untouched, and the show prints `prompt: |-`.

**In practice:** In these runs the two routes behave the same. All arms on both routes print an empty included prompt as a bare `|-`. Setting a prompt to `""` empties the included file and leaves troupe.yml alone. The only difference is that route 1 chose `|-` on purpose, while route 2 gets the same result without having considered the case.

**Trade-off:** Route 1 commits to a deliberate rule for empty prompts. Route 2 gives the same output today without having decided it, so that output could change later without anyone noticing.

### Route 1

- Route: `|-`
- Reasoning given: Literal rule
- Outcome: Kept
- proposed: 5 - Exact

rating: n/a
reason: Nothing to choose between: identical behaviour.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Edge

rating: n/a
reason: Identical behaviour.

## T24

**Question:** Where an empty value (`key:`) is filled in  
**Kind:** divergent

**What's at stake:** A config file can have keys with nothing after the colon, like `model:`, a comment-only `timeout: # seconds`, a bare list item `-`, or a last line `last:` with no newline. If a value is put in the wrong place, `config set` could refuse the key, damage the file or lose the comment.

**What each route does** (run against every arm's final code):

**Example 1:** `config set model opus` _(observed)_

Starting file:

~~~
model:
timeout:   # seconds
name: x
tags:
  -
  - b
last:
~~~

- Route 1: exit 0, no output; the first line now reads:

  ~~~
  model: opus
  The rest of the file is unchanged.
  ~~~

- Route 2: exit 0, no output; the first line now reads:

  ~~~
  model: opus
  The rest of the file is unchanged.
  ~~~


**Example 2:** `config set timeout 30` (the empty value has a trailing comment) _(observed)_

- Route 1: exit 0; the line now reads:

  ~~~
  timeout: 30 # seconds
  ~~~

- Route 2: exit 0; the line now reads:

  ~~~
  timeout: 30 # seconds
  ~~~


**Example 3:** `config set tags.0 a` (a bare `-` list item) _(observed)_

- Route 1: exit 0; the list now reads:

  ~~~
  tags:
    - a
    - b
  ~~~

- Route 2: exit 0; the list now reads:

  ~~~
  tags:
    - a
    - b
  ~~~


**Example 4:** `config set last done` (empty key on the last line, no trailing newline), then `config show` _(observed)_

- Route 1: exit 0; the last line now reads:

  ~~~
  last: done
  `config show` prints:
  model: opus
  timeout: 30
  name: x
  tags:
    - a
    - b
  last: done
  ~~~

- Route 2: exit 0; the last line now reads:

  ~~~
  last: done
  `config show` prints:
  model: opus
  timeout: 30
  name: x
  tags:
    - a
    - b
  last: done
  ~~~


**In practice:** Both routes gave exactly the same result on every command: 2 arms on route 1 and 4 arms on route 2, with no differences within either route. Every empty value was filled in on its own line, the `# seconds` comment was kept, and no command refused or failed. Route 1's stated reason was that otherwise such sets would be refused, but this test did not trigger that failure on route 2.

**Trade-off:** Route 1 adds its own handling for where an empty value goes; route 2 adds nothing extra and did just as well on this test.

### Route 1

- Route: Right after the ':' indicator rather than at the parser's mark
- Reasoning given: ruamel puts the empty value's mark on the next line, which made such sets refuse
- Outcome: Kept
- proposed: 5 - Fixes a real refusal bug

rating: n/a
reason: Nothing to choose between: identical behaviour.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Implementation detail

rating: n/a
reason: Identical behaviour.

## T25

**Question:** How errors map to exit codes and stdout  
**Kind:** divergent

**What's at stake:** Scripts and users rely on the exit code to know what went wrong, and on stdout being empty when a command fails. Both routes gave identical exit codes, and on every failure stdout was empty and no file changed. Only the error wording on stderr differed.

**What each route does** (run against every arm's final code):

**Example 1:** `config get agents` _(observed)_

Starting file:

~~~
name: demo  # project
tools:
  - lint
  - test
agents:
  coder: file:agents/coder.yaml
  reviewer:
    model: opus
~~~

- Route 1: all four arms: exit 5, stdout empty, stderr says agents is a mapping and points to `troupe config show agents`
- Route 2: both arms: exit 5, stdout empty, stderr says agents is a mapping and points to `troupe config show agents`

**Example 2:** `config set tools.5 build` _(observed)_

Starting file:

~~~
tools:
  - lint
  - test
~~~

- Route 1: all four arms: exit 5, stdout empty, file unchanged. Two arms give the list length; one also says to use index 2 to append (e.g. "list index 5 is beyond the end of a list of 2 (use index 2 to append)"). The other two only say index 5 is out of range.
- Route 2: both arms: exit 5, stdout empty, file unchanged, stderr gives the list length (2). One arm adds "only index 2 appends".

**Example 3:** `config set agents.coder '{model: haiku}'` _(observed)_

Starting file:

~~~
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: all four arms: exit 3, stdout empty, neither file changed. The stderr says the value comes from the included file. One arm puts coder.yaml's path at the start of the message instead of troupe.yml's.
- Route 2: both arms: exit 3, stdout empty, neither file changed. The stderr says the value comes from coder.yaml and the command refuses to replace it.

**Example 4:** `config set name '[a, {b'` _(observed)_

- Route 1: all four arms: exit 2, stdout empty, file unchanged. Three arms print one line, from bare ("troupe: invalid value: '[a, {b'") to detailed (with line and column). One arm prints the parser's raw output over 9 lines, with ^ markers.
- Route 2: both arms: exit 2, stdout empty, file unchanged. One line each, saying the value is invalid YAML ("expected ',' or '}', but got '<stream end>'"), with line and column or line only.

**Example 5:** `TROUPE_ACTOR=robot:x config show` _(observed)_

- Route 1: all four arms: exit 2, stdout empty, stderr says TROUPE_ACTOR must be human:<id> or agent:<id>
- Route 2: both arms: exit 2, stdout empty, stderr says TROUPE_ACTOR must be human:<id> or agent:<id>

**In practice:** From the outside, the routes behaved the same in these runs: same exit codes (5 for not found / wrong type, 3 for refusing to write through an include, 2 for bad input or environment), nothing on stdout and no file changed. The differences are in the stderr wording: whether it starts with "troupe:", how much it hints at a fix, and in one arm on route 1, a multi-line parser dump. The tests did not cover an unexpected internal error, which is where route 1 does not catch exceptions.

**Trade-off:** Route 1 keeps the exit-code mapping in one place but leaves unexpected crashes uncaught. Route 2 was not described as a design, and its visible results match route 1.

### Route 1

- Route: Typed errors each carry an exit code and only the CLI converts them; stdout is buffered and empty on any failure
- Reasoning given: One place for the code-to-meaning mapping; unexpected exceptions are not caught
- Outcome: Kept
- proposed: 5 - Clean

rating: 3
reason: RESLICE placeholder: exit codes are right everywhere; rated on error wording. One arm gives the fix (4), one the facts (3), two are bare (3).

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract-defined

rating: 3.5
reason: RESLICE placeholder: one arm gives the fix (4), one the facts (3).

## T26

**Question:** How a set VALUE that is a file: string is handled (before step 7)  
**Kind:** divergent

**What's at stake:** When the value given to `config set` starts with `file:`, it matters whether you get the literal text you typed or the contents of that file, and whether a typo'd or self-referencing file name is caught before anything is written. The routes behave the same on every write tested here. They differ in how `config show` prints a literal `file:` value and in which exit code a broken include target gets.

**What each route does** (run against every arm's final code):

**Example 1:** `config set note file:notes.txt` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
name: demo  # project
note: hello
other: x

.troupe/notes.txt:
included text
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  name: demo  # project
  note: !literal file:notes.txt
  other: x
  ~~~

- Route 2: all three arms: exit 0, no output; the file now reads:

  ~~~
  name: demo  # project
  note: !literal file:notes.txt
  other: x
  ~~~

- Route 3: both arms: exit 0, no output; the file now reads:

  ~~~
  name: demo  # project
  note: !literal file:notes.txt
  other: x
  ~~~


**Example 2:** `config set --include other file:notes.txt` _(observed)_

- Route 1: exit 0, no output; the file now reads:

  ~~~
  name: demo  # project
  note: !literal file:notes.txt
  other: file:notes.txt
  ~~~

- Route 2: all three arms: exit 0, no output; the file now reads:

  ~~~
  name: demo  # project
  note: !literal file:notes.txt
  other: file:notes.txt
  ~~~

- Route 3: both arms: exit 0, no output; the file now reads:

  ~~~
  name: demo  # project
  note: !literal file:notes.txt
  other: file:notes.txt
  ~~~


**Example 3:** `config show` (after the two sets above) _(observed)_

- Route 1: exit 0; prints:

  ~~~
  name: demo
  note: file:notes.txt
  other: |
    included text
  ~~~

- Route 2: all three arms: exit 0; prints:

  ~~~
  name: demo
  note: file:notes.txt
  other: |
    included text
  ~~~

- Route 3: both arms: exit 0; prints the literal with its tag:

  ~~~
  name: demo
  note: !literal file:notes.txt
  other: |
    included text
  ~~~


**Example 4:** `config set --include name file:missing.txt` _(observed)_

- Route 1: exit 3, nothing written: "troupe: name: include target not found: /theatre/.troupe/missing.txt (included from /theatre/.troupe/troupe.yml, at name); no file changed"
- Route 2: all three arms: exit 3, nothing written; the messages are worded differently but all say the written value would not load back, e.g. "troupe: name: the result would not load (.troupe/missing.txt: included file not found (from .troupe/troupe.yml)); not writing"
- Route 3: one arm: exit 3, nothing written: "troupe: write refused: name: cannot write this change faithfully (/theatre/.troupe/troupe.yml: include target /theatre/.troupe/missing.txt not found)"; one arm: exit 4, nothing written: "troupe: .troupe/missing.txt: included file not found (from ./.troupe/troupe.yml)"

**Example 5:** `config set --include name file:troupe.yml` (the file includes itself) _(observed)_

- Route 1: exit 3, nothing written: "troupe: name: include cycle at name: /theatre/.troupe/troupe.yml -> /theatre/.troupe/troupe.yml; no file changed"
- Route 2: all three arms: exit 3, nothing written; each reports an include cycle that would not load back, e.g. "troupe: error: name: the change to /theatre/.troupe/troupe.yml would not load back (/theatre/.troupe/troupe.yml: include cycle through /theatre/.troupe/troupe.yml); no file was changed"
- Route 3: one arm: exit 3, nothing written: "troupe: write refused: name: cannot write this change faithfully (/theatre/.troupe/troupe.yml: include cycle through /theatre/.troupe/troupe.yml)"; one arm: exit 4, nothing written: "troupe: .troupe/troupe.yml: include cycle (from ./.troupe/troupe.yml)"

**In practice:** Without `--include`, every route stores `file:...` as plain text (tagged `!literal` in the file). With `--include`, every route refuses a missing or self-referencing target and leaves the file untouched. On routes 1 and 2, `config show` prints the stored value as plain `file:notes.txt`. On route 3 it prints the `!literal` tag. On route 3, one arm also uses exit 4 instead of 3 for a bad include target.

**Trade-off:** Route 1 reports a bad target as an include problem at the key. Route 2's errors say the written value would not load back, worded differently across its three arms. Route 3 shows `!literal` in `config show`, and its arms disagree on the exit code (3 vs 4).

### Route 1

- Route: Verify a file: string as the written text
- Reasoning given: Contract silent
- Outcome: Superseded at step 7
- proposed: 4 - Safe, but how it treats the include meaning is unclear

rating: 2
reason: show drops the !literal mark; output should keep it.

### Route 2

- Route: Write it as a string and let the read-back load decide; a missing, cyclic or unloadable target exits 3
- Reasoning given: Refusing narrows the contract; verification keeps it safe. One arm reworked from a blanket refusal, another from comparing against the literal string
- Outcome: Reworked at step 1 in two arms; superseded at step 7 by writing !literal unless --include
- proposed: 5 - Contract-faithful and safe

rating: 2
reason: show drops the !literal mark; output should keep it.

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Writing an include that cannot load would break the configuration

rating: 3.5
reason: RESLICE placeholder: both keep the mark. One arm exits 3 (4); one exits 4, a load error, which is incorrect (3). See decisions/reslice.md.

## T27

**Question:** Style of a collection that replaces a flow collection  
**Kind:** divergent

**What's at stake:** When `config set` replaces a value written inline as `[a, b]` or `{k: v}`, the user's one-line config entry either stays on one line or becomes a multi-line block. That decides whether the file still looks the way they wrote it.

**What each route does** (run against every arm's final code):

**Example 1:** `config set tools "[grep, edit, run]"` _(observed)_

Starting file:

~~~
# troupe config
name: demo
tools: [read, write]  # default tools
limits: {cpu: 1, mem: 2}
agent: {model: opus, opts: {temp: 1}, tags: [a]}
retry: 3
~~~

- Route 1: exit 0; the list becomes a block, and the comment stays on the `tools:` line:

  ~~~
  tools:                # default tools
    - grep
    - edit
    - run
  ~~~

- Route 2: exit 0; the list stays on one line, with one space left before the comment:

  ~~~
  tools: [grep, edit, run] # default tools
  ~~~

- Route 3: three arms: exit 0, same as route 2:

  ~~~
  tools: [grep, edit, run] # default tools
  one arm: exit 0, stays on one line and keeps the original two spaces before the comment:
  tools: [grep, edit, run]  # default tools
  ~~~


**Example 2:** `config set limits "{cpu: 4, gpu: 1}"` (after the step above) _(observed)_

Starting file:

~~~
limits: {cpu: 1, mem: 2}
~~~

- Route 1: exit 0; the map becomes a block:

  ~~~
  limits:
    cpu: 4
    gpu: 1
  ~~~

- Route 2: exit 0; stays inline:

  ~~~
  limits: {cpu: 4, gpu: 1}
  ~~~

- Route 3: exit 0, all four arms; stays inline:

  ~~~
  limits: {cpu: 4, gpu: 1}
  ~~~


**Example 3:** `config set agent.opts "[x, y]"` (the parent `agent` is written inline) _(observed)_

Starting file:

~~~
agent: {model: opus, opts: {temp: 1}, tags: [a]}
~~~

- Route 1: exit 0; the new list is written inline inside the inline parent:

  ~~~
  agent: {model: opus, opts: [x, y], tags: [a]}
  ~~~

- Route 2: exit 0; same:

  ~~~
  agent: {model: opus, opts: [x, y], tags: [a]}
  ~~~

- Route 3: exit 0, all four arms; same:

  ~~~
  agent: {model: opus, opts: [x, y], tags: [a]}
  ~~~


**Example 4:** `config get agent.opts.1`, then `config show` _(observed)_

- Route 1: `get` prints `y`. `show` exits 0 and lists everything as blocks, with the second item quoted:

  ~~~
    opts:
      - x
      - 'y'
  ~~~

- Route 2: `get` prints `y`. `show` exits 0 and lists everything as blocks, with the item unquoted:

  ~~~
    opts:
      - x
      - y
  ~~~

- Route 3: all four arms: `get` prints `y`. `show` exits 0, the same as route 2 (`- y` unquoted)

**In practice:** Under route 1, the first `set` on any top-level inline list or map turns that one line into several. Inline values nested inside another inline value stay inline on every route, because a block can't go inside an inline value. Routes 2 and 3 leave the file shaped the way it was. They differ only in the spacing before a trailing comment: route 2 and three arms of route 3 shrink it to one space, while one arm of route 3 keeps the original two.

**Trade-off:** Route 1 gives every newly set top-level value a uniform block layout, but it rewrites the look of the user's inline lines and leaves the comment stranded on the key line. Routes 2 and 3 keep the user's layout, but a nested value's style follows its parent, not one consistent rule.

### Route 1

- Route: Block style (the 'new collection value' rule read literally; owner confirmed)
- Reasoning given: Owner confirmed
- Outcome: Kept
- proposed: 4 - Contract-faithful

rating: 3
reason: Rewrites an inline line as a block; keeping formatting and comments is desirable more often than not.

### Route 2

- Route: Render in the old one's style; new collections inside a flow parent use flow
- Reasoning given: Block lines cannot appear inside flow
- Outcome: Kept
- proposed: 4 - Reasonable

rating: 3
reason: Stays inline but shrinks the gap before the comment.

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Edge

rating: 3
reason: RESLICE placeholder: three arms shrink the comment gap (3); one keeps the formatting exactly (4). See decisions/reslice.md.

## T28

**Question:** Handling ruamel's U+0007 fold markers in folded values  
**Kind:** divergent

**What's at stake:** Folded (`>`) values in troupe.yml could pick up stray invisible bell characters (U+0007) that end up in `get`/`show` output, in the history log, or written back to the file. Meanwhile a real `\a` that the user wrote in a double-quoted value has to survive. In this run no route leaked any marker. The only difference between routes is whether `show` keeps the `!literal` tag.

**What each route does** (run against every arm's final code):

**Example 1:** `config get agents.coder.prompt` (prompt is a folded `>` block) and `config get agents.coder.motto` (a `!literal >` block) _(observed)_

Starting file:

~~~
agents:
  coder:
    prompt: >
      You review code carefully and
      explain every finding plainly.

      Keep answers short and cite
      the file and line.
    motto: !literal >
      file:notes.txt is not an include
      here, it is just folded text.
    bell: "ding\a"
~~~

- Route 1: both arms the same. exit 0, clean text with no stray characters:

  ~~~
  You review code carefully and explain every finding plainly.
  Keep answers short and cite the file and line.
  and for motto:
  file:notes.txt is not an include here, it is just folded text.
  ~~~

- Route 2: all four arms gave exactly the same output as route 1

**Example 2:** `config show agents.coder` _(observed)_

- Route 1: both arms: exit 0; the `!literal` tag on motto is dropped:

  ~~~
  prompt: |
    You review code carefully and explain every finding plainly.
    Keep answers short and cite the file and line.
  motto: |
    file:notes.txt is not an include here, it is just folded text.
  bell: "ding\a"
  ~~~

- Route 2: two arms: same as route 1 (`motto: |`, tag dropped). Two arms: exit 0, tag kept:

  ~~~
  motto: !literal |
    file:notes.txt is not an include here, it is just folded text.
  The prompt and bell lines are the same as route 1 in all four arms.
  ~~~


**Example 3:** `config set agents.coder.prompt "You review code carefully and explain every finding plainly.\nKeep answers brief, and always cite the file and the line number.\n"` _(observed)_

- Route 1: both arms: exit 0; the file now reads:

  ~~~
      prompt: >
        You review code carefully and
        explain every finding plainly.
  
        Keep answers brief, and
        always cite the file and
        the line number.
      motto: !literal >
        file:notes.txt is not an include
        here, it is just folded text.
      bell: "ding\a"
  ~~~

- Route 2: all four arms: identical to route 1, byte for byte

**Example 4:** `config history agents.coder` _(observed)_

- Route 1: both arms: exit 0. The imported prompt and motto values contain no bell characters. bell is recorded as "ding\u0007" (the real `\a` is kept). The set is logged as actor human:owner via cli.
- Route 2: all four arms: the same entries as route 1

**In practice:** With this config, the two routes act the same for get, set, history and the file written back. There are no leaked fold markers, and the double-quoted `\a` is preserved. The one visible difference is in `show`: route 1 always shows the `!literal` motto as a plain `|` block, and so do half of route 2's arms. The other half of route 2's arms keep `!literal |`. That means the tag is visible to the user in some arms and not in others.

**Trade-off:** Route 1 adds explicit stripping for folded values, but in this run that gained nothing visible and `show` dropped the `!literal` tag. Route 2 adds nothing, gives the same clean output here, but is inconsistent about showing the `!literal` tag.

### Route 1

- Route: Strip them from folded values (also under !literal)
- Reasoning given: show was printing them; only folded style is stripped because \a in double quotes is legitimate
- Outcome: Kept
- proposed: 5 - Correct values

rating: n/a
reason: No arm leaks anything; the only difference is the !literal mark in show, already rated in T8 and T26.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - show could print control characters

rating: n/a
reason: Same: no leaks; the !literal difference is already rated.

## T29

**Question:** Editing folded scalars with more-indented lines  
**Kind:** divergent

**What's at stake:** Someone whose config has a folded (`>`) text containing an indented line, such as a code snippet, wants to change the ordinary prose around it. The question is whether `config set` lets them, or refuses, so the only way to change it is editing the file by hand.

**What each route does** (run against every arm's final code):

**Example 1:** `config set note "First paragraph line one continues here.\n\n indented code line\n\nLast paragraph changed now and ends.\n"` (only the last paragraph changes; the indented line stays the same) _(observed)_

Starting file:

~~~
# folded scalars
note: >
  First paragraph line one
  continues here.

    indented code line

  Last paragraph is here
  and ends.
summary: >
  Short folded text
  on two lines.
other: x  # end
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  note: >
    First paragraph line one
    continues here.
  
      indented code line
  
    Last paragraph changed
    now and ends.
  summary: >
  The rest of the file, including the comment and `other: x  # end`, is unchanged. `config history note` shows the change recorded as a set by human:owner.
  ~~~

- Route 2: exit 3, file unchanged, nothing added to history. All three arms refused. One arm says "cannot rewrite this value safely (unsupported tag or block layout)". The other two say "value would put a more-indented line into a folded scalar" (one of them also names the file path).
- Route 3: exit 3, file unchanged, nothing added to history. Both arms refused. One arm says "its folded value contains a more-indented line, and writing it back would put a more-indented line into a folded value". The other says "the new value would put a more-indented line into the folded value at line 2 of …/troupe.yml".

**Example 2:** `config set note "First paragraph line one continues here.\n\n indented code CHANGED\n\nLast paragraph changed now and ends.\n"` (the indented line's own text changes) _(observed)_

- Route 1: exit 3, file unchanged: "note: the line ' indented code CHANGED' would be more-indented in a folded block"
- Route 2: exit 3, file unchanged. Every arm gives the same message it gave for the first edit.
- Route 3: exit 3, file unchanged. Both arms give the same message they gave for the first edit.

**Example 3:** `config set summary "Short folded text on two lines.\n new indented line\n"` (adds an indented line to a folded value that had none) _(observed)_

Starting file:

~~~
summary: >
  Short folded text
  on two lines.
~~~

- Route 1: exit 3, file unchanged: "summary: the line ' new indented line' would be more-indented in a folded block"
- Route 2: exit 3, file unchanged. All three arms refused. Two say the new value would need or put a more-indented line into a folded scalar. One arm repeats its "write refused … more-indented line" message.
- Route 3: exit 3, file unchanged. Both arms refused. One quotes the line ' new indented line'. The other points to line 10 of the file.

**In practice:** Routes 2 and 3 behaved the same in every observed case. Once a folded value contains an indented line, neither lets `config set` change anything in that value, not even ordinary prose elsewhere in it. Route 1 lets that prose be edited and keeps the indented line exactly as it was. It still refuses (exit 3) any set that changes the indented line's text or adds a new indented line. `config get` was the same on all routes.

**Trade-off:** Route 1 allows prose edits around an existing indented line but needs more complicated rewriting. Routes 2 and 3 are simpler and stricter, but any value that already has an indented line can then only be changed by hand-editing the file.

### Route 1

- Route: Edit allowed; existing indented runs are kept as opaque units; only adding a new more-indented line exits 3
- Reasoning given: Final validation: the contract refuses only adding such a line
- Outcome: Reworked at step 1 from refusing any edit, then kept
- proposed: 5 - Refuses exactly what the contract refuses

rating: 5
reason: Refuses exactly what the contract refuses; prose around an indented line stays editable.

### Route 2

- Route: Refuse (exit 3) a change that would introduce a more-indented line
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Contract-aligned; handling of existing runs left unstated

rating: 4
reason: Contract-aligned refusal, but blocks prose edits around an existing indented line.

### Route 3

- Route: Refuse any change to a folded value that already has more-indented lines
- Reasoning given: Its paragraphs cannot be split reliably; the owner confirmed
- Outcome: Kept
- proposed: 3 - Refuses legitimate edits the contract permits

rating: 3
reason: Refuses legitimate edits the contract permits.

## T30

**Question:** Randomised testing of write-back  
**Kind:** divergent

**What's at stake:** Every `config set` must write back into the user's own CRLF files, flow lists, block text and included files without damaging them, and `config show --sources` must display the result readably. Here every route wrote the files the same way. The only difference is how a CRLF-backed text value is displayed.

**What each route does** (run against every arm's final code):

**Example 1:** `config set limits.tags.2 c` _(observed)_

Starting file:

~~~
# team config
model: opus  # main model
limits: {retries: 3, tags: [a, b]}
agents:
  coder: file:agents/coder.yaml  # shared
  notes: file:notes.txt
~~~

- Route 1: exit 0; .troupe/troupe.yml now reads (CRLF and comments kept):

  ~~~
  limits: {retries: 3, tags: [a, b, c]}
  ~~~

- Route 2: all three arms: same as route 1, exit 0; .troupe/troupe.yml now reads:

  ~~~
  limits: {retries: 3, tags: [a, b, c]}
  ~~~


**Example 2:** `config set agents.coder.prompt "new one\nnew two\nnew three\n"` _(observed)_

Starting file:

~~~
temperature: 0.2
prompt: |
  line one
  line two
~~~

- Route 1: exit 0; .troupe/agents/coder.yaml now reads (still CRLF, no bare LF):

  ~~~
  temperature: 0.2
  prompt: |
    new one
    new two
    new three
  ~~~

- Route 2: all three arms: same as route 1, exit 0; .troupe/agents/coder.yaml now reads:

  ~~~
  temperature: 0.2
  prompt: |
    new one
    new two
    new three
  ~~~


**Example 3:** `config set agents.coder.max_tokens 4096` (coder is an included file) _(observed)_

- Route 1: exit 0; .troupe/troupe.yml now reads:

  ~~~
  agents:
    coder:  # shared
      $ref: file:agents/coder.yaml
      max_tokens: 4096
    notes: file:notes.txt
  ~~~

- Route 2: all three arms: same as route 1, exit 0; .troupe/troupe.yml now reads:

  ~~~
  agents:
    coder:  # shared
      $ref: file:agents/coder.yaml
      max_tokens: 4096
    notes: file:notes.txt
  ~~~


**Example 4:** `config set agents.notes "hello\nworld\n"`, then `config show --sources` _(observed)_

Starting file:

~~~
first note
second note
~~~

- Route 1: set: exit 0, notes.txt becomes "hello\r\nworld\r\n". show prints the value as a quoted string with escapes:

  ~~~
    notes: "hello\r\nworld\r\n" # from .troupe/notes.txt
  ~~~

- Route 2: set: all three arms exit 0, notes.txt becomes "hello\r\nworld\r\n". show differs between arms. Two arms print a clean block:

  ~~~
    notes: | # from .troupe/notes.txt
      hello
      world
  One arm prints a block with raw carriage-return characters left inside the output:
    notes: | # from .troupe/notes.txt
      hello
      world
  ~~~


**In practice:** On every route the files on disk came out byte-for-byte the same. CRLF was kept everywhere, comments survived, and the flow list stayed on one line. The only visible difference is how `config show --sources` displays a text value read from a CRLF file. Route 1 shows it as an escaped quoted string. On route 2, two arms show a clean block and one arm leaks stray carriage returns into the terminal output.

**Trade-off:** Route 1 costs writing and running randomised or seeded write-back tests (no new dependency). Route 2 skips that work but leaves the CRLF display behaviour unchecked, and on that route it differed between arms.

### Route 1

- Route: Random set sequences or seeded property tests over LF/CRLF, flow, block and includes, with no new dependency
- Reasoning given: Check that each set reads back and CRLF files never gain a bare LF
- Outcome: Kept
- proposed: 5 - Strong evidence

rating: 5
reason: Covers edge cases and unusual file shapes, which is where production issues come from, not the happy path

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Write-back has many corners that example tests miss

rating: 3
reason: Leaves edge-case write-back untested; production issues come from unusual cases, not the happy path

## T31

**Question:** Does get reconcile first  
**Kind:** divergent

**What's at stake:** After someone edits `.troupe/troupe.yml` or an agent file by hand, the question is whether `config get` returns the edited value or a stale one, and whether the edit gets recorded in history. In this test, both routes behaved the same way.

**What each route does** (run against every arm's final code):

**Example 1:** `config get model` (no hand edits yet) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
# main config
model: opus  # default model
retries: 2
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: all three arms: exit 0, prints `opus`
- Route 2: all three arms: exit 0, prints `opus`

**Example 2:** edit `.troupe/troupe.yml` by hand to `model: sonnet # default model`, then `config get model` _(observed)_

- Route 1: all three arms: exit 0, prints `sonnet`
- Route 2: all three arms: exit 0, prints `sonnet`

**Example 3:** edit `.troupe/agents/coder.yaml` by hand from `temperature: 0.2` to `temperature: 0.7`, then `config get agents.coder.temperature` _(observed)_

Starting file:

~~~
.troupe/agents/coder.yaml:
temperature: 0.2
role: coder
~~~

- Route 1: all three arms: exit 0, prints `0.7`
- Route 2: all three arms: exit 0, prints `0.7`

**Example 4:** `config history` after those two hand edits and gets _(observed)_

- Route 1: all three arms: exit 0; 4 import entries (model opus, retries 2, agents.coder.temperature 0.2, agents.coder.role coder), then seq 5 `set model opus -> sonnet` and seq 6 `set agents.coder.temperature 0.2 -> 0.7`, both `"via": "file"` and sharing one change id
- Route 2: all three arms: exit 0; same six entries, including seq 5 `set model opus -> sonnet` and seq 6 `set agents.coder.temperature 0.2 -> 0.7`, both `"via": "file"`

**Example 5:** `config show` _(observed)_

- Route 1: all three arms: exit 0, prints:

  ~~~
  model: sonnet
  retries: 2
  agents:
    coder:
      temperature: 0.7
      role: coder
  ~~~

- Route 2: all three arms: exit 0, same output

**In practice:** All six arms gave the same results, apart from timestamps and change ids. On both routes, `config get` returned the hand-edited values, and history recorded each hand edit as a `via: file` change. This test doesn't show which command wrote those history entries. No config file was changed by any troupe command.

**Trade-off:** Route 1 deliberately reconciles hand edits on `get`, the same way `show` does. Route 2 never considered the question but behaved the same way here, so this test shows no difference between them.

### Route 1

- Route: Yes, like show
- Reasoning given: Reads see hand edits the same way
- Outcome: Kept
- proposed: 5 - Consistent

rating: n/a
reason: Nothing to choose between: every arm picks up hand edits on get and logs them.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Rule covers it

rating: n/a
reason: Identical behaviour.

## T32

**Question:** How history's PATH filter matches  
**Kind:** divergent

**What's at stake:** When users ask for the history of a key such as `agents.coder`, they need its own changes and nothing from look-alike keys such as `agents.coderx`. A typo or unknown key also needs clear handling. In these runs every route behaved the same way. Only the wording of the error for a malformed path differed.

**What each route does** (run against every arm's final code):

**Example 1:** `config history agents.coder` _(observed)_

Starting file:

~~~
agent: solo
agents:
  coder:
    model: opus
  coderx:
    model: sonnet
  reviewer:
    model: haiku
~~~

- Route 1: exit 0; prints one entry, for `agents.coder.model` (new: "opus"). Nothing from `agents.coderx`
- Route 2: exit 0; prints one entry, for `agents.coder.model` (new: "opus"). Nothing from `agents.coderx`
- Route 3: exit 0; prints one entry, for `agents.coder.model` (new: "opus"). Nothing from `agents.coderx`
- Route 4: exit 0; prints one entry, for `agents.coder.model` (new: "opus"). Nothing from `agents.coderx`
- Route 5: both arms: exit 0; prints one entry, for `agents.coder.model` (new: "opus"). Nothing from `agents.coderx`

**Example 2:** `config history agent` _(observed)_

- Route 1: exit 0; prints only the entry for `agent` (new: "solo"). None of the `agents.*` entries
- Route 2: exit 0; prints only the entry for `agent` (new: "solo"). None of the `agents.*` entries
- Route 3: exit 0; prints only the entry for `agent` (new: "solo"). None of the `agents.*` entries
- Route 4: exit 0; prints only the entry for `agent` (new: "solo"). None of the `agents.*` entries
- Route 5: both arms: exit 0; prints only the entry for `agent` (new: "solo"). None of the `agents.*` entries

**Example 3:** `config history agents.cod` _(observed)_

- Route 1: exit 0; prints nothing
- Route 2: exit 0; prints nothing
- Route 3: exit 0; prints nothing
- Route 4: exit 0; prints nothing
- Route 5: both arms: exit 0; prints nothing

**Example 4:** `config history nosuch.key` _(observed)_

- Route 1: exit 0; prints nothing, no error
- Route 2: exit 0; prints nothing, no error
- Route 3: exit 0; prints nothing, no error
- Route 4: exit 0; prints nothing, no error
- Route 5: both arms: exit 0; prints nothing, no error

**Example 5:** `config history agents.coder.` _(observed)_

- Route 1: exit 2; stderr: `troupe: invalid path 'agents.coder.': empty segment`
- Route 2: exit 2; stderr: `troupe: invalid path: 'agents.coder.'`
- Route 3: exit 2; stderr: `troupe: error: invalid path 'agents.coder.': path segments must not be empty`
- Route 4: exit 2; stderr: `troupe: usage error: invalid path: 'agents.coder.'`
- Route 5: one arm: exit 2; stderr: `agents.coder.: malformed PATH 'agents.coder.': segments must not be empty (no leading, trailing or doubled '.')`; other arm: exit 2; stderr: `troupe: invalid path 'agents.coder.': empty segment`

**In practice:** Even though the routes were worded differently, including route 3's "plain string prefix", every route matched whole dot-separated segments only. A key matches only itself or keys below it, so `agent` does not pull in `agents.*` and `agents.coder` does not pull in `agents.coderx`. A key with no history, or a partial name, prints nothing and exits 0. You get no hint that the key doesn't exist. A trailing dot is rejected with exit 2 everywhere; only the message text differs.

**Trade-off:** In these runs the routes produced the same results, so the only cost that differs is how clear the error message for a malformed path is. Every route also has the same cost: a mistyped key silently returns empty output.

### Route 1

- Route: No matches print nothing and exit 0
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Sensible; matching rule unstated

rating: 4
reason: Identical matching everywhere; the error describes the issue at the location (empty segment).

### Route 2

- Route: Path prefix (segment awareness not stated)
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Possibly matches `ab` for `a`

rating: 3
reason: Error names the location but not the issue.

### Route 3

- Route: Plain string prefix; an unknown path prints nothing and exits 0
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 2 - `history a` also returns `ab.*` events

rating: 4
reason: Error describes the issue.

### Route 4

- Route: The path itself or a dotted-segment prefix
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 5 - Correct

rating: 3
reason: Error names the location but not the issue.

### Route 5

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Segment-unaware matching returns unrelated paths

rating: 4
reason: Both arms describe the issue.

## T33

**Question:** ASCII escaping in history JSON  
**Kind:** divergent

**What's at stake:** This is about how the change history prints non-English text: as readable characters (`café`, `zoë`, `代理`, 👋) or as `\u` escape codes. It also covers what happens to an invisible line-separator character (U+2028) inside a value, which some line-by-line readers treat as a line break.

**What each route does** (run against every arm's final code):

**Example 1:** `config history` (right after the existing config is imported) _(observed)_

Starting file:

~~~
name: café
greeting: "こんにちは"
mood: 🎭
rôle: naïve
note: "tab\there"
~~~

- Route 1: exit 0; non-ASCII text comes out as escape codes, e.g.:

  ~~~
  {"seq": 1, "op": "import", "path": "name", "old": null, "new": "caf\u00e9", ...}
  {"seq": 3, "op": "import", "path": "mood", "old": null, "new": "\ud83c\udfad", ...}
  {"seq": 4, "op": "import", "path": "r\u00f4le", "old": null, "new": "na\u00efve", ...}
  ~~~

- Route 2: exit 0; text is printed as is, e.g.:

  ~~~
  {"seq": 1, "op": "import", "path": "name", "old": null, "new": "café", ...}
  {"seq": 3, "op": "import", "path": "mood", "old": null, "new": "🎭", ...}
  {"seq": 4, "op": "import", "path": "rôle", "old": null, "new": "naïve", ...}
  ~~~

- Route 3: all four arms: exit 0; text is printed as is, the same as route 2 ("café", "🎭", "rôle", "naïve")

**Example 2:** `TROUPE_ACTOR=human:zoë config set greeting '"Grüß dich 👋 — ok"'`, then `config history greeting` _(observed)_

- Route 1: set: exit 0, no output, and the config file gets `greeting: "Grüß dich 👋 — ok"`. history: exit 0; the new entry reads:

  ~~~
  {"seq": 6, "op": "set", "path": "greeting", "old": "\u3053\u3093\u306b\u3061\u306f", "new": "Gr\u00fc\u00df dich \ud83d\udc4b \u2014 ok", "actor": {"kind": "human", "id": "zo\u00eb"}, "via": "cli", ...}
  ~~~

- Route 2: set: exit 0, and the config file is the same as in route 1. history: exit 0; the new entry reads:

  ~~~
  {"seq": 6, "op": "set", "path": "greeting", "old": "こんにちは", "new": "Grüß dich 👋 — ok", "actor": {"kind": "human", "id": "zoë"}, "via": "cli", ...}
  ~~~

- Route 3: all four arms: the same as route 2 (readable `"new": "Grüß dich 👋 — ok"` and `"id": "zoë"`)

**Example 3:** `TROUPE_ACTOR=agent:代理 config set rôle '"line sep ünïcode"' --reason 'pourquoi pas — 理由'` (the value has an invisible U+2028 line separator between "line" and "sep"), then `config history rôle` _(observed)_

- Route 1: set: exit 0; the config line now reads (unquoted, with the raw separator character):

  ~~~
  rôle: line
  sep ünïcode
  history: exit 0; the separator is escaped, so the entry stays on one visible line:
  {"seq": 7, "op": "set", "path": "r\u00f4le", "old": "na\u00efve", "new": "line\u2028sep \u00fcn\u00efcode", "actor": {"kind": "agent", "id": "\u4ee3\u7406"}, "via": "cli", ..., "reason": "pourquoi pas \u2014 \u7406\u7531", ...}
  ~~~

- Route 2: set: exit 0; the config line now reads (quoted, with the raw separator character):

  ~~~
  rôle: "line
  sep ünïcode"
  history: exit 0; the raw separator character is written inside the entry:
  {"seq": 7, "op": "set", "path": "rôle", "old": "naïve", "new": "line
  sep ünïcode", "actor": {"kind": "agent", "id": "代理"}, "via": "cli", ..., "reason": "pourquoi pas — 理由", ...}
  ~~~

- Route 3: The arms on this route wrote the config file differently. Two arms: exit 0; the config line now reads

  ~~~
  rôle: "line\Lsep ünïcode"
  One arm: exit 0; it reads (unquoted, raw separator)
  rôle: line
  sep ünïcode
  One arm: exit 0; it reads (quoted, raw separator)
  rôle: "line
  sep ünïcode"
  All four arms printed the same history: the raw separator inside the entry, as in route 2 (`"new": "line
  sep ünïcode"`, `"id": "代理"`).
  ~~~


**In practice:** On all three routes, history entries list their fields in the same order (seq, op, path, old, new, actor, via, at, reason, change), and a tab is printed as `\t`. The only difference in the history output is escaping. Route 1 prints only plain ASCII, which is hard for a person to read (`zo\u00eb`, `\u4ee3\u7406`) but always stays one entry per line. Routes 2 and 3 print readable text. They also pass a U+2028 character through raw, and some line-based readers split on it. On route 3, how that value is written to the config file depended on the arm.

**Trade-off:** Route 1 is safe but hard to read: names, values and reasons in non-English text show up as escape codes. Route 2 is readable but passes raw U+2028 into the history output. Route 3 gives the same history output as route 2, but its arms disagreed on how to write that value to the config file.

### Route 1

- Route: ASCII escaping
- Reasoning given: Deterministic
- Outcome: Kept
- proposed: n/a - Valid either way

rating: 1.5
reason: Two questions, averaged. History: escaped, hard to read (1). File: raw U+2028 unquoted (2).

### Route 2

- Route: ensure_ascii=False with keys in a fixed order
- Reasoning given: None recorded
- Outcome: Kept
- proposed: n/a - Valid either way

rating: 3
reason: Two questions, averaged. History: readable (4); the only improvement would be escaping the invisible character. File: raw U+2028 in quotes (2).

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Both forms are valid JSON

rating: 3.5
reason: RESLICE placeholder: history readable (4) in all arms. File: two arms escape it as \L in quotes (4), two write it raw (2). See decisions/reslice.md.

## T34

**Question:** Does history load the files once a store exists  
**Kind:** divergent

**What's at stake:** This decides whether you can still see who changed what once the config files no longer pass their own schema. A schema change that breaks the config is the moment you most need the change history, and on some routes it becomes unreadable.

**What each route does** (run against every arm's final code):

**Example 1:** `config set schema_text '{"type": "object", "required": ["absent"]}'` then `config history` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: opus
schema_text: file:troupe.schema.json

.troupe/troupe.schema.json:
{"type": "object"}
~~~

- Route 1: The set exits 0 and the schema file now reads:

  ~~~
  {"type": "object", "required": ["absent"]}
  Then `config history` exits 0 and lists all 3 events: the two imports (model, schema_text) and seq 3, the `set` of schema_text by human:owner.
  ~~~

- Route 2: Both arms behave the same. The set exits 0 and rewrites the schema file. Then `config history` exits 4 with nothing on stdout. Its stderr says the configuration does not match the schema: 'absent' is a required property.
- Route 3: The set exits 0 in all three arms. After it, the arms differ on `config history`. Two arms: exit 4, nothing listed, with the error "'absent' is a required property". One arm: exit 0 and all 3 events listed, the same as route 1.

**Example 2:** `config history model` (same broken state) _(observed)_

- Route 1: Exit 0. It prints only seq 1: the import of model, old null, new "opus".
- Route 2: Both arms: exit 4, same schema error, nothing listed.
- Route 3: Two arms: exit 4, same schema error. One arm: exit 0, seq 1 for model only.

**Example 3:** `config get model` (same broken state) _(observed)_

- Route 1: Exit 4: "configuration does not match … 'absent' is a required property".
- Route 2: Both arms: exit 4, same schema error.
- Route 3: All three arms: exit 4, same schema error.

**In practice:** All routes refuse to read config values once the files break the schema. The difference is history. On route 1, history keeps working from what was already recorded, so you can find the change that broke things. On route 2, history fails with exit 4 like every other command until the files are fixed. Route 3 is split: two arms fail, one keeps working.

**Trade-off:** Route 1 keeps history available but doesn't check the files' current state. Route 2 keeps a single load path and consistent errors, but you lose history exactly when the config is broken. Route 3's arms don't agree.

### Route 1

- Route: No; once state exists it reads recorded events without loading
- Reasoning given: It reports only what was recorded
- Outcome: Kept
- proposed: 5 - History stays available

rating: 5
reason: History stays available once the config is broken (5). Though validation should stop the invalid state being written at all.

### Route 2

- Route: Yes; broken files make history exit 4; at step 7 schema and remote fetches apply to it too
- Reasoning given: It loads in order to import; one load path
- Outcome: Kept
- proposed: 4 - Consistent; history unavailable while files are broken

rating: 4
reason: History unavailable while the files are broken (4).

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Minor

rating: 4.5
reason: RESLICE placeholder: one arm keeps history working (5), two fail (4). See decisions/reslice.md.

## T35

**Question:** When the first import happens, and whether it survives a later failure  
**Kind:** divergent

**What's at stake:** A user's first few commands against a theatre may fail (missing key, refused write, bad TROUPE_ACTOR). What matters is whether the history still begins with one clean import of the original file, or whether a failure loses or duplicates it.

**What each route does** (run against every arm's final code):

**Example 1:** `config get agents.coder.missing` (first command run against the theatre) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: opus  # default model
retries: 3
agents:
  coder: file:agents/coder.yaml

.troupe/agents/coder.yaml:
temperature: 0.2
tools: [shell, edit]
~~~

- Route 1: both arms: exit 5, 'path not found' on stderr; no file changed
- Route 2: all four arms: exit 5, 'not found' on stderr (wording differs; one arm prefixes the include file's path); no file changed

**Example 2:** `config set agents.coder "{a: 1}"` _(observed)_

- Route 1: both arms: exit 3, refused because the value comes from the include agents/coder.yaml; no file changed
- Route 2: all four arms: exit 3, same refusal (wording differs; some say to change the included file instead); no file changed

**Example 3:** `TROUPE_ACTOR=robot:x config get model` _(observed)_

- Route 1: both arms: exit 2, 'TROUPE_ACTOR must be human:<id> or agent:<id>'; nothing printed on stdout
- Route 2: all four arms: exit 2, same complaint in different words; nothing printed on stdout

**Example 4:** `config set model sonnet --reason "first successful command"` _(observed)_

- Route 1: both arms: exit 0; .troupe/troupe.yml now reads:

  ~~~
  model: sonnet # default model
  retries: 3
  agents:
    coder: file:agents/coder.yaml
  ~~~

- Route 2: all four arms: exit 0; .troupe/troupe.yml now reads:

  ~~~
  model: sonnet # default model
  retries: 3
  agents:
    coder: file:agents/coder.yaml
  ~~~


**Example 5:** `config history` _(observed)_

- Route 1: both arms: exit 0; 6 entries: seq 1-5 are one import (model=opus, retries=3, agents.coder.temperature=0.2, agents.coder.tools.0=shell, agents.coder.tools.1=edit; actor unknown, via import), then seq 6 is the set model opus→sonnet by human:owner with the reason
- Route 2: all four arms: exit 0; the same 6 entries: one import (seq 1-5), then the set (seq 6)

**In practice:** In this run every arm on both routes behaved the same. Exactly one import was recorded, before the successful set, and it was never repeated or lost. The earlier failures (exits 5, 3, 2) did not wipe it out or cause a second import. The history doesn't show which earlier command triggered the import, so this run can't tell 'first command of any kind' apart from 'first command whose configuration loads'.

**Trade-off:** Route 1 leaves open what happens to the import after a failure. Route 2 pins it down (the import stands after exits 2, 3 or 5; a load failure records nothing), but this run showed no visible difference between them.

### Route 1

- Route: The first command against a theatre imports it (persistence after a later failure not stated)
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Same rule but the failure case is left unpinned

rating: n/a
reason: Nothing to choose between: one clean import in every arm.

### Route 2

- Route: The first command whose configuration loads imports it; the import stands even if that command then exits 2, 3 or 5; a load failure records nothing
- Reasoning given: The theatre was read successfully; conservative reading of 'the first command imports'
- Outcome: Kept
- proposed: 5 - Clear rule with no state left behind on a load failure

rating: n/a
reason: Identical behaviour.

## T36

**Question:** Include kind, relative paths and cycles  
**Kind:** divergent

**What's at stake:** Config values can pull in other files (`file:...`). If a relative path resolves against the wrong directory, if an upper-case `.YML` file is read the wrong way, or if a self-including file is accepted, the user gets the wrong value or a config that will no longer load. In these runs both routes behaved the same on every read. They differed only in the exit code when a cycle was refused, and even there route 1's arms did not all agree.

**What each route does** (run against every arm's final code):

**Example 1:** `config get a.inner` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
a: file:sub/a.yaml
up: file:sub/upper.YML  # upper-case suffix

.troupe/sub/a.yaml:
inner: file:b.txt

(both .troupe/b.txt and .troupe/sub/b.txt exist)
~~~

- Route 1: all three arms: exit 0, prints `text from .troupe/sub/b.txt`, so the path is resolved next to sub/a.yaml, the file that includes it
- Route 2: all three arms: exit 0, prints `text from .troupe/sub/b.txt`

**Example 2:** `config get up` _(observed)_

Starting file:

~~~
up: file:sub/upper.YML  # upper-case suffix

.troupe/sub/upper.YML:
k: v
~~~

- Route 1: all three arms: exit 0, prints `k: v` (`config show` lists it as a block of text `up: |`, so the upper-case .YML file is read as text, not YAML)
- Route 2: all three arms: exit 0, prints `k: v`, also shown as text `up: |`

**Example 3:** `config set --include loop file:loop.yaml` _(observed)_

Starting file:

~~~
.troupe/loop.yaml:
again: file:sub/../loop.yaml
~~~

- Route 1: two arms: exit 3, refused as an include cycle (e.g. `written value cannot be read back: ... include cycle: /theatre/.troupe/loop.yaml -> /theatre/.troupe/sub/../loop.yaml`); one arm: exit 4, `troupe: .troupe/loop.yaml: include cycle (from .troupe/loop.yaml)`. In all three, no file changed and `config get a.inner` still works afterwards
- Route 2: all three arms: exit 3, refused as an include cycle (e.g. `troupe: loop: include cycle at loop.again: /theatre/.troupe/loop.yaml -> /theatre/.troupe/loop.yaml; no file changed`). No file changed and `config get a.inner` still works afterwards

**In practice:** On every read, both routes gave the same results. On both routes, every arm caught the cycle even though it was hidden behind `sub/../`, and every arm refused it without touching the config. Route 1 says cycles exit 4, but only one of its arms did that. Its other two arms, and every arm of route 2, exited 3, which is the code for a refused write.

**Trade-off:** Route 1 commits to fixed rules (case-sensitive suffix, paths relative to the including file, exit 4 on cycles) that one arm did not follow for exit codes. Route 2 never stated a rule but behaved the same here, with exit 3 on every arm.

### Route 1

- Route: YAML include by .yml/.yaml suffix (case-sensitive), else text; paths relative to the including file; cycles and missing or non-UTF-8 targets exit 4
- Reasoning given: Follows the contract; cycles detected through real paths
- Outcome: Kept
- proposed: 5 - Contract rules

rating: 4.5
reason: RESLICE placeholder: two arms refuse the cycle write with exit 3 (5); one uses exit 4, a load error, which is incorrect on a write (4, one point off, consistent with T26). See decisions/reslice.md.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract-defined

rating: 5
reason: Refuses the cycle write with exit 3; paths and suffixes correct (5).

## T37

**Question:** What set does when PATH's whole value comes from an include  
**Kind:** divergent

**What's at stake:** Whether `config set` on a key whose whole value comes from an include (a text file such as `prompt: file:prompt.txt`, or a YAML file such as `coder: file:agents/coder.yaml`) writes into the included file or refuses. It also decides whether re-sending the value the key already has is a quiet no-op or an exit-3 error, which matters to scripts that re-apply the same config.

**What each route does** (run against every arm's final code):

**Example 1:** `config set prompt '"Be terse.\n"'` (the same text prompt.txt already holds) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
prompt: file:prompt.txt  # system prompt
agents:
  coder: file:agents/coder.yaml
  reviewer:
    $ref: file:agents/reviewer.yaml
    temperature: 0.3

.troupe/prompt.txt:
Be terse.
~~~

- Route 1: exit 0, no output, no file changed
- Route 2: exit 0, no output, no file changed
- Route 3: exit 0, no output, no file changed
- Route 4: exit 0, no output, no file changed

**Example 2:** `config set prompt '"Be verbose.\n"'` _(observed)_

Starting file:

~~~
.troupe/prompt.txt:
Be terse.
~~~

- Route 1: exit 0, no output; troupe.yml is unchanged and .troupe/prompt.txt now reads:

  ~~~
  Be verbose.
  ~~~

- Route 2: exit 0, no output; troupe.yml is unchanged and .troupe/prompt.txt now reads:

  ~~~
  Be verbose.
  ~~~

- Route 3: exit 0, no output; troupe.yml is unchanged and .troupe/prompt.txt now reads:

  ~~~
  Be verbose.
  ~~~

- Route 4: exit 0, no output; troupe.yml is unchanged and .troupe/prompt.txt now reads:

  ~~~
  Be verbose.
  ~~~


**Example 3:** `config set agents.coder '{model: opus}'` (the value the included coder.yaml already gives) _(observed)_

Starting file:

~~~
.troupe/agents/coder.yaml:
model: opus
~~~

- Route 1: The two arms differed. One arm: exit 0, silent, nothing changed. The other arm: exit 3, `troupe: write refused: agents.coder: value comes from include /theatre/.troupe/agents/coder.yaml; refusing to replace it`
- Route 2: The two arms differed. One arm: exit 3, `/theatre/.troupe/agents/coder.yaml: agents.coder: the whole value comes from the include file:agents/coder.yaml; change the included file instead`. The other arm: exit 0, silent, nothing changed
- Route 3: exit 3, `troupe: error: agents.coder: its whole value comes from include 'file:agents/coder.yaml' in /theatre/.troupe/troupe.yml; change the included file instead`
- Route 4: exit 3, `troupe: agents.coder: value comes from include /theatre/.troupe/agents/coder.yaml; refusing to replace it (change a path inside it instead); no file changed`

**Example 4:** `config set agents.reviewer '{model: haiku, temperature: 0.3}'` (the same value it already resolves to, through `$ref` plus an override) _(observed)_

Starting file:

~~~
.troupe/agents/reviewer.yaml:
model: haiku
~~~

- Route 1: The two arms differed. One arm: exit 0, silent, nothing changed. The other arm: exit 3, `troupe: write refused: agents.reviewer: value comes from include /theatre/.troupe/agents/reviewer.yaml; refusing to replace it`
- Route 2: The two arms differed. One arm: exit 3, `/theatre/.troupe/agents/reviewer.yaml: agents.reviewer: the whole value comes from the include file:agents/reviewer.yaml; change the included file instead`. The other arm: exit 0, silent, nothing changed
- Route 3: exit 3, `troupe: error: agents.reviewer: its whole value comes from include 'file:agents/reviewer.yaml' in /theatre/.troupe/troupe.yml; change the included file instead`
- Route 4: exit 3, `troupe: agents.reviewer: value comes from include /theatre/.troupe/agents/reviewer.yaml with overrides; refusing to replace it (change a path inside it instead); no file changed`

**In practice:** On every route, setting a text-file include actually wrote the new text into prompt.txt. Even route 1's description says it always refuses, but neither of its arms did. The routes only differed on YAML-file includes. There, routes 3 and 4 refused even when the value was unchanged. On routes 1 and 2, one arm refused and the other quietly accepted the unchanged value, so neither route behaved the same across its arms. On every route, `config history` afterwards was the same: four import entries plus a single `set` of prompt from "Be terse.\n" to "Be verbose.\n" by human:owner. No-ops and refusals were not logged.

**Trade-off:** Refusing even unchanged values (routes 3 and 4, and one arm each of routes 1 and 2) means a script that re-applies the same config gets exit 3. Accepting them silently (the other arm of routes 1 and 2) avoids that, but the two arms of one route then act differently, and the text include is overwritten in place either way.

### Route 1

- Route: Exit 3 always, even when the new value is identical (including changes through an ancestor)
- Reasoning given: Follows rule 4 conservatively
- Outcome: Kept; extended at step 5 to mapping-form includes
- proposed: 4 - Safe; refusing a no-op is a little unfriendly

rating: 4
reason: Proposed accepted: safe; refusing a no-op is a little unfriendly.

### Route 2

- Route: Exit 3 only when the value would change; an identical value is a no-op
- Reasoning given: A no-op wins over a refusal
- Outcome: Kept
- proposed: 5 - Safe and idempotent

rating: 5
reason: Proposed accepted: safe and idempotent.

### Route 3

- Route: Rule 4 applies only to the root of a YAML include; a text include is edited in place
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Reasonable scoping; the no-op case is left open

rating: 4
reason: Proposed accepted: reasonable scoping; the no-op case left open.

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Contract rule 4 needs a definite answer

rating: 3
reason: Proposed accepted: contract rule 4 needs a definite answer.

## T38

**Question:** Where new entries go relative to trailing comments and blank lines  
**Kind:** divergent

**What's at stake:** When `config set` adds a new key or list item, where it lands decides whether hand-written comments and blank lines still sit next to the entries they describe. Both routes gave the same result on every command in this run.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder.temperature 0.3` _(observed)_

Starting file:

~~~
agents:
  coder:
    model: opus
    # coder notes

  reviewer:
    model: sonnet
      # deeper reviewer note
    # end of reviewer
  # agents-level note
# top-level comment

tools:
  - git
  # more tools here

  - shell
    # deeper comment

notes: x
# end of file comment
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
    coder:
      model: opus
      # coder notes
      temperature: 0.3
  
    reviewer:
  ~~~

- Route 2: exit 0, no output; the file now reads:

  ~~~
    coder:
      model: opus
      # coder notes
      temperature: 0.3
  
    reviewer:
  ~~~


**Example 2:** then `config set agents.reviewer.temperature 0.5` _(observed)_

- Route 1: exit 0; the new line goes below both reviewer comments and above the less-indented agents-level note:

  ~~~
      model: sonnet
        # deeper reviewer note
      # end of reviewer
      temperature: 0.5
    # agents-level note
  ~~~

- Route 2: exit 0; the new line goes below both reviewer comments and above the less-indented agents-level note:

  ~~~
      model: sonnet
        # deeper reviewer note
      # end of reviewer
      temperature: 0.5
    # agents-level note
  ~~~


**Example 3:** then `config set agents.tester '{model: haiku}'` _(observed)_

- Route 1: exit 0; the new agent goes below the agents-level note and above the top-level comment:

  ~~~
      temperature: 0.5
    # agents-level note
    tester:
      model: haiku
  # top-level comment
  ~~~

- Route 2: exit 0; the new agent goes below the agents-level note and above the top-level comment:

  ~~~
      temperature: 0.5
    # agents-level note
    tester:
      model: haiku
  # top-level comment
  ~~~


**Example 4:** then `config set tools.2 make` _(observed)_

- Route 1: exit 0; the new item goes below the deeper comment, and the blank line stays below it:

  ~~~
    - shell
      # deeper comment
    - make
  
  notes: x
  ~~~

- Route 2: exit 0; the new item goes below the deeper comment, and the blank line stays below it:

  ~~~
    - shell
      # deeper comment
    - make
  
  notes: x
  ~~~


**Example 5:** then `config set zeta 1` _(observed)_

- Route 1: exit 0; the new top-level key goes below the end-of-file comment, above the trailing blank line:

  ~~~
  notes: x
  # end of file comment
  zeta: 1
  ~~~

- Route 2: exit 0; the new top-level key goes below the end-of-file comment, above the trailing blank line:

  ~~~
  notes: x
  # end of file comment
  zeta: 1
  ~~~


**In practice:** A new entry goes after any trailing comments that are indented at least as far as the entries it joins. It stops before the first comment indented less than that. Blank lines that separate sections stay below the new entry. Every arm on both routes did exactly this, so this test shows no difference between the routes.

**Trade-off:** Route 1 follows a stated rule for where entries go. Route 2 never considered the question but produced the same files here, so any difference would only show up in layouts this test didn't cover.

### Route 1

- Route: After trailing comments indented at least to the entry column; blank lines stay below the new entry
- Reasoning given: Keeps the next section's visual grouping; only a less-indented comment ends a collection
- Outcome: Kept
- proposed: 5 - Follows the contract

rating: n/a
reason: Nothing to choose between: identical files.

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract rule

rating: n/a
reason: Identical behaviour.

## T39

**Question:** Leading spaces in literal blocks  
**Kind:** divergent

**What's at stake:** When a multi-line value starts with spaces, such as an indented code snippet, the tool has to write it into troupe.yml so that it reads back unchanged. It also decides whether the user sees a readable block or an escaped one-line string in the file and in `config show`.

**What each route does** (run against every arm's final code):

**Example 1:** `config set a.note "line one\nline two\n"` (no leading spaces) _(observed)_

Starting file:

~~~
a:
  note: hello
  code: plain  # keep
items:
  - name: a
    cmd: run
~~~

- Route 1: exit 0; the file now reads:

  ~~~
    note: |
      line one
      line two
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
    note: |
      line one
      line two
  ~~~

- Route 3: all arms: exit 0; the file now reads:

  ~~~
    note: |
      line one
      line two
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
    note: |
      line one
      line two
  ~~~


**Example 2:** `config set a.code " indented\nnext\n"` (the first line starts with two spaces) _(observed)_

Starting file:

~~~
  code: plain  # keep
~~~

- Route 1: exit 0; the file now holds an escaped one-line string:

  ~~~
    code: "  indented\nnext\n" # keep
  ~~~

- Route 2: exit 0; the file now holds an escaped one-line string:

  ~~~
    code: "  indented\nnext\n" # keep
  ~~~

- Route 3: two arms: exit 0; the file now holds a block with an indent marker:

  ~~~
    code: |2     # keep
        indented
      next
  one arm: exit 0; the file now holds an escaped one-line string:
    code: "  indented\nnext\n" # keep
  ~~~

- Route 4: exit 0; the file now holds a block with an indent marker:

  ~~~
    code: |2     # keep
        indented
      next
  ~~~


**Example 3:** `config set items.0.name " x\ny"` (a list item, with leading spaces and no final newline) _(observed)_

Starting file:

~~~
items:
  - name: a
    cmd: run
~~~

- Route 1: exit 0; the file now reads:

  ~~~
    - name: "  x\ny"
      cmd: run
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
    - name: "  x\ny"
      cmd: run
  ~~~

- Route 3: two arms: exit 0; the file now reads:

  ~~~
    - name: |2-
          x
        y
      cmd: run
  one arm: exit 0; the file now reads:
    - name: "  x\ny"
      cmd: run
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
    - name: |2-
          x
        y
      cmd: run
  ~~~


**Example 4:** `config get a.code` _(observed)_

- Route 1: exit 0; prints " indented", then "next", with the leading spaces kept
- Route 2: exit 0; prints " indented", then "next", with the leading spaces kept
- Route 3: all arms: exit 0; prints " indented", then "next", with the leading spaces kept
- Route 4: exit 0; prints " indented", then "next", with the leading spaces kept

**Example 5:** `config show` (after the commands above) _(observed)_

- Route 1: exit 0; shows blocks with indent markers, even though the file holds escaped strings:

  ~~~
    code: |2
        indented
      next
  items:
    - name: |2-
          x
        y
  ~~~

- Route 2: exit 0; shows escaped strings, the same as the file:

  ~~~
    code: "  indented\nnext\n"
  items:
    - name: "  x\ny"
  ~~~

- Route 3: all arms: exit 0; shows blocks with indent markers:

  ~~~
    code: |2
        indented
      next
  items:
    - name: |2-
          x
        y
  ~~~

- Route 4: exit 0; shows blocks with indent markers:

  ~~~
    code: |2
        indented
      next
  items:
    - name: |2-
          x
        y
  ~~~


**In practice:** Every route reads the values back exactly, and every route writes plain text without leading spaces as an ordinary block with no marker, including route 1 ("Always `2`"). The routes differ in two places: what lands in the file for text that starts with spaces, and what `config show` displays. Route 2 stays with escaped strings in both places. Route 4 and two arms of route 3 write readable blocks with a `|2` marker, both in the file and in `show`. Route 1 and the third arm of route 3 write escaped strings to the file but display blocks in `show`, so the file doesn't match what `show` displays. The `# keep` comment stayed in the file on every route. `config show` printed no comments on any route.

**Trade-off:** Route 1 writes escaped strings to the file but shows blocks in `show`, so the two don't match. Route 2 is consistent but leaves indented text as hard-to-read escaped strings. Routes 3 and 4 write readable `|2` blocks in the file, but one arm of route 3 behaved like route 1.

### Route 1

- Route: Always `2`
- Reasoning given: Literal 4.4 broke compact items
- Outcome: Kept
- proposed: 4 - Risk at root

rating: 2
reason: Quoted line in the file but show prints a block: file and screen disagree, which is confusing and error-prone

### Route 2

- Route: Double-quote instead
- Reasoning given: Literal block cannot hold it
- Outcome: Kept
- proposed: 4 - Loses readability

rating: 3
reason: Quoted line with \n is less readable than a block, though show at least matches the file

### Route 3

- Route: Indicator only when needed
- Reasoning given: YAML infers indentation
- Outcome: Kept
- proposed: 5 - Correct

rating: 3.5
reason: Blocks are more readable and match shell/cat usage; one arm quoted instead and its show did not match its file

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Edge

rating: 4
reason: Readable block with the comment kept on its line, and show matches the file

## T40

**Question:** via for old events  
**Kind:** divergent

**What's at stake:** Events recorded before the software started noting where each event came from ("via") have no such record. The choice decides whether those old events show nothing, show a source that may be wrong, or are clearly marked as unknown. Anyone filtering, counting or auditing events by source sees the result.

**In practice:** Route 1 leaves old events exactly as stored. They have no "via" at all, so anything that reads events has to handle the field being missing. Route 2 marks every old event as coming from the command line. Route 3 marks every old event as coming from a file. Either way, old events look the same as new ones, but some of them will be labelled wrongly: the record does not say which source each old event really had, and both backfills were picked without knowing that. A filter such as "show only file events" would then quietly include or leave out old events by mistake. Route 4 gives every old event a "via" field whose value is explicitly empty, meaning unknown. The field is always present and nothing is invented, but tools and reports have to handle an "unknown" value next to the real sources.

**Trade-off:** Route 1 costs nothing now but leaves a missing field that every reader must handle. Routes 2 and 3 give a uniform history at the price of possibly wrong source labels on old events. Route 4 is honest and consistent but adds an "unknown" value that everything downstream must accept.

### Route 1

- Route: No migration
- Reasoning given: Invent nothing
- Outcome: Kept
- proposed: 2 - Undefined

rating: 2
reason: Leaves a missing field every reader must handle.

### Route 2

- Route: cli
- Reasoning given: Owner ok
- Outcome: Kept
- proposed: 4 - In vocabulary

rating: 3
reason: Uniform, but invents a source that will sometimes be wrong.

### Route 3

- Route: file
- Reasoning given: Pairs unknown
- Outcome: Kept
- proposed: 4 - In vocabulary

rating: 3
reason: Uniform, but invents a source that will sometimes be wrong.

### Route 4

- Route: null
- Reasoning given: Unknown
- Outcome: Kept
- proposed: 2 - Outside vocabulary

rating: 4
reason: Closest: honest about what isn't known. Would be better with a distinct explicit value (e.g. 'unknown') rather than null.

## T41

**Question:** Which line ending new or rewritten lines use  
**Kind:** divergent

**What's at stake:** Someone with a config file that mixes Windows (CRLF) and Unix (LF) line endings sees their file get new lines with one ending or the other after `config set`. That can show up as noisy diffs, or as a mixed-ending file their editor or tools complain about. Notation below: a line ending in ␍ ends in CRLF; an unmarked line ends in LF.

**What each route does** (run against every arm's final code):

**Example 1:** `config set m.y 2` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
a: 1
m:␍
  x: 1␍
n:␍
  x: 1
inc: file:inc.yaml␍
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  m:␍
    x: 1␍
    y: 2␍
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  m:␍
    x: 1␍
    y: 2␍
  ~~~

- Route 3: exit 0 (all three arms); the file now reads:

  ~~~
  m:␍
    x: 1␍
    y: 2
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
  m:␍
    x: 1␍
    y: 2
  ~~~


**Example 2:** then `config set n.y 2` (the line above the new one ends in LF) _(observed)_

- Route 1: exit 0; the new line gets CRLF anyway:

  ~~~
  n:␍
    x: 1
    y: 2␍
  ~~~

- Route 2: exit 0; the new line copies the LF above it:

  ~~~
  n:␍
    x: 1
    y: 2
  ~~~

- Route 3: exit 0 (all three arms); the file now reads:

  ~~~
  n:␍
    x: 1
    y: 2
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
  n:␍
    x: 1
    y: 2
  ~~~


**Example 3:** `config set --in-include inc.z 3` _(observed)_

Starting file:

~~~
.troupe/inc.yaml:
k: 1␍
j: 2
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  k: 1␍
  j: 2
  z: 3␍
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  k: 1␍
  j: 2
  z: 3
  ~~~

- Route 3: exit 0 (all three arms); the file now reads:

  ~~~
  k: 1␍
  j: 2
  z: 3␍
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
  k: 1␍
  j: 2
  z: 3␍
  ~~~


**Example 4:** `config set a '"l1\nl2\n"'` (turns `a: 1`, which ends in LF, into a multi-line block) _(observed)_

- Route 1: exit 0; the file now reads (endings mixed inside the block):

  ~~~
  a: |␍
    l1␍
    l2
  m:␍
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  a: |
    l1
    l2
  m:␍
  ~~~

- Route 3: exit 0 (all three arms); the file now reads:

  ~~~
  a: |
    l1
    l2
  m:␍
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
  a: |
    l1
    l2
  m:␍
  ~~~


**Example 5:** `config show --sources` _(observed)_

- Route 1: exit 0; lists a, m.x, m.y, n.x, n.y, inc.k, inc.j and inc.z, each tagged `# from <file>`
- Route 2: exit 0; same listing as route 1
- Route 3: two arms: same listing as route 1; one arm: same values, but prints the keys quoted as `'y': 2` and `'n':`
- Route 4: exit 0; same listing as route 1

**In practice:** All routes behave the same on files with only one kind of line ending. They differ only on mixed files, and none of them fixes the lines that are already there, so a mixed file stays mixed. Route 1 writes CRLF as soon as the file has any CRLF. Route 2 copies the ending of the line just above the new one, so the result depends on where the edit lands. Routes 3 and 4 use the file's first line ending, so troupe.yml (its first line ends in LF) got LF and inc.yaml (its first line ends in CRLF) got CRLF. Routes 3 and 4 produced the same files.

**Trade-off:** Route 1 leans toward CRLF and can mix endings inside a single new block. Route 2 blends into each spot but follows no file-wide rule. Routes 3 and 4 are predictable but can add lines whose ending doesn't match their neighbors.

### Route 1

- Route: CRLF if any CRLF appears in the file, else LF
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Works; a single stray CRLF switches the whole file's insertions

rating: 4
reason: CRLF if any CRLF: works, but can mix endings inside a new block.

### Route 2

- Route: Copy the preceding line's ending
- Reasoning given: Minimal change that follows the user's own layout
- Outcome: Kept
- proposed: 5 - Also right for mixed files

rating: 5
reason: Copying the line above is probably the most predictable.

### Route 3

- Route: Taken from the file's first line break; LF for empty or LF-only files
- Reasoning given: Deterministic; the same rule decides whether a text include 'used CRLF'
- Outcome: Kept
- proposed: 4 - Good; mixed-ending files get the first ending

rating: 4
reason: First line's ending: predictable rule, but a new line can differ from its neighbour.

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Mixed endings corrupt CRLF files

rating: 4
reason: Same behaviour as route 3.

## T42

**Question:** Locating the config relative to taking the lock  
**Kind:** divergent

**What's at stake:** When there is no config file, a write command should fail cleanly. It should not leave a stray lock file or an empty event log in `.troupe/`. In the rare case where the config is renamed while a write waits for the lock, the write could go to the wrong file.

**What each route does** (run against every arm's final code):

**Example 1:** `config set model opus` (no `.troupe/troupe.yml` or `.troupe/troupe.yaml` exists) _(observed)_

- Route 1: All four arms: exit 4 and nothing created (no lock file, no events.sqlite). Only the message wording differs: one arm says `/theatre/.troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)`, one says `troupe: .troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)`, one says `troupe: .troupe/troupe.yml: no configuration file found` and one says `troupe: error: no configuration file: expected .troupe/troupe.yml or .troupe/troupe.yaml`
- Route 2: exit 4, `troupe: no configuration file: /theatre/.troupe/troupe.yml (or troupe.yaml)`; nothing created (no lock file, no events.sqlite)
- Route 3: exit 4, `troupe: ./.troupe/troupe.yml: no configuration file`; nothing created

**Example 2:** `TROUPE_ACTOR=agent:bot config set agents.coder.model sonnet --reason try` (no config) _(observed)_

- Route 1: All four arms: exit 4 with the same message each arm gave above; nothing created
- Route 2: exit 4 with the same message as above; nothing created
- Route 3: exit 4 with the same message as above; nothing created

**Example 3:** `config get model`, `config show` and `config history` (no config) _(observed)_

- Route 1: All four arms: exit 4 for each command with the same message as above; nothing created
- Route 2: exit 4 for each command with the same message as above; nothing created
- Route 3: exit 4 for each command with the same message as above; nothing created

**In practice:** In what was tested, a missing config behaves the same on every route: exit 4, nothing written and no lock file left behind. Only the error wording differs. The case route 2 was built for, where the config is renamed between finding it and taking the lock, was not exercised, so these results show no difference there.

**Trade-off:** Route 1 is simpler but trusts a config location found before taking the lock. Route 2 searches again under the lock to catch a rename, at the cost of a second lookup. Route 3 was never designed for this and matched the others only on the missing-config case.

### Route 1

- Route: Locate the config first, then lock
- Reasoning given: A missing config exits 4 with nothing created
- Outcome: Kept
- proposed: 5 - No state

rating: n/a
reason: Nothing to choose between in what was tested.

### Route 2

- Route: Lock, then re-locate under the lock
- Reasoning given: Handles a root file renamed in between
- Outcome: Kept
- proposed: 5 - Handles renames

rating: n/a
reason: Identical in what was tested; the rename race wasn't exercised.

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: n/a
reason: Identical behaviour.

## T43

**Question:** Errors opening or locking  
**Kind:** divergent

**What's at stake:** When `.troupe` is a plain file instead of the expected directory, the user needs an error that explains what went wrong, and no command should damage that file. Here, every command on both routes fails with exit 4 and says the configuration file is missing. No message says that `.troupe` itself is a regular file.

**What each route does** (run against every arm's final code):

**Example 1:** `config get model` (`config history`, `config show` and `config history model` give exactly the same result) _(observed)_

Starting file:

~~~
.troupe (a plain file):
this is a plain file, not a directory
~~~

- Route 1: exit 4, no stdout. The three arms word the error differently. One arm: `/theatre/.troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)`. One arm: `troupe: .troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)`. One arm: `troupe: error: no configuration file: expected .troupe/troupe.yml or .troupe/troupe.yaml`
- Route 2: exit 4, no stdout. The three arms word the error differently. One arm: `troupe: no configuration file: /theatre/.troupe/troupe.yml (or troupe.yaml)`. One arm: `troupe: .troupe/troupe.yml: no configuration file found`. One arm: `troupe: ./.troupe/troupe.yml: no configuration file`

**Example 2:** `TROUPE_ACTOR=agent:coder config set model sonnet` _(observed)_

Starting file:

~~~
.troupe (a plain file):
this is a plain file, not a directory
~~~

- Route 1: exit 4 on all three arms, with the same message each arm gives for reads. Nothing is stored, and `.troupe` is unchanged.
- Route 2: exit 4 on all three arms, with the same message each arm gives for reads. Nothing is stored, and `.troupe` is unchanged.

**In practice:** In this test, both routes behave the same for the user: exit 4, a 'no configuration file' message that points at `.troupe/troupe.yml`, and the file left alone. Route 1 plans to name `.troupe` or the lock file in its errors, but none of its arms did that here. Every arm on both routes fell back to the missing-config error. Some arms print the full path, some a relative path; some start with `troupe:` and one has no prefix at all.

**Trade-off:** Route 1 sets out to give opening and locking failures their own exit-4 errors naming `.troupe` or the lock file, which this test never triggered. Route 2 makes no such plan, and its results here were the same.

### Route 1

- Route: Exit 4 naming .troupe or the lock file; keep step-1 missing-config errors
- Reasoning given: Consistent with store errors
- Outcome: Kept
- proposed: 5 - Clear

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Network filesystems may not support flock

rating: n/a
reason:

## T44

**Question:** How commands and watch are serialised  
**Kind:** divergent

**What's at stake:** When two commands, or a command and the watcher, touch the project's `.troupe` store at the same time, one has to wait so they don't corrupt each other's changes. What differs is whether the store gets an extra file, and how locking behaves when the folder can't be written to.

**What each route does** (run against every arm's final code):

**Example 1:** Run a command while the watcher is running in the same project _(inferred, not run)_

- Route 1: The command waits until the watcher finishes its current step, then runs. Nothing new appears in `.troupe/`.
- Route 2: The command waits until the watcher finishes its current step, then runs. A lock file appears in `.troupe/` and stays there.

**Example 2:** A command is killed partway through (Ctrl-C, crash, `kill -9`) _(inferred, not run)_

- Route 1: The next command runs right away. The system drops the lock when the process dies, and there's nothing left to clean up.
- Route 2: The next command runs right away. The system drops the lock when the process dies. The lock file stays behind, but it's harmless and doesn't need deleting.

**Example 3:** Run a command in a project whose `.troupe/` folder you can read but not write _(inferred, not run)_

- Route 1: The lock is taken on the folder itself, so no new file has to be created and the command doesn't need write access just to lock.
- Route 2: If the lock file can't be created, it falls back to opening it read-only, so locking can still work if the file already exists.

**In practice:** Both routes make commands and the watcher take turns, and neither leaves a stale lock that blocks people after a crash. Users see the difference mainly as one extra file in `.troupe/` under route 2. Maintainers see it elsewhere. Route 1 relies on locking a folder, which is less common, and some systems or network drives may not support it. Route 2 is the usual approach and is easy to recognise, but it adds a file that tools copying or cleaning the store have to cope with. Under both routes, a second command waits with no time limit rather than failing.

**Trade-off:** Route 1 adds no file to the store but depends on locking a folder, which is less usual. Route 2 uses the familiar lock-file approach but leaves a permanent extra file in `.troupe/` and needs a read-only fallback.

### Route 1

- Route: Exclusive blocking fcntl.flock on the .troupe directory itself; no lock file
- Reasoning given: Creates no file; the kernel releases it on death; SQLite cannot cover the file writes
- Outcome: Kept
- proposed: 5 - Correct, no extra state

rating: 5
reason: Correct, no extra state

### Route 2

- Route: fcntl.flock on a lock file in .troupe/
- Reasoning given: Groups it with the store's files; falls back to read-only open
- Outcome: Kept
- proposed: 4 - Works; leaves an extra file

rating: 4
reason: Works; leaves an extra file

## T45

**Question:** Wait or fail when the lock is held  
**Kind:** divergent

**What's at stake:** When two commands try to change the config at the same time, or one has crashed or hung while holding it, the user either waits indefinitely or gets an answer. That can mean a terminal that sits silent with no explanation, or a script that never finishes.

**In practice:** Route 1: if another process is holding the config lock, a second command waits quietly until the lock is released. It has no time limit. If the first process hangs, the second one hangs too until someone kills the first. Users get no message saying they are waiting. If the same running program tries to take the lock a second time while it already holds it, it stops right away with an error instead of locking itself up. For maintainers, this means a code path that nests lock-taking shows up as a clear error rather than a silent freeze. Route 2: nobody decided what should happen when the lock is already held. What users get depends on whatever the underlying locking does by default. That could be waiting, failing, or freezing on a nested acquire, and it was never written down or chosen on purpose.

**Trade-off:** Route 1 costs possible indefinite, silent waits behind a hung process. Route 2 costs predictability, because behaviour when the lock is held, including nested use, is left to chance.

### Route 1

- Route: Block without timeout; a nested acquire in one process raises
- Reasoning given: A hung process blocking others is acceptable for small configs
- Outcome: Kept
- proposed: 4 - Simple; hang risk accepted

rating: 2
reason: Waits indefinitely and silently behind another holder: bad, but it catches the nested acquire

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 1
reason: Unconsidered; can freeze on its own nested acquire (unverified), worse than waiting on another process

## T46

**Question:** Keys over 1024 chars  
**Kind:** divergent

**What's at stake:** YAML cannot hold a plain key longer than 1024 characters. If a user sets one, the tool must refuse cleanly rather than write a config file that no longer loads. In every run on both routes, the file was left untouched. The only differences were the exit code and how readable the error was.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.<1,090-char key> long-key-value` (the key is "abcdefghij" repeated 109 times) _(observed)_

Starting file:

~~~
# team config
agents:
  coder:
    model: opus  # main model
~~~

- Route 1: Both arms: exit 3, file unchanged. One arm says "…: written value cannot be read back: … invalid YAML: … could not find expected ':' (line 5, column 1095)". The other arm says "…: cannot parse …/troupe.yml: could not find expected ':' at line 5; no file changed".
- Route 2: Three arms: exit 3, file unchanged, each with a one-line refusal: "the result would not load (… invalid YAML (line 5, column 1093) …); not writing", "write refused: …: cannot write this change faithfully (… invalid YAML: while scanning a simple key)", and "the change … would not load back (…multi-line parser trace…); no file was changed". One arm: exit 4, file unchanged, but stderr is only the raw multi-line YAML parser trace ("invalid YAML: while scanning a simple key … could not find expected ':' … column 1093"). It never says that nothing was written.

**Example 2:** `config get agents.<same 1,090-char key>` _(observed)_

- Route 1: Both arms: exit 5, not found. One arm adds "(at segment '…')", and the other adds "(no agents.…)".
- Route 2: All four arms: exit 5, "not found" / "path not found".

**Example 3:** `config set agents.coder.model sonnet`, then `config show agents` and `config history` _(observed)_

Starting file:

~~~
# team config
agents:
  coder:
    model: opus  # main model
~~~

- Route 1: Both arms: exit 0; the file now reads:

  ~~~
  # team config
  agents:
    coder:
      model: sonnet # main model
  `show` prints `coder:\n  model: sonnet`. History has two entries: the import of opus and the set to sonnet. The failed long-key set left no entry.
  ~~~

- Route 2: All four arms: exit 0; the file now reads:

  ~~~
  # team config
  agents:
    coder:
      model: sonnet # main model
  `show` and history are the same as route 1, again with no entry for the failed set.
  ~~~


**In practice:** Neither route ever damaged the file or added a history entry, and normal edits kept working afterwards. Route 2 is slightly less uniform. One of its runs exits with 4 instead of 3 and shows only a raw parser dump. Every other run on both routes gives a short refusal.

**Trade-off:** Route 1 adds no code and refuses the write with exit 3 in both runs. Route 2 also adds nothing, but in one run its error was a raw parser dump with a different exit code.

### Route 1

- Route: Leave unhandled
- Reasoning given: Out of contract
- Outcome: Kept
- proposed: 4 - Fine

rating: 3.5
reason: RESLICE placeholder: A (exit 3, clear no-write refusal) 4; B (exit 3, reads as if written) 3

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Unrealistic

rating: 3.5
reason: RESLICE placeholder: A 4 x3; C (exit 4, raw parser trace only) 2

## T47

**Question:** Malformed PATH such as `a..b` or an empty PATH  
**Kind:** divergent

**What's at stake:** If someone mistypes a key path (a doubled dot, a trailing dot, or an empty string), the tool should refuse it clearly instead of writing a strange key into troupe.yml or recording a bogus change in history. In these runs, every arm on both routes refused all four bad paths the same way: exit 2, nothing written. The only difference is the wording of the error.

**What each route does** (run against every arm's final code):

**Example 1:** `config set a..b 1` _(observed)_

Starting file:

~~~
models:
  default: opus  # main model
retry: 3
~~~

- Route 1: Both arms: exit 2 and the file is unchanged. One arm prints `a..b: malformed PATH 'a..b': segments must not be empty (no leading, trailing or doubled '.')`. The other prints `troupe: error: invalid path 'a..b': path segments must not be empty`.
- Route 2: All four arms: exit 2 and the file is unchanged. Two arms print `troupe: invalid path 'a..b': empty segment`. One arm prints `troupe: usage error: invalid path: 'a..b'`. One arm prints `troupe: invalid path: 'a..b'`.

**Example 2:** `config get ""` (empty PATH) _(observed)_

- Route 1: Both arms: exit 2. One arm prints `malformed PATH '': PATH is empty`. The other prints `troupe: error: invalid path '': path segments must not be empty`.
- Route 2: All four arms: exit 2. Two arms print `troupe: invalid path '': empty segment`. One arm prints `troupe: usage error: invalid path: ''`. One arm prints `troupe: invalid path: ''`.

**Example 3:** `config set models. sonnet` _(observed)_

Starting file:

~~~
models:
  default: opus  # main model
retry: 3
~~~

- Route 1: Both arms: exit 2, and `models.default` stays `opus`. One arm prints `models.: malformed PATH 'models.': segments must not be empty (no leading, trailing or doubled '.')`. The other prints `troupe: error: invalid path 'models.': path segments must not be empty`.
- Route 2: All four arms: exit 2 and the file is unchanged. Two arms print `troupe: invalid path 'models.': empty segment`. One arm prints `troupe: usage error: invalid path: 'models.'`. One arm prints `troupe: invalid path: 'models.'`.

**Example 4:** `config history models..default` _(observed)_

- Route 1: Both arms: exit 2 with an invalid-path message (one says `malformed PATH 'models..default': segments must not be empty ...`, the other says `troupe: error: invalid path 'models..default': path segments must not be empty`).
- Route 2: All four arms: exit 2 with an invalid-path message (two arms: `troupe: invalid path 'models..default': empty segment`; the others: `troupe: usage error: invalid path: 'models..default'` and `troupe: invalid path: 'models..default'`).

**Example 5:** `config history` (after the four rejected commands) _(observed)_

- Route 1: Both arms: exit 0. History lists only the 2 import entries (`models.default` = opus, `retry` = 3); none of the rejected commands was recorded.
- Route 2: All four arms: exit 0. History lists only the same 2 import entries; nothing from the rejected commands.

**In practice:** From the user's side the two routes behaved the same: every malformed path was refused with exit 2, troupe.yml was never touched, and history kept no trace of the rejected attempts. What a user would notice is the error text. Some arms explain the problem (empty segment, no leading, trailing or doubled dot). Others only say the path is invalid. These runs can't show whether any arm opened or created its state before refusing, because a theatre with history already existed by the end in every case.

**Trade-off:** Route 1 commits to a clear message about the rule up front. Route 2 left the behaviour unplanned, but here it still refused cleanly, with messages ranging from explanatory to a bare "invalid path".

### Route 1

- Route: Exit 2 before the theatre is opened (history too), with a clear message
- Reasoning given: The argument is malformed, not missing; no state is created
- Outcome: Kept
- proposed: 5 - Right exit code, no side effects

rating: 4.5
reason: RESLICE placeholder: A (states the rule) 5; B (states the problem) 4

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Could create empty-string keys

rating: 3.5
reason: RESLICE placeholder: B 4 x2; C (bare 'invalid path') 3 x2

## T48

**Question:** How a set that changes several files is applied  
**Kind:** divergent

**What's at stake:** One `config set` can change both troupe.yml and a prompt file it points to. The user needs to know whether both files change together, whether a bad value is refused before anything is written, and whether the prompt file keeps its own file and the comments survive.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder '{model: sonnet, prompt: "Be terse.\n"}' --reason "multi-file set"` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
# team config
agents:
  coder:
    model: opus  # main model
    prompt: file:prompts/coder.md
  reviewer:
    model: opus
    prompt: file:prompts/reviewer.md

.troupe/prompts/coder.md:
You write code.
~~~

- Route 1: The three arms on this route split. One arm: exit 0; both files change. coder.md now reads `Be terse.` and troupe.yml reads:

  ~~~
    coder:
      model: sonnet # main model
      prompt: file:prompts/coder.md
  Two arms: exit 0; coder.md is left as `You write code.`, and the prompt is copied into troupe.yml. The `# main model` comment and the file link are gone:
    coder:
      model: sonnet
      prompt: |
        Be terse.
  ~~~

- Route 2: exit 0; both files change. coder.md now reads `Be terse.` and troupe.yml reads:

  ~~~
    coder:
      model: sonnet # main model
      prompt: file:prompts/coder.md
  ~~~

- Route 3: Both arms: exit 0; both files change. coder.md now reads `Be terse.` and troupe.yml reads:

  ~~~
    coder:
      model: sonnet # main model
      prompt: file:prompts/coder.md
  ~~~


**Example 2:** `config set agents.reviewer '{model: haiku, prompt: 42}' --reason "should fail on second file"` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
  reviewer:
    model: opus
    prompt: file:prompts/reviewer.md

.troupe/prompts/reviewer.md:
Review carefully.
~~~

- Route 1: One arm: exit 3, `troupe: agents.reviewer.prompt: is the text of .troupe/prompts/reviewer.md; VALUE must be a string`. No file changes and the model stays opus. Two arms: exit 0, accepted. The file link is replaced and troupe.yml now reads:

  ~~~
    reviewer:
      model: haiku
      prompt: 42
  History records prompt changing from "Review carefully.\r\n" to 42.
  ~~~

- Route 2: exit 3, `/theatre/.troupe/prompts/reviewer.md: agents.reviewer: the value is the text include file:prompts/reviewer.md, which can only be set to a string`. No file changes, the model stays opus, and nothing is added to history.
- Route 3: Both arms: exit 3. No file changes and nothing is added to history. The messages differ: `troupe: write refused: /theatre/.troupe/prompts/reviewer.md: a text include can only be set to a string` and `troupe: agents.reviewer.prompt: text include .troupe/prompts/reviewer.md can only be set to a string`.

**Example 3:** `config show agents --sources` (after both sets) _(observed)_

- Route 1: One arm: coder's prompt shows `# from .troupe/prompts/coder.md`, and reviewer still shows `model: opus` with `prompt: "Review carefully.\r\n" # from .troupe/prompts/reviewer.md`. Two arms: every value shows `# from .troupe/troupe.yml`, including `model: haiku` and `prompt: 42`.
- Route 2: coder's prompt shows `# from .troupe/prompts/coder.md`. reviewer shows `model: opus` and its prompt as a block from .troupe/prompts/reviewer.md.
- Route 3: Both arms: coder's prompt shows `# from .troupe/prompts/coder.md`, and reviewer shows `model: opus` with its prompt from .troupe/prompts/reviewer.md. One arm prints the prompt as `"Review carefully.\r\n"`. The other arm prints a block reading `Review carefully.` without the \r, but the file itself was not touched.

**In practice:** Every arm that refused the bad value did so before writing anything, so these runs never test what happens if the disk write itself fails partway through. Rollback, and naming a file that could not be restored, was never exercised. The real split is on route 1: two of its three arms never write to more than one file. They copy the prompt text into troupe.yml, which breaks the file link and drops comments, and they accept a number as a prompt.

**Trade-off:** Route 1: least code, but checking everything before writing protects against bad values, not against the write itself failing; two of its arms skipped the two-file write and lost comments. Route 2: more code (rollback, reporting any file it could not restore) for all-or-nothing that also covers failed writes. Route 3: not designed for this question, but in these runs it behaved the same as route 2.

### Route 1

- Route: Compute and verify every file first, then write each; nothing is written if any check fails
- Reasoning given: Only OS errors during the write itself remain
- Outcome: Kept
- proposed: 4 - Good, but a failure between file writes leaves a partial change

rating: 3
reason: RESLICE placeholder: A (writes both files, keeps link) 5; B (inlines prompt, drops link and comment, accepts 42) 2 x2

### Route 2

- Route: Refuse multi-file sets, reworked within step 1 to: verify all, write each atomically, roll back on failure, and name any file that could not be restored
- Reasoning given: Refusing contradicted the contract rule that only required bytes change; rollback keeps the set all-or-nothing
- Outcome: Reworked at step 1, then kept
- proposed: 5 - Closest to all-or-nothing

rating: 5
reason: Writes both files, keeps link and comment, refuses non-string prompt; rollback not exercised

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Partial multi-file writes are a real corruption path

rating: 5
reason: Same as route 2 in these runs

## T49

**Question:** Quick successive edits  
**Kind:** divergent

**What's at stake:** If you edit the config file by hand twice before running any command, the history may keep only the overall change from before the first edit to after the second. The value in between is lost, and a value that changed and then changed back leaves no record. This matters to anyone who uses the history to audit or roll back changes.

**What each route does** (run against every arm's final code):

**Example 1:** `config set retry 5`, then `config set retry 7`, then `config history` _(observed)_

Starting file:

~~~
retry: 3
timeout: 3
limit: 3
~~~

- Route 1: both arms: each set exits 0 with no output. History lists the 3 imported values, then two separate entries: `retry` 3 -> 5 and `retry` 5 -> 7, both by human owner via cli.
- Route 2: all four arms: the same as route 1. Each set exits 0 with no output, and history shows `retry` 3 -> 5 and `retry` 5 -> 7 as two entries by human owner via cli.

**Example 2:** edit the file by hand to: retry: 7 timeout: 5 limit: 5 then right away edit it by hand again to: retry: 7 timeout: 7 limit: 3 then run `config get timeout` and `config history` _(observed)_

Starting file:

~~~
retry: 7
timeout: 3
limit: 3
~~~

- Route 1: both arms: `config get timeout` prints `7`, exit 0. History adds only one entry: `timeout` 3 -> 7, by an unknown actor, via file. The intermediate timeout of 5 is not recorded, and limit's change 3 -> 5 -> 3 does not appear at all.
- Route 2: all four arms: the same as route 1. `config get timeout` prints `7`, and history adds a single entry `timeout` 3 -> 7 (unknown actor, via file). Nothing is recorded for timeout 5 or for limit.

**In practice:** All 6 arms on both routes behaved the same way. Commands are each recorded as a separate entry. Hand edits are picked up only the next time a command runs, as a comparison against the last recorded state. So several hand edits made in between collapse into their net change, and a value edited and then restored disappears from the history. This net-change behaviour is what route 1 describes. Route 2 never addressed the question, but it behaves the same way.

**Trade-off:** Route 1 states the behaviour on purpose, so users can rely on it; route 2 gives the same results without stating them, so the loss of intermediate hand edits goes undocumented.

### Route 1

- Route: May be recorded as their net difference
- Reasoning given: A diff against recorded state is net
- Outcome: Kept
- proposed: 5 - Honest

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Implicit

rating: n/a
reason:

## T50

**Question:** Which quoting style new keys and items copy  
**Kind:** divergent

**What's at stake:** When you add a key or list item to a hand-edited config, the tool decides how to quote it. If it guesses wrong, the file ends up with mixed quoting styles, or quotes you wrote are removed. In one case below, replacing a whole section with `config set` strips quotes from an entry you did not change.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.planner haiku` _(observed)_

Starting file:

~~~
agents:
  coder: opus
  'reviewer': 'sonnet'
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  agents:
    coder: opus
    'reviewer': 'sonnet'
    'planner': 'haiku'
  ~~~

- Route 2: exit 0; same as route 1: the new key copies the single quotes of the entry above it:

  ~~~
  agents:
    coder: opus
    'reviewer': 'sonnet'
    'planner': 'haiku'
  ~~~


**Example 2:** `config set tags.2 gamma` _(observed)_

Starting file:

~~~
tags:
  - alpha
  - "beta"
~~~

- Route 1: exit 0; the file now reads:

  ~~~
  tags:
    - alpha
    - "beta"
    - "gamma"
  ~~~

- Route 2: exit 0; same as route 1:

  ~~~
  tags:
    - alpha
    - "beta"
    - "gamma"
  ~~~


**Example 3:** `config set teams '{red: one, blue: two, gold: four}'` (this replaces the section, drops green and adds gold) _(observed)_

Starting file:

~~~
teams:
  red: one
  "blue": "two"
  'green': 'three'
~~~

- Route 1: exit 0. Arms on this route differed. One arm: gold copies the double quotes of blue, now the last remaining entry:

  ~~~
  teams:
    red: one
    "blue": "two"
    "gold": "four"
  Two arms: gold copies the single quotes of the deleted green entry:
  teams:
    red: one
    "blue": "two"
    'gold': 'four'
  ~~~

- Route 2: exit 0. Arms on this route differed. One arm: gold copies the single quotes of the deleted green entry:

  ~~~
  teams:
    red: one
    "blue": "two"
    'gold': 'four'
  Two arms: the whole section is rewritten without quotes, and the existing blue entry loses its quotes too:
  teams:
    red: one
    blue: two
    gold: four
  ~~~


**Example 4:** `config set fresh.name 'x y'` (a new section with nothing to copy) _(observed)_

- Route 1: exit 0; the following is added at the end, unquoted:

  ~~~
  fresh:
    name: x y
  ~~~

- Route 2: exit 0; same as route 1:

  ~~~
  fresh:
    name: x y
  ~~~


**Example 5:** `config show` after the four commands above _(observed)_

- Route 1: exit 0; same output in every arm, quotes removed:

  ~~~
  teams:
    red: one
    blue: two
    gold: four
  fresh:
    name: x y
  ~~~

- Route 2: exit 0; identical to route 1

**In practice:** Adding one key or list item gave the same result on both routes: the new entry copies the quoting of the entry above it, and a brand-new section gets no quotes. The routes only differed when `config set` replaced a whole section and dropped its last entry. Neither route was consistent across its arms in that case. On route 1 the new entry was quoted in one of two ways, but no existing quoting changed. On route 2, two arms stripped the quotes from the untouched blue entry. `config show` displays the values the same way everywhere, so these differences only appear in the file on disk.

**Trade-off:** Route 1: never removes your existing quotes, but a new key can still copy the style of an entry the same command just deleted. Route 2: same as route 1 for single additions, but replacing a section can remove quotes from entries you didn't change.

### Route 1

- Route: Copy the preceding sibling's style (after a merge deletes the last entry, the last remaining one), else the minimal style
- Reasoning given: Contract rule; 'preceding sibling' means an entry in the written file
- Outcome: Kept
- proposed: 5 - Follows the user's style

rating: 4
reason: RESLICE placeholder: A (copies remaining sibling) 4; B (copies deleted entry) 4 x2

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - The contract asks new entries to follow their siblings

rating: 4.5
reason: RESLICE placeholder: B 4; C (section rewritten as given, unquoted) 5 x2

## T51

**Question:** Is the state store created when the configuration fails to load  
**Kind:** divergent

**What's at stake:** When troupe.yml is broken or missing, a read-only command like `config get` can still leave a new event database or lock file in the project's .troupe folder. The user never asked for these files, and they stay behind after the error.

**What each route does** (run against every arm's final code):

**Example 1:** with a broken troupe.yml, run `config get retry`, `config show`, `config set retry 5` and `config history`, then list .troupe _(observed)_

Starting file:

~~~
retry: 3
agents:
  coder: [unclosed, list
  reviewer: {model: opus
~~~

- Route 1: four arms: all four commands exit 4 with an invalid-YAML error that names line 4; .troupe still holds only troupe.yml (67 bytes). One arm: the same exit 4 and error, but .troupe now also holds a new empty file `events.sqlite3.lock` (0 bytes)
- Route 2: all four commands exit 4 with a multi-line invalid-YAML error; .troupe now also holds `events.lock` (0 bytes) and `events.sqlite` (12288 bytes), a new event database

**Example 2:** `config set --theatre=nocfg retry 5` (nocfg/.troupe has no troupe.yml, only a README) _(observed)_

- Route 1: all five arms: exit 4, "no configuration file". Four arms: nocfg/.troupe still holds only README. One arm (the same one as above): a new empty `nocfg/.troupe/events.sqlite3.lock` appears
- Route 2: exit 4, `troupe: nocfg/.troupe/troupe.yml: no configuration file`; nocfg/.troupe still holds only README

**Example 3:** `--theatre ok config get retry` (ok/.troupe/troupe.yml is valid: `retry: 3`) _(observed)_

- Route 1: four arms: exit 2, `--theatre` is rejected before the command name ("invalid choice: 'ok'"); no files are created. One arm: prints `3`, exit 0, and creates `ok/.troupe/events.sqlite` (12288 bytes)
- Route 2: exit 2, "invalid choice: 'ok' (choose from config)"; no files are created

**In practice:** The listings were taken only after all the failing commands had run, so they don't show which command created the files. Usage errors created no files on either route, including a missing VALUE and `TROUPE_ACTOR=robot` (both exit 2). On route 1, one arm still leaves a 0-byte lock file wherever a load fails. On route 2, a failed load leaves a full event database behind. The only time any arm created a database was when the config loaded and the command succeeded.

**Trade-off:** Route 1 has to check the config and the arguments before touching storage, and one arm still leaves a lock file; route 2 creates the store first, so any broken config leaves a database and lock file behind.

### Route 1

- Route: Open or create the store only after the configuration loads and arguments are valid
- Reasoning given: A failing load must create no state; one arm reworked its step-2 sync design to keep this
- Outcome: Kept
- proposed: 5 - No surprise state

rating: 5
reason: RESLICE placeholder: A (no state left) 5 x4; B (empty lock file left) 4

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - A broken config could leave a .troupe state file behind

rating: 2
reason: Broken config leaves a lock file and a new event database behind

## T52

**Question:** How non-finite floats appear in history JSON  
**Kind:** divergent

**What's at stake:** The change-history log is meant to hold one JSON object per line. Route 1 records infinity and NaN as the text ".inf", "-.inf" and ".nan", so a real number can't be told apart from a string that happens to read ".inf". Route 2 writes bare Infinity and NaN, which strict JSON readers reject.

**What each route does** (run against every arm's final code):

**Example 1:** `config history` _(observed)_

Starting file:

~~~
limits:
  max: .inf
  min: -.inf
  ratio: .nan
  retry: 1.5
  name: ".inf"
~~~

- Route 1: exit 0; the import entries read (other fields trimmed):

  ~~~
  "path": "limits.max", "old": null, "new": ".inf"
  "path": "limits.min", "old": null, "new": "-.inf"
  "path": "limits.ratio", "old": null, "new": ".nan"
  "path": "limits.retry", "old": null, "new": 1.5
  "path": "limits.name", "old": null, "new": ".inf"
  The number max and the string name are logged identically. Both arms gave this output.
  ~~~

- Route 2: exit 0; the import entries read (other fields trimmed):

  ~~~
  "path": "limits.max", "old": null, "new": Infinity
  "path": "limits.min", "old": null, "new": -Infinity
  "path": "limits.ratio", "old": null, "new": NaN
  "path": "limits.retry", "old": null, "new": 1.5
  "path": "limits.name", "old": null, "new": ".inf"
  The values are bare Infinity, -Infinity and NaN, which are not valid strict JSON. All four arms gave this output.
  ~~~


**Example 2:** `config set limits.max 10`, then `config history limits` _(observed)_

Starting file:

~~~
limits:
  max: .inf
  min: -.inf
  ratio: .nan
  retry: 1.5
  name: ".inf"
~~~

- Route 1: exit 0; the file now has `max: 10`. The new history line reads:

  ~~~
  "op": "set", "path": "limits.max", "old": ".inf", "new": 10
  Both arms gave this.
  ~~~

- Route 2: exit 0; the file now has `max: 10`. The new history line reads:

  ~~~
  "op": "set", "path": "limits.max", "old": Infinity, "new": 10
  All four arms gave this.
  ~~~


**Example 3:** `config set limits.retry -.inf` _(observed)_

Starting file:

~~~
limits:
  max: .inf
  min: -.inf
  ratio: .nan
  retry: 1.5
  name: ".inf"
~~~

- Route 1: The two arms differ. One arm: exit 0; the file now reads `retry: -.inf`, and history logs "old": 1.5, "new": "-.inf". Other arm: exit 2, `troupe: troupe config set: the following arguments are required: value`, and nothing changes.
- Route 2: All four arms: exit 2, nothing changes. Each arm says the value argument is required; two of them also print the full usage text.

**Example 4:** `config get limits.ratio` _(observed)_

Starting file:

~~~
limits:
  max: .inf
  min: -.inf
  ratio: .nan
  retry: 1.5
  name: ".inf"
~~~

- Route 1: exit 0, prints `nan` (both arms)
- Route 2: exit 0, prints `nan` (all four arms)

**In practice:** Only the history log differs; the config file and `config get` behave the same on both routes. A script that reads route 1's history with a standard JSON parser works, but sees ".inf" as plain text and can't tell infinity from the string ".inf". On route 2, a strict JSON parser rejects the line, while a lenient one reads the real number. A value starting with '-', like `-.inf`, is rejected as a missing argument everywhere except one route-1 arm.

**Trade-off:** Route 1: valid JSON, but a non-finite number and a look-alike string are logged identically. Route 2: the numeric type is kept, but the history lines are not strict JSON.

### Route 1

- Route: YAML-style strings .inf/-.inf/.nan (encoded with allow_nan=False)
- Reasoning given: JSON Lines required; null would lose the value
- Outcome: Kept
- proposed: 5 - Valid and unambiguous

rating: 3
reason: Valid JSON, but infinity and the string '.inf' are logged identically; neither route marks the type

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Python's default emits Infinity/NaN, which is invalid JSON

rating: 2
reason: Keeps the number but bare Infinity/NaN break strict JSON Lines readers

## T53

**Question:** Quoting new keys that would read back as non-strings  
**Kind:** divergent

**What's at stake:** When someone sets a config key named like `true`, `null`, `1e3` or `<<`, the question is whether the YAML file on disk still holds that key as plain text. Unquoted, other YAML readers will load such a key as a boolean, null, number or merge key instead of a name.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder.true on` _(observed)_

Starting file:

~~~
agents:
  coder:
    model: opus  # main model
~~~

- Route 1: exit 0; the file now reads:

  ~~~
      model: opus  # main model
      'true': on
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
      model: opus  # main model
      true: on
  ~~~

- Route 3: all four arms: exit 0; the file now reads:

  ~~~
      model: opus  # main model
      'true': on
  ~~~


**Example 2:** `config set agents.coder.null x`, then `config set agents.coder.1e3 y` _(observed)_

- Route 1: both exit 0; the file now reads:

  ~~~
      'true': on
      'null': x
      '1e3': y
  ~~~

- Route 2: both exit 0; the file now reads:

  ~~~
      true: on
      null: x
      1e3: y
  ~~~

- Route 3: all four arms: both exit 0; the file now reads:

  ~~~
      'true': on
      'null': x
      '1e3': y
  ~~~


**Example 3:** `config set agents.coder.<< z` _(observed)_

- Route 1: exit 0; the file gains the line:

  ~~~
      '<<': z
  ~~~

- Route 2: exit 0; the file gains the line:

  ~~~
      '<<': z
  ~~~

- Route 3: all four arms: exit 3, no file change. The wording differs by arm, e.g. "troupe: agents.coder.<<: '<<' is the merge key; troupe never writes merge keys; no file changed" and "troupe: error: agents.coder.<<: troupe never writes a merge key (<<)"

**Example 4:** `config show agents.coder` (after the commands above) _(observed)_

- Route 1: exit 0; prints:

  ~~~
  model: opus
  'true': on
  'null': x
  '1e3': y
  '<<': z
  ~~~

- Route 2: exit 0; prints the same quoted keys even though the file has them unquoted:

  ~~~
  model: opus
  'true': on
  'null': x
  '1e3': y
  '<<': z
  ~~~

- Route 3: three arms: exit 0; prints:

  ~~~
  model: opus
  'true': on
  'null': x
  '1e3': y
  one arm: exit 0; also quotes the values:
  model: opus
  'true': 'on'
  'null': x
  '1e3': 'y'
  ~~~


**In practice:** On route 2, `config show` displays the keys quoted, but the file itself contains plain `true:`, `null:` and `1e3:`. Any other tool or person reading the file will see those as a boolean, a null and a number, not as names. Routes 1 and 3 write the quotes into the file. Route 3 also refuses to create a `<<` key at all, while routes 1 and 2 store it quoted.

**Trade-off:** Route 1 quotes every ambiguous key and allows a quoted `<<`. Route 2 only guards `<<`, so the file is left with keys that other readers take as non-strings. Route 3 quotes ambiguous keys too but rejects `<<` with exit 3, and one arm also quotes some values in `show`.

### Route 1

- Route: Quote any new key whose plain form would not read back as a string
- Reasoning given: Unquoted, it would read back as a boolean or number
- Outcome: Kept; at step 6 a new key named << is also written quoted
- proposed: 5 - General and correct

rating: 5
reason: Quotes every ambiguous key in the file, including '<<'

### Route 2

- Route: Quote keys spelled << (found in review)
- Reasoning given: The loader refuses a plain <<
- Outcome: Kept; the show renderer later applied the general rule
- proposed: 4 - Fixes the known case only

rating: 2
reason: File left with true:/null:/1e3: keys other readers take as non-strings; show hides it

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - A plain key like `true` reads back as a boolean

rating: 4
reason: Quotes ambiguous keys, but refuses a valid quoted '<<' key (clear message)

## T54

**Question:** Anchors, aliases, merge keys and tags at load before step 6  
**Kind:** divergent

**What's at stake:** This is about config files that use YAML anchors, aliases, merge keys (`<<: *d`) or explicit tags (`!!str`, `!!bool`, `!!float`). Depending on the route, a user is blocked from reading the file at all, reads values with the wrong type, or edits one key and changes other keys that share it without being told.

**What each route does** (run against every arm's final code):

**Example 1:** `config show` _(observed)_

Starting file:

~~~
defaults: &d
  model: opus
  port: !!str 8080
coder:
  settings: *d
reviewer:
  <<: *d
  model: sonnet
flags:
  enabled: !!bool "true"
  ratio: !!float 1
~~~

- Route 1: exit 4, prints nothing. The file cannot be read at all. One arm: `defaults.port: explicit tag '!!str' is not supported`; one arm: `cannot parse ...: tags are not supported at line 3`. Every other command (`history`, `set`) fails the same way.
- Route 2: exit 0; the tags are honoured and the merge is resolved:

  ~~~
  port: '8080'
  ...
  reviewer:
    port: '8080'
    model: sonnet
  flags:
    enabled: true
    ratio: 1.0
  ~~~

- Route 3: exit 0; the tags are ignored (port becomes a number, enabled becomes a string) and `<<` is shown as an ordinary key:

  ~~~
  port: 8080
  ...
  reviewer:
    <<:
      model: opus
      port: 8080
    model: sonnet
  flags:
    enabled: 'true'
    ratio: 1
  ~~~

- Route 4: exit 0; the tags are honoured, but `<<` is shown as an ordinary key:

  ~~~
  port: '8080'
  ...
  reviewer:
    <<:
      model: opus
      port: '8080'
    model: sonnet
  flags:
    enabled: true
    ratio: 1.0
  ~~~

- Route 5: exit 0; the tags are ignored but the merge is resolved:

  ~~~
  port: 8080
  ...
  reviewer:
    port: 8080
    model: sonnet
  flags:
    enabled: 'true'
    ratio: 1
  ~~~


**Example 2:** `config set reviewer.port 9090` (reviewer gets port only through `<<: *d`) _(observed)_

- Route 1: exit 4, same parse error as above; file unchanged
- Route 2: exit 3: `reviewer.port is supplied by the merge key reviewer.<<; troupe never writes merge keys (--expand-alias cannot help), so edit the file by hand`; file unchanged
- Route 3: exit 0; the file now reads:

  ~~~
  reviewer:
    <<: *d
    model: sonnet
    port: 9090
  ~~~

- Route 4: exit 0; the file now reads:

  ~~~
  reviewer:
    <<: *d
    model: sonnet
    port: 9090
  ~~~

- Route 5: exit 3: `write refused: reviewer.port comes from a merge key (<<: *d), and merge keys are never written. Set it at the anchor, or use --expand-alias to give it its own key here`; file unchanged

**Example 3:** `config set defaults.port '"9091"'` (the anchored key, shared by coder and reviewer) _(observed)_

- Route 1: exit 4, same parse error; file unchanged
- Route 2: exit 3: `defaults.port: cannot rewrite this value safely (unsupported tag or block layout)`; file unchanged
- Route 3: exit 0, no warning; the `!!str` tag is dropped and the file now reads:

  ~~~
  defaults: &d
    model: opus
    port: '9091'
  History records this one command as three changes: defaults.port, coder.settings.port and reviewer.<<.port, all 8080 -> "9091"
  ~~~

- Route 4: exit 0, no warning; the `!!str` tag is dropped and the file now reads:

  ~~~
  defaults: &d
    model: opus
    port: '9091'
  History records three changes: defaults.port, coder.settings.port and reviewer.<<.port, all "8080" -> "9091"
  ~~~

- Route 5: exit 0, no warning; the tag is kept and the file now reads:

  ~~~
  defaults: &d
    model: opus
    port: !!str '9091'
  History records three changes: defaults.port, coder.settings.port and reviewer.port, all 8080 -> "9091"
  ~~~


**In practice:** On routes 3, 4 and 5, changing an anchored key also changes every key that points to it. The command exits 0 and prints nothing about it; you only see it in `history`. Routes 3 and 5 also read `port: !!str 8080` as the number 8080 and `enabled: !!bool "true"` as the string 'true', so a value's type can differ from what the file says. Routes 3 and 4 show `<<` in `show` and in history paths as if it were a real key.

**Trade-off:** Route 1 locks you out of any file that uses these features, even for reading. Route 2 reads correctly but refuses both edits. Routes 3 and 4 accept every edit and silently change shared keys, and route 3 also gets types wrong. Route 5 keeps the tags and refuses edits to merged keys, but still gets types wrong on read and silently changes shared keys when you edit an anchor.

### Route 1

- Route: Anchors, aliases, merge keys and tags exit 4
- Reasoning given: Out of contract until step 6; writes through an alias would change other paths
- Outcome: Replaced at step 6 by full alias support
- proposed: 5 - Safe refusal

rating: 2
reason: Refuses to even read a valid file (exit 4 on everything)

### Route 2

- Route: Honour explicit core tags; other tags, anchors and aliases exit 4
- Reasoning given: Conservative choice
- Outcome: Replaced at step 6
- proposed: 5 - Safe and slightly more capable

rating: 4
reason: Reads correctly; refuses both edits clearly

### Route 3

- Route: Ignore tags: plain scalars always resolved, quoted or block scalars stay strings
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 3 - Silently drops explicit typing the user wrote

rating: 1
reason: Wrong types, phantom << key, drops !!str tag, silent shared change

### Route 4

- Route: Leave anchors/aliases/merge keys out of contract, undefined and untested; do not flag loss of explicit tags
- Reasoning given: Outside the contract
- Outcome: At step 6 this arm found silent writes through aliases (exit 0) and fixed them
- proposed: 2 - Allowed a silent shared-value corruption until step 6

rating: 2
reason: Right types, but phantom << key, drops tag, silent shared change

### Route 5

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Writing through an alias silently changes other paths

rating: 3
reason: Wrong types on read and silent anchor change, but refusals offer fixes and the tag is kept

## T55

**Question:** Share set's leaf diff with reconcile  
**Kind:** divergent

**What's at stake:** This decides whether the change history (`config history`) records a hand edit of the config file the same way it records the same change made with `config set`. If the two disagree, anyone reading or diffing the history would see the same change logged two different ways.

**What each route does** (run against every arm's final code):

**Example 1:** `config set cli.m "{x: 10, y: 2, z: 3}"`, then `config set cli.l "[a, true]"`, then `config history cli` _(observed)_

Starting file:

~~~
cli:
  m:
    x: 1
    tags:
      - p
      - q
      - r
    y: 2
  l:
    - a
    - b
    - c
~~~

- Route 1: Three arms: both sets exit 0 and the file now reads `x: 10`, `y: 2`, `z: 3`, with `tags` gone and `l` as `a`, `true`. History adds, all marked via cli: set cli.m.x 1→10, set cli.m.z →3, remove cli.m.tags.0/1/2, set cli.l.1 b→true, remove cli.l.2. The unchanged y gets no entry. One arm: same file and same events, but in a different order: the three tags removes come first, then set x and set z, then remove cli.l.2 before set cli.l.1.
- Route 2: Exit 0 and the same file. History adds the same events in the same order as the three-arm group on route 1: set x, set z, remove tags.0/1/2, set l.1, remove l.2.
- Route 3: Exit 0 and the same file. History adds the same events in the same order as the three-arm group on route 1: set x, set z, remove tags.0/1/2, set l.1, remove l.2.

**Example 2:** Edit the `hand:` section by hand to the same new values (first m, then l to `a`, `true`), then `config history hand` _(observed)_

Starting file:

~~~
hand:
  m:
    x: 1
    tags:
      - p
      - q
      - r
    y: 2
  l:
    - a
    - b
    - c
~~~

- Route 1: On every arm, `config get hand.m.z` prints 3 and `config get hand.l.1` prints true. The history adds the same events, in the same order, as that arm's own `config set` run (via file, actor unknown). Three arms: set x, set z, remove tags.0/1/2, set l.1, remove l.2. One arm: remove tags.0/1/2, set x, set z, remove l.2, set l.1.
- Route 2: `config get` prints 3 and true. The history adds set x, set z, remove tags.0/1/2, set l.1, remove l.2 (via file, actor unknown). That is the same order as this route's `config set` run.
- Route 3: `config get` prints 3 and true. The history adds set x, set z, remove tags.0/1/2, set l.1, remove l.2 (via file, actor unknown). That is the same order as this route's `config set` run.

**In practice:** Every arm on every route logged a hand edit with the same events as the matching `config set`, and in the same order. Only the via and actor fields differ: via file and actor unknown for the hand edit, versus via cli and actor human. Route 2's stated reason was a different remove order for hand edits, but that did not show up in these runs. The only difference seen was on route 1: one arm put the removes before the sets, for both `config set` and hand edits. That arm stayed consistent with itself, but its order differs from the other route 1 arms and from routes 2 and 3.

**Trade-off:** Route 1 uses one diff for both, so the two paths can't drift apart, but its arms didn't all agree on event order. Route 2 keeps a second, smaller diff that has to be kept in step by hand. Route 3 was never planned or reasoned about, yet it behaved the same as route 2 here.

### Route 1

- Route: One shared diff function for set and reconcile
- Reasoning given: A set and a hand edit with the same effect record the same events
- Outcome: Kept
- proposed: 5 - One definition

rating: n/a
reason:

### Route 2

- Route: Separate small reconcile diff reusing the shared scalar comparison
- Reasoning given: Reconcile's 'before' is a path map with a different remove order
- Outcome: Kept
- proposed: 4 - Two diff paths to maintain

rating: n/a
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: n/a
reason:

## T56

**Question:** Do reconcile events stand when the command then fails  
**Kind:** divergent

**What's at stake:** If you edit the config file by hand and your next command fails, the question is whether the history still records your edit. If it doesn't, the edit shows up later as a change with no history entry, or gets credited to the wrong command.

**What each route does** (run against every arm's final code):

**Example 1:** Edit `.troupe/troupe.yml` by hand to change `retry: 3` to `retry: 7`, then run `config set models.5 haiku` (the list has only 2 items) _(observed)_

Starting file:

~~~
# troupe config
retry: 3  # attempts
timeout: 30
models:
  - opus
  - sonnet
~~~

- Route 1: All four arms: exit 5, file left as hand-edited, nothing on stdout. The error wording differs by arm:

  ~~~
  `/theatre/.troupe/troupe.yml: models.5: not found: list index 5 is beyond the end of a list of 2 (use index 2 to append)`
  `troupe: models.5: index 5 is out of range (length 2)`
  `troupe: models.5: index 5 is out of range for models (length 2; only index 2 appends)`
  `troupe: error: models.5: index out of range (list has 2 items)`
  ~~~

- Route 2: Both arms: exit 5, file left as hand-edited, nothing on stdout. The error wording differs by arm:

  ~~~
  `troupe: path not found: models.5 (index 5 out of range)`
  `troupe: models.5: index 5 out of range`
  ~~~


**Example 2:** `config history` right after that failed set _(observed)_

- Route 1: All four arms: exit 0. The 4 original import entries, then a new one for the hand edit:

  ~~~
  {"seq": 5, "op": "set", "path": "retry", "old": 3, "new": 7, "actor": {"kind": "unknown", "id": null}, "via": "file", ...}
  There is no entry for the failed `models.5` set.
  ~~~

- Route 2: Both arms: exit 0. Same result: the 4 imports, then

  ~~~
  {"seq": 5, "op": "set", "path": "retry", "old": 3, "new": 7, "actor": {"kind": "unknown", "id": null}, "via": "file", ...}
  There is no entry for the failed set.
  ~~~


**Example 3:** `TROUPE_ACTOR=agent:coder config set timeout 60`, then `config history` _(observed)_

- Route 1: All four arms: exit 0; the file now reads:

  ~~~
  retry: 7  # attempts
  timeout: 60
  In the history, the hand edit stays as seq 5 (actor unknown, via file), followed by seq 6 `timeout` 30 -> 60, actor agent `coder`, via cli. The hand edit is not credited to the agent.
  ~~~

- Route 2: Both arms: exit 0; the file now reads:

  ~~~
  retry: 7  # attempts
  timeout: 60
  In the history, the hand edit stays as seq 5 (actor unknown, via file), followed by seq 6 `timeout` 30 -> 60, actor agent `coder`, via cli. The hand edit is not credited to the agent.
  ~~~


**In practice:** In this run the two routes behave the same in every way except the error wording. In all six arms the hand edit is in the history, recorded as a file change by an unknown actor, and the failed command leaves no entry of its own. The run can't tell whether the failing `set` saved the hand-edit entry or whether the following `config history` call recorded it when it read the file, so it neither confirms nor rules out the 'saved before the command body' claim for route 1.

**Trade-off:** Route 1 deliberately saves hand edits in their own write before the command runs, which is an extra save per command. Route 2 never addressed the case, yet produced the same visible history in this run.

### Route 1

- Route: Yes; saved in their own save before the command body
- Reasoning given: The hand edit really happened; matches import
- Outcome: Kept
- proposed: 5 - Truthful history

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 4 - Likely the same behaviour, but unstated

rating: n/a
reason:

## T57

**Question:** Order of remove events in a reconcile  
**Kind:** divergent

**What's at stake:** When a whole section is replaced (by editing the file or with `config set`), `config history` lists one remove event per key that disappeared. The order of those events is what someone reading the audit trail sees, and what any tool replaying the history depends on.

**What each route does** (run against every arm's final code):

**Example 1:** hand-edit `.troupe/troupe.yml` so that `m` becomes `m: 0`, then `config history m` _(observed)_

Starting file:

~~~
m:
  b: 3
  z: 9
  a: 2
  c: 4
n:
  b: 3
  z: 9
  a: 2
  c: 4
(z and a came from the original file, b and c were added later with `config set`, and the file was then reordered by hand)
~~~

- Route 1: exit 0; the history ends with: set m = 0, then remove m.z, m.a, m.b, m.c (seq 11–15)
- Route 2: two arms: set m = 0, then remove m.z, m.a, m.b, m.c (seq 11–15); one arm: remove m.z, m.a, m.b, m.c first, then set m = 0 last (seq 11–15)
- Route 3: exit 0; the history ends with: set m = 0, then remove m.z, m.a, m.b, m.c (seq 11–15)
- Route 4: exit 0; the history ends with: set m = 0, then remove m.z, m.a, m.b, m.c (seq 11–15)

**Example 2:** `config set n 0`, then `config history n` _(observed)_

Starting file:

~~~
m: 0
n:
  b: 3
  z: 9
  a: 2
  c: 4
~~~

- Route 1: exit 0; the file now reads `m: 0` / `n: 0`; the history ends with: set n = 0, then remove n.b, n.z, n.a, n.c (seq 16–20)
- Route 2: exit 0; the file now reads `m: 0` / `n: 0`. Two arms: set n = 0, then remove n.b, n.z, n.a, n.c; one arm: remove n.b, n.z, n.a, n.c first, then set n = 0 last
- Route 3: exit 0; the file now reads `m: 0` / `n: 0`; the history ends with: set n = 0, then remove n.b, n.z, n.a, n.c (seq 16–20)
- Route 4: exit 0; the file now reads `m: 0` / `n: 0`; the history ends with: set n = 0, then remove n.b, n.z, n.a, n.c (seq 16–20)

**In practice:** In these runs, every route logged the removes in the same order. A hand edit logs them in the order the keys were first created (z, a, b, c), not in the order they appear in the file (b, z, a, c). `config set` on the command line logs them in file order (b, z, a, c). The only visible difference is one of the three arms on route 2, which logs the replacing value after the removes instead of before. Files, `config get` output and exit codes were identical on every route.

**Trade-off:** Route 1 follows the order keys were created, which stays stable however the file is rearranged. Route 2 uses the order keys were first recorded, and its arms disagree on whether the new value comes before or after the removes. Route 3 sets the order for sets but leaves the order of removes unstated. Route 4 never addressed the question, though in this test it behaved like the others.

### Route 1

- Route: Order of the seq that created each leaf
- Reasoning given: Closest stable equivalent of the old document order
- Outcome: Kept
- proposed: 5 - Stable

rating: 4
reason: Set then (redundant) removes

### Route 2

- Route: Projection order (when leaves were first recorded)
- Reasoning given: The old document is gone; reuse diff order
- Outcome: Kept
- proposed: 5 - Stable

rating: 3.5
reason: RESLICE placeholder: A (set then removes) 4 x2; B (removes then set) 3

### Route 3

- Route: Sets in document order, then removes (order unstated)
- Reasoning given: Same order as set
- Outcome: Kept
- proposed: 4 - Underspecified

rating: 4
reason: Set then (redundant) removes

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 4
reason: Set then (redundant) removes

## T58

**Question:** Where the code decides which commands reconcile  
**Kind:** divergent

**What's at stake:** Whether every command sees the stored data brought up to date (reconciled) before it runs, and whether a command added later could quietly skip that step and show or act on stale data.

**In practice:** Route 1: before each command runs, the program calls a reconcile step on the data store. Only the history command is left out. For a user, every existing command except history works on up-to-date data. For a maintainer, the rule is a single exception written in one place. A new command gets reconciled automatically unless someone adds it to the exception. Nothing in the code says why history is skipped, though, and the only rule is "everything but history". Route 2: one shared function that opens the session decides for every command whether reconciling happens. That decision can be on by default, come from a list of commands, or be something each command must state explicitly. The recorded reason is that a new command cannot forget to reconcile. For a user the result is the same today. For a maintainer, the decision lives where the data is opened, so a command cannot get to the data without going through it. The exact behaviour depends on which form is used. With on-by-default, new commands reconcile unless they opt out. With a list, a new command left off the list is not reconciled. With a required statement, a command can't be written without choosing.

**Trade-off:** Route 1 costs little now, but the reconcile rule is a single hard-coded exception with no stated reason, so it relies on the command list staying as it is; route 2 costs some extra setup in the shared open function, and depending on its form, maintainers must keep a list current or state a choice for every command.

### Route 1

- Route: A store reconcile method called before every command except history
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Works; easier to miss

rating: n/a
reason:

### Route 2

- Route: One session/open function decides for every command (default-on flag, a command list, or a required keyword)
- Reasoning given: A new command cannot forget to reconcile
- Outcome: Kept
- proposed: 5 - Safe default

rating: n/a
reason:

## T59

**Question:** Empty or non-mapping root files  
**Kind:** divergent

**What's at stake:** If a user's config file holds just `~`, `---`, a bare word or a list instead of key/value pairs, this decides whether troupe refuses to read it at all or prints it and only refuses writes, and which exit code a script sees. Every arm treats an empty or comment-only file as an empty config that can be written into.

**What each route does** (run against every arm's final code):

**Example 1:** `config show --theatre tilde` _(observed)_

Starting file:

~~~
~
~~~

- Route 1: Two arms: exit 4, nothing printed, stderr says the file's top level must be a mapping (one: `tilde/.troupe/troupe.yml: the top-level node is a scalar; expected a mapping`; the other: `troupe: error: /theatre/tilde/.troupe/troupe.yml: the top level must be a mapping`). Three arms: exit 0, prints `null`.
- Route 2: exit 0, prints `null`

**Example 2:** `config show --theatre dashes` _(observed)_

Starting file:

~~~
---
~~~

- Route 1: Two arms: exit 4 with the same 'expected a mapping' / 'must be a mapping' error. Three arms: exit 0, prints `null`.
- Route 2: exit 0, prints `null`

**Example 3:** `config set --theatre tilde x 1` (the same happens with `---` and with a file reading `hello`) _(observed)_

Starting file:

~~~
~
~~~

- Route 1: File left unchanged in every arm. Two arms: exit 4 with the same 'must be a mapping' error. Three arms: exit 5, with three different messages: `troupe: x: is a scalar, not a mapping or list`, `troupe: path not found: x ( is not a mapping or list)` and `troupe: x: is not a mapping or list`.
- Route 2: exit 5, `troupe: x: (root) is a scalar`, file unchanged

**Example 4:** `config show --theatre scalar` _(observed)_

Starting file:

~~~
hello
~~~

- Route 1: Two arms: exit 4, 'expected a mapping' / 'must be a mapping'. Three arms: exit 0, prints `hello`.
- Route 2: exit 0, prints `hello`

**Example 5:** `config show --theatre list`, then `config set --theatre list x 1` _(observed)_

Starting file:

~~~
- a
~~~

- Route 1: Two arms: both commands exit 4 (`the top-level node is a list; expected a mapping` / `the top level must be a mapping`). Three arms: show exits 0 and prints `- a`; set exits 5 and leaves the file unchanged (`troupe: x: the root is a list`, `troupe: path not found: x (not a list index: x)` and `troupe: x: root is a list`).
- Route 2: show exits 0 and prints `- a`; set exits 5 with `troupe: x: (root) is a list; expected an index, got 'x'`, file unchanged

**Example 6:** `config show --theatre comment`, then `config set --theatre comment x 1` _(observed)_

Starting file:

~~~
# only a comment here
~~~

- Route 1: Show: four arms print `{}`, one arm prints `null` (exit 0 in all five). Set: exit 0 in all five arms; the file now reads:

  ~~~
  # only a comment here
  x: 1
  ~~~

- Route 2: show prints `{}`; set exits 0 and the file now reads:

  ~~~
  # only a comment here
  x: 1
  ~~~


**Example 7:** `config show --theatre empty`, then `config set --theatre empty x 1` _(observed)_

Starting file:

~~~
(empty file)
~~~

- Route 1: Show: four arms print `{}`, one arm prints `null`. Set: exit 0 in all five arms; the file now reads:

  ~~~
  x: 1
  ~~~

- Route 2: show prints `{}`; set exits 0 and the file now reads:

  ~~~
  x: 1
  ~~~


**In practice:** Route 1 promises exit 4 for any non-mapping root, but only two of its five arms do that. The other three behave like route 2: `show` prints the odd file as-is, and only `set` fails, with exit 5 and a different message in each arm. So on route 1, a script checking the exit code may see 4 or 5 for the same file, and may see 0 on `show`, depending on the arm. Route 2 is a single arm and was consistent throughout.

**Trade-off:** Route 1 (where it held, in two arms): a malformed root is caught up front with exit 4, but even `show` refuses, so you can't view the file through troupe. Its other three arms and route 2: `show` still prints the file, and the problem only surfaces on `set`, as exit 5 with a path-style message.

### Route 1

- Route: An empty or comment-only file is an empty mapping and can be written into; a non-mapping root (including ~ or ---) exits 4
- Reasoning given: Conservative and deterministic
- Outcome: Kept
- proposed: 5 - Sensible defaults

rating: 4
reason: RESLICE placeholder: A (exit 4, names the problem) 5 x2; B (show prints, set exit 5 not-found) 3 x3

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Every relevant arm decided this

rating: 3
reason: Show prints the odd root; set exits 5 with a not-found style message

## T60

**Question:** How get/show print scalars  
**Kind:** divergent

**What's at stake:** When you read a setting with `config get` or `config show`, the value printed is what scripts and people will copy. A huge integer, a float written as `1e3`, a hex number, `-.inf` or a YAML null each need to come out in a predictable form without crashing. In these tests both routes printed exactly the same thing for every case.

**What each route does** (run against every arm's final code):

**Example 1:** `config get big` (a stored integer several thousand digits long) _(observed)_

Starting file:

~~~
big: 1234567890…(the same 10 digits repeated, several thousand digits in all)
~~~

- Route 1: exit 0, nothing on stderr; prints the whole number on one line (the capture cut off the last 131 bytes); no digit-limit error
- Route 2: exit 0, nothing on stderr; prints the whole number on one line (the capture cut off the last 131 bytes); no digit-limit error

**Example 2:** `config show f` _(observed)_

Starting file:

~~~
f: 1e3
~~~

- Route 1: exit 0; prints `1000.0`
- Route 2: exit 0; prints `1000.0`

**Example 3:** `config get ninf` _(observed)_

Starting file:

~~~
ninf: -.inf
~~~

- Route 1: exit 0; prints `-inf`
- Route 2: exit 0; prints `-inf`

**Example 4:** `config get hex` _(observed)_

Starting file:

~~~
hex: 0x1F
~~~

- Route 1: exit 0; prints `31` (decimal, not `0x1F`)
- Route 2: exit 0; prints `31` (decimal, not `0x1F`)

**Example 5:** `config get n` _(observed)_

Starting file:

~~~
n: ~
~~~

- Route 1: exit 0; prints `null`
- Route 2: exit 0; prints `null`

**In practice:** All three implementations on each route gave identical results on every command. You can't tell the routes apart from what a user sees here. Both print YAML values in their resolved form rather than as written: `1e3` becomes `1000.0`, `0x1F` becomes `31`, `~` becomes `null` and `-.inf` becomes `-inf`. Every output ends with one newline.

**Trade-off:** Route 1 sets the printing rules on purpose: lower-case null/true/false, floats in full form, integers as plain digits. One of its implementations dropped special handling for very long integers as unneeded. Route 2 never addressed printing at all, yet its output matched route 1 on every case tested.

### Route 1

- Route: null/true/false lower-case, floats via repr, ints via str, one trailing newline
- Reasoning given: One arm removed large-int digit-limit handling as needless
- Outcome: Kept
- proposed: 5 - Simple and exact

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract-defined

rating: n/a
reason:

## T61

**Question:** A scalar with an end-of-line comment replaced by a block collection  
**Kind:** divergent

**What's at stake:** When a plain value that has a trailing comment (`name: alpha # project name`) is replaced with a nested map or list, the routes differ only on list entries. All arms keep the comment. They differ on whether the new item's first line moves onto the dash line or the dash is left alone with the comment and everything goes below it.

**What each route does** (run against every arm's final code):

**Example 1:** `config set name "{a: 1, b: x}"` _(observed)_

Starting file:

~~~
name: alpha    # project name
~~~

- Route 1: exit 0, no output (all four arms); the file now reads:

  ~~~
  name:          # project name
    a: 1
    b: x
  ~~~

- Route 2: exit 0, no output (both arms); the file now reads:

  ~~~
  name:          # project name
    a: 1
    b: x
  ~~~


**Example 2:** `config set limits "[x, y]"` _(observed)_

Starting file:

~~~
limits: 5  # max
~~~

- Route 1: exit 0, no output (all four arms); the file now reads:

  ~~~
  limits:    # max
    - x
    - y
  ~~~

- Route 2: exit 0, no output (both arms); the file now reads:

  ~~~
  limits:    # max
    - x
    - y
  ~~~


**Example 3:** `config set tags.0 "{k: v, m: w}"` _(observed)_

Starting file:

~~~
tags:
  - one   # first
  - two  # second
~~~

- Route 1: exit 0, no output. Two arms: the dash stays alone with the comment and the map goes below:

  ~~~
  tags:
    -       # first
      k: v
      m: w
    - two  # second
  Two arms: the first key moves onto the dash line and the comment follows it:
  tags:
    - k: v  # first
      m: w
    - two  # second
  ~~~

- Route 2: exit 0, no output (both arms); the dash stays alone with the comment:

  ~~~
  tags:
    -       # first
      k: v
      m: w
    - two  # second
  ~~~


**Example 4:** `config set tags.1 "[p, q]"` (right after the previous command) _(observed)_

Starting file:

~~~
tags:
  - two  # second
~~~

- Route 1: exit 0, no output. Two arms:

  ~~~
    -      # second
      - p
      - q
  Two arms (nested list starts on the dash line):
    - - p  # second
      - q
  ~~~

- Route 2: exit 0, no output (both arms):

  ~~~
    -      # second
      - p
      - q
  ~~~


**Example 5:** `config set agents.coder.temperature 0.3` _(observed)_

Starting file:

~~~
agents:
  coder: file:agents/coder.yaml  # c
~~~

- Route 1: exit 0, no output (all four arms); agents/coder.yaml is untouched, and troupe.yml now reads:

  ~~~
  agents:
    coder:  # c
      $ref: file:agents/coder.yaml
      temperature: 0.3
  ~~~

- Route 2: exit 0, no output (both arms); agents/coder.yaml is untouched, and troupe.yml now reads:

  ~~~
  agents:
    coder:  # c
      $ref: file:agents/coder.yaml
      temperature: 0.3
  ~~~


**In practice:** Every command worked on both routes, and no comment was lost. Map keys gave the same result everywhere: the old value is blanked, the comment stays at its column, and the new collection goes below. The only difference is on list entries. Route 2 and half of route 1's arms leave a bare `-` holding the comment. The other half of route 1's arms put the first line of the new item on the dash line (`- k: v # first`, `- - p # second`), which is what route 1 says it does. When the include reference became a map, all arms moved the comment so it sits right after `coder:` instead of keeping its old column.

**Trade-off:** Route 1 promises compact list items, but only half its arms produced them; the rest left the same bare-dash layout as route 2. Route 2 never considered the case, yet behaved consistently and keeps the comment's column, at the cost of a lone `-` line.

### Route 1

- Route: Value removed; comment stays at its column on the key (or dash) line; the collection goes below; list items become compact
- Reasoning given: Matches the rule for keys
- Outcome: Kept; at step 5 the include conversion follows the contract example instead
- proposed: 5 - Contract rule

rating: 3.5
reason: RESLICE placeholder: A (comment stays on the item) 4 x2; B (comment moves to the first key) 3 x2

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract-defined

rating: 4
reason: Comment stays on the item, collection below

## T62

**Question:** How a history line's seq is derived  
**Kind:** divergent

**What's at stake:** The `seq` number is how a user or agent refers to a specific config change and reads the order changes happened in. If the numbers have gaps, repeat, or come out in a different order, it's harder to audit who changed what and to point at one change. Nothing about the config file itself is at stake.

**What each route does** (run against every arm's final code):

**Example 1:** `config set retry 3` (retry is already 3), as human:owner _(observed)_

Starting file:

~~~
retry: 3  # attempts
agents:
  coder: opus
  reviewer: haiku
tags: [a, b]
~~~

- Route 1: exit 0, no output; the file is unchanged and no history line is written for it
- Route 2: all three arms: exit 0, no output; the file is unchanged and no history line is written for it
- Route 3: both arms: exit 0, no output; the file is unchanged and no history line is written for it

**Example 2:** `config set agents.coder '{model: sonnet, temperature: 0.2}'` as agent:planner, then `config set retry 4` as human:owner, then `config history` _(observed)_

Starting file:

~~~
retry: 3  # attempts
agents:
  coder: opus
  reviewer: haiku
tags: [a, b]
~~~

- Route 1: exit 0; 9 lines numbered 1–9 with no gaps. seq 1–5 import the starting file (retry, agents.coder, agents.reviewer, tags.0, tags.1; actor unknown). Then 6 set agents.coder.model=sonnet, 7 set agents.coder.temperature=0.2, 8 remove agents.coder (old "opus"), all by agent planner. Then 9 set retry 3→4 by human owner
- Route 2: all three arms: exit 0; 9 lines numbered 1–9 with no gaps, and seq 1–5 import the starting file. Two arms: 6 set model, 7 set temperature, 8 remove agents.coder (old "opus"), 9 retry 3→4. One arm puts the removal first: 6 remove agents.coder (old "opus"), 7 set model, 8 set temperature, 9 retry 3→4
- Route 3: both arms: exit 0; 9 lines numbered 1–9 with no gaps, and seq 1–5 import the starting file. Then 6 set model, 7 set temperature, 8 remove agents.coder (old "opus"), 9 retry 3→4

**Example 3:** `config history agents` (same sequence as above) _(observed)_

- Route 1: exit 0; 5 lines that keep their global numbers, so there are gaps: seq 2, 3, 6, 7, 8 (6=set model, 7=set temperature, 8=remove agents.coder)
- Route 2: all three arms: exit 0; 5 lines numbered seq 2, 3, 6, 7, 8. Two arms: 6=set model, 7=set temperature, 8=remove agents.coder. One arm: 6=remove agents.coder, 7=set model, 8=set temperature
- Route 3: both arms: exit 0; 5 lines numbered seq 2, 3, 6, 7, 8 (6=set model, 7=set temperature, 8=remove agents.coder)

**In practice:** In this run, every route produced the same numbers: 1–9, gapless, starting at 1. The starting file appears as seq 1–5, and a set that doesn't change the value uses up no number. Filtered history keeps the global numbers, so it shows gaps. The only visible difference was within route 2: in one arm, replacing `agents.coder: opus` with a map logs the removal of the old value before the two new keys. Everywhere else the removal is logged after them. The file contents were identical in every arm.

**Trade-off:** Route 1 keeps a full copy of the history in memory, so it grows with every change. Route 2 stores nothing extra but ties `seq` to the internal event count, so it only stays gapless while each saved event is exactly one history line. No reasoning was recorded for route 3.

### Route 1

- Route: Keep the history log in the aggregate's state and number seq by position in that log
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Correct, but the whole log is rebuilt in memory

rating: n/a
reason:

### Route 2

- Route: seq = originator_version - 1; the created/started event is not a history line
- Reasoning given: Gapless and starting at 1 by construction, with no counter to maintain
- Outcome: Kept
- proposed: 5 - Simple and stable

rating: n/a
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Any gapless scheme on one aggregate works

rating: n/a
reason:

## T63

**Question:** Setting a path below a null or scalar parent  
**Kind:** divergent

**What's at stake:** Whether `config set` on a path under a key that already holds a plain value (`coder: opus`) or is empty/null (`reviewer:`, `planner: null`) gets refused or overwritten. A refusal leaves the file untouched; an overwrite would replace an existing setting. Both routes behaved the same in every run: they refuse those paths with exit 5, and only the error wording differs.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder.model sonnet` _(observed)_

Starting file:

~~~
# team config
agents:
  coder: opus  # main model
  reviewer:
  planner: null  # tbd
retry: 3
~~~

- Route 1: exit 5, file unchanged. Each of the four arms words the error differently: "…agents.coder.model: not found: a scalar value has no children (at segment 'model')"; "agents.coder is a scalar, not a mapping or list"; "agents.coder is a scalar"; "its parent is a scalar, not a mapping or list"
- Route 2: exit 5, file unchanged. The two arms word the error differently: "path not found: agents.coder.model (agents.coder is not a mapping or list)"; "agents.coder is not a mapping or list"

**Example 2:** `config set agents.reviewer.model haiku` (`reviewer:` is a bare key with no value) _(observed)_

- Route 1: exit 5, file unchanged. One arm says "not found: a null value has no children (at segment 'model')"; the other three call the empty key "a scalar"
- Route 2: exit 5, file unchanged; "agents.reviewer is not a mapping or list" (both arms, with the same small wording difference as above)

**Example 3:** `config set agents.planner.model opus` (`planner: null # tbd`) _(observed)_

- Route 1: exit 5, file unchanged. One arm says "a null value has no children"; the other three say "agents.planner is a scalar" or "its parent is a scalar"
- Route 2: exit 5, file unchanged; "agents.planner is not a mapping or list"

**Example 4:** `config set agents.tester.model haiku` (tester does not exist yet) _(observed)_

- Route 1: exit 0 (all four arms); the file now reads:

  ~~~
  # team config
  agents:
    coder: opus  # main model
    reviewer:
    planner: null  # tbd
    tester:
      model: haiku
  retry: 3
  ~~~

- Route 2: exit 0 (both arms); the file now reads:

  ~~~
  # team config
  agents:
    coder: opus  # main model
    reviewer:
    planner: null  # tbd
    tester:
      model: haiku
  retry: 3
  ~~~


**Example 5:** `config show` (after the four commands above) _(observed)_

- Route 1: exit 0; prints:

  ~~~
  agents:
    coder: opus
    reviewer: null
    planner: null
    tester:
      model: haiku
  retry: 3
  ~~~

- Route 2: exit 0; same output as route 1

**In practice:** The two routes act the same: a plain value is never turned into a section, an empty `key:` or `null` key is also refused, and a missing key is created along with its parents while comments are kept. The only difference is the error text. Most of route 1's arms call the empty or null key "a scalar", and one arm calls it "a null value". Route 2's messages say "not a mapping or list" and never name the kind of value.

**Trade-off:** Route 1: an empty `reviewer:` can't be filled in with a nested setting until it is edited by hand, and most of its messages call that empty key "a scalar". Route 2: the same refusal, with a vaguer message that never explains why the path was rejected.

### Route 1

- Route: Exit 5; a scalar or null parent is not a mapping (a bare `key:` counts as null)
- Reasoning given: Conservative; never turn a scalar into a mapping
- Outcome: Kept
- proposed: 5 - No silent data loss

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Turning a scalar into a mapping silently loses data

rating: n/a
reason:

## T64

**Question:** Which events a set records and in what order  
**Kind:** divergent

**What's at stake:** Every `config set` writes events to `config history`, and that log is how a user audits who changed what. The routes record the same events but list them in different orders: route 3 puts removals before new values, and on routes 1 and 2 the order changes from arm to arm.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agent "{temp: 0.5, model: sonnet, beta: 3}"`, then `config history` _(observed)_

Starting file:

~~~
agent:
  zeta: 1
  model: opus
  alpha: 2
tools:
  - grep
  - sed
  - awk
~~~

- Route 1: Arms differ. Two arms: exit 0; the file now reads:

  ~~~
  agent:
    model: sonnet
    temp: 0.5
    beta: 3
  The history adds set agent.model (opus→sonnet), set agent.temp, set agent.beta, remove agent.zeta, remove agent.alpha.
  One arm: exit 0; the file now reads:
  agent:
    temp: 0.5
    model: sonnet
    beta: 3
  The history adds set agent.temp, set agent.model, set agent.beta, remove agent.zeta, remove agent.alpha.
  ~~~

- Route 2: Arms differ. One arm: exit 0; the file now reads:

  ~~~
  agent:
    temp: 0.5
    model: sonnet
    beta: 3
  The history adds set temp, set model, set beta, remove zeta, remove alpha.
  One arm: exit 0; the file now reads:
  agent:
    model: sonnet
    temp: 0.5
    beta: 3
  The history adds set model, set temp, set beta, remove zeta, remove alpha.
  ~~~

- Route 3: exit 0; the file now reads:

  ~~~
  agent:
    model: sonnet
    temp: 0.5
    beta: 3
  The history adds remove agent.zeta, remove agent.alpha, then set agent.model, set agent.temp, set agent.beta (removals first).
  ~~~


**Example 2:** `config set tools "[sed]"`, then `config history` _(observed)_

Starting file:

~~~
tools:
  - grep
  - sed
  - awk
~~~

- Route 1: All arms: exit 0; the file now reads:

  ~~~
  tools:
    - sed
  The history adds set tools.0 (grep→sed), remove tools.1 (sed), remove tools.2 (awk).
  ~~~

- Route 2: All arms: exit 0; same file. The history adds set tools.0 (grep→sed), remove tools.1 (sed), remove tools.2 (awk).
- Route 3: exit 0; same file. The history adds remove tools.1 (sed), remove tools.2 (awk), then set tools.0 (grep→sed).

**Example 3:** repeat `config set agent "{temp: 0.5, model: sonnet, beta: 3}"`, then `config history` _(observed)_

- Route 1: All arms: exit 0; the file is unchanged and no new events are added (the history still ends at seq 14).
- Route 2: All arms: exit 0; the file is unchanged and no new events are added (still ends at seq 14).
- Route 3: exit 0; the file is unchanged and no new events are added (still ends at seq 14).

**In practice:** All routes record the same events: one per changed, added or removed leaf, and nothing for a set that changes nothing. Only the order differs. Routes 1 and 2 list new values first, then removals. Route 3 lists removals first. On routes 1 and 2 the order of the new values follows the file, and the arms wrote the keys in different orders (one keeps the old `model` position, one uses the typed order), so the history order differs between arms. List elements are tracked by position on every route: shrinking `[grep, sed, awk]` to `[sed]` is logged as "sed removed from tools.1", even though sed stays in the list.

**Trade-off:** Route 1 promises new values first, then removals, but its arms still differ on key order. Route 2 promises no order, and its arms differed. Route 3 lists removals first, so a reader sees what was dropped before what was set.

### Route 1

- Route: Leaf diff of before/after; set events in new document order, then remove events in old document order
- Reasoning given: Deterministic; the same order is reused by reconcile
- Outcome: Kept
- proposed: 5 - Deterministic and readable

rating: n/a
reason:

### Route 2

- Route: Leaf diff with one event per changed/new/removed leaf; order not pinned
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Correct events; ordering left implicit

rating: n/a
reason:

### Route 3

- Route: Leaf diff; remove events in old document order before set events
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Deterministic; the order is arbitrary but fine

rating: n/a
reason:

## T65

**Question:** Wait for a changing file to settle before reconciling  
**Kind:** divergent

**What's at stake:** When an editor saves by emptying the file and then rewriting it, a running `config watch` may record the empty moment as real changes. If it does, history shows every key deleted and then added back, and each quick intermediate save gets its own entry.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` running; the file is saved empty, then 0.3 s later rewritten as before with `retry: 2`; then `config history` _(observed)_

Starting file:

~~~
# team config
model: opus
retry: 1
~~~

- Route 1: Both arms recorded the empty save anyway. History shows `remove model` (opus -> null) and `remove retry` (1 -> null), then `set model` null -> opus a moment later. Both runs got the same result.
- Route 2: All four arms recorded the empty save. History shows `remove model` and `remove retry`, then `set model` null -> opus and `set retry` null -> 2.

**Example 2:** Continuing: 0.3 s after `retry: 2` is written, it is changed to `retry: 3`. Then 3 s later it becomes `retry: 9`, then `config history` _(observed)_

- Route 1: One arm never recorded the short-lived 2. History goes `set retry` null -> 3, then 3 -> 9, for 7 entries. One arm recorded every step: null -> 2, 2 -> 3, 3 -> 9, for 8 entries.
- Route 2: All four arms recorded every step: `set retry` null -> 2, 2 -> 3, 3 -> 9, for 8 entries.

**Example 3:** Ctrl-C (SIGINT) to stop `config watch` _(observed)_

- Route 1: Both arms: exit 0, printed nothing beyond the watching line. One printed `watching /theatre`, the other `watching .`.
- Route 2: Two arms: exit 0 and quiet. One arm: exit 137. One arm: exit 0, but stderr shows a Python `KeyboardInterrupt` traceback ("Exception ignored in: <function Application.__del__ ...>").

**In practice:** In this run, neither route stopped the empty mid-save file from being recorded as two deletions. Every arm on both routes did that, even though avoiding it was route 1's stated reason. The only visible difference from waiting for the file to settle was on one route 1 arm: a value that existed for only 0.3 s (`retry: 2`) never reached history. The final value (`retry: 9`) was recorded correctly by every arm.

**Trade-off:** Route 1 waits for repeated identical reads, so changes land slightly later and very brief intermediate values may be skipped. Route 2 records every save it sees, including half-written states.

### Route 1

- Route: Reconcile only after the bytes read the same on consecutive checks
- Reasoning given: Avoid recording a file an editor emptied mid-save
- Outcome: Kept
- proposed: 5 - Cheap protection

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 4 - Editors mostly save atomically; half-written files are rare

rating: n/a
reason:

## T66

**Question:** Writes into a file included at more than one place  
**Kind:** divergent

**What's at stake:** When `agents/base.yaml` is included by both `coder` and `reviewer`, a `config set coder.…` command either edits the shared file, which silently changes `reviewer` too, or refuses. That decides whether the user can edit shared settings at all, and whether one agent's settings can change without anyone noticing.

**What each route does** (run against every arm's final code):

**Example 1:** `config set coder.model sonnet` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
coder: file:agents/base.yaml  # coder
reviewer:
  $ref: file:agents/base.yaml
  temperature: 0.5

.troupe/agents/base.yaml:
model: opus
temperature: 0.2
~~~

- Route 1: exit 0, no output; base.yaml now reads:

  ~~~
  model: sonnet
  temperature: 0.2
  ~~~

- Route 2: exit 0, no output; base.yaml now reads:

  ~~~
  model: sonnet
  temperature: 0.2
  ~~~

- Route 3: exit 3, no file changed. Both arms refuse, with different messages. One arm: `troupe: coder.model: cannot write this change byte-surgically; no file changed`. The other arm: `troupe: coder.model: write-back would disturb reviewer.model`
- Route 4: Arms differ. One arm: exit 3, `troupe: coder.model: the edited files would not read back as intended; not writing`, no file changed. The other arm: exit 0; base.yaml now reads:

  ~~~
  model: sonnet
  temperature: 0.2
  ~~~


**Example 2:** then `config set coder.temperature 0.3` (reviewer has its own temperature override) _(observed)_

- Route 1: exit 0; the shared base.yaml temperature line now reads `temperature: 0.3`
- Route 2: exit 0; the shared base.yaml temperature line now reads `temperature: 0.3`
- Route 3: exit 0 in both arms (accepted this time); base.yaml now reads:

  ~~~
  model: opus
  temperature: 0.3
  ~~~

- Route 4: exit 0 in both arms; base.yaml's temperature line now reads `temperature: 0.3` (model is still `opus` in the arm that refused before, `sonnet` in the other)

**Example 3:** then `config set --in-include coder.max_tokens 100` _(observed)_

- Route 1: exit 0; base.yaml now reads:

  ~~~
  model: sonnet
  temperature: 0.3
  max_tokens: 100
  ~~~

- Route 2: exit 0; base.yaml now reads:

  ~~~
  model: sonnet
  temperature: 0.3
  max_tokens: 100
  ~~~

- Route 3: exit 3, no file changed. Both arms refuse, with the same two kinds of message as above (`cannot write this change byte-surgically` / `write-back would disturb reviewer.max_tokens`)
- Route 4: Arms differ. One arm: exit 3, `the edited files would not read back as intended; not writing`. The other arm: exit 0, and `max_tokens: 100` is added to base.yaml

**Example 4:** then `config show` _(observed)_

- Route 1: exit 0:

  ~~~
  coder:
    model: sonnet
    temperature: 0.3
    max_tokens: 100
  reviewer:
    model: sonnet
    temperature: 0.5
    max_tokens: 100
  ~~~

- Route 2: exit 0:

  ~~~
  coder:
    model: sonnet
    temperature: 0.3
    max_tokens: 100
  reviewer:
    model: sonnet
    temperature: 0.5
    max_tokens: 100
  ~~~

- Route 3: exit 0 in both arms:

  ~~~
  coder:
    model: opus
    temperature: 0.3
  reviewer:
    model: opus
    temperature: 0.5
  ~~~

- Route 4: One arm: same as route 3 (model still opus, no max_tokens). The other arm: same as routes 1 and 2 (reviewer also gets model sonnet and max_tokens 100)

**In practice:** On routes 1 and 2, setting a value on `coder` also changes it for `reviewer` whenever reviewer doesn't override that key, and no warning is printed. Route 3 refuses only when the edit would leak into reviewer. The temperature change went through because reviewer overrides temperature, so one session can get a mix of accepted and refused edits to the same file. Route 2 is described as refusing conflicting values with exit 3, but nothing in these runs triggered that case, so it behaved exactly like route 1 here. Route 4's two arms disagree: one refuses like route 3, the other writes like route 1.

**Trade-off:** Routes 1 and 2: shared files stay editable, but an edit for one agent can quietly change the others. Route 3: no hidden changes, but a value that lives only in the shared file can't be changed through `coder`, and `--in-include` is blocked too. Route 4: behaviour depends on which implementation you get.

### Route 1

- Route: Allowed; only override writes are matched by reference so writes into a twice-included file keep working
- Reasoning given: Step 1 and --in-include need such writes
- Outcome: Kept
- proposed: 5 - Matches the contract

rating: 4
reason: Writes the shared file; reviewer changes silently (a warning would be better)

### Route 2

- Route: Refused at step 1, reworked at step 5 to follow the placement rules (conflicting values exit 3)
- Reasoning given: The owner said no contract rule refuses such a write
- Outcome: Reworked at step 5
- proposed: 5 - Owner-confirmed reading

rating: 4
reason: Same as route 1 in these runs

### Route 3

- Route: Refused with exit 3
- Reasoning given: Cautious choice on a contract gap; the change alters every includer
- Outcome: Kept; one arm also refuses --in-include in that case at step 5
- proposed: 3 - No contract rule refuses such writes (as one owner ruled)

rating: 2.5
reason: RESLICE placeholder: R1 (refuses, names the conflict) 3; R2 (refuses, vague) 2

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Such writes change every includer

rating: 3
reason: RESLICE placeholder: W (writes silently) 4; R2 (refuses, vague) 2

## T67

**Question:** show on a mapping or list in step 1  
**Kind:** divergent

**What's at stake:** Whether asking for a whole section (a mapping or a list) with `config get` fails with a pointer to `config show`, and whether `config show` prints that section readably. In practice both routes behave the same and differ only in the wording of the error.

**What each route does** (run against every arm's final code):

**Example 1:** `config get agents` _(observed)_

Starting file:

~~~
# team config
agents:
  coder:
    model: opus  # main model
    temperature: 0.2
  tools: [grep, "read file"]
retry: 3
~~~

- Route 1: Exit 5, prints nothing, file unchanged. Two arms, same meaning, different wording. One arm: `troupe: agents: is a mapping, not a scalar; use `troupe config show agents` to print it`. The other: `troupe: agents: is a mapping, not a scalar (use `troupe config show agents`)`
- Route 2: Exit 5, prints nothing, file unchanged. Four arms, same meaning, different wording. One arm names the file instead of the program: `/theatre/.troupe/troupe.yml: agents: is a mapping, not a value; print it with `troupe config show agents``. The others: `troupe: agents: is a mapping, not a scalar (use `troupe config show agents` to print it)`; `troupe: agents is a mapping, not a scalar; use 'troupe config show agents'`; `troupe: error: agents: is a mapping, not a scalar; use `troupe config show agents` to print it`

**Example 2:** `config get agents.tools` _(observed)_

- Route 1: Exit 5, prints nothing. Both arms say `agents.tools` is a list, not a scalar, and point to `troupe config show agents.tools`
- Route 2: Exit 5, prints nothing. All four arms say it is a list and point to `troupe config show agents.tools`. One arm starts the message with the file path and says "not a value" instead of "not a scalar"

**Example 3:** `config show agents` _(observed)_

- Route 1: Exit 0 (both arms); prints:

  ~~~
  coder:
    model: opus
    temperature: 0.2
  tools:
    - grep
    - read file
  ~~~

- Route 2: Exit 0 (all four arms); prints the same:

  ~~~
  coder:
    model: opus
    temperature: 0.2
  tools:
    - grep
    - read file
  ~~~


**Example 4:** `config show agents.tools` _(observed)_

- Route 1: Exit 0; prints:

  ~~~
  - grep
  - read file
  ~~~

- Route 2: Exit 0; prints:

  ~~~
  - grep
  - read file
  ~~~


**Example 5:** `config show agents.coder.temperature` _(observed)_

- Route 1: Exit 0; prints `0.2`
- Route 2: Exit 0; prints `0.2`

**In practice:** Both routes behave the same for the user: `get` on a section fails with exit 5 and tells you to use `show`, and `show` prints any section or single value as plain YAML. `show` drops the file's comments (`# main model`) and the quotes around "read file". Nothing was ever written to the file. The only differences are the error message wording, which varies between arms even within the same route. One arm on route 2 starts the message with the config file's path instead of `troupe:`.

**Trade-off:** Route 1 made exit 5 an explicit decision, so its result is a recorded choice. Route 2 got the same behaviour without anyone deciding it, so nothing guarantees it will stay that way, and its error wording varies the most.

### Route 1

- Route: Exit 5
- Reasoning given: None recorded
- Outcome: Replaced at step 3 by get/show
- proposed: 5 - Contract behaviour

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - The contract fixes it

rating: n/a
reason:

## T68

**Question:** Floats in YAML output  
**Kind:** divergent

**What's at stake:** This decides how decimal numbers, infinity and NaN are written to the YAML config and shown back. If they are written badly, some YAML readers load a value as text instead of a number, or a value like `-.inf` cannot be set at all.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agent.temperature .inf` _(observed)_

Starting file:

~~~
agent:
  temperature: 0.5  # sampling
  weights: [0.1, 0.2]
  name: coder
~~~

- Route 1: All three arms: exit 0; the file now reads:

  ~~~
    temperature: .inf # sampling
  (comment kept, other lines unchanged)
  ~~~

- Route 2: All three arms: exit 0; the file now reads:

  ~~~
    temperature: .inf # sampling
  (comment kept, other lines unchanged)
  ~~~


**Example 2:** `config set agent.top_p 1e20` _(observed)_

- Route 1: Two arms: exit 0; the file gets the value as typed:

  ~~~
    top_p: 1e20
  One arm: exit 0; the file gets:
    top_p: 1e+20
  ~~~

- Route 2: Two arms: exit 0; the file gets:

  ~~~
    top_p: 1e+20
  One arm: exit 0; the file gets the value as typed:
    top_p: 1e20
  ~~~


**Example 3:** `config set agent.weights.2 -.inf` _(observed)_

- Route 1: One arm: exit 0; the file now reads:

  ~~~
    weights: [0.1, 0.2, -.inf]
  Two arms: exit 2, the file is unchanged, and the value is taken for an option: "the following arguments are required: VALUE" (one arm) / "usage error: the following arguments are required: value" (other arm)
  ~~~

- Route 2: All three arms: exit 2, the file is unchanged, and the value is taken for an option: "the following arguments are required: value". One arm also prints the full usage text.

**Example 4:** `config set agent.extra "{a: .nan, b: 1e-7, c: 2.0, d: -0.0}"` _(observed)_

- Route 1: Two arms: exit 0; the file now reads:

  ~~~
    extra:
      a: .nan
      b: 1e-7
      c: 2.0
      d: -0.0
  One arm: exit 0; the file now reads:
    extra:
      a: .nan
      b: 1e-07
      c: 2.0
      d: -0.0
  ~~~

- Route 2: Two arms: exit 0; the file now reads:

  ~~~
    extra:
      a: .nan
      b: 1e-07
      c: 2.0
      d: -0.0
  One arm: exit 0; the file now reads:
    extra:
      a: .nan
      b: 1e-7
      c: 2.0
      d: -0.0
  ~~~


**Example 5:** `config show agent` (after the commands above) _(observed)_

- Route 1: Two arms: exit 0; prints

  ~~~
  top_p: 1e+20
  ...
    b: 1e-07
  One arm: exit 0; prints with an added .0:
  top_p: 1.0e+20
  ...
    b: 1.0e-07
  (In all three, `.inf`, `.nan`, `2.0` and `-0.0` are shown as is. Only the arm that accepted `-.inf` lists `- -.inf` under weights.)
  ~~~

- Route 2: All three arms: exit 0; prints

  ~~~
  top_p: 1e+20
  ...
    b: 1e-07
  (`.inf`, `.nan`, `2.0` and `-0.0` are shown as is)
  ~~~


**In practice:** Both routes write infinity and NaN as `.inf`/`.nan` and keep `2.0` and `-0.0`. Where they differ is exponent numbers. Most arms write `1e+20`/`1e-07`, or keep what you typed (`1e20`). Strict YAML 1.1 readers do not treat an exponent number without a decimal point as a number, so they read those back as text. Only one route 1 arm shows `1.0e+20`/`1.0e-07`, which every reader loads as a number, and that arm still writes `1e+20` to the file itself. Whether `-.inf` can be set at all depends on the command-line parsing, not on this choice: one route 1 arm accepted it, and the other five arms rejected it as a missing value.

**Trade-off:** Route 1 handles special values on purpose, but its arms produce three different outputs. Route 2 gives nearly the same results by default, with no deliberate handling of numbers that some readers load back as text.

### Route 1

- Route: repr when finite; .inf/-.inf/.nan otherwise
- Reasoning given: Reads back as floats; one arm also adds .0
- Outcome: Kept
- proposed: 5 - Correct

rating: 4.5
reason: RESLICE placeholder: P (keeps typed spelling) 5 x2; N (rewrites to 1e+20) 4

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: 4.5
reason: RESLICE placeholder: P 5; N (rewrites to 1e+20) 4 x2

## T69

**Question:** Quoting in show output  
**Kind:** divergent

**What's at stake:** `config show` output is what people copy into other files or feed to other tools. Some strings read as non-strings in older YAML readers if they are printed bare: `yes`, `off`, `y` and `On` become true/false, and `1:30` becomes the number 90. Pasting the output elsewhere could then quietly change a setting's meaning.

**What each route does** (run against every arm's final code):

**Example 1:** `config show` _(observed)_

Starting file:

~~~
flags:
  enabled: 'yes'
  legacy: "off"
  short: 'y'
  mixed: 'On'
  time: '1:30'
  big: '1_000'
  real: 'true'
  number: '42'
  plain: hello
'yes': 1
'on': 'no'
'true': x
~~~

- Route 1: exit 0; prints:

  ~~~
  flags:
    enabled: 'yes'
    legacy: 'off'
    short: 'y'
    mixed: 'On'
    time: '1:30'
    big: '1_000'
    real: 'true'
    number: '42'
    plain: hello
  'yes': 1
  'on': 'no'
  'true': x
  ~~~

- Route 2: exit 0; prints:

  ~~~
  flags:
    enabled: yes
    legacy: off
    short: y
    mixed: On
    time: 1:30
    big: 1_000
    real: 'true'
    number: '42'
    plain: hello
  yes: 1
  on: no
  'true': x
  ~~~


**Example 2:** `config show flags --sources` _(observed)_

- Route 1: exit 0; prints:

  ~~~
  enabled: 'yes' # from .troupe/troupe.yml
  legacy: 'off' # from .troupe/troupe.yml
  short: 'y' # from .troupe/troupe.yml
  mixed: 'On' # from .troupe/troupe.yml
  time: '1:30' # from .troupe/troupe.yml
  big: '1_000' # from .troupe/troupe.yml
  real: 'true' # from .troupe/troupe.yml
  number: '42' # from .troupe/troupe.yml
  plain: hello # from .troupe/troupe.yml
  ~~~

- Route 2: exit 0; prints:

  ~~~
  enabled: yes # from .troupe/troupe.yml
  legacy: off # from .troupe/troupe.yml
  short: y # from .troupe/troupe.yml
  mixed: On # from .troupe/troupe.yml
  time: 1:30 # from .troupe/troupe.yml
  big: 1_000 # from .troupe/troupe.yml
  real: 'true' # from .troupe/troupe.yml
  number: '42' # from .troupe/troupe.yml
  plain: hello # from .troupe/troupe.yml
  ~~~


**Example 3:** `config set flags.extra on`, then `config show flags` _(observed)_

- Route 1: set: exit 0; the file gains this line under flags (no quotes):

  ~~~
    extra: on
  show then prints the earlier values (all quoted, as above) and:
  extra: 'on'
  ~~~

- Route 2: set: exit 0; the file gains this line under flags (no quotes):

  ~~~
    extra: on
  show then prints the earlier values (bare, as above) and:
  extra: on
  ~~~


**In practice:** Both routes leave the file exactly as it was. They differ only in what `show` prints. Route 1 adds quotes to anything an older YAML reader would take as a boolean or number, including keys such as 'yes' and 'on'. Route 2 quotes only the values that today's YAML reads as non-strings ('true', '42') and prints yes/off/On/1:30 bare. Both routes write `extra: on` to the file without quotes when you run `config set`.

**Trade-off:** Route 1 prints more quotes, but its output keeps the same meaning in any YAML reader. Route 2's output is cleaner and follows the same quoting rule as `set`, but older readers will take some of its bare values as booleans or numbers.

### Route 1

- Route: Plain only if both YAML 1.2 and 1.1 readers read it back unchanged
- Reasoning given: Review found 1.1 misreads
- Outcome: Reworked at step 3
- proposed: 5 - Safe for any reader

rating: 5
reason: Quotes anything a YAML 1.1 or 1.2 reader would misread; output reads back the same

### Route 2

- Route: set's plain/single/double chain; keys plain only when they read back as strings
- Reasoning given: One quoting rule
- Outcome: Kept
- proposed: 5 - Shared

rating: 2
reason: Prints yes/off/On/1:30 bare; YAML 1.1 readers get booleans and numbers

## T70

**Question:** How a source file is named  
**Kind:** divergent

**What's at stake:** When a config file is reached through a symlink (here `agents/` points to `real/`), this decides which name `config show --sources` gives for it. It also decides whether troupe treats `agents/coder.yaml` and `real/coder.yaml` as one file, which affects `config set` and the history log.

**What each route does** (run against every arm's final code):

**Example 1:** `config show --sources --theatre=proj` _(observed)_

Starting file:

~~~
proj/.troupe/agents -> real
proj/.troupe/troupe.yml:
# team config
coder: file:agents/coder.yaml  # via symlinked dir
reviewer: file:real/coder.yaml  # same file, real name
prompt: file:agents/prompt.txt
retry: 3
~~~

- Route 1: The 5 arms on this route gave three different outputs, all exit 0.

  ~~~
  Two arms used the name each key was written with:
  coder:
    model: opus # from .troupe/agents/coder.yaml
    temperature: 0.2 # from .troupe/agents/coder.yaml
  reviewer:
    model: opus # from .troupe/real/coder.yaml
    temperature: 0.2 # from .troupe/real/coder.yaml
  prompt: | # from .troupe/agents/prompt.txt
    Be terse.
  retry: 3 # from .troupe/troupe.yml
  One arm used the symlinked name for everything, including reviewer:
  reviewer:
    model: opus # from .troupe/agents/coder.yaml
    temperature: 0.2 # from .troupe/agents/coder.yaml
  Two arms used the real name everywhere, the same output as route 2.
  ~~~

- Route 2: exit 0; every file is shown by its real path:

  ~~~
  coder:
    model: opus # from .troupe/real/coder.yaml
    temperature: 0.2 # from .troupe/real/coder.yaml
  reviewer:
    model: opus # from .troupe/real/coder.yaml
    temperature: 0.2 # from .troupe/real/coder.yaml
  prompt: | # from .troupe/real/prompt.txt
    Be terse.
  retry: 3 # from .troupe/troupe.yml
  ~~~


**Example 2:** `config set coder.model sonnet --theatre linked` (`linked` is a symlink to `proj`) _(observed)_

Starting file:

~~~
proj/.troupe/real/coder.yaml:
model: opus  # default model
temperature: 0.2
~~~

- Route 1: Three arms: exit 0; the file now reads:

  ~~~
  model: sonnet # default model
  temperature: 0.2
  (the two spaces before the comment became one). Two arms refused with exit 3 and changed nothing. One printed `troupe: coder.model: the edited files would not read back as intended; not writing`; the other printed `troupe: coder.model: cannot write this change byte-surgically; no file changed`.
  ~~~

- Route 2: exit 0; the file now reads:

  ~~~
  model: sonnet # default model
  temperature: 0.2
  ~~~


**Example 3:** `config history --theatre linked`, run after the set above and a hand edit of real/coder.yaml to `temperature: 0.5` _(observed)_

- Route 1: Two arms: the `reviewer.model` opus->sonnet change is logged under the same change as `coder.model`, by `human:owner` via `cli`. One arm: `coder.model` is logged by `human:owner` via `cli`, but `reviewer.model` gets a separate entry by an unknown actor via `file`, as if someone had edited it by hand. Two arms (the ones that refused the set): both model changes appear only when the hand edit is picked up, by an unknown actor via `file`.
- Route 2: `coder.model` and `reviewer.model` are logged as one change by `human:owner` via `cli`. The hand edit is logged by an unknown actor via `file`.

**In practice:** Route 2 always names a symlinked file by its real path, so the same file never appears under two names. In route 1's two arms that shows only the real path, the source column looked exactly like route 2's. On route 1, how a symlink was named, and whether `set` through a symlinked theatre worked, depended on the arm.

**Trade-off:** Route 1 shows the path you typed, but the arms disagreed on the output and two refused the write; route 2 shows a path you may never have typed, but behaved consistently and treated both names as one file.

### Route 1

- Route: Lexical path relative to the theatre with / separators; ../ outside; symlinks not resolved
- Reasoning given: Users recognise what they wrote; matches watch
- Outcome: Kept
- proposed: 5 - Familiar

rating: 3.5
reason: RESLICE placeholder: Q1 naming R5 x2, L4 x2, S2; Q2 set via symlink G5 x2, H2, F2 x2; average per arm

### Route 2

- Route: Real paths with symlinks resolved, relative to the resolved theatre (reworked from lexical during planning)
- Reasoning given: Names the file set would write
- Outcome: Reworked at step 3
- proposed: 4 - Accurate; may surprise

rating: 5
reason: Real path everywhere (one file, one name); set via symlinked theatre works and logs one change

## T71

**Question:** Which commands accept --sources  
**Kind:** divergent

**What's at stake:** Whether `--sources` (the annotation showing which file each value came from) works on `show` only or also on the other config commands, and whether passing it to a command that doesn't support it could silently change your config.

**What each route does** (run against every arm's final code):

**Example 1:** `config show agents --sources` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
name: demo
agents:
  coder: file:agents/coder.yaml

.troupe/agents/coder.yaml:
model: opus
temperature: 0.2
~~~

- Route 1: all five arms: exit 0, prints:

  ~~~
  coder:
    model: opus # from .troupe/agents/coder.yaml
    temperature: 0.2 # from .troupe/agents/coder.yaml
  ~~~

- Route 2: exit 0, prints:

  ~~~
  coder:
    model: opus # from .troupe/agents/coder.yaml
    temperature: 0.2 # from .troupe/agents/coder.yaml
  ~~~


**Example 2:** `config get agents.coder.model --sources` _(observed)_

- Route 1: all five arms: exit 2, nothing on stdout, the error names the flag. The wording differs by arm: `troupe: unrecognized arguments: --sources`; `troupe: troupe: unrecognized arguments: --sources` ("troupe:" printed twice); `troupe: unrecognized arguments: --sources (see 'troupe --help')`; `troupe: usage error: unrecognized arguments: --sources`; or a usage line `usage: troupe [-h] COMMAND ...` followed by `troupe: error: unrecognized arguments: --sources`
- Route 2: exit 2, nothing on stdout; stderr: `usage: troupe [-h] {config} ...` then `troupe: error: unrecognized arguments: --sources`

**Example 3:** `config history agents.coder.model --sources` _(observed)_

- Route 1: all five arms: exit 2 with the same message each arm gave for `get`
- Route 2: exit 2 with the same message it gave for `get`

**Example 4:** `config set agents.coder.model sonnet --sources`, then `config get agents.coder.model` _(observed)_

Starting file:

~~~
.troupe/agents/coder.yaml:
model: opus
temperature: 0.2
~~~

- Route 1: all five arms: the set exits 2 with the unrecognized-arguments error and writes nothing; the follow-up get prints `opus`
- Route 2: the set exits 2 with the unrecognized-arguments error and writes nothing; the follow-up get prints `opus`

**In practice:** The two routes behave the same in practice. `--sources` works only on `show`. On `get`, `history` and `set` it fails with exit 2 and changes nothing. Only the wording of the error differs, both between arms on route 1 and between the routes. One arm on route 1 prints "troupe: troupe:" twice.

**Trade-off:** Route 1 decided on purpose that only `show` takes `--sources`, citing the contract. Route 2 never considered the question but ended up with the same behavior.

### Route 1

- Route: show only; get --sources exits 2
- Reasoning given: Contract
- Outcome: Kept
- proposed: 5 - Contract

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract

rating: n/a
reason:

## T72

**Question:** Should the event store read eventsourcing settings from the process environment  
**Kind:** divergent

**What's at stake:** Every arm on both routes ignored the eventsourcing environment variables. Change history went to the tool's own file under `.troupe/` whatever the user's shell exported. The variables never redirected the history, lost it or broke it, so the routes behaved the same in practice.

**What each route does** (run against every arm's final code):

**Example 1:** `PERSISTENCE_MODULE=eventsourcing.popo config set retry 4`, then `config history` with the variable set, then `config history` with it unset _(observed)_

Starting file:

~~~
model: opus
retry: 3
~~~

- Route 1: exit 0, nothing printed; troupe.yml now reads `retry: 4`. Both history runs print the same 3 entries: the import of model and retry, then `set retry 3 -> 4`. The history was saved to disk, not kept in memory. One arm writes it to `.troupe/events.sqlite` (12288 bytes); the other writes it to `.troupe/history.sqlite` (12288 bytes).
- Route 2: exit 0, nothing printed; troupe.yml now reads `retry: 4`. Both history runs print the same 3 entries: the import of model and retry, then `set retry 3 -> 4`. The history was saved to disk. The four arms write it to `.troupe/history.sqlite`, `.troupe/troupe-state.sqlite`, `.troupe/events.sqlite` (plus an empty `events.lock`) and `.troupe/events.sqlite3` (plus an empty `events.sqlite3.lock`), each 12288 bytes.

**Example 2:** `IS_SNAPSHOTTING_ENABLED=y PERSISTENCE_MODULE=eventsourcing.sqlite SQLITE_DBNAME=elsewhere.db config set retry 5`, then `config history` with and without those variables _(observed)_

- Route 1: exit 0; troupe.yml now reads `retry: 5`. No `elsewhere.db` was created. Both history runs show 4 entries, ending with `set retry 4 -> 5`, all in the same `.troupe/` file as before. One arm's file grew to 16384 bytes; the other's stayed at 12288.
- Route 2: exit 0; troupe.yml now reads `retry: 5`. No `elsewhere.db` was created. Both history runs show 4 entries, ending with `set retry 4 -> 5`, all in the same `.troupe/` file as before. Three arms' files grew to 16384 bytes; one arm's stayed at 12288.

**Example 3:** `PERSISTENCE_MODULE=nonexistent config set retry 6`, then `config history` with and without the variable _(observed)_

- Route 1: exit 0, no error or warning; troupe.yml now reads `retry: 6`. Both history runs show 5 entries, ending with `set retry 5 -> 6`. File list unchanged.
- Route 2: exit 0, no error or warning; troupe.yml now reads `retry: 6`. Both history runs show 5 entries, ending with `set retry 5 -> 6`. File list unchanged.

**In practice:** On both routes, stray eventsourcing variables in a user's shell (such as `PERSISTENCE_MODULE`, `SQLITE_DBNAME` or `IS_SNAPSHOTTING_ENABLED`) changed nothing visible. Even a bogus value made no difference. The only visible differences were between arms: the name of the history file under `.troupe/`, whether a 0-byte lock file sat next to it, and whether that file grew from 12288 to 16384 bytes after the run with those variables set.

**Trade-off:** Route 1 explicitly configures the store so the environment can't steer it. Route 2 never addressed the question but ended up ignoring the variables just the same in these runs, so it offers no stated guarantee that this will hold.

### Route 1

- Route: Configure the store through explicit constructor settings and ignore the process environment
- Reasoning given: Keeps the process environment untouched; eventsourcing otherwise still reads user variables
- Outcome: Kept
- proposed: 5 - Deterministic storage location and behaviour

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - eventsourcing honours environment variables, so a user's shell could move or change the store

rating: n/a
reason:

## T73

**Question:** How store failures and corrupt history are reported  
**Kind:** divergent

**What's at stake:** If the history store is damaged, a user could get a clear one-line error, a Python crash dump on every command (including plain reads like `config get`), or no sign of the damage at all, with a fresh history quietly started next to the broken file. This test planted junk files named `.troupe/events.db`, `events.sqlite`, `eventstore.db` and `troupe.db`, each containing "this is not a sqlite database, it is corrupt history".

**What each route does** (run against every arm's final code):

**Example 1:** `config history` _(observed)_

- Route 1: All three arms: exit 0. None of them read the planted junk file. Each printed a fresh two-row history it had just made by importing troupe.yml: `model` → "opus" and `retry` → 3, both with op "import" and actor kind "unknown". No warning about the corrupt file.
- Route 2: Two arms: exit 1, nothing on stdout, and a full Python traceback on stderr ending in `sqlite3.DatabaseError: file is not a database`. One arm: same as route 1 (exit 0, a fresh two-row import history, no warning).

**Example 2:** `config get model` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: opus  # main model
retry: 3
~~~

- Route 1: All three arms: exit 0, prints `opus`.
- Route 2: Two arms: exit 1 with the same full traceback (`sqlite3.DatabaseError: file is not a database`) and no value printed. A plain read fails because the store is opened first. One arm: exit 0, prints `opus`.

**Example 3:** `TROUPE_ACTOR=agent:coder config set --include agent file:sub` (where `.troupe/sub` is a directory) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: opus  # main model
retry: 3
~~~

- Route 1: All three arms: exit 3, troupe.yml unchanged, and each arm words the error differently: `/theatre/.troupe/troupe.yml: agent: written value cannot be read back: ... include target /theatre/.troupe/sub does not exist or is not a regular file`; `troupe: agent: include target is a directory: /theatre/.troupe/sub (included from /theatre/.troupe/troupe.yml, at agent); no file changed`; `troupe: error: agent: the change to /theatre/.troupe/troupe.yml would not load back (/theatre/.troupe/sub: is a directory, not a file); no file was changed`.
- Route 2: Two arms: exit 1 with the corrupt-store traceback. The include problem is never reached, and troupe.yml is unchanged. One arm: exit 3, `troupe: write refused: agent: cannot write this change faithfully (/theatre/.troupe/troupe.yml: include target /theatre/.troupe/sub not found)`, troupe.yml unchanged.

**Example 4:** `config history model` (after the commands above) _(observed)_

- Route 1: All three arms: exit 0. Shows only the single import row for `model` ("opus"). The refused set left no entry.
- Route 2: Two arms: exit 1 with the same traceback. One arm: exit 0, shows the single import row for `model`.

**In practice:** Route 1's promised 'exit 4 naming the store' never showed up, because no route 1 arm opened any of the planted corrupt files. They kept history somewhere else and started over without a warning. So this run doesn't show what route 1 does with a truly corrupt store, only that none of its arms crashed here. On route 2, the two arms that did open a corrupt file made every command unusable, and each one dumped about 40 lines of Python internals instead of a message. The design notes also say one route 1 arm accepted a traceback for a damaged history row missing a field; this test did not exercise that.

**Trade-off:** Route 1: no crashes in this test, but its clean exit-4 error went untested, and a broken file under one of these names was ignored with no warning. Route 2: no error handling for the store, so in two of three arms a corrupt file meant a traceback and exit 1 on every command, reads included.

### Route 1

- Route: Exit 4 naming the store (sqlite, persistence and OS errors; corrupt or unknown lineage values)
- Reasoning given: No tracebacks; a damaged row gives exit 4. One arm accepted a traceback for a step-4 row missing a field
- Outcome: Kept
- proposed: 5 - Clear errors

rating: n/a
reason: Untested: no arm opened the planted corrupt files

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Tracebacks instead of exit codes

rating: 1
reason: RESLICE placeholder: T (traceback, exit 1 on every command incl. reads) 1 x2; one arm untested (n/a)

## T74

**Question:** Should the history store be closed explicitly at the end of each command  
**Kind:** divergent

**What's at stake:** Whether running troupe leaves only the config and its history database in `.troupe/`, or also leaves stray `-wal`/`-shm` side files and lock files there. Stray files matter most when a watch process is stopped by a signal. Recording and reading history worked the same on both routes.

**What each route does** (run against every arm's final code):

**Example 1:** `TROUPE_ACTOR=human:owner config set model sonnet`, then list `.troupe/` _(observed)_

Starting file:

~~~
model: opus
~~~

- Route 1: both arms: exit 0, no output. `.troupe/` holds only `history.sqlite` (12288 bytes) and `troupe.yml` (14 bytes).
- Route 2: all four arms: exit 0, no output. Two arms leave only a database and `troupe.yml`; one names the database `events.sqlite`, the other `troupe-state.sqlite`. One arm also leaves an empty `events.lock` next to `events.sqlite`. One arm leaves `events.sqlite3` plus an empty `events.sqlite3.lock`.

**Example 2:** `config history`, then `config get model` _(observed)_

- Route 1: both arms: exit 0. Prints two JSON lines: an import of `opus` (actor unknown), then a set from `opus` to `sonnet` by human `owner` via cli. `get` prints `sonnet`. No new files appear.
- Route 2: all four arms: the same two history lines and `sonnet`. No new files appear.

**Example 3:** `config watch`, edit `troupe.yml` by hand to `model: haiku`, wait 3s, send Ctrl-C (SIGINT) _(observed)_

- Route 1: both arms: print `watching /theatre`, then exit 0 on Ctrl-C.
- Route 2: three arms: print `watching /theatre` or `watching .`, then exit 0 on Ctrl-C. One arm: prints `watching .`, does not exit on Ctrl-C and ends with exit 137 (killed).

**Example 4:** `--theatre . config watch`, then SIGTERM _(observed)_

- Route 1: both arms: refused at once with exit 2 and an `invalid choice: '.' (choose from config)` message. Nothing ran.
- Route 2: three arms: refused the same way (exit 2, invalid choice '.'). One arm: accepts it, prints `watching .`, and ends with exit 137 on SIGTERM.

**Example 5:** list `.troupe/` after all of the above _(observed)_

- Route 1: both arms: only `history.sqlite` (12288 bytes) and `troupe.yml` (13 bytes). No `-wal` or `-shm` files.
- Route 2: two arms (the two that ended with exit 137): leftover `-shm` (32768 bytes) and `-wal` files next to the database; one `-wal` is 0 bytes, the other 8272 bytes. Two arms: no `-wal`/`-shm`, but their empty lock file (`events.lock` or `events.sqlite3.lock`) remains.

**In practice:** Normal commands behave the same on both routes. The difference shows when a watch is stopped by a signal. On route 1 the folder ended with just the database and the config every time. On route 2, two of four arms ended with exit 137 instead of a clean exit and left `-wal`/`-shm` files beside the database; one of those was still holding 8 KB of history data in its `-wal` file. Route 2 arms also differ from each other in the database file name and in whether they leave a lock file.

**Trade-off:** Route 1 needs explicit closing code in every command, and it reliably left a clean folder in all runs. Route 2 skips that work, and its results varied: stray side files and lock files depending on the arm, plus two arms that only stopped with exit 137.

### Route 1

- Route: One store instance per command, closed explicitly at the end so no -wal/-shm files remain
- Reasoning given: A deterministic, testable end state; dropping the last reference closes the pool unpredictably
- Outcome: Kept
- proposed: 5 - Clean end state at no cost

rating: 5
reason: Clean end state: database and config only

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 4 - Leftover -wal/-shm files are a minor cost

rating: 4.5
reason: RESLICE placeholder: B (empty lock file; counted at T44) 5 x2; C (-wal/-shm left after a killed watch) 4 x2

## T75

**Question:** How a string containing a TAB is quoted  
**Kind:** divergent

**What's at stake:** When you store a value containing a TAB, it decides how that value is quoted in .troupe/troupe.yml, which is the file you later read and edit by hand. Single quotes keep a literal TAB character in the file, which you can't see. Double quotes would show it as a visible `\t`.

**What each route does** (run against every arm's final code):

**Example 1:** `config set name '"a\tb"'` _(observed)_

Starting file:

~~~
# troupe settings
name: bob  # agent name
prompt: hello
limits:
  retry: 3
~~~

- Route 1: exit 0, no output; the file now reads (a real TAB between a and b, comment kept):

  ~~~
  name: 'a	b' # agent name
  ~~~

- Route 2: exit 0, no output; the file now reads (a real TAB between a and b, comment kept):

  ~~~
  name: 'a	b' # agent name
  ~~~


**Example 2:** `config set prompt '"\tindented"'` _(observed)_

- Route 1: exit 0, no output; the file now reads (starts with a real TAB):

  ~~~
  prompt: '	indented'
  ~~~

- Route 2: exit 0, no output; the file now reads (starts with a real TAB):

  ~~~
  prompt: '	indented'
  ~~~


**Example 3:** `config set extra.sep '"x\t"'` (a key that is not in the file yet) _(observed)_

- Route 1: exit 0, no output; a new block is added at the end (ends with a real TAB):

  ~~~
  extra:
    sep: 'x	'
  ~~~

- Route 2: exit 0, no output; a new block is added at the end (ends with a real TAB):

  ~~~
  extra:
    sep: 'x	'
  ~~~


**Example 4:** `config get name` (after the commands above) _(observed)_

- Route 1: exit 0; prints a, a real TAB, then b
- Route 2: exit 0; prints a, a real TAB, then b

**In practice:** Both routes gave the same results on every command. Every value with a TAB was written in single quotes with the raw TAB inside, and it read back correctly. Neither route wrote the double-quoted `"a\tb"` form. On both routes, the two spaces before the `# agent name` comment became one.

**Trade-off:** Route 1 deliberately chose single quotes and changed the tests that expected double quotes. Route 2 never considered the question but produced the same file. Either way, the TAB in the file can't be seen.

### Route 1

- Route: Single quotes (tests changed from the double-quoted expectation)
- Reasoning given: The contract puts single before double quotes; a single-quoted TAB is valid
- Outcome: Kept
- proposed: 5 - Follows the contract order

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - The contract's fallback order decides it

rating: n/a
reason:

## T76

**Question:** What VALUE types may be written into a text include  
**Kind:** divergent

**What's at stake:** Text includes are settings whose value lives in a separate text file. This decides what happens when someone runs `config set` on one with a number, a true/false value or a structure such as `{a: 1}` instead of plain text. Either that file's text is quietly replaced with whatever was typed, or the command is refused and nothing changes.

**What each route does** (run against every arm's final code):

**Example 1:** `config set prompt 42` (`prompt` is a text include using LF line endings) _(observed)_

Starting file:

~~~
troupe.yml:
prompt: file:prompt.txt  # LF text include
notes: file:notes.txt  # CRLF text include
model: opus

prompt.txt:
You are a helpful coder.
Be brief.
~~~

- Route 1: exit 0, no output; prompt.txt now holds only the following, with no line break at the end:

  ~~~
  42
  ~~~

- Route 2: exit 3; prompt.txt is unchanged. Both arms refuse this, with differently worded messages: "troupe: write refused: /theatre/.troupe/prompt.txt: a text include can only be set to a string" / "troupe: prompt: text include .troupe/prompt.txt can only be set to a string"
- Route 3: exit 3; prompt.txt is unchanged. All three arms refuse this, with differently worded messages, e.g. "troupe: prompt: is the text of .troupe/prompt.txt; VALUE must be a string"

**Example 2:** `config set prompt '{a: 1, b: [x, y]}'` then `config get prompt` _(observed)_

Starting file:

~~~
prompt.txt:
You are a helpful coder.
Be brief.
~~~

- Route 1: set: exit 0; prompt.txt now reads (no line break at the end):

  ~~~
  {a: 1, b: [x, y]}
  get: prints `{a: 1, b: [x, y]}`. The structure was stored as plain text and the original prompt is gone.
  ~~~

- Route 2: set: exit 3 in both arms ("…can only be set to a string"); the file is unchanged. get prints the original two lines "You are a helpful coder." and "Be brief."
- Route 3: set: exit 3 in all three arms ("…must be a string"); the file is unchanged. get prints the original two lines "You are a helpful coder." and "Be brief."

**Example 3:** `config set notes '"new one\nnew two\n"'` (`notes` is a text include using CRLF line endings) _(observed)_

Starting file:

~~~
notes.txt (CRLF):
line one
line two
~~~

- Route 1: exit 0; notes.txt now reads, with the CRLF endings kept:

  ~~~
  new one
  new two
  ~~~

- Route 2: exit 0; notes.txt now reads, with the CRLF endings kept:

  ~~~
  new one
  new two
  ~~~

- Route 3: exit 0; notes.txt now reads, with the CRLF endings kept:

  ~~~
  new one
  new two
  ~~~


**Example 4:** `config set notes true` (CRLF text include) _(observed)_

- Route 1: exit 3; nothing changed. Message: "troupe: notes: text include /theatre/.troupe/notes.txt uses CRLF line endings, so VALUE must be a string; no file changed"
- Route 2: exit 3 in both arms; nothing changed. The message says a text include can only be set to a string.
- Route 3: exit 3 in all three arms; nothing changed. The message says the value must be a string.

**In practice:** On route 1, whether a non-text value is accepted depends on the file's line endings, which users can't see. The same `config set prompt 42` succeeds on an LF file and fails on a CRLF file. When it succeeds, the old text is replaced with the typed characters and no warning is shown. On routes 2 and 3, every non-text value is refused and the file is left alone, whatever its line endings. Routes 2 and 3 behaved the same in every command; their arms differ only in the wording of the error message.

**Trade-off:** Route 1 accepts anything on LF files but can silently replace a prompt with a stray number or structure, and its rule depends on line endings. Routes 2 and 3 apply one rule everywhere (text only) but make users quote anything that looks like a number, true/false or a structure.

### Route 1

- Route: Any VALUE on an LF target (non-strings written as typed); refuse only a non-string for a CRLF target. Reworked from an early draft that refused mappings and lists
- Reasoning given: The product owner ruled that the contract gives no such refusal
- Outcome: Reworked at step 1, then kept
- proposed: 4 - Follows the owner's reading of the contract

rating: 3
reason: Accepts non-strings on LF files but refuses on CRLF: a hidden rule; silently replaces a prompt with a stray value

### Route 2

- Route: Only strings (otherwise exit 3); CRLF endings of the target are preserved
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 3 - Refuses values that, by the owner's reading, the contract allows

rating: 4
reason: One clear rule: text only, clear refusal; forces quoting

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Non-string values into text files need a rule

rating: 4
reason: Same as route 2

## T77

**Question:** How the read-back check compares text-include content in CRLF files  
**Kind:** divergent

**What's at stake:** A system prompt kept in a separate file with Windows (CRLF) line endings is rewritten when you set it from the command line. What matters is whether a value with mixed line endings is saved with consistent CRLF endings or rejected outright, leaving the old prompt in place.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder.prompt "line one\nline two\n"` _(observed)_

Starting file:

~~~
`.troupe/troupe.yml` has `prompt: file:prompt.txt  # system prompt`, and `.troupe/prompt.txt` holds "You are a coder.\r\nBe brief.\r\n" (CRLF line endings)
~~~

- Route 1: exit 0, no output; prompt.txt now reads (CRLF line endings):

  ~~~
  line one
  line two
  ~~~

- Route 2: exit 0, no output; prompt.txt now reads (CRLF line endings):

  ~~~
  line one
  line two
  ~~~

- Route 3: exit 0, no output; prompt.txt now reads (CRLF line endings):

  ~~~
  line one
  line two
  ~~~

- Route 4: all three arms: exit 0, no output; prompt.txt now reads (CRLF line endings):

  ~~~
  line one
  line two
  ~~~


**Example 2:** `config set agents.coder.prompt "alpha\nbeta"` (no final newline) _(observed)_

- Route 1: exit 0; prompt.txt is exactly "alpha\r\nbeta"
- Route 2: exit 0; prompt.txt is exactly "alpha\r\nbeta"
- Route 3: exit 0; prompt.txt is exactly "alpha\r\nbeta"
- Route 4: all three arms: exit 0; prompt.txt is exactly "alpha\r\nbeta"

**Example 3:** `config set agents.coder.prompt "mixed\r\nends\nhere\r\n"` (mixed line endings) _(observed)_

Starting file:

~~~
prompt.txt is "alpha\r\nbeta"
~~~

- Route 1: exit 0, no output; prompt.txt is now "mixed\r\nends\r\nhere\r\n" (the bare \n became CRLF)
- Route 2: exit 0, no output; prompt.txt is now "mixed\r\nends\r\nhere\r\n" (the bare \n became CRLF)
- Route 3: exit 3; stderr `troupe: agents.coder.prompt: value cannot be written back faithfully`; prompt.txt is unchanged ("alpha\r\nbeta")
- Route 4: all three arms: exit 0, no output; prompt.txt is now "mixed\r\nends\r\nhere\r\n"

**Example 4:** `config get agents.coder.prompt` (after the three sets) _(observed)_

- Route 1: prints "mixed\r\nends\r\nhere\r\n"
- Route 2: prints "mixed\r\nends\r\nhere\r\n"
- Route 3: prints "alpha\r\nbeta" plus a newline (the old value)
- Route 4: all three arms: print "mixed\r\nends\r\nhere\r\n"

**Example 5:** `config history agents.coder.prompt` _(observed)_

- Route 1: shows the import plus three sets (seq 3, 4, 5); the last set records new "mixed\r\nends\r\nhere\r\n"
- Route 2: shows the import plus three sets (seq 3, 4, 5); the last set records new "mixed\r\nends\r\nhere\r\n"
- Route 3: shows the import plus two sets (seq 3, 4); the rejected mixed-ending set is not recorded
- Route 4: all three arms: show the import plus three sets (seq 3, 4, 5), as in routes 1 and 2

**In practice:** On every route, setting text that uses plain \n line endings works and is saved with CRLF endings, matching the file. Routes 1, 2 and 4 behaved identically in every run: a value with mixed endings is accepted and saved with all-CRLF endings, and the history records the converted value. Only route 3 behaved differently: it refuses mixed endings with exit 3, and the file, the stored value and the history all stay as they were.

**Trade-off:** Routes 1, 2 and 4 accept any line endings and quietly convert them all to CRLF. Route 3 never changes your text without telling you, but it rejects values that mix line endings, so you have to clean those up yourself first.

### Route 1

- Route: Compare against a CRLF-converted expectation
- Reasoning given: Verification failed because the expected value was not CRLF-converted
- Outcome: Kept
- proposed: 5 - Exact check

rating: 4
reason: Accepts mixed endings, normalises to the file's CRLF silently

### Route 2

- Route: Compare against the raw content written
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 5 - Exact check

rating: 4
reason: Same as route 1

### Route 3

- Route: Normalise line endings before comparing
- Reasoning given: The check tripped on CRLF text includes
- Outcome: Kept
- proposed: 3 - Hides a wrong line ending, which is exactly what it should catch

rating: 3
reason: Refuses mixed endings with a vague message that names neither the problem nor the fix

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Internal detail of the verifier

rating: 4
reason: Same as route 1

## T78

**Question:** Where --theatre is accepted and its default  
**Kind:** divergent

**What's at stake:** This decides where `--theatre` can go on the command line. Put it in a spot a route doesn't accept and the command stops with exit 2 and a usage error. It never reads the wrong theatre. Every route uses the current directory when `--theatre` is left out.

**What each route does** (run against every arm's final code):

**Example 1:** `config get name` (no `--theatre`, run from the directory that holds `.troupe/` and `sub/`) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
name: root-theatre
retry: 3

sub/.troupe/troupe.yml:
name: sub-theatre
retry: 7
~~~

- Route 1: exit 0, prints `root-theatre`
- Route 2: all three arms: exit 0, print `root-theatre`
- Route 3: both arms: exit 0, print `root-theatre`

**Example 2:** `config get name --theatre=sub` (also `config get --theatre=sub name`) _(observed)_

- Route 1: exit 0, prints `sub-theatre`
- Route 2: all three arms: exit 0, print `sub-theatre`
- Route 3: both arms: exit 0, print `sub-theatre`

**Example 3:** `config --theatre=sub get name` _(observed)_

- Route 1: exit 0, prints `sub-theatre`
- Route 2: all three arms: exit 2, `unrecognized arguments: --theatre=sub`
- Route 3: both arms: exit 0, print `sub-theatre`

**Example 4:** `config --theatre . get name` _(observed)_

- Route 1: exit 0, prints `root-theatre`
- Route 2: all three arms: exit 2, the error reads the `.` as the subcommand: `invalid choice: '.' (choose from get, show, set, history, watch)` (the order of the list varies)
- Route 3: both arms: exit 0, print `root-theatre`

**Example 5:** `--theatre=sub config get name` _(observed)_

- Route 1: exit 2, `troupe: error: unrecognized arguments: --theatre=sub`
- Route 2: all three arms: exit 2, `unrecognized arguments: --theatre=sub`
- Route 3: one arm: exit 0, prints `sub-theatre`; the other arm: exit 2, `unrecognized arguments: --theatre=sub (see 'troupe --help')`

**Example 6:** `--theatre . config get name` _(observed)_

- Route 1: exit 2, the error reads the `.` as the command: `invalid choice: '.' (choose from config)`
- Route 2: all three arms: exit 2, same kind of `invalid choice: '.' (choose from config)` error
- Route 3: one arm: exit 0, prints `root-theatre`; the other arm: exit 2, `invalid choice: '.' (choose from config) (see 'troupe --help')`

**In practice:** `--theatre` works after the subcommand (`config get --theatre X …`) on every route. Route 1 also accepts it between `config` and the subcommand. Route 2 accepts it only after the subcommand. Route 3's two arms differ: both accept it in both of those places, and one arm also accepts it before `config`. When `--theatre` is in a place it isn't accepted, the error doesn't name the flag. Instead it says its value (`.`) is an invalid command or subcommand, which can confuse people.

**Trade-off:** Route 1 lets you put `--theatre` in two places, but `troupe --theatre …` still fails. Route 2 has one fixed place, and every other placement fails with exit 2. Route 3 behaves differently depending on the arm: one accepts the flag anywhere, the other behaves like route 1.

### Route 1

- Route: Both at the config level and the subcommand level, defaulting to `.`
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 4 - Harmless extra surface not in the contract

rating: 4
reason: Accepted at config and subcommand level, not before config

### Route 2

- Route: Only after the subcommand, defaulting to the current directory. One arm added it before the subcommand, then removed it
- Reasoning given: Matches the contract form; requirements must not be invented
- Outcome: Kept (one arm reworked at step 1)
- proposed: 5 - Contract form

rating: 3
reason: Only after the subcommand; other placements fail with a confusing error

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract-defined

rating: 4.5
reason: RESLICE placeholder: anywhere 5; two places 4

## T79

**Question:** What counts as equal for no-op and change detection  
**Kind:** divergent

**What's at stake:** This decides whether re-typing a value that looks the same, such as `1` over `1.0` or `1` over `true`, counts as a change. If it counts, the file is rewritten and a history entry is logged. If it doesn't, the call does nothing. Re-setting NaN to NaN should leave both the file and the history untouched.

**What each route does** (run against every arm's final code):

**Example 1:** `config set a 1.0` _(observed)_

Starting file:

~~~
a: 1  # int
b: 1.0  # float
c: true  # bool
d: .nan  # nan
~~~

- Route 1: exit 0, no output, counted as a change in all five arms; the line now reads:

  ~~~
  a: 1.0 # int
  The history logs `set a` with old 1 and new 1.0.
  ~~~

- Route 2: exit 0, no output, counted as a change; the line now reads:

  ~~~
  a: 1.0 # int
  The history logs `set a` with old 1 and new 1.0.
  ~~~


**Example 2:** `config set c 1` (c was `true`) _(observed)_

- Route 1: exit 0, counted as a change in all five arms; the line now reads:

  ~~~
  c: 1     # bool
  The history logs old true and new 1.
  ~~~

- Route 2: exit 0, counted as a change; the line now reads:

  ~~~
  c: 1     # bool
  The history logs old true and new 1.
  ~~~


**Example 3:** `config set b 1` (b was `1.0`) _(observed)_

- Route 1: exit 0, counted as a change in all five arms; the line now reads:

  ~~~
  b: 1    # float
  The history logs old 1.0 and new 1.
  ~~~

- Route 2: exit 0, counted as a change; the line now reads:

  ~~~
  b: 1    # float
  The history logs old 1.0 and new 1.
  ~~~


**Example 4:** `config set d .nan` (d was `.nan`) _(observed)_

- Route 1: exit 0; no-op in all five arms: the file is unchanged and nothing is added to the history
- Route 2: exit 0; no-op: the file is unchanged and nothing is added to the history

**Example 5:** `config history` (the import entry for d) _(observed)_

- Route 1: Four arms: `"new": NaN` (a number). One arm: `"new": ".nan"` (a quoted string).
- Route 2: `"new": ".nan"` (a quoted string)

**In practice:** Both routes behaved the same in this run. 1 over 1.0, 1.0 over 1, and 1 over true each rewrote the file and logged a change. Re-setting NaN did nothing. The one difference is how the history stores the imported NaN. Four of the five arms on route 1 record it as the number NaN. The fifth arm on route 1, and route 2, record it as the text ".nan". When stored as text, a later real NaN could compare as different from it. In every arm, the rewritten line `a: 1.0 # int` lost one space before its comment.

**Trade-off:** Route 1 sets one written rule for what counts as equal, used by both set and reconcile, though one arm still logs NaN as text. Route 2 has no stated rule; it gave the same results here, but nothing says it has to.

### Route 1

- Route: Type-strict: 1, 1.0, true and '1' differ; NaN equals NaN; a type change counts as a change
- Reasoning given: Same definition used by set and reconcile
- Outcome: Kept
- proposed: 5 - Precise

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Most arms decided it

rating: n/a
reason:

## T80

**Question:** Writing U+2028/U+2029/U+0085/U+FEFF  
**Kind:** divergent

**What's at stake:** This is about what lands in troupe.yml when a stored value contains an invisible character (zero-width no-break space U+FEFF, line separator U+2028, paragraph separator U+2029 or next-line U+0085). Some routes put the raw invisible character in the file and others write a visible escape. Raw characters can't be seen in an editor, and some YAML readers treat them as line breaks, so they may read back differently.

**What each route does** (run against every arm's final code):

**Example 1:** `config set a "x\uFEFFy"` _(observed)_

Starting file:

~~~
a: plain  # p
b: 'single'  # s
c: "double"  # d
~~~

- Route 1: exit 0; line a now reads (the raw invisible U+FEFF is between x and y; the value is unquoted):

  ~~~
  a: x﻿y    # p
  ~~~

- Route 2: All three arms: exit 0; line a now reads (raw U+FEFF, now in double quotes):

  ~~~
  a: "x﻿y"  # p
  ~~~

- Route 3: one arm: exit 0; line a now reads (raw U+FEFF in double quotes):

  ~~~
  a: "x﻿y"  # p
  one arm: exit 0; line a now reads (a visible escape):
  a: "x\uFEFFy" # p
  ~~~


**Example 2:** `config set b "p\u2028q"` (U+2028 is the line separator) _(observed)_

Starting file:

~~~
b: 'single'  # s
~~~

- Route 1: exit 0; line b now reads (raw invisible U+2028 between p and q, in single quotes):

  ~~~
  b: 'p
  q'     # s
  ~~~

- Route 2: two arms: exit 0; line b now reads (raw U+2028 in double quotes):

  ~~~
  b: "p
  q"     # s
  one arm: exit 0; line b now reads (a visible escape):
  b: "p\Lq"    # s
  ~~~

- Route 3: one arm: exit 0; line b now reads (raw U+2028 in single quotes):

  ~~~
  b: 'p
  q'     # s
  one arm: exit 0; line b now reads:
  b: "p\Lq"    # s
  ~~~


**Example 3:** `config set c "r\u0085s\u2029t"` (next-line, then paragraph separator) _(observed)_

Starting file:

~~~
c: "double"  # d
~~~

- Route 1: exit 0; line c now reads (U+0085 written as \N, raw invisible U+2029 between s and t):

  ~~~
  c: "r\Ns
  t"  # d
  ~~~

- Route 2: two arms: exit 0; line c now reads (\N escape plus raw U+2029):

  ~~~
  c: "r\Ns
  t"  # d
  one arm: exit 0; line c now reads (both escaped):
  c: "r\Ns\Pt" # d
  ~~~

- Route 3: one arm: exit 0; line c now reads (\N escape plus raw U+2029):

  ~~~
  c: "r\Ns
  t"  # d
  one arm: exit 0; line c now reads (both escaped):
  c: "r\Ns\Pt" # d
  ~~~


**Example 4:** `config get b`, then `config show` (after the three sets) _(observed)_

- Route 1: get: exit 0, prints `p`, the raw U+2028, `q`. show: exit 0, prints:

  ~~~
  a: x﻿y
  b: p
  q
  c: "r\Ns
  t"
  ~~~

- Route 2: All arms: get: exit 0, prints `p`, the raw U+2028, `q`.

  ~~~
  two arms: show prints:
  a: "x﻿y"
  b: "p
  q"
  c: "r\Ns
  t"
  one arm: show prints:
  a: "x﻿y"
  b: "p\Lq"
  c: "r\Ns\Pt"
  ~~~

- Route 3: Both arms: get: exit 0, prints `p`, the raw U+2028, `q`.

  ~~~
  one arm: show prints everything raw and unquoted except a (c holds a raw U+0085 and a raw U+2029):
  a: "x﻿y"
  b: p
  q
  c: r
  s
  t
  one arm: show prints every value escaped:
  a: "x\uFEFFy"
  b: "p\Lq"
  c: "r\Ns\Pt"
  ~~~


**In practice:** Route 1 and two of route 2's three arms leave invisible characters in the file. You can't see them in an editor, and a YAML reader that treats U+2028/U+2029 as line breaks may read the value back differently. In route 1, `x﻿y` is even stored unquoted. One route 2 arm and one route 3 arm write visible escapes (`\L`, `\P`, `\N`); route 3's other arm writes visible escapes only for U+0085 and leaves the rest raw. On every route, `config get` returned the same value that was set.

**Trade-off:** Route 1 keeps the existing write-back exactly, but leaves raw invisible characters in plain and single-quoted values. Route 2 always double-quotes; its arms disagree on writing the characters raw or escaped, and the raw form can read back differently in ruamel. Route 3 was never considered, and its arms ranged from mostly raw to fully escaped.

### Route 1

- Route: Leave strings with U+FEFF in plain or single quotes
- Reasoning given: Pre-existing write-back behaviour; changing it would change set's bytes
- Outcome: Kept
- proposed: 3 - Likely mis-reads

rating: n/a
reason: Same issue as T33 Q2; not double-counted

### Route 2

- Route: Only inside double quotes (written literally there)
- Reasoning given: ruamel's scanner treats them as line breaks; the contract asks for them literal
- Outcome: Kept; one arm left a read-back difference with ruamel for the owner
- proposed: 5 - Safe and readable

rating: n/a
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Rare

rating: n/a
reason:

## T81

**Question:** How non-string scalars are spelled when written  
**Kind:** divergent

**What's at stake:** When you set a number, boolean or null, the config file either keeps it the way you typed it (`0x1A`, `TRUE`, `~`, `1E3`) or rewrites it in one standard spelling (`26`, `true`, `null`, `1000.0`). Either way the value means the same thing. What differs is whether the file still looks like what you wrote.

**What each route does** (run against every arm's final code):

**Example 1:** `config set retry 0x1A` _(observed)_

Starting file:

~~~
# agent settings
retry: 3
debug: false
timeout: 30
ratio: 0.5
~~~

- Route 1: exit 0, no output; file line becomes `retry: 26`
- Route 2: exit 0, no output; file line becomes `retry: 0x1A`
- Route 3: two arms differ. One arm: `retry: 0x1A`. The other arm: `retry: 26`. Both exit 0 with no output.

**Example 2:** `config set debug TRUE` _(observed)_

- Route 1: exit 0; `debug: true`
- Route 2: exit 0; `debug: TRUE`
- Route 3: one arm: `debug: TRUE`; the other arm: `debug: true`

**Example 3:** `config set timeout ~` _(observed)_

- Route 1: exit 0; `timeout: null`
- Route 2: exit 0; `timeout: ~`
- Route 3: one arm: `timeout: ~`; the other arm: `timeout: null`

**Example 4:** `config set ratio 1E3` _(observed)_

- Route 1: exit 0; `ratio: 1000.0`
- Route 2: exit 0; `ratio: 1E3`
- Route 3: one arm: `ratio: 1E3`; the other arm: `ratio: 1000.0`

**Example 5:** `config set extra "{flag: True, none: Null, oct: 0o17, pad: +007, inf: -.INF, num: 2.50}"` _(observed)_

- Route 1: exit 0; the file now ends with:

  ~~~
  extra:
    flag: true
    none: null
    oct: 15
    pad: 7
    inf: -.inf
    num: 2.5
  ~~~

- Route 2: exit 0; the file now ends with:

  ~~~
  extra:
    flag: True
    none: Null
    oct: 0o17
    pad: +007
    inf: -.INF
    num: 2.50
  ~~~

- Route 3: One arm: the file ends with

  ~~~
  extra:
    flag: True
    none: Null
    oct: 0o17
    pad: +007
    inf: -.INF
    num: 2.50
  The other arm: the file ends with
  extra:
    flag: true
    none: null
    oct: 15
    pad: 7
    inf: -.inf
    num: 2.5
  ~~~


**In practice:** Every command on every route exited 0 with no output, and the comment line `# agent settings` was kept every time. The routes differ only in how the value is spelled in the file. Route 1 always writes the standard form, so `0o17` becomes `15` and `2.50` becomes `2.5`. Route 2 writes exactly what you typed. On route 3, one arm behaved like route 2 and the other like route 1.

**Trade-off:** Route 1 loses your own spelling (hex, octal, padding, `~`, capitals) in exchange for a uniform file. Route 2 keeps your spelling, so the file can mix styles like `TRUE`/`true` and `~`/`null`. On route 3 you get one or the other depending on the arm.

### Route 1

- Route: Canonical plain form (true/false, null, decimal int, repr(float), .inf/.nan)
- Reasoning given: Quoting a non-string would change its type
- Outcome: Kept
- proposed: 4 - Correct; may respell what the user typed

rating: 4
reason: Canonical spelling: loses the user's 0x1A, TRUE, ~, 1E3

### Route 2

- Route: Keep VALUE's own spelling (floats fall back to repr; .inf/.nan for non-finite)
- Reasoning given: Minimal surprise; one definition per style
- Outcome: Kept
- proposed: 5 - Writes what the user typed

rating: 5
reason: Keeps the user's spelling

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Either is valid YAML

rating: 4.5
reason: RESLICE placeholder: K (keeps spelling) 5; C (canonical) 4

## T82

**Question:** Which VALUE forms set accepts (empty, block collections, tags, anchors)  
**Kind:** divergent

**What's at stake:** When someone types an unusual VALUE (nothing at all, `a: b`, `!!str 5`, `&n 1`), the result is one of three things: it gets written into troupe.yml, possibly in a different form than they meant, or it is refused with exit 2 and the file is left alone. One case is easy to miss: `!!str 5` can end up stored as the number 5 instead of the string "5".

**What each route does** (run against every arm's final code):

**Example 1:** `config set empty ""` _(observed)_

Starting file:

~~~
name: demo  # project
retries: 3
~~~

- Route 1: exit 0; the file gains:

  ~~~
  empty: null
  ~~~

- Route 2: Two arms: exit 2, nothing written ("empty: VALUE is not a single flow node: VALUE is empty or contains only comments" / "troupe: error: invalid VALUE '': expected a YAML flow node"). One arm: exit 0, the file gains:

  ~~~
  empty: null
  ~~~

- Route 3: Both arms: exit 0, the file gains:

  ~~~
  empty: null
  ~~~


**Example 2:** `config set block "a: b"` _(observed)_

- Route 1: exit 0; the file gains a nested mapping:

  ~~~
  block:
    a: b
  ~~~

- Route 2: All three arms: exit 2, nothing written. The messages differ, e.g. "block: VALUE is not a single flow node: block mapping (write it in flow style, e.g. {a: 1} or [a, b])"
- Route 3: Both arms: exit 2, nothing written. One arm's message is "troupe: invalid VALUE 'a: b': must be a single flow node (quote it to make a string)"

**Example 3:** `config set tagged "!!str 5"` _(observed)_

- Route 1: exit 0; the tag is dropped and the value is stored as a plain number:

  ~~~
  tagged: 5
  ~~~

- Route 2: One arm: exit 2, "explicit tag '!!str' (tags are refused)". One arm: exit 0, stored as a number:

  ~~~
  tagged: 5
  One arm: exit 0, stored as a string:
  tagged: '5'
  ~~~

- Route 3: One arm: exit 0, stored as a string:

  ~~~
  tagged: '5'
  One arm: exit 2, "troupe: cannot parse VALUE '!!str 5': anchors and tags are not supported at line 1"
  ~~~


**Example 4:** `config set anchored "&n 1"` _(observed)_

- Route 1: exit 0; the anchor is dropped silently:

  ~~~
  anchored: 1
  ~~~

- Route 2: One arm: exit 2, "anchor '&n' (anchors and aliases are refused)". Two arms: exit 0, anchor dropped:

  ~~~
  anchored: 1
  ~~~

- Route 3: Both arms: exit 2, nothing written (e.g. "troupe: invalid VALUE '&n 1': anchors (&) and aliases (*) cannot be written")

**In practice:** Route 1 accepts everything it is given. Route 2 is described as refusing empty input, block collections, tags and anchors with exit 2, but only one of its three arms did all of that. The other two refused `a: b`, and between them they also wrote an empty value as null, wrote tags and anchors, and stored `!!str 5` either as the number 5 or as '5'. Every arm on route 2 and route 3 refused `a: b`. Wherever `!!str 5` was accepted, it came out either as the number 5 (route 1 and one route-2 arm) or as '5' (the others).

**Trade-off:** Route 1 never refuses, but it quietly turns `a: b` into a mapping, an empty value into null, and `!!str 5` into the number 5. Route 2 aims to refuse anything outside one plain value, so the user has to quote or rewrite, but its arms did not behave the same way. Route 3 refuses block mappings and anchors and stores an empty value as null, and its arms disagree on tags.

### Route 1

- Route: Compose VALUE as a single flow-sequence item; empty or whitespace-only VALUE becomes null
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 2 - An empty argument from a script bug silently writes null

rating: 2.5
reason: Accepts all: empty->null, a: b->map, !!str 5->number 5 (tag dropped), anchor dropped silently

### Route 2

- Route: Exactly one scalar or flow node; empty input, block collections, multi-document, tags and anchors exit 2
- Reasoning given: The contract says a single flow node; accepting more invents behaviour. A bare `a: b` must be quoted
- Outcome: Kept; anchors/aliases still exit 2 at step 6 and tags at step 7
- proposed: 5 - Strict and predictable

rating: 4
reason: RESLICE placeholder: per-case ratings averaged per arm (see reslice.md)

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - Unclear VALUE parsing can silently write the wrong thing

rating: 4.5
reason: RESLICE placeholder: per-case ratings averaged per arm (see reslice.md)

## T83

**Question:** How a set's edited text is checked before anything is written  
**Kind:** divergent

**What's at stake:** Every `config set` is checked before it writes. A strict check refuses edits that would quietly change something besides the target, and a loose check might let a bad rewrite reach disk. In this run, all five edits passed the check and were written the same way on both routes.

**What each route does** (run against every arm's final code):

**Example 1:** `config set defaults.model sonnet` _(observed)_

Starting file:

~~~
# troupe config
defaults: &d
  model: opus
  temperature: 0.2
coder:
  settings: *d
  agent: file:agents/coder.yaml  # shared
reviewer:
  settings: *d
tags: [a, b]
steps:
  - lint
  # trailing step comment
# top-level comment
notes: plain
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  defaults: &d
    model: sonnet
    temperature: 0.2
  The rest is unchanged, so coder.settings and reviewer.settings, which both point at *d, now resolve to sonnet too.
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, the same one-line change, and the aliases now resolve to sonnet. It was not refused, even though the values behind the aliases changed.

**Example 2:** `config set --expand-alias reviewer.settings.temperature 0.5` (run next, on the result above) _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
  reviewer:
    settings:  # expanded from *d by troupe
      model: sonnet
      temperature: 0.5
  defaults and coder.settings: *d are untouched.
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0 and the same expanded block with its marker comment.

**Example 3:** `config set coder.agent.retries 3` (agent was `file:agents/coder.yaml # shared`) _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
    agent:  # shared
      $ref: file:agents/coder.yaml
      retries: 3
  agents/coder.yaml is not touched.
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, the same $ref conversion with the comment kept, and agents/coder.yaml is not touched.

**Example 4:** `config set tags.2 '"x: y"'` (tags was `[a, b]`) _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
  tags: [a, b, 'x: y']
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0, `tags: [a, b, 'x: y']`.

**Example 5:** `config set steps.1 '"line one\nline two\n"'` _(observed)_

- Route 1: exit 0; the file now reads:

  ~~~
  steps:
    - lint
    # trailing step comment
    - |
      line one
      line two
  # top-level comment
  notes: plain
  ~~~

- Route 2: Same as route 1 (all five arms): exit 0 and the same block, with the new item placed after the trailing step comment.

**In practice:** In this run the two routes behaved exactly the same. Every edit succeeded with exit 0, no output and identical file contents, and no refusal (exit 3) happened. The difference only shows up if a rewrite goes wrong. Route 1 checks just the value you set, so a stray change elsewhere in the file would still be written. Route 2 reloads the whole config, includes and aliases included, and refuses with no write if anything else changed. Even so, route 2 accepted `defaults.model`, whose change carries through the aliases, so its "nothing else changes" rule must count alias effects as expected.

**Trade-off:** Route 1 is a simple check that only catches problems at the path you set; route 2 also catches damage elsewhere in the config but needs a growing list of allowances (include conversion, aliases, schema) to avoid refusing legitimate edits.

### Route 1

- Route: Re-parse the edited text and compare only the value at PATH with VALUE
- Reasoning given: A formatting bug then becomes a refused write, not a corrupted config
- Outcome: Kept
- proposed: 3 - Misses accidental changes to other values, the main way a splice goes wrong

rating: n/a
reason:

### Route 2

- Route: Reload the whole configuration from the edited in-memory texts; require PATH to read back as VALUE and nothing else to change; otherwise exit 3 with no write
- Reasoning given: Turns any renderer bug into a refusal instead of a corrupted file; the loader is the single definition of meaning
- Outcome: Kept; later widened with allowances for include conversion, aliases and schema checks
- proposed: 5 - A general safety net that catches collateral damage

rating: n/a
reason:

## T84

**Question:** What <dir> the watching line shows  
**Kind:** divergent

**What's at stake:** When `config watch` starts, its first line tells you which directory it is watching. If you didn't pass a directory, that line either names the real folder or just says `.`, which only helps if you already know where you launched it. A directory you pass yourself is printed exactly as you typed it on every route, so that line never reveals where a symlink actually points.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` (no flag, no TROUPE_THEATRE, started in /theatre) _(observed)_

- Route 1: prints `watching /theatre` and keeps running; Ctrl-C ends it with exit 0 (all four arms)
- Route 2: prints `watching .` and keeps running; Ctrl-C ends it with exit 0
- Route 3: prints `watching .` and keeps running; Ctrl-C ends it with exit 0

**Example 2:** `config watch --theatre=sub` _(observed)_

- Route 1: prints `watching sub`; Ctrl-C ends it cleanly with exit 0 (all four arms)
- Route 2: prints `watching sub`; on Ctrl-C it exits 0 but prints a Python traceback ending in `KeyboardInterrupt` ("Exception ignored in: <function Application.__del__ ...>")
- Route 3: prints `watching sub`; Ctrl-C ends it cleanly with exit 0

**Example 3:** `config watch --theatre linked` (linked is a symlink to sub) _(observed)_

- Route 1: all four arms print `watching linked`, not sub. On Ctrl-C, two arms: exit 0; one arm: exit 130; one arm: exit 137
- Route 2: prints `watching linked`; Ctrl-C ends it with exit 0
- Route 3: prints `watching linked`; Ctrl-C ends it with exit 0

**Example 4:** `--theatre . config watch` (flag before the command) _(observed)_

- Route 1: three arms: exit 2, nothing watched, an error such as `troupe: argument COMMAND: invalid choice: '.' (choose from config)`; one arm: accepts it, prints `watching .` and runs until Ctrl-C (exit 0)
- Route 2: exit 2, nothing watched: `troupe: usage error: argument group: invalid choice: '.' (choose from config)`
- Route 3: exit 2, nothing watched: `usage: troupe [-h] {config} ...` then `troupe: error: argument command: invalid choice: '.' (choose from config)`

**Example 5:** with `config watch` running, hand-edit .troupe/troupe.yml, wait 3 s, Ctrl-C, then `config history model` _(observed)_

Starting file:

~~~
model: opus  # main theatre
retries: 2
~~~

- Route 1: all arms the same: the history shows the import of `opus`, then `set` `opus` -> `sonnet` via `file`
- Route 2: same: import `opus`, then `set` `opus` -> `sonnet` via `file`
- Route 3: same: import `opus`, then `set` `opus` -> `sonnet` via `file`

**In practice:** Only one case differs between routes: running with no directory given. Route 1 prints the full path of the current folder; routes 2 and 3 print `.`. If you pass a directory, every route prints it exactly as typed, so a symlink shows its own name rather than its target. The other differences belong to single arms and not to the route chosen: an arm on route 1 that accepts `--theatre` before the command, the varied Ctrl-C exit codes on route 1, and the traceback on route 2.

**Trade-off:** Route 1 tells you where it's watching when you didn't say, but prints the cwd path unresolved, so on macOS it may show /var where the real path is /private/var. Routes 2 and 3 print a bare `.`, which is simple but tells you nothing about the location.

### Route 1

- Route: --theatre or TROUPE_THEATRE as given; the absolute cwd when neither is set
- Reasoning given: Resolving would turn /var into /private/var on macOS
- Outcome: Kept
- proposed: 5 - Matches the input

rating: 4.5
reason: Shows the absolute cwd when no directory is given; a home-relative path (~/Projects/theatre) would be better still

### Route 2

- Route: As given, falling back to '.'
- Reasoning given: None recorded
- Outcome: Kept
- proposed: 3 - `watching .` is uninformative

rating: 3
reason: Shows a bare '.', uninformative

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - The contract line should match the user's input

rating: 3
reason: Shows a bare '.', uninformative

## T85

**Question:** When the watching line is printed  
**Kind:** divergent

**What's at stake:** Scripts and users take the `watching …` line as the sign that edits will now be picked up. If the line comes out before the watcher is ready, an edit made right after it could be missed. If it comes out late, the user waits longer. In this test the edit came immediately after the line, and every implementation caught it.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` in the background; as soon as it prints its line, edit `.troupe/troupe.yml` (`main: before` -> `main: after`) and `.troupe/inc/edited.yml`, wait 3 s, then press Ctrl-C (SIGINT) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
# troupe config
edited:
  main: before
  inc: file:inc/edited.yml
(plus a large `bulk:` section and three included `parts`)

.troupe/inc/edited.yml:
value: before
~~~

- Route 1: All five arms printed their watching line and kept running. Three arms printed `watching /theatre`; two printed `watching .`. On Ctrl-C, three arms exited 0 and two exited 137 (killed, not a clean exit). Nothing went to stderr. `.troupe/inc/edited.yml` now reads:

  ~~~
  value: after
  ~~~

- Route 2: Printed `watching /theatre` and kept running. On Ctrl-C it exited 0. Nothing went to stderr. `.troupe/inc/edited.yml` now reads:

  ~~~
  value: after
  ~~~


**Example 2:** then `config history edited` _(observed)_

- Route 1: All five arms: exit 0. History shows the startup import (seq 1–2: `edited.main` and `edited.inc.value` = "before", via import), then seq 706 `edited.main` before -> after and seq 707 `edited.inc.value` before -> after, both via file. Both edits made right after the line were recorded.
- Route 2: Exit 0. Same history: import at seq 1–2, then seq 706 `edited.main` before -> after and seq 707 `edited.inc.value` before -> after, via file. Both edits were recorded.

**Example 3:** `config watch` again, then stop it straight away with SIGTERM (no edits) _(observed)_

- Route 1: All five arms printed the watching line again, the same text as before. Exit codes on SIGTERM: two arms exited 0, three exited 143. Afterwards `config history edited` showed the same four entries, with nothing new, and the `.troupe` listing was unchanged.
- Route 2: Printed `watching /theatre` again and exited 143 on SIGTERM. Afterwards `config history edited` showed the same four entries, with nothing new, and the `.troupe` listing was unchanged.

**In practice:** In these runs there was no visible difference between the routes. On both routes the line appeared, an edit made right after it was recorded, and a restart added no new history. Two other things varied, and they varied between arms within route 1 as well as between the routes: the text of the line (`watching /theatre` or `watching .`) and the exit code when stopped (0, 137 or 143). The test never sent a stop while watch was still starting, so route 1's rule of skipping the line in that case was not exercised.

**Trade-off:** Route 1 holds the line back until the watcher is fully set up and the initial import is done, so it may appear a bit later but promises that later edits are seen. Route 2 makes no such promise, though here it caught the edit too.

### Route 1

- Route: After handlers are installed and the initial import or reconcile; skipped if a stop came during start
- Reasoning given: Every change after the line is seen
- Outcome: Kept
- proposed: 5 - True promise

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: n/a
reason:

## T86

**Question:** Unloadable config when watch starts  
**Kind:** divergent

**What's at stake:** If the config file is broken or missing when someone starts `config watch`, the question is whether watch stops at once with a clear error or stays running and waits for a fix. In every run, on both routes, watch stopped at once. It never printed its "watching" line and did not notice the fix made afterwards.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` (the file has an unclosed `[`), then fix the file by hand, wait 3s, press Ctrl-C _(observed)_

Starting file:

~~~
agents:
  coder: [opus, sonnet
  reviewer: haiku
~~~

- Route 1: All five arms: exit 4 straight away. Nothing went to stdout and no watching line was printed. The process had already exited before Ctrl-C, so the hand fix was never picked up. The error wording differs by arm:

  ~~~
  - two arms give the full parser report, line 2 col 10 and line 3 col 11, with caret pointers
  - one arm: `troupe: .troupe/troupe.yml: invalid YAML (line 3, column 11): expected ',' or ']', but got ':'`
  - one arm: `troupe: cannot parse /theatre/.troupe/troupe.yml: expected ',' or ']', but got ':' at line 3`
  - one arm: `troupe: /theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence` (no line number)
  ~~~

- Route 2: Exit 4 straight away. Nothing went to stdout and no watching line was printed. The process had already exited before Ctrl-C, so the hand fix was never picked up. The error has no `troupe:` prefix: `/theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence, expected ',' or ']', but got ':' (line 3, column 11)`

**Example 2:** `ls .troupe` after the failed watch _(observed)_

- Route 1: Three arms: only `troupe.yml` is there. One arm: the failed watch also left `events.lock` (0 bytes) and `events.sqlite` (12288 bytes). One arm: it left `events.sqlite3.lock` (0 bytes).
- Route 2: Only `troupe.yml` is there.

**Example 3:** `config history` after the hand fix _(observed)_

- Route 1: All arms: exit 0. It lists 3 import entries: `agents.coder.0`=opus, `agents.coder.1`=sonnet, `agents.reviewer`=haiku.
- Route 2: Exit 0. It lists the same 3 import entries.

**Example 4:** `config watch --theatre sub` (the directory has no `.troupe/`), wait 2s, Ctrl-C _(observed)_

- Route 1: All arms: exit 4 straight away with no watching line, and nothing is created in `sub/`. The message differs by arm, for example `troupe: sub/.troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)` or `troupe: error: no configuration file: expected sub/.troupe/troupe.yml or sub/.troupe/troupe.yaml`.
- Route 2: Exit 4 straight away with no watching line, and nothing is created in `sub/`. Message: `sub/.troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)`

**Example 5:** `--theatre sub config get agents.reviewer` _(observed)_

- Route 1: One arm: exit 4, `troupe: sub/.troupe/troupe.yml: no configuration file (expected troupe.yml or troupe.yaml)` (the option is accepted before the command). Four arms: exit 2, a usage error along the lines of `invalid choice: 'sub' (choose from config)`.
- Route 2: Exit 2: `troupe: argument COMMAND: invalid choice: 'sub' (choose from config)`

**In practice:** Both routes fail fast in the same way: exit 4, no watching line, no waiting for a fix. The differences are small. Route 2's error has no `troupe:` prefix. On route 1 the wording varies by arm, and two of its arms leave lock or database files in `.troupe/` even though watch never started.

**Trade-off:** Route 1 fails fast like every other command, but its five arms word the error differently and two leave stray files behind. Route 2 also fails fast and leaves nothing behind, but its error has no `troupe:` prefix.

### Route 1

- Route: Exit 4 without the line
- Reasoning given: Like every other command; the line is a promise
- Outcome: Kept
- proposed: 5 - Consistent

rating: n/a
reason:

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract exit codes

rating: n/a
reason:

## T87

**Question:** What watch prints to stdout  
**Kind:** divergent

**What's at stake:** `config watch` runs in the background and records hand edits to the config file. The question is what it prints while it runs: anything a script reads from its output depends on that line, and a user has to be able to tell when a broken edit was not recorded.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` (with TROUPE_ACTOR=human:owner), then three hand edits to .troupe/troupe.yml: `model: opus` -> `sonnet`, then `retry: [3` (broken YAML), then `retry: 5`; then Ctrl-C (SIGINT) _(observed)_

Starting file:

~~~
# troupe settings
model: opus  # default model
retry: 3
agents:
  coder:
    temperature: 0.2
~~~

- Route 1: All four arms print one line on stdout, `watching /theatre` (the full directory path), and nothing else. The two good edits print nothing.
- Route 2: Both arms print one line on stdout, `watching .` (relative path, not the full directory), and nothing else. The two good edits print nothing.

**Example 2:** the broken edit `retry: [3` while watch is running _(observed)_

- Route 1: Nothing on stdout. All four arms report it on stderr, each worded differently. One arm: `/theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence, expected ',' or ']', but got ':' (line 4, column 7)`. One arm: `troupe: .troupe/troupe.yml: invalid YAML (line 4, column 7): expected ',' or ']', but got ':'`. One arm: `troupe: cannot parse /theatre/.troupe/troupe.yml: expected ',' or ']', but got ':' at line 4`. One arm prints the parser's full multi-line dump, starting `troupe: error: /theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence` and pointing at `retry: [3` and `agents:` with carets.
- Route 2: Nothing on stdout. Both arms report it on stderr. One arm prints a single line with no location and no reason: `troupe: /theatre/.troupe/troupe.yml: invalid YAML: while parsing a flow sequence`. The other prints the full multi-line parser dump, starting `troupe: ./.troupe/troupe.yml: invalid YAML: while parsing a flow sequence`.

**Example 3:** Ctrl-C (SIGINT) to stop watch _(observed)_

- Route 1: It stops in every arm. Three arms exit 0; one arm exits 137.
- Route 2: It stops in both arms. One arm exits 0; one arm exits 137.

**Example 4:** `config history` afterwards _(observed)_

- Route 1: exit 0 in all arms. Three import entries, then `model` opus->sonnet and `retry` 3->5, both `via: file`. The broken edit left no entry. Actor is recorded as `unknown`, even though watch ran with TROUPE_ACTOR=human:owner.
- Route 2: Same in both arms: three import entries, then `model` opus->sonnet and `retry` 3->5 via file, no entry for the broken edit, actor `unknown`.

**In practice:** On both routes, watch prints only its start line, so the only way to see what it recorded is `config history`. The routes differ mainly in that line: route 1 names the full directory, while route 2 prints `.`. On both routes the error for a broken edit appears only on stderr and its wording differs from arm to arm; one route-2 arm gives no line number or reason. On each route, one arm exits 137 instead of 0 on Ctrl-C.

**Trade-off:** Route 1: the start line names the full directory, but you have to run history to see what was recorded. Route 2: the same quiet output with a less informative `watching .` line, and in one arm a broken-edit error with no location.

### Route 1

- Route: Only the watching line; diagnostics on stderr; events visible through history
- Reasoning given: The contract promises one line
- Outcome: Kept
- proposed: 5 - Contract

rating: 5
reason: RESLICE placeholder: A (one line, location and reason) 5 x3; D (multi-line dump) 4

### Route 2

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Contract

rating: 3
reason: RESLICE placeholder: D (multi-line dump) 4; X (no location, no reason) 2

## T88

**Question:** Store failures during watch  
**Kind:** divergent

**What's at stake:** While `config watch` runs, it records each hand edit of troupe.yml in the history. The question is what happens when writing that record fails: watch either reports the failure and keeps going, or stops. In this run no route ever reported a store failure. Hand edits were recorded on every route. The routes differed mainly in how watch ended on Ctrl-C.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` running; junk text ("this is not a database, just junk text") written over `.troupe/events.db`, `history.db`, `eventstore.db`, `events.sqlite`, `store.db` and `troupe.db`; then troupe.yml edited by hand; wait 3s _(observed)_

Starting file:

~~~
# team settings
retry: 3
model: opus  # default model
~~~

- Route 1: Watch printed only `watching /theatre` and nothing on stderr; no error shown. Neither arm keeps its history in any of the overwritten files. One arm uses `.troupe/history.sqlite` and the other uses `.troupe/events.sqlite3`.
- Route 2: Watch printed only `watching /theatre` and nothing on stderr; no error shown. Its history lives in `.troupe/events.sqlite`, which was one of the files overwritten with junk, and it still said nothing.
- Route 3: All three arms printed only their watching line (`watching /theatre` or `watching .`) and nothing on stderr; no error shown. One arm stores in `.troupe/events.sqlite`, which was overwritten with junk, and stayed silent. The other two (`history.sqlite`, `troupe-state.sqlite`) were not touched.

**Example 2:** then `config history` _(observed)_

- Route 1: Both arms: exit 0 with 4 entries: import retry 3, import model opus, then `set retry 3 -> 7` and `set model opus -> sonnet` via file. The hand edit was recorded.
- Route 2: Exit 0 with the same 4 entries, including `set retry 3 -> 7` and `set model opus -> sonnet` via file. The edit was recorded even though the store file had been overwritten with junk.
- Route 3: All three arms: exit 0 with the same 4 entries; the edit was recorded.

**Example 3:** Ctrl-C (SIGINT) to stop the running `config watch` _(observed)_

- Route 1: Both arms: exit 0, clean stop, nothing on stderr.
- Route 2: Exit 137 and nothing on stderr. It did not stop cleanly on Ctrl-C and ended as a killed process.
- Route 3: Each arm did something different. One arm: exit 0, clean. One arm: exit 137 (killed), nothing on stderr. One arm: exit 130 and a Python traceback ending in `KeyboardInterrupt`, raised while watch was installing its signal handler.

**In practice:** This run never actually made a store write fail. The junk files had names the harness guessed, and most routes keep their history under other names. Where the real store file was overwritten (route 2, and one arm on route 3), the edit was still recorded and nothing was reported. So 'report and retry' and 'stop watch' were never put to the test. The behaviour you can see is that Ctrl-C ended watch cleanly with exit 0 on route 1 (both arms), but not on route 2. Route 3 was inconsistent across its arms.

**Trade-off:** Route 1: watch keeps running through store errors, so a broken store could go unnoticed apart from repeated reports. Route 2: watch stops on an unexpected store error, so edits made after that point are not recorded until someone restarts it. Route 3: no deliberate policy, so the behaviour is whatever each arm happens to do.

### Route 1

- Route: Report and retry like load errors
- Reasoning given: So no hand edit is lost
- Outcome: Kept
- proposed: 5 - Robust

rating: n/a
reason: Untested: no store write failure could be triggered

### Route 2

- Route: Unexpected non-load exceptions end watch through the normal error path
- Reasoning given: Stop rather than run on silently
- Outcome: Kept
- proposed: 4 - Conservative

rating: n/a
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - A hand edit could be lost or watch could crash

rating: n/a
reason:

## T89

**Question:** Keep the store open for watch's lifetime  
**Kind:** divergent

**What's at stake:** While `config watch` runs, the user may look in `.troupe/` and find extra database side files, and the watcher has to keep recording both CLI and hand edits. When the user presses Ctrl-C, it should stop cleanly and leave a tidy directory.

**What each route does** (run against every arm's final code):

**Example 1:** start `config watch`, then list `.troupe/` while it runs _(observed)_

Starting file:

~~~
.troupe/troupe.yml  56 bytes
~~~

- Route 1: two arms: `.troupe/events.sqlite` (4096 bytes) plus `events.sqlite-shm` (32768) and `events.sqlite-wal` (20632). One of those arms also has an empty `events.lock`.
- Route 2: only `.troupe/history.sqlite` (12288 bytes); no side files
- Route 3: arms differ. One arm: only `history.sqlite` (12288). One arm: `troupe-state.sqlite` plus `-shm` (32768) and `-wal` (20632) side files. One arm: `events.sqlite3` (12288) plus an empty `events.sqlite3.lock`.

**Example 2:** with watch running: `config set retry 5` as agent:helper, then hand-edit `model: opus` -> `model: sonnet`, wait 3s, list `.troupe/` _(observed)_

- Route 1: both arms: exit 0. The `-wal` file grows from 20632 to 28872 after the set and to 37112 after the hand edit.
- Route 2: exit 0; still only `history.sqlite` at 12288 bytes
- Route 3: exit 0. The arm with `-wal`/`-shm` side files grows its `-wal` to 37112. The other two arms show no change in the store files.

**Example 3:** press Ctrl-C on `config watch`, then list `.troupe/` _(observed)_

- Route 1: both arms: exit 0 and quiet. The `-shm` and `-wal` side files are gone and `events.sqlite` is now 12288 bytes. The empty `events.lock` stays in the one arm that had it.
- Route 2: exit 0 and quiet; directory unchanged (`history.sqlite` 12288)
- Route 3: arms differ. One arm: exit 137 (it was killed after Ctrl-C), nothing on stderr. One arm: exit 130 and prints a Python traceback ending in `KeyboardInterrupt`; its side files are cleaned up. One arm: exit 0 and quiet, but the empty `events.sqlite3.lock` stays.

**Example 4:** `config history` after watch stopped _(observed)_

- Route 1: both arms: exit 0, 4 entries. Two are import entries; seq 3 is retry 3->5 by agent helper via cli; seq 4 is agent.model opus->sonnet via file, actor unknown.
- Route 2: exit 0; the same 4 entries
- Route 3: all three arms: exit 0; the same 4 entries

**In practice:** On every route the watcher recorded the CLI set and the hand edit. The routes differ only in what the user sees on disk while watch runs and in how watch exits on Ctrl-C. On route 1, `-wal`/`-shm` side files sit next to the store for as long as watch runs and disappear only when it stops. Route 2 never leaves side files. Route 3's arms each did something different, and two of its arms exited badly on Ctrl-C (one killed with 137, one with a traceback).

**Trade-off:** Route 1: database side files visible for watch's whole lifetime, clean exit. Route 2: nothing extra on disk, clean exit. Route 3: unpredictable layout across arms, and in two arms a messy Ctrl-C.

### Route 1

- Route: One store/app for the whole run
- Reasoning given: repository.get rebuilds from storage each time
- Outcome: Kept
- proposed: 4 - Works; relies on no cache

rating: n/a
reason:

### Route 2

- Route: Open per sync inside the lock
- Reasoning given: No -wal/-shm files; no stale caches
- Outcome: Kept
- proposed: 5 - Clean

rating: n/a
reason:

### Route 3

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: n/a - Detail

rating: n/a
reason:

## T90

**Question:** Files first or events first, and what if one of them fails  
**Kind:** divergent

**What's at stake:** This decides whether a config file can end up changed with no history entry for the change, and what a user sees when the history store can't be written. None of the runs tested a failure, though. Every route was only exercised on normal changes, and on those they all did the same thing.

**What each route does** (run against every arm's final code):

**Example 1:** `config set retry 5 --reason succeeds` (as human:owner), then `config history retry` _(observed)_

Starting file:

~~~
retry: 3  # attempts
notes: file:notes.txt
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: Both arms: exit 0; the file now reads:

  ~~~
  retry: 5  # attempts
  The comment is kept. History shows the import (3), then seq 4: set 3 -> 5 by human owner via cli, reason "succeeds".
  ~~~

- Route 2: Exit 0; the file now reads:

  ~~~
  retry: 5  # attempts
  The comment is kept. History shows the import (3), then seq 4: set 3 -> 5 by human owner via cli, reason "succeeds".
  ~~~

- Route 3: Exit 0; the file now reads:

  ~~~
  retry: 5  # attempts
  The comment is kept. History shows the import (3), then seq 4: set 3 -> 5 by human owner via cli, reason "succeeds".
  ~~~

- Route 4: Both arms: exit 0; the file now reads:

  ~~~
  retry: 5  # attempts
  The comment is kept. History shows the import (3), then seq 4: set 3 -> 5 by human owner via cli, reason "succeeds".
  ~~~


**Example 2:** `config set agents.coder "{model: sonnet}"` (a value that comes entirely from an included file), then `config history agents` _(observed)_

Starting file:

~~~
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: Both arms: exit 3, no file changed, no event recorded (history still shows only the import of model: opus). The messages differ. One arm: "troupe: agents.coder: its whole value comes from .troupe/agents/coder.yaml; not replacing it". The other: "troupe: agents.coder: value comes from include /theatre/.troupe/agents/coder.yaml; refusing to replace it (change a path inside it instead); no file changed".
- Route 2: Exit 3, no file changed, no event recorded. Message: "/theatre/.troupe/agents/coder.yaml: agents.coder: the whole value comes from the include file:agents/coder.yaml; change the included file instead".
- Route 3: Exit 3, no file changed, no event recorded. Message: "troupe: error: agents.coder: its whole value comes from include 'file:agents/coder.yaml' in /theatre/.troupe/troupe.yml; change the included file instead".
- Route 4: Both arms: exit 3, no file changed, no event recorded. The messages differ. One arm: "troupe: write refused: agents.coder: value comes from include /theatre/.troupe/agents/coder.yaml; refusing to replace it". The other: "troupe: agents.coder: value comes from include .troupe/agents/coder.yaml".

**Example 3:** `config set notes '"new text\n"'` (as agent:bot), where notes.txt is a symlink to shared/notes.txt; then `config history notes` _(observed)_

Starting file:

~~~
old text
~~~

- Route 1: Both arms: exit 0. shared/notes.txt now reads "new text" and notes.txt is still a symlink to it. History shows seq 5: old text -> new text by agent bot via cli.
- Route 2: Exit 0. shared/notes.txt now reads "new text" and notes.txt is still a symlink to it. History shows seq 5: old text -> new text by agent bot via cli.
- Route 3: Exit 0. shared/notes.txt now reads "new text" and notes.txt is still a symlink to it. History shows seq 5: old text -> new text by agent bot via cli.
- Route 4: Both arms: exit 0. shared/notes.txt now reads "new text" and notes.txt is still a symlink to it. History shows seq 5: old text -> new text by agent bot via cli.

**Example 4:** Edit troupe.yml by hand to `retry: 7 # attempts`, then `config get retry` and `config history retry` _(observed)_

Starting file:

~~~
retry: 5  # attempts
~~~

- Route 1: Both arms: `get` prints 7. History adds seq 6: set 5 -> 7, actor unknown, via file.
- Route 2: `get` prints 7. History adds seq 6: set 5 -> 7, actor unknown, via file.
- Route 3: `get` prints 7. History adds seq 6: set 5 -> 7, actor unknown, via file.
- Route 4: Both arms: `get` prints 7. History adds seq 6: set 5 -> 7, actor unknown, via file.

**In practice:** On normal use you can't tell the routes apart. Every route wrote the file, recorded the event and caught the hand edit the same way. The only visible differences were the wording of the refusal message and the name of the history file in .troupe (events.sqlite, history.sqlite, events.sqlite3 plus a lock file, troupe-state.sqlite, or events.sqlite plus events.lock). The cases where the routes are meant to differ were not run: a history store that can't be written, a read-only target or directory, or a crash between the write and the record. So none of the behaviour that sets them apart was observed.

**Trade-off:** Route 1 is simplest, but a crash or store failure can leave a change on disk with no event (it is later recorded only as an anonymous hand edit). Route 2 undoes the file write and exits 4 if recording fails. Route 3 also refuses up front with exit 3 when anything isn't writable, which means extra checks and a stricter tool. Route 4 never considered the question.

### Route 1

- Route: Write files, then record; a failed write records nothing; a crash between them can lose an event
- Reasoning given: The reverse order could record a change that never reached disk; losing an event on a crash is acceptable
- Outcome: Kept (reconcile at step 2 later records such missed changes as hand edits)
- proposed: 4 - Sound order with a small crash window

rating: 2
reason: Files first; a failed or crashed record leaves a change with no event (owner prefers events first)

### Route 2

- Route: Write files, then record; if recording fails, restore the files and exit 4 naming the store
- Reasoning given: Never leave a written change without its history
- Outcome: Kept
- proposed: 5 - Keeps files and history consistent

rating: 4
reason: Files first, but restores files and exits 4 if recording fails: closest to files and history never disagreeing

### Route 3

- Route: Write then record, but refuse up front (exit 3) when the target, its directory or the store is not writable; other store failures exit 4
- Reasoning given: The atomic rename would replace read-only files; a change must never be written without its events
- Outcome: Kept
- proposed: 4 - Covers the common failure up front; the crash window remains

rating: 3
reason: Refuses up front when not writable; the crash window remains

### Route 4

- Route: not considered
- Reasoning given: (none)
- Outcome: (none)
- proposed: 3 - The ordering decides whether history can claim a change that never happened

rating: 2
reason: Never considered

## T91

**Question:** Which YAML library provides the node positions for byte-surgical write-back  
**Kind:** divergent

**What's at stake:** When you set a value through the CLI, the question is whether the YAML file gets exactly what you typed or a re-rendered version of it. The other question is whether existing values like `yes`, `017` or `.inf` are typed the same way when they are read back.

**What each route does** (run against every arm's final code):

**Example 1:** `config set c 0o20` _(observed)_

Starting file:

~~~
c: 017   # leading zero
~~~

- Route 1: exit 0; the line now reads:

  ~~~
  c: 0o20  # leading zero
  ~~~

- Route 2: two arms: exit 0; the line now reads:

  ~~~
  c: 0o20  # leading zero
  three arms: exit 0; your spelling is replaced by its decimal value:
  c: 16    # leading zero
  ~~~


**Example 2:** `config set n 1e3` (new key) _(observed)_

- Route 1: exit 0; a line is appended at the end of the file:

  ~~~
  n: 1e3
  ~~~

- Route 2: two arms: exit 0; appended:

  ~~~
  n: 1e3
  three arms: exit 0; appended:
  n: 1000.0
  ~~~


**Example 3:** `config set m '"crème brûlée 😀😀"'` _(observed)_

Starting file:

~~~
m: "café 😀"  # note
~~~

- Route 1: exit 0; the line now reads (the comment is kept, with one space before it instead of two):

  ~~~
  m: "crème brûlée 😀😀" # note
  ~~~

- Route 2: all five arms: exit 0; the same line as route 1:

  ~~~
  m: "crème brûlée 😀😀" # note
  ~~~


**Example 4:** `config history` on the starting file (the import of the existing values) _(observed)_

Starting file:

~~~
# typing probes
a: yes
b: 0o17
c: 017   # leading zero
d: 1_000
e: 1e3
f: 1:30
g: .inf
h: 0x1F
i: ~
j: Off
k: 2001-12-14
m: "café 😀"  # note
~~~

- Route 1: exit 0; a, d, f, j and k are imported as strings ("yes", "1_000", "1:30", "Off", "2001-12-14"). b = 15, c = 17, e = 1000.0, g = Infinity, h = 31, i = null, m = "café 😀"
- Route 2: four arms: the same as route 1; one arm: the same, except that g is recorded as the string ".inf" instead of Infinity, and m is written with escape codes ("caf\u00e9 \ud83d\ude00")

**Example 5:** `config show --sources` _(observed)_

- Route 1: exit 0; plain values, e.g. `a: yes # from .troupe/troupe.yml`, `c: 17 …`, `g: .inf …`, `j: Off …`
- Route 2: four arms: output identical to route 1; one arm: string values are shown in quotes: `a: 'yes'`, `d: '1_000'`, `f: '1:30'`, `j: 'Off'`, `k: '2001-12-14'`

**In practice:** Both routes read the file the same way: `yes`/`Off` stay text, `017` is 17 and `0o17` is 15. In both routes, every arm leaves untouched lines and comments byte-for-byte as they were. The only differences are what a `set` writes and some small display differences. Route 1's single arm, and two of route 2's five arms, write your value exactly as typed. The other three route 2 arms rewrite numbers in a normalized form (`0o20` becomes `16`, `1e3` becomes `1000.0`).

**Trade-off:** Route 1 needs its own typing rules on top of a library built for an older YAML version. Route 2 gets those rules from its library, but its arms were inconsistent: three normalized the numbers you typed, one recorded `.inf` as text, and one quoted strings in `show`.

### Route 1

- Route: PyYAML compose for node positions, with custom YAML 1.2 core resolution
- Reasoning given: PyYAML follows YAML 1.1 rules, so scalar typing is replaced
- Outcome: Kept; a loader subclass was added at step 6 to locate aliases
- proposed: 4 - Works, but the scanner is still YAML 1.1, so edge cases differ from the 1.2 contract

rating: n/a
reason:

### Route 2

- Route: ruamel.yaml compose only (nodes and marks); never use its dumper
- Reasoning given: The round-trip dumper reformats untouched text, PyYAML is YAML 1.1 only, and a hand-written parser is too big a risk
- Outcome: Kept through step 7; later extended with composer hooks for aliases
- proposed: 5 - Exact spans with a YAML 1.2 parser; the dumper risk is avoided

rating: n/a
reason:

# Unanimous (27)

## T92

**Question:** TROUPE_ACTOR unset, no login name  
**Kind:** unanimous

**What's at stake:** When nobody has set TROUPE_ACTOR and no login name can be found, every change still has to be recorded under some author. The question is whether the history marks that change as made by an unnamed person or treats it as an error or a guess.

**What each route does** (run against every arm's final code):

**Example 1:** `config set --reason "no login name" retry 3` (TROUPE_ACTOR, USER, LOGNAME, LNAME and USERNAME all unset; the user has no account entry) _(observed)_

Starting file:

~~~
retry: 1  # attempts
name: demo
~~~

- Route 1: all six arms: exit 0, prints nothing; the file now reads:

  ~~~
  retry: 3  # attempts
  name: demo
  ~~~


**Example 2:** `config set --reason "user alice" retry 4` with USER=alice, then `config set --reason "empty USER" retry 5` with USER set to an empty string _(observed)_

- Route 1: all six arms: both exit 0 and print nothing; the file reads `retry: 4 # attempts` and then `retry: 5 # attempts`, and the comment is kept

**Example 3:** `config history retry` _(observed)_

- Route 1: all six arms: exit 0 and the same four entries. The import of retry=1 has actor {"kind": "unknown", "id": null}. The set to 3 with no login name has actor {"kind": "human", "id": null}. The set to 4 has {"kind": "human", "id": "alice"}. The set to 5 with an empty USER has {"kind": "human", "id": null}, so an empty name is treated the same as a missing one.

**Example 4:** `--theatre . config history` (no login name) _(observed)_

- Route 1: five arms: exit 2, prints nothing to stdout, and stderr says '.' is an invalid choice. The wording differs, e.g. `troupe: argument COMMAND: invalid choice: '.' (choose from config)`, and two of these arms also print a usage line. One arm: exit 0 and lists the full history, including the `name` import, with the same actor values as above.

**In practice:** The only route records a change made with no identifiable user as a human with an empty id, not as an error. The note given for this route says the actor should be shown as "unknown", but the recorded kind is "human". "unknown" appears only on the entries created when the file is first imported. The arms differ only on the `--theatre` option, which is unrelated to this question: one arm accepts it and five reject it.

**Trade-off:** Route 1: setting a value never fails for lack of a name, but the history cannot tell apart different unnamed users, or an empty USER from a missing one.

### Route 1

- Route: {kind: human, id: null}
- Reasoning given: Say unknown
- Outcome: Kept
- proposed: 1 - Breaks the owner's stated preference to fail

rating: n/a
reason:

## T93

**Question:** Which commands check TROUPE_ACTOR  
**Kind:** unanimous

**What's at stake:** If `TROUPE_ACTOR` holds a bad value, a user wants to find out right away, on any command, and not only when a write goes into the history under a garbage name. The flip side is that a bad value also blocks plain reads.

**What each route does** (run against every arm's final code):

**Example 1:** `TROUPE_ACTOR=robot:x config get model` _(observed)_

Starting file:

~~~
# team config
model: opus  # default model
retry: 3
~~~

- Route 1: exit 2, prints nothing on stdout; stderr says the actor value is invalid and must be human:<id> or agent:<id>. All six arms behaved the same except for the wording, e.g. `troupe: invalid TROUPE_ACTOR: 'robot:x' (expected human:<id> or agent:<id>)`

**Example 2:** `TROUPE_ACTOR=robot:x config get no.such.path` _(observed)_

- Route 1: exit 2 with the same actor error. The bad actor is reported first, so the user never hears that the path doesn't exist. Same in all six arms.

**Example 3:** `TROUPE_ACTOR=robot:x config history` _(observed)_

- Route 1: exit 2 with the same actor error, and no history is printed, even though this command only reads. Same in all six arms.

**Example 4:** `TROUPE_ACTOR=robot:x config set model sonnet --reason try`, then `TROUPE_ACTOR=human:owner config history` _(observed)_

Starting file:

~~~
# team config
model: opus  # default model
retry: 3
~~~

- Route 1: The set exits 2 with the actor error and leaves the file unchanged. The history call then exits 0 and lists only the two original import entries (model = "opus" and retry = 3, actor unknown), with no record of the failed set. Same in all six arms.

**In practice:** There is only one route here, and all six arms behaved the same way: a malformed `TROUPE_ACTOR` stops every command (get, set and history) with exit 2 before it does anything. Only the wording of the error message differs between arms. Once the variable is fixed, everything works normally.

**Trade-off:** Route 1 catches a bad actor value straight away and never writes anything with it, but the cost is that read-only commands like `get` and `history` also refuse to run until the variable is fixed.

### Route 1

- Route: Every command, first
- Reasoning given: Fail early
- Outcome: Kept
- proposed: 5 - Safe

rating: n/a
reason:

## T94

**Question:** How watch notices file changes  
**Kind:** unanimous

**What's at stake:** With `config watch` running, a user expects a change to the file their agent config points at to be noticed and recorded, and a change to an unrelated file to be left alone. In this run nothing tested whether a real change gets picked up. The harness failed to repoint the link, so the only file edited by hand was one the config does not use.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` (in the background), then the harness tries to repoint `.troupe/agents/current.yaml` from `coder-v1.yaml` to `coder-v2.yaml` _(observed)_

- Route 1: All six arms printed a watching line and kept running. Four printed `watching /theatre` and two printed `watching .`. The repoint failed with exit 1: `.troupe/agents/current.yaml already exists`. The link stayed `current.yaml -> coder-v1.yaml`, and the final listing confirms it.

**Example 2:** With watch running, the user edits `.troupe/agents/coder-v2.yaml` by hand (retries 5 -> 6). This file is not linked into the config. After 3 s they stop watch with Ctrl-C (SIGINT). _(observed)_

Starting file:

~~~
model: sonnet
retries: 5
~~~

- Route 1: In all six arms watch printed nothing beyond its watching line and exited 0 on Ctrl-C. No change was recorded.

**Example 3:** `config history coder`, then `config get coder.model` _(observed)_

- Route 1: All six arms exited 0. History has only the two original import entries: `coder.model` null -> "opus" and `coder.retries` null -> 3, with actor unknown and via import. `get` prints `opus`.

**Example 4:** `--theatre . config history coder` _(observed)_

- Route 1: Five arms reject it with exit 2, each with different wording of "invalid choice: '.' (choose from config)". Two of the five also print a usage line. One arm accepts it, exits 0 and shows the same two import entries.

**In practice:** The run only shows that watch stays quiet when an unlinked file changes, and that it starts and stops cleanly on Ctrl-C. Because the link repoint failed, nothing here shows whether polling catches a repointed link or an edit to the linked file. Leftover files differ between arms: the history database has different names (`history.sqlite`, `events.sqlite`, `troupe-state.sqlite`, `events.sqlite3`), and two arms also leave an empty lock file.

**Trade-off:** Route 1 needs no extra dependency and compares the file's actual contents, so in principle it catches save-by-rename and same-size edits. The cost is re-reading the files every 0.1-0.25 s while watch runs.

### Route 1

- Route: Poll file bytes with the stdlib every 0.1-0.25 s; no watcher library, no mtime
- Reasoning given: No dependency; catches save-by-rename and same-size edits; mtime resolution misses fast writes
- Outcome: Kept
- proposed: 5 - Simple and meets the 2 s promise

rating: n/a
reason:

## T95

**Question:** How history is persisted  
**Kind:** unanimous

**What's at stake:** This choice decides whether every config change is kept as a numbered, ordered record of who changed what, when and why, and whether `config history` can show it. The file stays readable with its comments, and one command's changes are recorded together.

**What each route does** (run against every arm's final code):

**Example 1:** `TROUPE_ACTOR=agent:planner config set agents.coder.model sonnet --reason "try sonnet"` _(observed)_

Starting file:

~~~
# theatre config
agents:
  coder:
    model: opus  # main model
    temperature: 0.2
retry: 3
~~~

- Route 1: All six arms: exit 0, no output; the file now reads:

  ~~~
  # theatre config
  agents:
    coder:
      model: sonnet # main model
      temperature: 0.2
  retry: 3
  
  The comment is kept, but the two spaces before it became one.
  ~~~


**Example 2:** `TROUPE_ACTOR=human:owner config set limits "{timeout: 30, tags: [a, b]}"` _(observed)_

- Route 1: All six arms: exit 0, no output; the file gains:

  ~~~
  limits:
    timeout: 30
    tags:
      - a
      - b
  
  History then shows this as 3 entries (seq 5–7: `limits.timeout`, `limits.tags.0`, `limits.tags.1`). All 3 carry actor human:owner and share one change id and timestamp.
  ~~~


**Example 3:** `TROUPE_ACTOR=human:owner config set agents.coder.model sonnet` (value already sonnet) _(observed)_

- Route 1: All six arms: exit 0, no output, the file is unchanged, and no history entry is added (history still ends at seq 7).

**Example 4:** `config history` _(observed)_

- Route 1: All six arms: exit 0. Prints 7 JSON lines numbered 1–7 with no gaps. Seqs 1–3 are `import` entries for the file's starting values (actor kind "unknown", reason null). Seq 4 is `{"op": "set", "path": "agents.coder.model", "old": "opus", "new": "sonnet", "actor": {"kind": "agent", "id": "planner"}, "via": "cli", "reason": "try sonnet", ...}`. Seqs 5–7 are the limits entries.

**Example 5:** `config history agents.coder` _(observed)_

- Route 1: All six arms: exit 0. Prints only seqs 1, 2 and 4 (the import of model and temperature, then the planner's model change). The original numbers are kept, so the filtered list has a gap at 3.

**In practice:** On this route all six arms gave the same results. The only differences were timestamps and change ids. The starting config is imported into history the first time a command runs, so history always starts from the file's original values.

**Trade-off:** Route 1: it needs a database under .troupe/ next to the YAML, plus an external library. Imports and nested values become one history line per leaf, so a single `set` can add several entries.

### Route 1

- Route: eventsourcing with SQLite under .troupe/, one aggregate per theatre with a fixed id, each command's events saved in one save
- Reasoning given: Required library; one stream gives a total order and gapless numbering; SQLite saves are atomic
- Outcome: Kept; event classes were versioned at step 4
- proposed: 5 - Durable, atomic and inside the allowed state directory

rating: n/a
reason:

## T96

**Question:** How a folded scalar is re-wrapped after a change  
**Kind:** unanimous

**What's at stake:** When you change one paragraph of a folded `brief: >` text, you want the paragraphs you did not touch to stay byte-for-byte as they were and only the changed text re-wrapped. Otherwise every edit produces a noisy diff, or the wrapping ends up oddly narrow.

**What each route does** (run against every arm's final code):

**Example 1:** `config set brief "The quick brown fox jumps over the lazy dog and keeps running until it reaches the river.\nShort para width now grows much longer than before.\nThird paragraph is left exactly as it was, with odd spacing.\n"` (only the middle paragraph changes) _(observed)_

Starting file:

~~~
team: alpha
brief: >
  The quick brown fox jumps over the lazy dog and keeps
  running until it reaches the river.

  Short para
  width.

  Third paragraph is left exactly
  as it was,   with odd spacing.
next: 1  # tail
~~~

- Route 1: All six arms gave the same result: exit 0, no output. The first and third paragraphs are untouched (the odd spacing is kept), and the changed paragraph is re-wrapped at its old, very narrow width. The file now reads:

  ~~~
  team: alpha
  brief: >
    The quick brown fox jumps over the lazy dog and keeps
    running until it reaches the river.
  
    Short para
    width now
    grows much
    longer
    than
    before.
  
    Third paragraph is left exactly
    as it was,   with odd spacing.
  next: 1  # tail
  ~~~


**Example 2:** next: `config set brief` with the same text plus a new first paragraph "A brand new opening paragraph that has no counterpart in the old value at all, so it wraps wide." _(observed)_

- Route 1: All six arms gave the same result: exit 0. The new paragraph is wrapped at about 55 columns and the existing paragraphs keep their bytes. The block now reads:

  ~~~
  brief: >
    A brand new opening paragraph that has no counterpart
    in the old value at all, so it wraps wide.
  
    The quick brown fox jumps over the lazy dog and keeps
    running until it reaches the river.
  
    Short para
    width now
    grows much
    longer
    than
    before.
  
    Third paragraph is left exactly
    as it was,   with odd spacing.
  next: 1  # tail
  ~~~


**Example 3:** next: `config set brief` with the same four paragraphs reordered (Third, Quick fox, Brand new, Short para) _(observed)_

- Route 1: The arms split on how the moved "Third paragraph" is wrapped; all exit 0. Five arms re-wrap it:

  ~~~
    Third paragraph is left exactly as it was,   with odd
    spacing.
  
    The quick brown fox jumps over the lazy dog and keeps
    running until it reaches the river.
  
  One arm keeps its original bytes:
    Third paragraph is left exactly
    as it was,   with odd spacing.
  
    The quick brown fox jumps over the lazy dog and keeps
    running until it reaches the river.
  
  In all six arms, the other paragraphs are as before.
  ~~~


**Example 4:** next: the same, but the fox paragraph becomes "...lazy dog and keeps<TAB>running until it reaches the river today." _(observed)_

- Route 1: All six arms: exit 0. The fox paragraph is re-wrapped so that the line does not break at the TAB, and the TAB stays inside the line:

  ~~~
    The quick brown fox jumps over the lazy dog and
    keeps	running until it reaches the river today.
  The "Third paragraph" lines stay as they were after the previous step (five arms re-wrapped, one arm original).
  ~~~


**Example 5:** next: `config set brief "Third paragraph is left exactly as it was, with odd spacing.\n this line is more indented\n"` _(observed)_

- Route 1: All six arms: exit 3, and the file is not changed. Only the error wording differs, e.g. `troupe: value would put a more-indented line into a folded scalar`. Some messages name the file path, the offending line or line 2.

**In practice:** Paragraphs you don't touch are kept exactly, odd spacing included. A paragraph you edit is re-wrapped at the width its old lines had, so a paragraph that used to be short ends up as a tall column of one- or two-word lines. New paragraphs wrap at about 55 columns. If you only reorder paragraphs, five arms re-wrap a moved paragraph and one arm keeps its old line breaks.

**Trade-off:** Route 1: small diffs that keep your existing wrapping, at the cost of very narrow re-wrapping wherever the old paragraph was short.

### Route 1

- Route: Align paragraphs with difflib; unchanged paragraphs keep their bytes; changed ones re-wrap at the old width (default 80)
- Reasoning given: Inserting or removing a paragraph leaves the others byte-identical; the contract requires re-wrapping. One arm made re-wrapping reordered paragraphs a required fix; another never breaks next to a TAB
- Outcome: Kept
- proposed: 5 - Minimal byte change

rating: 4
reason: RESLICE placeholder: K (keeps a moved paragraph's bytes) 5; W (re-wraps it) 4 x5

## T97

**Question:** How get and show divide the work  
**Kind:** unanimous

**What's at stake:** Scripts that run `config get` on a single setting need to keep getting a plain value back. Asking `get` for a whole section has to fail clearly and point to `config show`, and `show` must print the merged config, either all of it or just one part.

**What each route does** (run against every arm's final code):

**Example 1:** `config get agents.coder.temperature` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
agents:
  coder: file:agents/coder.yaml

.troupe/agents/coder.yaml:
model: opus
temperature: 0.2
~~~

- Route 1: all six arms: exit 0, prints `0.2` (it follows the file reference into coder.yaml)

**Example 2:** `config get prompt` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
prompt: file:prompt.txt

.troupe/prompt.txt:
Be concise.
Be kind.
~~~

- Route 1: all six arms: exit 0, prints the file's text:

  ~~~
  Be concise.
  Be kind.
  ~~~


**Example 3:** `config get agents.coder` _(observed)_

- Route 1: all six arms: exit 5, nothing on stdout. All the error messages name the path and point to `troupe config show agents.coder`, but the wording differs. One arm: `/theatre/.troupe/agents/coder.yaml: agents.coder: is a mapping, not a value; print it with `troupe config show agents.coder``. Five arms start with `troupe:` and say 'is a mapping, not a scalar', e.g. `troupe: agents.coder: is a mapping, not a scalar (use `troupe config show agents.coder` to print it)`. One of those five starts with `troupe: error:`.

**Example 4:** `config show tools` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
tools: [git, shell]
~~~

- Route 1: all six arms: exit 0, prints:

  ~~~
  - git
  - shell
  ~~~


**Example 5:** `config show` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
retry: 3  # attempts
name: "demo"
agents:
  coder: file:agents/coder.yaml
tools: [git, shell]
prompt: file:prompt.txt
~~~

- Route 1: all six arms: exit 0, prints:

  ~~~
  retry: 3
  name: demo
  agents:
    coder:
      model: opus
      temperature: 0.2
  tools:
    - git
    - shell
  prompt: |
    Be concise.
    Be kind.
  ~~~


**In practice:** There is only one route, and all six arms gave the same exit codes and output. The only difference is the wording of the error on stderr. `show` prints the resolved config: the referenced files are pulled in, and the `# attempts` comment and the quotes around "demo" are not shown. Nothing on disk changed.

**Trade-off:** Route 1: scripts keep getting plain values from `get`, but anyone who wants a whole section has to switch to `show`, because `get` exits with 5 instead of printing it.

### Route 1

- Route: get keeps step-1 scalar show; collections exit 5 with a message naming the path and `troupe config show`; show takes an optional PATH
- Reasoning given: Scripts keep working through get
- Outcome: Kept
- proposed: 5 - Contract

rating: n/a
reason:

## T98

**Question:** Does history reconcile  
**Kind:** unanimous

**What's at stake:** If you edit a config file by hand and then run `config history`, the log won't show your edit yet. It only gets recorded when some other command reads the config. Until then, history can show an old value as if it were still current.

**What each route does** (run against every arm's final code):

**Example 1:** `config history` (first command ever run in this theatre) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
retry: 3
model: opus
coder: file:agents/coder.yml

.troupe/agents/coder.yml:
temperature: 0.2
role: coder
~~~

- Route 1: All six arms: exit 0. It creates a history store and prints four import entries: seq 1 retry → 3, seq 2 model → opus, seq 3 coder.temperature → 0.2, seq 4 coder.role → coder. Every entry has actor kind "unknown" and via "import", even though TROUPE_ACTOR=human:owner was set.

**Example 2:** Edit by hand: retry 3 → 9 in troupe.yml and temperature 0.2 → 0.7 in coder.yml. Then run `config history`, then `config history retry` _(observed)_

- Route 1: All six arms: exit 0 both times. `config history` still prints only the four import entries. `config history retry` prints only seq 1 (retry → 3), even though the file now says 9. Neither edit is recorded.

**Example 3:** `config get retry`, then `config history` _(observed)_

- Route 1: All six arms: `config get retry` prints `9`. The next `config history` now has two more entries, both with via "file" and actor kind "unknown": seq 5 retry 3 → 9 and seq 6 coder.temperature 0.2 → 0.7. So the hand edits were recorded during `get`, not during `history`.

**Example 4:** `config set model sonnet`, then `config history`, then `config history coder` _(observed)_

- Route 1: All six arms: `set` exits 0 with no output, and troupe.yml now reads:

  ~~~
  retry: 9
  model: sonnet
  coder: file:agents/coder.yml
  History adds seq 7 model opus → sonnet with actor human/owner and via "cli". `config history coder` prints seq 3, 4 and 6.
  ~~~


**In practice:** All six arms on route 1 produced the same results; only timestamps and change IDs differed. On a theatre that was never imported, `history` does import the starting values. After that it never picks up hand edits itself, and they show up only after a command like `get`. The arms named their history store differently: two used history.sqlite, one events.sqlite, one events.sqlite plus events.lock, one events.sqlite3 plus events.sqlite3.lock, and one troupe-state.sqlite.

**Trade-off:** Route 1: `history` is a cheap read with no side effects on a theatre that already has history, but what it shows can be out of date until another command records the hand edits.

### Route 1

- Route: Never reconciles; still imports a never-imported theatre
- Reasoning given: Importing is not reconciling
- Outcome: Kept
- proposed: 5 - Contract

rating: n/a
reason:

## T99

**Question:** How the indent step and sequence offset are chosen for new content  
**Kind:** unanimous

**What's at stake:** When a command adds new nested content, the user needs it to match the indentation the file already uses (4 spaces with indented lists in the main config, 3 spaces with flush lists in the included file). Otherwise their hand-kept layout becomes a mix of styles.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.planner "{model: sonnet, tools: [read, grep], limits: {retries: 3}}"` _(observed)_

Starting file:

~~~
# main config, 4-space indent, indented sequences
agents:
    coder:
        model: opus
        tools:
            - read
            - write
    tester: file:agents/tester.yaml
~~~

- Route 1: exit 0; every arm gave the same result. The file now reads:

  ~~~
  agents:
      coder:
          model: opus
          tools:
              - read
              - write
      tester: file:agents/tester.yaml
      planner:
          model: sonnet
          tools:
              - read
              - grep
          limits:
              retries: 3
  ~~~


**Example 2:** `config set --in-include agents.tester.opts "{mode: strict, steps: [lint, test]}"` _(observed)_

Starting file:

~~~
model: haiku
limits:
   retries: 2
tools:
- read
- grep
~~~

- Route 1: exit 0 for every arm, but the arms differed. Four arms followed the file's flush list style, so .troupe/agents/tester.yaml now ends:

  ~~~
  opts:
     mode: strict
     steps:
     - lint
     - test
  Two arms indented the list items one step further, which doesn't match the existing `tools:` list:
  opts:
     mode: strict
     steps:
        - lint
        - test
  ~~~


**Example 3:** `config set agents.tester.extra "{level: 2, tags: [a, b]}"` (tester is a `file:` reference in the main config) _(observed)_

Starting file:

~~~
    tester: file:agents/tester.yaml
~~~

- Route 1: exit 0; every arm gave the same result. The reference was turned into a `$ref` key in the main file with 4-space indent:

  ~~~
      tester:
          $ref: file:agents/tester.yaml
          extra:
              level: 2
              tags:
                  - a
                  - b
  ~~~


**Example 4:** `config set --expand-alias reviewer.settings.model sonnet` _(observed)_

Starting file:

~~~
defaults: &d
    model: opus
    flags:
        - fast
reviewer:
    settings: *d
~~~

- Route 1: exit 0; every arm gave the same result. The file now reads:

  ~~~
  reviewer:
      settings:  # expanded from *d by troupe
          model: sonnet
          flags:
              - fast
  ~~~


**In practice:** In the 4-space main config, every arm matched the file's style. The only split was in the included file, which uses 3-space mappings with list items flush under their key. Four arms kept that flush list style for the new list. Two arms indented the new list items, so that file ended up with two list styles.

**Trade-off:** Route 1 follows each file's own layout and falls back to 2 spaces. It depends on how well the detection reads the file: here some arms caught the flush-list style and some missed it.

### Route 1

- Route: Detect from the file's existing nesting, defaulting to 2
- Reasoning given: Follow the user's own layout; the contract does not say how to detect it
- Outcome: Kept; one arm made detection anchor-aware at step 6
- proposed: 5 - Follows the file

rating: 4.5
reason: RESLICE placeholder: F (follows flush list style) 5 x4; I (indents, mixes styles) 3 x2

## T100

**Question:** Where a literal block's source comment goes  
**Kind:** unanimous

**What's at stake:** With `config show --sources`, each value is annotated with the file it came from. For multi-line values the annotation has to go somewhere that can't be mistaken for part of the text, such as a prompt line that itself starts with `#`.

**What each route does** (run against every arm's final code):

**Example 1:** `config show agents.reviewer --sources` (reviewer prompt file has a line `# not a comment, just text` and no trailing newline) _(observed)_

- Route 1: exit 0; prints:

  ~~~
  prompt: |- # from .troupe/prompts/reviewer.txt
    You are the reviewer.
    # not a comment, just text
    No trailing newline
  notes: | # from .troupe/troupe.yml
    inline line one
    inline line two
  ~~~


**Example 2:** `config show --sources` _(observed)_

Starting file:

~~~
name: demo  # project
agents:
  coder:
    prompt: file:prompts/coder.txt
    model: opus
  reviewer:
    prompt: file:prompts/reviewer.txt
    notes: |
      inline line one
      inline line two
~~~

- Route 1: exit 0; prints:

  ~~~
  name: demo # from .troupe/troupe.yml
  agents:
    coder:
      prompt: | # from .troupe/prompts/coder.txt
        You are the coder.
        Write small diffs.
      model: opus # from .troupe/troupe.yml
    reviewer:
      prompt: |- # from .troupe/prompts/reviewer.txt
        You are the reviewer.
        # not a comment, just text
        No trailing newline
      notes: | # from .troupe/troupe.yml
        inline line one
        inline line two
  ~~~


**Example 3:** `config set agents.coder.style "keep it short\nand clear\n"` then `config show agents.coder --sources` _(observed)_

- Route 1: set: exit 0; the troupe.yml file now has, under coder:

  ~~~
      style: |
        keep it short
        and clear
  show: exit 0; prints:
  prompt: | # from .troupe/prompts/coder.txt
    You are the coder.
    Write small diffs.
  model: opus # from .troupe/troupe.yml
  style: | # from .troupe/troupe.yml
    keep it short
    and clear
  ~~~


**In practice:** All 6 arms on route 1 gave identical results. On a multi-line value, the source note always goes on the `|` / `|-` line. The text below that line comes out exactly as stored, including lines that start with `#`. The note is never written into the config file itself. Only `show --sources` displays it.

**Trade-off:** Route 1: the source note sits on the block's header line, beside the `|`/`|-` marker. It's a little less obvious there than on a line of its own, but it's never confused with the value's text.

### Route 1

- Route: On the `|` header line
- Reasoning given: Content lines would absorb it
- Outcome: Kept
- proposed: 5 - Forced

rating: n/a
reason:

## T101

**Question:** What the lock covers  
**Kind:** unanimous

**What's at stake:** With `config watch` running in the background while people edit the file by hand and run `config set`, the history should record each change once, in order, under the right actor, and nothing should be lost or overwritten. All six implementations of route 1 did this; they differed only in how watch exits on Ctrl-C and in what files they leave in `.troupe/`.

**What each route does** (run against every arm's final code):

**Example 1:** `config history` (first command run on a fresh project) _(observed)_

Starting file:

~~~
# troupe config
name: demo
retry: 3  # attempts
timeout: 10
model: opus
~~~

- Route 1: all six arms: exit 0; prints 4 import entries (name demo, retry 3, timeout 10, model opus), actor unknown, all sharing one change id. history imports the existing file on its own.

**Example 2:** with `config watch` running: hand-edit `retry: 3` to `retry: 5`, wait 0.3 s, then `TROUPE_ACTOR=agent:bot config set timeout 30 --reason "cli during watch"` _(observed)_

Starting file:

~~~
# troupe config
name: demo
retry: 3  # attempts
timeout: 10
model: opus
~~~

- Route 1: all six arms: exit 0, prints nothing; the file now reads:

  ~~~
  # troupe config
  name: demo
  retry: 5  # attempts
  timeout: 30
  model: opus
  The hand edit was kept, and the comment too. history later shows seq 5 retry 3→5 (via file, actor unknown) and then seq 6 timeout 10→30 (via cli, agent bot, reason "cli during watch").
  ~~~


**Example 3:** still watching: hand-edit `model: opus` to `model: haiku`, wait 0.3 s, then `TROUPE_ACTOR=human:owner config set model sonnet --reason "same key right after hand edit"` _(observed)_

Starting file:

~~~
# troupe config
name: demo
retry: 5  # attempts
timeout: 30
model: opus
~~~

- Route 1: all six arms: exit 0; the file now reads:

  ~~~
  # troupe config
  name: demo
  retry: 5  # attempts
  timeout: 30
  model: sonnet
  history shows seq 7 model opus→haiku (via file, actor unknown) and then seq 8 model haiku→sonnet (via cli, human owner). The hand edit got its own entry before the set, with no duplicates and no missing steps: 8 entries in total.
  ~~~


**Example 4:** Ctrl-C (SIGINT) to stop `config watch` after the above _(observed)_

- Route 1: four arms: exit 0 with nothing on stderr. One arm: exit 0, but stderr shows a Python traceback ("Exception ignored in: <module 'threading' ...> ... KeyboardInterrupt"). One arm: exit 137, meaning it had to be killed instead of exiting on Ctrl-C. In every arm watch printed only its "watching" line: four said "watching /theatre" and two said "watching .".

**Example 5:** list `.troupe/` at the end _(observed)_

- Route 1: all six arms: troupe.yml (74 bytes) plus one 12288-byte history database. Database names vary: history.sqlite in two arms, events.sqlite in two, troupe-state.sqlite in one, events.sqlite3 in one. Two arms also leave an empty lock file (events.lock or events.sqlite3.lock); the other four leave no visible lock file.

**In practice:** Only one route exists. In this run, the history stayed correct with watch running alongside hand edits and `config set`, including a set on a key that had just been hand-edited. The only differences between arms were how watch behaves on Ctrl-C and what files end up in `.troupe/`.

**Trade-off:** Route 1: every command waits for the lock and `set` holds it for its whole run, so a `set` may briefly wait on watch or another command. In return, a hand edit is always recorded before a CLI change lands on top of it.

### Route 1

- Route: Every command (history too) takes it; set holds it through load, reconcile, write and record; watch holds it only per reconcile
- Reasoning given: So watch never sees a write-back before its events exist; history may import
- Outcome: Kept
- proposed: 5 - Exactly-once holds

rating: n/a
reason:

## T102

**Question:** Login source  
**Kind:** unanimous

**What's at stake:** Every change gets stamped with a login name taken from the environment, and `config history` shows that name as the person who made the change. If the name is wrong or missing, the history can't say who changed the setting.

**What each route does** (run against every arm's final code):

**Example 1:** `USER=alice config set retry 1`, then `config history retry` _(observed)_

Starting file:

~~~
retry: 0
name: demo
~~~

- Route 1: exit 0, prints nothing; the file now reads:

  ~~~
  retry: 1
  name: demo
  The history entry for this change shows actor {"kind": "human", "id": "alice"}. All six arms did the same.
  ~~~


**Example 2:** `LOGNAME=bob USER=alice config set retry 3` _(observed)_

- Route 1: exit 0, value stored; the history records "bob". When both are set, LOGNAME wins over USER. All six arms did the same.

**Example 3:** `USERNAME=carol config set retry 4`, then `LNAME=dave USERNAME=carol config set retry 6` _(observed)_

- Route 1: both exit 0, values stored. The first is recorded as "carol". The second is recorded as "dave": LNAME wins over USERNAME. All six arms did the same.

**Example 4:** `config set retry 7` with none of LOGNAME, USER, LNAME or USERNAME set, and no account entry for the user _(observed)_

- Route 1: exit 0, no warning, and retry is now 7. The history entry reads {"kind": "human", "id": null}: the change is saved without saying who made it. All six arms did the same.

**In practice:** The name comes from whichever of these variables is set first, in this order: LOGNAME, USER, LNAME, USERNAME. It works without a terminal. Anyone can claim to be someone else by setting one of these variables. When none is set and there is no account entry, saving still succeeds and gives no warning, and the history records a human with no name.

**Trade-off:** Route 1: always works, even without a terminal, but anyone who sets an environment variable can pick the name, and with nothing set the change is saved with no name and no warning.

### Route 1

- Route: getpass.getuser
- Reasoning given: Works without tty
- Outcome: Kept
- proposed: 5 - Right

rating: n/a
reason:

## T103

**Question:** Other multi-line strings in show  
**Kind:** unanimous

**What's at stake:** When a setting holds text that spans several lines, such as a prompt, `config show` decides whether you see it as readable lines or as one escaped string. It also decides whether that text survives being copied back into the file without changes like lost trailing newlines, stripped spaces or altered line endings.

**What each route does** (run against every arm's final code):

**Example 1:** `config show agents.coder` _(observed)_

Starting file:

~~~
agents:
  coder:
    prompt: "line one\nline two\n"
    no_final_newline: "first\nsecond"
    keep_trailing: "para\n\n\n"
    indented_first: "  indented start\nnext\n"
    trailing_spaces: "spaces after   \nend\n"
    has_cr: "windows\r\nline\r\n"
    has_control: "bell\u0007here\nok\n"
    leading_blank: "\nafter blank\n"
    single_line: "just one line"
~~~

- Route 1: Five arms: exit 0; prints:

  ~~~
  prompt: |
    line one
    line two
  no_final_newline: |-
    first
    second
  keep_trailing: |+
    para
  
  
  indented_first: |2
      indented start
    next
  trailing_spaces: |
    spaces after   
    end
  has_cr: "windows\r\nline\r\n"
  has_control: "bell\ahere\nok\n"
  leading_blank: |
  
    after blank
  single_line: just one line
  
  One arm: exit 0; same output except the text that starts with spaces stays quoted:
  indented_first: "  indented start\nnext\n"
  ~~~


**Example 2:** `config show agents.notes --sources` _(observed)_

Starting file:

~~~
  notes:
    - "item one\nitem two\n"
    - "tab\there\nnext"
~~~

- Route 1: All six arms: exit 0; prints (with a real tab between "tab" and "here"):

  ~~~
  - | # from .troupe/troupe.yml
    item one
    item two
  - |- # from .troupe/troupe.yml
    tab	here
    next
  ~~~


**Example 3:** `config show agents.coder.indented_first` _(observed)_

- Route 1: All six arms: exit 0; prints the raw value with no YAML around it:

  ~~~
    indented start
  next
  ~~~


**In practice:** Text with several lines is shown as indented lines. A marker on the first line records whether the text ends in a newline, has no final newline (`|-`) or keeps extra blank lines at the end (`|+`). Trailing spaces, tabs and a leading blank line are kept. Text with Windows line endings (\r) or control characters stays in one double-quoted line with escapes. The arms on route 1 split only on text whose first line starts with spaces: five show it as lines, using the `|2` indent marker, and one keeps it double-quoted.

**Trade-off:** Route 1: most multi-line text is easy to read and copies back exactly, but you have to read markers like `|-`, `|+` and `|2`, and text with \r or control characters still appears as an escaped one-liner.

### Route 1

- Route: Literal block when it can hold them exactly, else double-quoted
- Reasoning given: Readable and exact
- Outcome: Kept
- proposed: 5 - Good

rating: n/a
reason:

## T104

**Question:** How set writes a new multi-line string  
**Kind:** unanimous

**What's at stake:** When someone sets a value that contains line breaks, the YAML file has to stay valid and give back exactly the same text, including leading spaces and trailing blank lines. It should also look like something a person would write by hand. Values inside an inline `{...}` map can't use the indented block style, so they need a different form there.

**What each route does** (run against every arm's final code):

**Example 1:** `config set app.desc "line one\nline two"` _(observed)_

Starting file:

~~~
app:
  name: demo  # the name
  flow: {a: 1}
  # trailing comment about app
other: x
~~~

- Route 1: All six arms: exit 0, no output; the file now reads:

  ~~~
  app:
    name: demo  # the name
    flow: {a: 1}
    # trailing comment about app
    desc: |-
      line one
      line two
  other: x
  (The new key goes in after the trailing comment. The `# the name` comment is kept.)
  ~~~


**Example 2:** `config set app.flow.b "x\ny\n"` (the key is inside the inline map `{a: 1}`) _(observed)_

- Route 1: All six arms: exit 0, no output; that line now reads:

  ~~~
    flow: {a: 1, b: "x\ny\n"}
  (The value is double-quoted with `\n` escapes, and the map stays inline.)
  ~~~


**Example 3:** `config set app.lead " indented first\nnext\n"` (the first line starts with two spaces) _(observed)_

- Route 1: The arms split 3–3. All exit 0 with no output. Three arms write a double-quoted line:

  ~~~
    lead: "  indented first\nnext\n"
  The other three write a literal block with an explicit indent marker:
    lead: |2
        indented first
      next
  ~~~


**Example 4:** `config set app.tail "a\nb\n\n\n"` (the value ends in blank lines) _(observed)_

- Route 1: All six arms: exit 0, no output; the file now has:

  ~~~
    tail: |+
      a
      b
  
  
  other: x
  (The `|+` marker keeps the trailing blank lines.)
  ~~~


**Example 5:** `config show app` (after the four sets above) _(observed)_

- Route 1: All six arms: exit 0. Five arms print the same thing, no matter how they stored `lead`:

  ~~~
  name: demo
  flow:
    a: 1
    b: |
      x
      y
  desc: |-
    line one
    line two
  lead: |2
      indented first
    next
  tail: |+
    a
    b
  
  
  One arm (one that wrote `lead` quoted) prints it as `lead: "  indented first\nnext\n"`. Its other lines are the same.
  ~~~


**In practice:** Normal multi-line text becomes an indented `|` block that's easy to read. Inside an inline `{...}` map it becomes a quoted string with `\n` escapes. The arms only differ on text that starts with spaces: half of them fall back to a quoted string, and half write a `|2` block. In every arm, a new key goes after any comment that sits at the end of its section.

**Trade-off:** Route 1: the file always reads back exactly, but a multi-line value's style depends on where it sits (block vs quoted), and text with leading spaces gets either a quoted line or a less familiar `|2` block, depending on the arm.

### Route 1

- Route: Literal block in block context; double-quoted in flow context or when a literal block cannot hold it exactly
- Reasoning given: YAML forbids block scalars in flow; the result must read back. One arm also double-quotes when a literal would swallow deeper-indented comments; another fixed a bug that sent all multi-line strings to double quotes
- Outcome: Kept
- proposed: 5 - Readable and exact

rating: n/a
reason:

## T105

**Question:** What the files are compared against to find hand edits  
**Kind:** unanimous

**What's at stake:** When someone edits the config files by hand, the edit is recorded only if it differs from the configuration troupe last recorded. The user relies on this to get history that shows who changed what, without fake entries and without missing edits.

**What each route does** (run against every arm's final code):

**Example 1:** edit `.troupe/troupe.yml` by hand (model opus -> haiku) and `.troupe/agents/coder.yaml` by hand (temperature 0.2 -> 0.5), then `TROUPE_ACTOR=agent:bot config set retry 4`, then `config history` _(observed)_

Starting file:

~~~
model: opus
retry: 3
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: All six arms: exit 0; troupe.yml now reads:

  ~~~
  model: haiku
  retry: 4
  agents:
    coder: file:agents/coder.yaml
  The history lists seq 5 `model` opus -> haiku and seq 6 `agents.coder.temperature` 0.2 -> 0.5. Both are marked "via file" with actor unknown and grouped as one change. Seq 7 is `retry` 3 -> 4 by agent bot via cli. The set's own write to the file creates no extra entry.
  ~~~


**Example 2:** edit troupe.yml by hand to `retry: 7`, then edit it again to `retry: 4 # restored`, with no troupe command in between; then `config get retry` and `config history` _(observed)_

Starting file:

~~~
model: haiku
retry: 4
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: All six arms: `config get retry` prints 4. The history is unchanged and still ends at seq 7. The value 7 is never recorded, and adding the comment records nothing.

**Example 3:** edit troupe.yml by hand to `model: sonnet`, then `TROUPE_ACTOR=agent:bot troupe --theatre . config set model sonnet`, then `config history` _(observed)_

Starting file:

~~~
model: haiku
retry: 4  # restored
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: Five arms: exit 2 with a usage error like `invalid choice: '.' (choose from config)`. The wording differs between arms. Nothing is recorded, and the history still ends at seq 7, so the hand edit to sonnet does not appear. One arm: exit 0, and the history gains seq 8 `model` haiku -> sonnet, "via file" with actor unknown. The hand edit is credited to the file, not to the bot, and the bot's set adds no entry because the value already matched.

**In practice:** A hand edit is recorded as the difference between the files and the last recorded configuration, and only when a later command checks for it. Changes in between are lost: an edit that is undone before the next run never appears. Running `config history` alone after a hand edit did not show that edit.

**Trade-off:** Route 1: there are no fake entries from troupe's own writes and edits made while troupe isn't running are still caught, but values changed and changed back between runs leave no trace.

### Route 1

- Route: The recorded configuration (projection of the events), diffed leaf by leaf against the loaded files
- Reasoning given: Idempotent; catches offline edits; a set's own write-back then shows no difference
- Outcome: Kept
- proposed: 5 - Exactly-once with no self-write bookkeeping

rating: n/a
reason:

## T106

**Question:** Which quoting style a changed or new string gets  
**Kind:** unanimous

**What's at stake:** When you set a value, the tool decides how it is quoted in troupe.yml. That decides whether the file stays the way you wrote it, and whether a value like `true` comes back as text or as a yes/no flag.

**What each route does** (run against every arm's final code):

**Example 1:** `config set a "🎭 bravo"` _(observed)_

Starting file:

~~~
a: 'x'
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  a: '🎭 bravo'
  The single quotes were kept with the emoji (all 6 arms the same)
  ~~~


**Example 2:** `config set b "'nbsp here'"` _(observed)_

Starting file:

~~~
b: plain
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  b: nbsp here
  The line stays unquoted, as it was, and the quotes you typed are dropped (all 6 arms the same)
  ~~~


**Example 3:** `config set e "'true'"` _(observed)_

Starting file:

~~~
e: yes-ish
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  e: 'true'
  The line was unquoted before, but now gets single quotes so it is read as text, not as a yes/no value (all 6 arms the same)
  ~~~


**Example 4:** `config set d '"tab\there"'` (double-quoted, with a \t escape) _(observed)_

Starting file:

~~~
d: 'one'
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  d: 'tab	here'
  The single quotes were kept, and the \t became a real tab character between the words (all 6 arms the same)
  ~~~


**Example 5:** `config set m.k2 "'🎭 new'"` (new key) _(observed)_

Starting file:

~~~
m:
  k1: 'v1'
~~~

- Route 1: exit 0, no output; the file now reads:

  ~~~
  m:
    k1: 'v1'
    k2: '🎭 new'
  The new key gets single quotes, not plain text (all 6 arms the same)
  ~~~


**In practice:** If a line already has a quoting style that can hold the new value, the line keeps that style. If it can't, the tool picks a different style: a `yes-ish` line set to the text `true` gets single quotes. A new key whose value contains an emoji also got single quotes, even though unquoted comes first in the fallback order. One arm changed how it decides which characters count as printable (non-breaking space, emoji) after review. In these runs all six arms produced the same file.

**Trade-off:** Route 1 keeps your file's existing quoting wherever it can. In exchange, a value can be written differently depending on which line it lands on, for example a real tab inside single quotes.

### Route 1

- Route: Keep the existing style if it can hold the value; otherwise plain, then single, then double
- Reasoning given: The contract's fallback order
- Outcome: Kept; one arm fixed its printable check (NBSP, emoji) after review
- proposed: 5 - Contract rule

rating: n/a
reason:

## T107

**Question:** Use the library's resolver or an own YAML 1.2 core-schema resolver for plain scalars  
**Kind:** unanimous

**What's at stake:** This choice decides what a hand-written value in troupe.yml becomes when the tool reads it. For example, it decides whether `2024-01-15` stays text or becomes a date, whether `yes` or `on` becomes a boolean, and whether `.inf` becomes a number. It also decides whether `config set` stores what you typed or rewrites it.

**What each route does** (run against every arm's final code):

**Example 1:** `config history` (the starting file is imported and each value's type is shown) _(observed)_

Starting file:

~~~
date: 2024-01-15
big: 1_000
flag: yes
switch: on
octal: 0o17
legacy: 017
hex: 0x1F
sexa: 1:30
exp: 1e3
inf: .inf
nul: ~
num: +12
~~~

- Route 1: exit 0. All six arms agree on everything except `inf`: date -> "2024-01-15" (text), big -> "1_000" (text), flag -> "yes" (text), switch -> "on" (text), octal -> 15, legacy -> 17 (decimal, not octal), hex -> 31, sexa -> "1:30" (text), exp -> 1000.0, nul -> null, num -> 12. For `inf`, two arms give ".inf" (text) and four arms give `Infinity`, a bare token in the history output.

**Example 2:** `config set when 2024-02-01` _(observed)_

- Route 1: All six arms: exit 0. The file gains the line `when: 2024-02-01`, and history records "2024-02-01" as text, not a date.

**Example 3:** `config set flag 0x1F` (flag was `yes`) _(observed)_

Starting file:

~~~
flag: yes
~~~

- Route 1: All six arms: exit 0, and history records old "yes" -> new 31. Three arms rewrite your input, so the file now reads:

  ~~~
  flag: 31
  The other three keep your spelling, so the file now reads:
  flag: 0x1F
  ~~~


**Example 4:** `config set retry -1e3` _(observed)_

- Route 1: One arm: exit 0. The file gains `retry: -1e3`, and history records -1000.0. Five arms: exit 2 and nothing is stored, because `-1e3` is taken as an option and the error says the value argument is missing. The message wording differs between arms, and two of them also print the usage text.

**In practice:** Each of the six arms behaved differently somewhere. Plain words such as dates, `yes`/`on`, `1_000` and `1:30` reliably stay text, and hex, `0o` octal and `1e3` become numbers. However, `.inf` is text in some arms and `Infinity` in others. Setting a hex number rewrites the file to `31` in half the arms. Only one arm accepts a negative number like `-1e3` as a value; in the rest it fails as a missing argument.

**Trade-off:** Route 1: one set of typing rules for both the file and typed values. The cost is that edge cases (`.inf`, whether hex input is kept as typed, values with a leading `-`) came out differently from arm to arm.

### Route 1

- Route: Own YAML 1.2 core-schema resolver for both file values and VALUE
- Reasoning given: The library resolver reads dates as timestamps and 1_000 as an int, which departs from the 1.2 core schema; one place holds the typing rules
- Outcome: Kept
- proposed: 5 - Typing exactly matches the contract

rating: n/a
reason:

## T108

**Question:** How show produces YAML  
**Kind:** unanimous

**What's at stake:** `config show` is how a user reads the merged configuration back. What matters is whether each value prints in a form that means the same thing as the source (`on` vs `'on'`, a date vs a string, `0x1F` vs `31`), whether multi-line text stays readable, and whether `--sources` reliably says which file each value came from.

**What each route does** (run against every arm's final code):

**Example 1:** `config show flags` _(observed)_

Starting file:

~~~
flags: [on, "true", yes, "null", null, 0x1F, '', "café — ok"]
~~~

- Route 1: exit 0. Five arms agree on the rest of the list, but `on` and `yes` differ.

  ~~~
  Four arms print `on` and `yes` bare, as in the source:
  - on
  - 'true'
  - yes
  - 'null'
  - null
  - 31
  - ''
  - café — ok
  One arm quotes them:
  - 'on'
  - 'true'
  - 'yes'
  - 'null'
  - null
  - 31
  - ''
  - café — ok
  In every arm, `0x1F` comes out as `31`.
  ~~~


**Example 2:** `config show` (the `released` line) _(observed)_

Starting file:

~~~
released: 2026-10-09
~~~

- Route 1: exit 0. Five arms print `released: 2026-10-09`. One arm (the same one that quotes `on` and `yes`) prints `released: '2026-10-09'`.

**Example 3:** `config show` (the `banner` line, read from banner.txt) _(observed)_

Starting file:

~~~
banner.txt:
  indented first line
second line
~~~

- Route 1: exit 0. Five arms print it as a block:

  ~~~
  banner: |2-
      indented first line
    second line
  One arm prints it as a single escaped line:
  banner: "  indented first line\nsecond line"
  ~~~


**Example 4:** `config show agents.reviewer --sources` _(observed)_

Starting file:

~~~
troupe.yml:
  reviewer:
    $ref: file:agents/coder.yaml
    temperature: 0.7
    tools:
      - review
~~~

- Route 1: exit 0 in all six arms, with identical output. Each value is tagged with the file it came from:

  ~~~
  model: opus # from .troupe/agents/coder.yaml
  temperature: 0.7 # from .troupe/troupe.yml
  tools:
    - review # from .troupe/troupe.yml
  notes: |- # from .troupe/agents/coder.yaml
    line one
    line two
  folded: | # from .troupe/agents/coder.yaml
    first part of a sentence
  ~~~


**Example 5:** `config show` (the `folded` key in coder.yaml) _(observed)_

Starting file:

~~~
folded: >
  first part
  of a sentence
~~~

- Route 1: exit 0 in all six arms. The folded block comes out already joined, as a literal block:

  ~~~
  folded: |
    first part of a sentence
  ~~~


**Example 6:** `config show agents.coder.tools --sources` _(observed)_

Starting file:

~~~
tools:
  - name: grep
    args: ["-n", "x: y", "#tag"]
  - shell
~~~

- Route 1: exit 0 in all six arms, with identical output. Strings that contain `: ` or start with `#` are quoted, so the source comments never get mixed into the values:

  ~~~
  - name: grep # from .troupe/agents/coder.yaml
    args:
      - -n # from .troupe/agents/coder.yaml
      - 'x: y' # from .troupe/agents/coder.yaml
      - '#tag' # from .troupe/agents/coder.yaml
  - shell # from .troupe/agents/coder.yaml
  ~~~


**In practice:** There is only one route, and all six arms on it behave the same way on structure, merging, `--sources` tagging, key quoting (`'key: with # colon': plain`) and empty values (`{}`, `[]`). Adding `--sources` only adds `# from …` comments; the values themselves don't change. The arms differ on three things. Four arms print `on`, `yes` and the date exactly as the source wrote them, while one arm quotes all three. Five arms show multi-line file text as an indented block, while one arm squeezes the banner onto one escaped line. In every arm, `0x1F` is printed as `31` and a folded `>` block is printed as joined text under `|`.

**Trade-off:** Route 1 owns its quoting rules, so each arm decides for itself how unusual scalars appear (`on`/`yes`, dates, text with leading spaces). That is why the arms disagree on exactly those values.

### Route 1

- Route: Own emitter over the source-mapped tree; lines tagged with sources; --sources only adds comments
- Reasoning given: A dumper hides which line holds which scalar and decides quoting itself
- Outcome: Kept
- proposed: 5 - Exact control

rating: n/a
reason:

## T109

**Question:** show's YAML layout  
**Kind:** unanimous

**What's at stake:** This sets what `config show` prints: whether the YAML is readable, whether you can paste it back as valid config, and whether the values keep their meaning. For example, the string "yes" should stay a string and not turn into a boolean.

**What each route does** (run against every arm's final code):

**Example 1:** `config show` _(observed)_

Starting file:

~~~
project:
    name: demo
    tags: [alpha, beta]
    empty_map: {}
    empty_list: []
    flags:
        verbose: true
        level: 0.2
agents:
    - name: coder
      tools:
          - shell
          - - nested1
            - nested2
      opts: {}
    - name: reviewer
      notes: "yes"
      prompt: file:prompt.txt
      matrix: [[1, 2], [], {}]
~~~

- Route 1: exit 0 in all six arms. The layout is the same everywhere: 2-space indent, inline lists expanded to `- ` items, empty values shown as {} and [], and the prompt file's text inlined as a `|` block. Five arms print:

  ~~~
  project:
    name: demo
    tags:
      - alpha
      - beta
    empty_map: {}
    empty_list: []
    flags:
      verbose: true
      level: 0.2
  agents:
    - name: coder
      tools:
        - shell
        - - nested1
          - nested2
      opts: {}
    - name: reviewer
      notes: yes
      prompt: |
        You review code.
        Be concise.
      matrix:
        - - 1
          - 2
        - []
        - {}
  One arm prints the same output except for one line:
      notes: 'yes'
  ~~~


**Example 2:** `config show agents.0.tools` _(observed)_

- Route 1: exit 0 in all six arms, which print:

  ~~~
  - shell
  - - nested1
    - nested2
  ~~~


**Example 3:** `config show project --sources` _(observed)_

- Route 1: exit 0 in all six arms. Each value gets a source comment; empty {} and [] get none:

  ~~~
  name: demo # from .troupe/troupe.yml
  tags:
    - alpha # from .troupe/troupe.yml
    - beta # from .troupe/troupe.yml
  empty_map: {}
  empty_list: []
  flags:
    verbose: true # from .troupe/troupe.yml
    level: 0.2 # from .troupe/troupe.yml
  ~~~


**Example 4:** `config show --sources` (reviewer agent part) _(observed)_

- Route 1: exit 0 in all six arms. The prompt is credited to the prompt file. Five arms print:

  ~~~
    - name: reviewer # from .troupe/troupe.yml
      notes: yes # from .troupe/troupe.yml
      prompt: | # from .troupe/prompt.txt
        You review code.
        Be concise.
      matrix:
        - - 1 # from .troupe/troupe.yml
          - 2 # from .troupe/troupe.yml
        - []
        - {}
  One arm prints the same except:
      notes: 'yes' # from .troupe/troupe.yml
  ~~~


**In practice:** All arms produce the same layout. The one difference is the string "yes": five arms print it unquoted as `notes: yes`, and many YAML readers load that as the boolean true. If you paste that output back into the config, the meaning can change. One arm prints `'yes'` in quotes, so it stays a string.

**Trade-off:** Route 1: easy-to-read output in the common 2-space style. In most arms it prints strings like "yes" without quotes, so the output can change meaning if you paste it back as config.

### Route 1

- Route: 2-space indent, compact items, {} and []
- Reasoning given: Common style
- Outcome: Kept
- proposed: 5 - Clear

rating: n/a
reason:

## T110

**Question:** How show output is checked  
**Kind:** unanimous

**What's at stake:** Whether the output of `show` can be trusted to match what is actually stored. If it can't, a user may copy or re-load printed settings and quietly get different values.

**In practice:** There is only one route here, and every implementation took it. Route 1 keeps the part that produces `show` output as a plain formatter: it only turns stored settings into text and does nothing else. Tests check that output by reading the printed text back in and confirming it gives the same settings that went in. For a user, this means values that are easy to get wrong in text, such as negative numbers, values starting with a dash, empty strings, or quoted text, should look in `show` exactly like what was stored. For a maintainer, any change to the output format that would make the printed text read back differently should fail the tests straight away. Nothing could be run, so none of this was observed.

**Trade-off:** Route 1 costs a reader, or an equivalent check, that can parse the printed text, and those tests only confirm the output reads back correctly. They don't pin down its exact look or layout.

### Route 1

- Route: Round-trip tests
- Reasoning given: Pure renderer
- Outcome: Kept
- proposed: 5 - Good

rating: n/a
reason:

## T111

**Question:** show of a scalar without --sources  
**Kind:** unanimous

**What's at stake:** When you run `config show <key>` without `--sources`, the output should be exactly what `config get <key>` prints. Otherwise scripts and people reading `show` would see a different value than `get` reports for the same key.

**What each route does** (run against every arm's final code):

**Example 1:** `config show temperature`, then `config get temperature` _(observed)_

Starting file:

~~~
temperature: 1e3   # YAML 1.2 float
~~~

- Route 1: All six implementations: both exit 0 and print the same line:

  ~~~
  1000.0
  ~~~


**Example 2:** `config show prompt` _(observed)_

Starting file:

~~~
prompt: file:prompt.txt

.troupe/prompt.txt:
Be terse.
No preamble.
~~~

- Route 1: All six implementations: exit 0; prints the file's contents, not the `file:` reference:

  ~~~
  Be terse.
  No preamble.
  ~~~


**Example 3:** `config show notes` _(observed)_

Starting file:

~~~
notes: |+
  line one
  line two
~~~

- Route 1: All six implementations: exit 0; prints the text with the trailing blank line kept (`|+` keeps it):

  ~~~
  line one
  line two
  ~~~


**Example 4:** `config show fallback` _(observed)_

Starting file:

~~~
fallback: ~
~~~

- Route 1: All six implementations: exit 0; prints:

  ~~~
  null
  ~~~


**In practice:** There is only one route here, and all six implementations behaved the same way. No command changed any file.

**Trade-off:** Route 1: `show` uses the same printing code as `get`, so the two always match. Whatever `get` prints (for example, `1000.0` for `1e3`) is also what `show` prints.

### Route 1

- Route: Printed exactly as get prints it through the same function
- Reasoning given: Holds by construction
- Outcome: Kept
- proposed: 5 - Contract

rating: n/a
reason:

## T112

**Question:** Are the files or the event store the source of current values  
**Kind:** unanimous

**What's at stake:** When two agents load the same included settings file, changing one agent's value either silently changes the other agent's value too, or is refused. Every implementation reads current values from the files, so the outcome depends on how each one handles that shared file.

**What each route does** (run against every arm's final code):

**Example 1:** `config history` (first run on the starting files) _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
# two agents share one settings file
a: file:shared.yml
b: file:shared.yml  # same include

.troupe/shared.yml:
model: opus  # shared
temperature: 0.2
~~~

- Route 1: All six arms: exit 0; four import entries (a.model=opus, a.temperature=0.2, b.model=opus, b.temperature=0.2), each with actor kind "unknown" and via "import".

**Example 2:** `TROUPE_ACTOR=human:owner config set a.model sonnet` _(observed)_

Starting file:

~~~
.troupe/shared.yml:
model: opus  # shared
temperature: 0.2
~~~

- Route 1: Three arms: exit 0, no output; .troupe/shared.yml now reads:

  ~~~
  model: sonnet # shared
  temperature: 0.2
  (the two spaces before the comment became one). Three arms: exit 3, no file changed, each with a different message: "troupe: a.model: the edited files would not read back as intended; not writing" / "troupe: a.model: cannot write this change byte-surgically; no file changed" / "troupe: a.model: write-back would disturb b.model".
  ~~~


**Example 3:** `config get b.model` (after that set) _(observed)_

- Route 1: Three arms (the ones that wrote): prints `sonnet`, so b changed even though only a was set. Three arms (the ones that refused): prints `opus`.

**Example 4:** `config show --sources` _(observed)_

- Route 1: All six arms: exit 0; every value is labelled `# from .troupe/shared.yml`. Three arms show model: sonnet for both a and b; three arms show model: opus for both.

**Example 5:** `config history b` _(observed)_

- Route 1: Three arms that wrote: the two import entries, then `{"seq": 6, "op": "set", "path": "b.model", "old": "opus", "new": "sonnet", "actor": {"kind": "human", "id": "owner"}, "via": "cli", ...}`, so b's history records the change the owner made through a. Three arms that refused: only the two import entries.

**In practice:** There is only one route, and its six arms split evenly. In half of them, setting one agent's value in a shared include also changes it for every agent using that file, records the change in each agent's history, and changes the comment spacing on the edited line. In the other half, the set is refused with exit 3 and the files stay untouched, so you have to edit the shared file yourself (or split it) to change the value.

**Trade-off:** Route 1 always treats the files as the truth, but depending on the arm a set on a shared include either changes every agent that uses it or is refused outright.

### Route 1

- Route: Files on disk are authoritative; show and set read the files; the store is change history only
- Reasoning given: A projection would show stale values after a hand edit; matches 'importing is not reconciling'
- Outcome: Kept; the 'hand edits produce no events' part was superseded by reconcile at step 2 in every arm
- proposed: 5 - Cannot hide or lose a user's edit

rating: n/a
reason:

## T113

**Question:** show PATH --sources on a scalar  
**Kind:** unanimous

**What's at stake:** When you ask where a single value comes from, you need output that names the file it was read from and is still valid YAML, including values pulled in from a separate text file.

**What each route does** (run against every arm's final code):

**Example 1:** `config show model --sources` _(observed)_

Starting file:

~~~
.troupe/troupe.yml:
model: opus  # main model
retries: 3
prompt: file:prompts/system.txt
agents:
  coder: file:agents/coder.yaml
~~~

- Route 1: exit 0; prints:

  ~~~
  opus # from .troupe/troupe.yml
  (the file's own `# main model` comment is not shown; no files changed)
  ~~~


**Example 2:** `config show agents.coder.temperature --sources` _(observed)_

Starting file:

~~~
.troupe/agents/coder.yaml:
temperature: 0.2
name: "Coder"
~~~

- Route 1: exit 0; prints:

  ~~~
  0.2 # from .troupe/agents/coder.yaml
  (gives the included file, not troupe.yml)
  ~~~


**Example 3:** `config show prompt --sources` _(observed)_

Starting file:

~~~
.troupe/prompts/system.txt:
You are helpful.
Be brief.
~~~

- Route 1: exit 0; prints a literal block:

  ~~~
  | # from .troupe/prompts/system.txt
    You are helpful.
    Be brief.
  ~~~


**Example 4:** `config show prompt` (no --sources) _(observed)_

- Route 1: exit 0; prints the plain text:

  ~~~
  You are helpful.
  Be brief.
  ~~~


**Example 5:** `config show agents.coder --sources` _(observed)_

- Route 1: exit 0; prints:

  ~~~
  temperature: 0.2 # from .troupe/agents/coder.yaml
  name: Coder # from .troupe/agents/coder.yaml
  (the quotes around "Coder" are dropped)
  ~~~


**In practice:** All six implementations on route 1 gave exactly the same results, and no command changed any file. With --sources, a single value prints on one line with a `# from <file>` comment. A value that comes from an included text file becomes a `|` block with the comment on its first line. Without --sources, you get just the raw value.

**Trade-off:** Route 1: the output for one value is valid YAML and names its source file, but text from an included file changes shape (indented block instead of plain text) when you add --sources, and the original file's comments and quotes are not kept.

### Route 1

- Route: One-scalar YAML with the comment; a text include becomes a literal block
- Reasoning given: A bare value cannot carry a source
- Outcome: Kept
- proposed: 5 - Consistent

rating: n/a
reason:

## T114

**Question:** How the CLI is tested  
**Kind:** unanimous

**What's at stake:** Whether the command-line tool people actually type behaves exactly as promised. If it isn't tested the way people really run it, the tool can pass every check and still print wrong text, give the wrong exit status, or not start at all once installed.

**In practice:** There is only one route here (route 1), and every implementation took it. Every scenario the tool is supposed to handle has its own test. Each test runs the command against a throwaway sample project (a temporary 'theatre') and compares what gets printed against the expected output character for character. Some tests run the command inside the test process and some start it as a separate program. On top of that, one check launches the tool the way a real user would, through the installed `troupe` command, to confirm it starts. For a user, this means the printed messages and exit statuses they see are the ones that were checked, and the tool is known to start from a real install. For a maintainer, it means any change to wording, spacing or exit status fails a test, even when the change was intended. So deliberate changes to output also mean updating the expected text. The tests never touch a real project, because each one builds and discards its own.

**Trade-off:** Route 1: strong guarantees that the output matches and the tool starts from a real install, but every intended change to wording or spacing means updating the expected text, and the tests that start a separate program run more slowly.

### Route 1

- Route: Byte-exact CLI tests against temporary theatres (in-process or subprocess), plus a real `uv run troupe` smoke test
- Reasoning given: Prove the entry point; every scenario maps to a test
- Outcome: Kept
- proposed: 5 - Appropriate

rating: n/a
reason:

## T115

**Question:** What watch compares new bytes against  
**Kind:** unanimous

**What's at stake:** While `config watch` runs, it has to tell troupe's own writes apart from hand edits. If it gets this wrong, a troupe write shows up twice in history as an unknown file edit. Or a hand edit gets skipped, even one that puts back text troupe wrote earlier, and the change never appears in history.

**What each route does** (run against every arm's final code):

**Example 1:** with `config watch` running: `TROUPE_ACTOR=agent:setter config set model sonnet --reason "via troupe while watching"`, then wait 3s _(observed)_

Starting file:

~~~
model: opus
retry: 3
~~~

- Route 1: all six arms: exit 0, no output; the file now reads:

  ~~~
  model: sonnet
  retry: 3
  History later shows exactly one entry for it: seq 3, opus -> sonnet, actor agent:setter, via cli, with the reason. The watcher did not add a second "via file" entry for troupe's own write.
  ~~~


**Example 2:** still watching: edit .troupe/troupe.yml by hand to `model: haiku`, then wait 3s _(observed)_

Starting file:

~~~
model: sonnet
retry: 3
~~~

- Route 1: all six arms: the watcher picked it up. History seq 4: sonnet -> haiku, actor unknown, via file.

**Example 3:** still watching: edit the file by hand back to `model: sonnet` (the same text troupe wrote earlier), then wait 3s _(observed)_

Starting file:

~~~
model: haiku
retry: 3
~~~

- Route 1: all six arms: recorded, not skipped as "troupe's own text". History seq 5: haiku -> sonnet, actor unknown, via file. Afterwards `config get model` -> sonnet, and history has 5 entries in total (2 import, 1 cli, 2 file).

**Example 4:** `config watch`, later stopped with Ctrl-C (SIGINT) _(observed)_

- Route 1: all six arms stop with exit 0. Four arms print `watching /theatre` (the absolute path); two arms print `watching .`. One of those two also prints a Python traceback to stderr on Ctrl-C ("Exception ignored in: <function Application.__del__ …> … KeyboardInterrupt"), though it still exits 0. The other five print nothing on stderr.

**In practice:** In this run, history came out the same on every arm. Each change landed once, under the right actor. Where they differ: the arms keep history in differently named files under .troupe/ (history.sqlite, events.sqlite, troupe-state.sqlite or events.sqlite3), and two also leave a 0-byte lock file. The watching line shows either the absolute path or `.`. One arm prints a noisy traceback when you press Ctrl-C.

**Trade-off:** Route 1 has to re-read every included file and both root names after each sync to rebuild its snapshot. That extra reading buys it a guarantee: no edit made between the load and the watching line can be missed.

### Route 1

- Route: The exact texts the last load read (all includes plus both root names, absent files as None), rebuilt after each sync
- Reasoning given: No edit can slip between load and the watching line. One arm reworked from a pre-load snapshot after review
- Outcome: Kept
- proposed: 5 - No gap

rating: n/a
reason:

## T116

**Question:** A config that breaks while watch runs  
**Kind:** unanimous

**What's at stake:** While `config watch` is running, the config can go briefly broken: a file is saved half-written, or an include points at a file that doesn't exist yet. What matters is whether watch stays up, says what's wrong without flooding the terminal, keeps the broken state out of history, and picks up the fix on its own.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch` running; edit `.troupe/troupe.yml` to add `coder: file:agents/coder.yaml` before that file exists; 2 s later create `.troupe/agents/coder.yaml` with `model: sonnet` _(observed)_

Starting file:

~~~
model: opus
~~~

- Route 1: All six arms: watch keeps running and prints the missing-include error once on stderr. Once the file exists, it picks it up. `config history` then shows seq 2 `set coder.model` null -> "sonnet" via file, and nothing for the broken moment. The wording differs by arm, e.g. `troupe: .troupe/agents/coder.yaml: included file not found (from .troupe/troupe.yml)` or `/theatre/.troupe/troupe.yml: coder: include target /theatre/.troupe/agents/coder.yaml does not exist or is not a regular file`.

**Example 2:** with watch still running, save `.troupe/agents/coder.yaml` as broken YAML; 3 s later fix it _(observed)_

Starting file:

~~~
model: sonnet
~~~

- Route 1: All six arms: watch stays up and prints the YAML error once on stderr, even though the broken file sat there for about 3 s. Nothing is recorded while it's broken. After the fix to `model: haiku`, history gets seq 3 `set coder.model` "sonnet" -> "haiku" and `config show` prints:

  ~~~
  model: opus
  coder:
    model: haiku
  How much detail the error gives varies by arm. Four arms print one line (two with line and column, one with the line only, one with neither), e.g. `troupe: .troupe/agents/coder.yaml: invalid YAML (line 2, column 14): expected ',' or ']', but got ':'`. Two arms print the parser's multi-line output with caret markers pointing at `model: [sonnet` and `temperature: : 0.3`.
  ~~~


**Example 3:** Ctrl-C (SIGINT) to stop `config watch` _(observed)_

- Route 1: Five arms: exit 0. One arm: exit 137. The starting line also differs: four arms print `watching /theatre` and two print `watching .`.

**In practice:** On this route all six arms do what the route says: each problem is reported once, nothing broken is recorded, and watch resumes by itself when the file is fixed. The test only checked local files. It didn't exercise the noted difference where one arm retries failed remote fetches only after a local change.

**Trade-off:** Route 1: you never get stale or broken entries in history, but while the config is broken the error on stderr is the only sign, and how much it tells you depends on the arm (one terse line or the parser's full multi-line output).

### Route 1

- Route: Report on stderr (each distinct message once), record nothing, retry every tick, resume when it loads
- Reasoning given: Editors save partial files; retrying catches new include targets. One arm did not state de-duplication
- Outcome: Kept; at step 7 one arm retries failed fetches only after a local change
- proposed: 5 - Robust

rating: n/a
reason:

## T117

**Question:** SIGINT/SIGTERM handling  
**Kind:** unanimous

**What's at stake:** This route is about stopping `config watch` with Ctrl-C or a kill/stop signal. The user needs it to stop cleanly, report success to scripts or service managers, and leave the history database whole, without a traceback or a half-written change. The six implementations on this route did not behave alike: exit codes ranged over 0, 130, 143 and 137.

**What each route does** (run against every arm's final code):

**Example 1:** `config watch`, hand-edit `.troupe/troupe.yml` to `retry: 5`, wait 3 s, send SIGTERM _(observed)_

Starting file:

~~~
retry: 4
~~~

- Route 1: two arms: exit 0. Four arms: exit 143 (the usual code for a process ended by SIGTERM). In all six, stdout was only the `watching …` line and stderr was empty, so no traceback. The 4→5 change was recorded in every arm: a later `config history` shows `{"seq": 2, "op": "set", "path": "retry", "old": 4, "new": 5, … "via": "file" …}`

**Example 2:** `config watch --theatre .`, then send SIGTERM right away (no edit) _(observed)_

- Route 1: two arms: exit 0, and `.troupe` holds only the database and `troupe.yml` as before. Two arms: exit 143, files unchanged. Two arms: exit 137 (the code a process gets when it is force-killed, i.e. it did not stop on SIGTERM), and two extra files are left next to the database: `events.sqlite-shm 32768 bytes` and `events.sqlite-wal 0 bytes` in one arm, `troupe-state.sqlite-shm` / `troupe-state.sqlite-wal` in the other. All six: stderr empty

**Example 3:** `config watch`, hand-edit to `retry: 6`, press Ctrl-C (SIGINT) immediately, then `config history` _(observed)_

Starting file:

~~~
retry: 5
~~~

- Route 1: four arms: exit 0. One arm: exit 130. One arm: exit 137 (force-killed). All six: stderr empty. In every arm `config history` shows only two entries, `import` of 4 and `set` 4→5. The edit to 6 made just before Ctrl-C was not recorded by any arm, but `troupe.yml` still reads `retry: 6`

**In practice:** Only one route was tested, but the six arms on it did not agree. Just two arms exited 0 on every signal. The others reported a signal-style exit code (143 or 130), so a service manager or script would see a failure. In some runs (two arms on SIGTERM, one on Ctrl-C) the watcher did not stop on the signal and was force-killed (137), and twice that left database side-files behind. Nothing in this test showed a partial or corrupted history entry. When the signal came right after an edit, every arm stopped without recording that edit.

**Trade-off:** Route 1: shutdown is clean and never prints a traceback, but a file edit made just before the signal is not recorded, and in practice the exit code was not reliably 0.

### Route 1

- Route: Handlers only set a flag/Event; an in-progress reconcile finishes; exit 0; previous handlers restored
- Reasoning given: Never a partial transaction or traceback
- Outcome: Kept
- proposed: 5 - Clean

rating: 3.5
reason: RESLICE placeholder: C (exit 0 cleanly) 5 x2; S (143/130) 4; K (force-killed 137, leaves side files) 2

## T118

**Question:** How set changes a file  
**Kind:** unanimous

**What's at stake:** When `config set` changes one value in a hand-edited `.troupe/troupe.yml`, everything else in the file should stay exactly as the user wrote it. That covers comments, column alignment, quoting style, hex numbers, inline `{...}` maps and wrapped text blocks. If they get reformatted, a one-value change shows up as a noisy diff and the user's layout is gone.

**What each route does** (run against every arm's final code):

**Example 1:** `config set agents.coder.temp 0.35` _(observed)_

Starting file:

~~~
agents:
    coder:
        model: "opus"    # model
        temp: 0.2        # temperature

    # trailing comment in coder block
~~~

- Route 1: all six arms behaved the same. Exit 0, no output; the file now reads:

  ~~~
  agents:
      coder:
          model: "opus"    # model
          temp: 0.35       # temperature
  
      # trailing comment in coder block
  The comment stays in the same column, and every other line of the file is unchanged.
  ~~~


**Example 2:** `config set name "a much longer new name"` _(observed)_

Starting file:

~~~
name: 'old name'      # single-quoted
~~~

- Route 1: all six arms behaved the same. Exit 0, no output; the line now reads:

  ~~~
  name: 'a much longer new name' # single-quoted
  The single quotes and the comment are kept. The comment moves right with a single space before it because the value is longer.
  ~~~


**Example 3:** `config set flags.c 3` _(observed)_

Starting file:

~~~
flags: {a: 1, b: [x, y]}   # flow style
~~~

- Route 1: five arms: exit 0; the line now reads:

  ~~~
  flags: {a: 1, b: [x, y], c: 3} # flow style
  (the gap before the comment shrinks to one space). One arm: exit 0; the line now reads:
  flags: {a: 1, b: [x, y], c: 3}   # flow style
  (the original three-space gap is kept). In both cases the map stays on one line in `{...}` form.
  ~~~


**Example 4:** `config set desc '"Changed folded text in the first paragraph only.\n\nSecond paragraph stays exactly as written.\n"'` _(observed)_

Starting file:

~~~
desc: >
  This is a folded
  paragraph that wraps.

  Second paragraph stays
  exactly as written.
~~~

- Route 1: all six arms behaved the same. Exit 0, no output; the block now reads:

  ~~~
  desc: >
    Changed folded text
    in the first
    paragraph only.
  
  
    Second paragraph stays
    exactly as written.
  The block keeps its `>` wrapped-text form. The new first paragraph is broken over three short lines, and there are now two blank lines between the paragraphs, which matches the two `\n`s in the typed value.
  ~~~


**Example 5:** `config get retry` (after all the sets above) _(observed)_

Starting file:

~~~
retry: 0x1F           # hex int
~~~

- Route 1: all six arms behaved the same. Exit 0 and prints `31`. The file line `retry: 0x1F # hex int` was never touched by the earlier sets.

**In practice:** Only the value being set changes. The `0x1F` hex value, `yes`, `~`, the extra spaces after `version:`, the header comment and the trailing comment in the `coder` block all came through every set exactly as written. The arms differed in one place only: when a value grows inside an inline `{...}` map, most arms shrink the gap before that line's comment to one space, and one arm keeps the original gap.

**Trade-off:** Route 1: the rest of the file stays byte-for-byte as written, but every kind of value needs its own patching code. Edge cases such as comment spacing after a longer value or how a rewritten wrapped-text block is broken into lines depend on that code.

### Route 1

- Route: Splice replacement text into the original at the node's span; never re-serialise the file
- Reasoning given: Re-dumping normalises indentation, quoting, comments and folded scalars; splicing leaves untouched bytes alone
- Outcome: Kept
- proposed: 5 - The only way to meet a byte-surgical contract

rating: n/a
reason:
