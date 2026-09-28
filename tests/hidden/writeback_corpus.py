"""Step 1 write-back golden corpus: nasty YAML + hand-written expected output.

Started from spike A's Q9 corpus (spike-config-roundtrip/tests/q9_corpus.py), with out-of-contract
cases removed and expected bytes changed where the owner's rules (scenario/contract.md, "set PATH VALUE")
differ from what the spike did. GOLDENS ARE WRITTEN BY HAND, NEVER GENERATED FROM THE REFERENCE.

Each case: exact bytes before, `set` ops applied one CLI call at a time, exact bytes after.
`expect`: "splice" (success, exit 0), "error" (write refused, exit 3), "path" (path error, exit 5).
On a non-zero exit the file must be unchanged, so `after == before`."""
from dataclasses import dataclass


@dataclass
class Case:
    name: str
    group: str
    before: str
    ops: list  # [(dotted path, value)]
    after: str
    expect: str = "splice"
    note: str = ""


CASES: list[Case] = []


def case(*a, **k):
    CASES.append(Case(*a, **k))


# ------------------------------------------------------------------ block scalars
G = "block scalars"
case("literal | change one line", G,
     "name: demo\nprompt: |\n  line one\n  line two\n  line three\nafter: 1\n",
     [("prompt", "line one\nline 2\nline three\n")],
     "name: demo\nprompt: |\n  line one\n  line 2\n  line three\nafter: 1\n")
case("literal |- (strip) change one line", G,
     "script: |-\n  echo a\n  echo b\nnext: 1\n",
     [("script", "echo a\necho B")],
     "script: |-\n  echo a\n  echo B\nnext: 1\n")
case("literal |+ (keep) with trailing blank lines", G,
     "keep: |+\n  x\n  y\n\n\nnext: 1\n",
     [("keep", "x\nY\n\n\n")],
     "keep: |+\n  x\n  Y\n\n\nnext: 1\n")
case("explicit indentation indicator |2", G,
     "code: |2\n    indented first\n  normal\nnext: 1\n",
     [("code", "  indented first\nchanged\n")],
     "code: |2\n    indented first\n  changed\nnext: 1\n")
case("clip block followed by blank lines", G,
     "a: |\n  x\n\n\nb: 1\n",
     [("a", "y\n")],
     "a: |\n  y\n\n\nb: 1\n")
case("block followed by a comment", G,
     "a: |\n  x\n  y\n# about b\nb: 1\n",
     [("a", "x\nz\n")],
     "a: |\n  x\n  z\n# about b\nb: 1\n")
case("block header with comment", G,
     "a: |  # keep me\n  x\nb: 1\n",
     [("a", "y\n")],
     "a: |  # keep me\n  y\nb: 1\n")
case("plain -> multi-line (EOL comment moves to header)", G,
     "a: short  # note\nb: 1\n",
     [("a", "line1\nline2\n")],
     "a: |      # note\n  line1\n  line2\nb: 1\n",
     note="the header replaces the value on the key line; the comment returns to its old column 10")
case("plain -> multi-line without final newline uses |-", G,
     "a: short\nb: 1\n",
     [("a", "line1\nline2")],
     "a: |-\n  line1\n  line2\nb: 1\n")
case("multi-line -> plain", G,
     "a: |\n  x\n  y\n\nb: 1\n",
     [("a", "single")],
     "a: single\n\nb: 1\n")
case("block scalar as sequence item", G,
     "steps:\n  - |\n    echo a\n    echo b\n  - done\n",
     [("steps.0", "echo a\necho c\n")],
     "steps:\n  - |\n    echo a\n    echo c\n  - done\n")
case("block scalar at EOF without trailing newline", G,
     "a: 1\nb: |-\n  x\n  y",
     [("b", "x\nz")],
     "a: 1\nb: |-\n  x\n  z",
     note="last line of file has no line break")
case("chomping change: clip value gains trailing newlines -> |+", G,
     "a: |\n  x\nb: 1\n",
     [("a", "x\n\n")],
     "a: |+\n  x\n\nb: 1\n",
     note="header indicator changes because the value's trailing newlines changed; that is part of the value")

# ------------------------------------------------------------------ comments everywhere
G = "comments"
case("comments above keys", G,
     "# top\n# about a\na: 1  # eol\n# about b\nb: 2\n",
     [("b", 3)],
     "# top\n# about a\na: 1  # eol\n# about b\nb: 3\n")
case("file with no trailing newline; change + add", G,
     "a: 1\nb: 2",
     [("b", 3), ("c", 4)],
     "a: 1\nb: 3\nc: 4")
case("commented-out key after mapping; add", G,
     "a:\n  x: 1\n#  y: 2\nb: 1\n",
     [("a.z", 3)],
     "a:\n  x: 1\n  z: 3\n#  y: 2\nb: 1\n")
case("explicit document start marker and header comment", G,
     "---\n# config\na: 1\n",
     [("a", 2), ("b", 3)],
     "---\n# config\na: 2\nb: 3\n")

# ------------------------------------------------------------------ flow collections
G = "flow collections"
case("flow mapping: change one, add one", G,
     "m: {a: 1, b: 2}  # flow\n",
     [("m.b", 3), ("m.c", 4)],
     "m: {a: 1, b: 3, c: 4} # flow\n",
     note="the flow mapping (the value on this line) grew past the comment's column 17, so one space")
case("flow sequence: change one, append one", G,
     "l: [x, y]\n",
     [("l.0", "z"), ("l.2", "w")],
     "l: [z, y, w]\n")
case("nested flow; quote style kept; append inside", G,
     "m: {l: [1, 2], s: 'q'}\n",
     [("m.s", "r"), ("m.l.2", 3)],
     "m: {l: [1, 2, 3], s: 'r'}\n")
case("flow value that needs quoting", G,
     "l: [x, y]\n",
     [("l.0", "a, b")],
     "l: ['a, b', y]\n")
case("empty flow collections", G,
     "m: {}\nl: []\n",
     [("m.a", 1), ("l.0", "x")],
     "m: {a: 1}\nl: [x]\n")
case("multi-line flow mapping", G,
     "m: {\n  a: 1,\n  b: 2\n}\n",
     [("m.b", 3), ("m.c", 4)],
     "m: {\n  a: 1,\n  b: 3, c: 4\n}\n",
     note="appended element joins the last line rather than getting its own line")

# ------------------------------------------------------------------ lists
G = "lists"
case("change an item in a block list", G,
     "tools:\n  - bash\n  - edit  # the editor\n  - web\n",
     [("tools.1", "write")],
     "tools:\n  - bash\n  - write # the editor\n  - web\n",
     note="EOL comment returns to its old column (10); the longer value reaches it, so one space")
case("append to a block list", G,
     "tools:\n  - bash\n  - edit\nnext: 1\n",
     [("tools.2", "web")],
     "tools:\n  - bash\n  - edit\n  - web\nnext: 1\n")
case("two indentation styles in one file", G,
     "a:\n- x\n- y\nb:\n    - p\n    - q\n",
     [("a.2", "z"), ("b.2", "r"), ("b.0", "P")],
     "a:\n- x\n- y\n- z\nb:\n    - P\n    - q\n    - r\n")
case("list of mappings: append a mapping, add key to an item", G,
     "agents:\n  - name: a\n    model: x\n",
     [("agents.1", {"name": "b", "model": "y"}), ("agents.0.temp", 0.1)],
     "agents:\n  - name: a\n    model: x\n    temp: 0.1\n  - name: b\n    model: y\n")
case("append to a list whose last item is a nested list", G,
     "m:\n  - - 1\n    - 2\n  - x\n",
     [("m.2", "y")],
     "m:\n  - - 1\n    - 2\n  - x\n  - y\n")

# ------------------------------------------------------------------ quoting
G = "quoting"
case("plain stays plain", G, "k: v  # c\n", [("k", "w")], "k: w  # c\n")
case("single-quoted with apostrophe in new value", G,
     "k: 'v'\n", [("k", "it's")], "k: 'it''s'\n")
case("double-quoted with escapes", G,
     'k: "tab\\there \\u00e9"\n', [("k", "new\tval é")], 'k: "new\\tval é"\n',
     note="ruamel emits the tab as \\t; é stays literal (original used a \\u escape for it)")
case("plain -> needs quoting: contains ': '", G, "k: v\n", [("k", "a: b")], "k: 'a: b'\n")
case("plain -> needs quoting: contains ' #'", G, "k: v\n", [("k", "x # y")], "k: 'x # y'\n")
case("plain -> needs quoting: starts with '*'", G, "k: v\n", [("k", "*star")], "k: '*star'\n")
case("plain -> needs quoting: string that looks like a bool/int", G,
     "a: v\nb: v\n", [("a", "true"), ("b", "123")], "a: 'true'\nb: '123'\n")
case("quoted string -> int keeps it an int (type change is the edit)", G,
     'k: "8000"\n', [("k", 9000)], "k: 9000\n")

# ------------------------------------------------------------------ layout
G = "layout"
case("blank lines between sections and key order preserved; add in middle section", G,
     "a: 1\n\n\nb:\n  c: 2\n\n  d: 3\n\n\ne: 4\n",
     [("b.c", 5), ("b.x", 6), ("f", 7)],
     "a: 1\n\n\nb:\n  c: 5\n\n  d: 3\n  x: 6\n\n\ne: 4\nf: 7\n")
case("deep new path creates intermediate mapping in place", G,
     "a:\n  b: 1\n\nz: 0\n",
     [("a.c.d.e", 1)],
     "a:\n  b: 1\n  c:\n    d:\n      e: 1\n\nz: 0\n")
case("scalar -> mapping keeps EOL comment on the key line", G,
     "model: 'opus'  # default\nnext: 1\n",
     [("model", {"name": "opus", "temperature": 0.2})],
     "model:  # default\n  name: opus\n  temperature: 0.2\nnext: 1\n")

# ------------------------------------------------------------------ unicode / CRLF / tabs
G = "encoding"
case("unicode values and comments", G,
     "name: café ✓  # ünïcode\nemoji: 🎭\n",
     [("name", "naïve ✓✓"), ("emoji", "🎭🎭")],
     "name: naïve ✓✓ # ünïcode\nemoji: 🎭🎭\n",
     note="comment was at column 14 (code points); the new value ends at 14, so one space")
case("CRLF line endings: change, append, block scalar, add key", G,
     "a: 1\r\nb:\r\n  - x\r\n  - y\r\nc: |\r\n  one\r\n  two\r\n",
     [("a", 2), ("b.2", "z"), ("c", "one\nthree\n"), ("d", 4)],
     "a: 2\r\nb:\r\n  - x\r\n  - y\r\n  - z\r\nc: |\r\n  one\r\n  three\r\nd: 4\r\n")
case("tabs inside comment text", G,
     "a: 1  # tab\there\n#\tindented\tcomment\nb: 2\n",
     [("a", 5), ("b", 6)],
     "a: 5  # tab\there\n#\tindented\tcomment\nb: 6\n")

# ------------------------------------------------------------------ structural / anchors / nulls
G = "structural"
case("mapping -> scalar (key-line comment kept, next-section comment kept)", G,
     "m:  # c\n  x: 1\n  y: 2\n# next\nn: 1\n", [("m", "flat")], "m: flat # c\n# next\nn: 1\n",
     note="comment was at column 4; the new value ends at 7, so one space")
case("mapping -> mapping", G,
     "m:  # c\n  x: 1\nn: 1\n", [("m", {"z": 9})], "m:  # c\n  z: 9\nn: 1\n")
case("list -> list keeps the list's dash indentation", G,
     "l:\n    - 1\nn: 1\n", [("l", [7, 8])], "l:\n    - 7\n    - 8\nn: 1\n")
case("null (`a:`) -> scalar", G, "a:\nb: 1\n", [("a", 5)], "a: 5\nb: 1\n")
case("null with comment -> multi-line", G, "a:  # c\nb: 1\n", [("a", "x\ny\n")], "a: | # c\n  x\n  y\nb: 1\n",
     note="comment was at column 4; the block header ends at 4 (reaches it), so one space")
case("null gains a child key", G, "a:\nb: 1\n", [("a.c", 5)], "a:\n  c: 5\nb: 1\n")
case("add key that needs quoting / has a space", G,
     "a: 1\n", [("my key", 1), ("x: y", 2)], "a: 1\nmy key: 1\n'x: y': 2\n")
case("aligned values", G, "a:     1\nbb:    2\n", [("a", 10)], "a:     10\nbb:    2\n")

# ------------------------------------------------------------------ spike cases whose goldens the owner's rules change
# (the spike's versions re-emitted changed folded paragraphs on one line, switched to `|` on more-indented
# lines, kept EOL-comment spacing bytes, put new entries ABOVE trailing comments, and wrote new keys plain)
G = "block scalars"
# folded paragraph re-wrapped to its previous width (longest content line "Second para" = 11 columns)
case("folded > change second paragraph, first stays wrapped", G,
     "desc: >\n  This is a long\n  wrapped paragraph.\n\n  Second para\n  here.\nnext: 1\n",
     [("desc", "This is a long wrapped paragraph.\nSecond paragraph changed.\n")],
     "desc: >\n  This is a long\n  wrapped paragraph.\n\n  Second\n  paragraph\n  changed.\nnext: 1\n",
     note="changed paragraph re-wrapped greedily at 11 columns; a word wider than that takes its own line")
# width 7 ("one two")
case("folded >- change", G,
     "summary: >-\n  one two\n  three\nnext: 1\n",
     [("summary", "one two four")],
     "summary: >-\n  one two\n  four\nnext: 1\n")
# folded value gaining a more-indented line is refused
G = "structural"
case("folded value gains a more-indented line -> refused", G,
     "d: >\n  para one\nn: 1\n", [("d", "para one\n  indented\n")], "d: >\n  para one\nn: 1\n",
     expect="error")
G = "comments"
# end-of-line comments return to their old column (b: '#' at col 11; c: '#' at col 6, value now reaches col 5)
case("EOL comments with varied spacing (1 space, 6 spaces)", G,
     "a: 1 # one space\nb: 22      # six\nc: x  # two\n",
     [("b", 7), ("c", "yy")],
     "a: 1 # one space\nb: 7       # six\nc: yy # two\n")
# appended list item goes below the trailing comment
case("comments between list items; change + append", G,
     "l:\n  - a\n  # between\n  - b\n  # after last\nnext: 1\n",
     [("l.1", "c"), ("l.2", "d")],
     "l:\n  - a\n  # between\n  - c\n  # after last\n  - d\nnext: 1\n")
# D4: new mapping key goes below the mapping's trailing comment
case("comments inside nested mappings; change + add", G,
     "outer:\n  # c1\n  inner:\n    # c2\n    k: v  # c3\n    # c4\n  other: 1\n",
     [("outer.inner.k", "w"), ("outer.inner.new", 1)],
     "outer:\n  # c1\n  inner:\n    # c2\n    k: w  # c3\n    # c4\n    new: 1\n  other: 1\n")
case("comment at end of file; change + add root key", G,
     "a: 1\nb: 2\n# trailing comment\n",
     [("b", 3), ("c", 4)],
     "a: 1\nb: 3\n# trailing comment\nc: 4\n")
G = "structural"
# new keys copy their neighbours' quoting
case("JSON-style file (it's YAML too): change + add", G,
     '{"a": 1, "b": [1, 2]}\n', [("a", 5), ("c", 6)], '{"a": 5, "b": [1, 2], "c": 6}\n')

# ------------------------------------------------------------------ owner rules the spike corpus lacks
G = "owner rules"
case("new string value copies the preceding sibling's double quotes", G,
     'a: "x"\nb: "y"\n', [("c", "z")], 'a: "x"\nb: "y"\nc: "z"\n')
case("new key copies single-quoted sibling key style", G,
     "'a': 1\n", [("b", 2)], "'a': 1\n'b': 2\n")
case("new key in a mapping with no siblings is plain", G,
     "m: {}\n", [("m.k", "v")], "m: {k: v}\n")
case("comment column kept when value shrinks", G,
     "model: claude-opus-5-5 # m\n", [("model", "opus")], "model: opus            # m\n")
case("comment column: value grows past it -> one space", G,
     "model:   opus        # default model\nbudget:  5           # USD\n",
     [("model", "claude-opus-5-5")],
     "model:   claude-opus-5-5 # default model\nbudget:  5           # USD\n")
case("folded: unchanged paragraphs keep bytes when another paragraph changes", G,
     "d: >\n  one\n  two\n\n  three\n  four\nn: 1\n",
     [("d", "one two\nthree four five\n")],
     "d: >\n  one\n  two\n\n  three\n  four\n  five\nn: 1\n",
     note="second paragraph width 5; 'three four five' wraps to three/four/five")
case("append to a list with no trailing comment", G,
     "l:\n  - a\nn: 1\n", [("l.1", "b")], "l:\n  - a\n  - b\nn: 1\n")
case("index beyond list length is refused as path error", G,
     "l:\n  - a\n", [("l.5", "b")], "l:\n  - a\n", expect="path")
