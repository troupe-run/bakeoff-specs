# Commits (29, newest first)

Each commit's short SHA and subject, then its message body.

## ce00206 feat(config-aliases): validate the issue #2 scenario end to end

These tests pin the reporter's exact file and the three outcomes the issue
asks for, byte for byte and for both troupe.yml and troupe.yaml:
- setting coder's model through `*d` is refused and points to --expand-alias,
  with nothing changed;
- setting `defaults.model` changes everyone;
- `--expand-alias` gives coder its own commented copy, while reviewer keeps
  the shared value.


## bd2656d feat(config-aliases): accept --expand-alias on set and validate it end to end

The issue #2 reporter asked for an explicit way to give coder its own copy of
the shared settings. `set --expand-alias coder.settings.model sonnet` now
writes exactly `settings:  # expanded from *d by troupe` / `model: sonnet`,
and `defaults` and `reviewer` stay byte-identical.

The flag takes no value. It may stand anywhere among the arguments and
combines with --reason and --in-include; `--expand-alias=TEXT` is a usage
error. End-to-end tests cover nested aliases, list items, no-ops, the flag
with no alias, and every refusal naming the user's PATH.


## b0c5669 feat(config-aliases): expand aliases before setting in the set use case

With expansion requested, the set use case expands one alias at a time in
memory, reloads and re-checks until no alias on PATH remains. It then runs the
usual set on the expanded configuration, so "sets the value in the copy" uses
every earlier write rule. Verification, events and restore all compare with
the original files, so expansion records no event and a failed write puts the
original bytes back.

After each round the setter also checks that the whole configuration is
unchanged. The review found that YAML anchor redefinition can make a copied
inner alias bind to another anchor and silently change values elsewhere.
Refusing that case is the conservative choice.


## 6955d0b feat(config-aliases): validate writes at anchors end to end

These tests pin the issue reporter's expectation that changing
`defaults.model` changes everyone. Through the real CLI, a set at an anchor
writes only at the anchor and keeps `&name`. The change appears at every alias
and every `<<: *d` use, but not where an own key shadows it. History records
one event per changed path in one cli change.

The tests compare whole files byte for byte and cover replacements and kind
changes of anchored nodes, own-key writes beside `<<`, and the issue #2 file.


## 3e56861 feat(config-aliases): run the guard in set and refuse writes through aliases and merge keys

This is the fix for issue #2. `set coder.settings.model sonnet` used to be
able to change `defaults` and every other agent through `*d`. It now exits 3
before any file changes, and stderr names the file, PATH and `*d` and
mentions `--expand-alias`.

The guard runs after target resolution and before the no-op check, so a no-op
through an alias is refused too (choice 17). It also covers merge keys, a
used anchor and an anchored include. The temporary blanket refusal is
removed, so a set at the anchor now writes and reaches every alias.


## 556fb2b feat(config-aliases): keep an anchor on a block list item that is replaced by a collection

`- &d k: 1` makes `&d` the anchor of the key, and `- &d - 1` is not YAML.
Replacing an anchored list item with a mapping or list was therefore refused
by read-back, although 4.3 says the anchor stays on the new value. Such an
item now keeps `- &d` alone on its line, with the collection on the lines
below it. Unanchored items keep the compact form, byte for byte as before.


## 0fb300f feat(config-aliases): replicate a replacement of an anchored node itself to its alias places

"Changing it at the anchor changes it everywhere" must hold when the anchored
node itself is replaced, for example `set defaults.model sonnet` on a scalar
anchor or a kind change. Before, the replacement was recorded only under its
parent's slot, so the intended configuration missed it at every alias place.
Read-back then refused a correct write.

The replacement is now also recorded at the anchored node's own location, so
alias places and merge uses see it. A merge source replaced by a non-mapping
is refused by read-back (exit 3) instead of crashing.

The review found that an anchored block list item replaced by a mapping
loses its anchor to the key. That is task 3.9, added before the end-to-end
anchor writes.


## f3ef120 feat(config-aliases): expand collection aliases into block copies

The issue #2 reporter needs coder's settings as their own copy, so that they
can override them without changing reviewer or defaults. An alias of a
mapping or list now becomes `key:  # expanded from *d by troupe` with a
block copy below it.

The copy uses the file's indentation, dash offset and line breaks, and keeps
key and scalar spelling. It copies includes as written and keeps inner aliases
as aliases. It never repeats an anchor, so every other alias still refers to
the original. At the end of a file without a final line break, it adds none
unless a block scalar needs it to keep its value.


## bedb2b9 feat(config-aliases): expand an alias on its line with the troupe comment

`--expand-alias` must give one place its own copy without touching the
anchor or the other aliases. The expander rewrites only the alias's line:
the alias becomes the anchored scalar (in its source style), an empty
collection, or a block scalar re-indented in place, followed by
`  # expanded from *<name> by troupe`.

It refuses to expand in a flow collection, on a line that already has a
comment (which would be lost or altered), and when the copy would have to
write a merge key. Collection copies follow in 3.7.


## 2a6a884 spec(config-aliases): restore the blank line before the decision records heading


## 9ec066d feat(config-aliases): refuse removing a used anchor and converting an anchored include

Removing an anchored node that a remaining alias still uses would leave a
file that no longer loads. The planner now refuses that before writing and
names the anchor and the alias that uses it (4.6). Removing an anchor
together with all its aliases is still planned. Deleting an anchored list
item now takes its `&name` with it.

Converting an anchored scalar-form include to mapping form is refused (4.7),
because no written rule says where the anchor goes.

The review found that replacing an anchored node itself fails read-back. That
is task 3.8, added to the plan before the end-to-end anchor writes (4.2).


## 35cf11c feat(config-aliases): write own keys of a mapping that has a merge key

A mapping with `<<` shows a merged view, but only its own entries are written
in it. The planner now changes own entries in place, adds new keys after the
last written entry (which may be `<<`), and deletes own entries around it.
It never writes, empties or re-renders the merge key (9.1, 9.3).

Any write that would touch a merged value, including a whole replacement of
the mapping, is refused with the guard's message. That way the planner is
safe even if a caller skips the guard.


## 48d2ac5 feat(config-aliases): decide refuse, expand or proceed for a set, and index anchor uses

Issue #2 happened because a set through an alias was written at the anchor.
One guard now decides, before planning, whether a set is reached through an
alias place or a merge key:
- an alias place is refused, or expanded when the flag is given;
- a merge key is always refused;
- anything else proceeds.

"Reached through" follows the requirements' definition side by side across
include layers. A key written in an include's own overrides is not refused
just because the include's `$ref` is an alias. The conservative leftovers
are recorded in research.md.

The anchor-use index lets the planner refuse removing an anchor that is
still used (4.6).


## 0ce11ff feat(config-aliases): replicate changes through merge keys when building the intended configuration

Read-back verification compares the files with an intended configuration
rebuilt from written locations. Alias places already share the anchor's
locations, but mappings with `<<` were rebuilt from their merged view, so a
change at an anchor never reached them. Verification would then wrongly
refuse a correct anchor write.

Such mappings are now rebuilt from the mapping as written and merged again.
The merge-key precedence rule moves into merge_keys.merged_pairs, so the
loader and verification cannot disagree about what a merge key means.


## 899ed16 feat(config-aliases): teach the file layout about anchor properties, alias places and merge-key mappings

Write rules find extents, entry ends, insertion points, comments and the
indentation step by walking the nodes written in a file. Three things now
fit that walk:
- An anchored value starts after its `&name` property, so every existing
  replacement keeps the anchor.
- An alias place is a leaf at its `*name` token, not a second copy of the
  anchor's text.
- A mapping with `<<` is walked as written.
Files without these constructs lay out exactly as before.


## 8c09781 feat(config-aliases): validate that every command reads the expanded configuration

The design relies on readers working unchanged once the loader expands
aliases and merge keys. These end-to-end tests pin that through the real CLI:
- get, show and show --sources print expanded values and correct file labels;
- import and reconcile record events at every alias and merged path;
- a hand expansion into an equal copy records nothing;
- watch picks up an edit at an anchor.
No reader code needed to change.


## 294ba2c feat(config-aliases): load merge keys into the merged view

The step 6 contract names merge keys, so files that use them must load
(requirements choice 1). A plain `<<` merges its mapping sources the way YAML
defines it. The mapping as written is kept behind the merged view, so the
writer can reach the physical entries and never write `<<`.

Includes are refused as merge sources (exit 4). Combining the `$ref` merge with
the merge-key merge has no defined meaning, so refusing is the conservative
choice. The `<<` text now has one home in constants.py.


## cac7eca feat(config-aliases): build alias places in the expanded configuration

Every reader should see what YAML means, so each alias is now built as its
own place holding the anchored node's content. Its origins point at the
anchor's written spans, which later lets a write at the anchor be copied to
every alias place by written location.

Each place records its alias, so the writer can refuse or expand writes
through it. deep_merge keeps that provenance behind $ref overrides, so an
alias stays visible even when an override is merged over it.

An alias used as a key or inside its own anchored node is refused, as is an
undefined alias. The temporary set refusal still blocks every configuration
with aliases until the write guard exists (4.1).


## a871f25 feat(config-aliases): accept anchors on values, with value spans that exclude the property

Theatres that share settings with anchors could not be read at all (decision
H). Anchors on values now load. The node's span leaves out the `&name`
property, so later write rules that start at the value keep the anchor.
Anchors on keys and tags written next to an anchor stay refused.

Two guards keep this step safe on its own:
- Every alias is a load error until alias places exist (2.2). Otherwise it
  would silently load as a plain copy.
- `set` refuses any configuration with an anchor, alias or merge key until
  the write guard exists (4.1), so no commit in between can reproduce
  issue #2.


## 47c0c69 feat(config-aliases): compose each file while recording every alias occurrence

ruamel's composer gives the anchored node itself at an alias, so the alias's
own position is lost. A compose_node hook records each `*name` token by parent
and slot before it is resolved. That is the only way to give the writer the
alias's position and to tell an alias place from its anchor.

The loader composes through the hook without changing anything users see.
A reused anchor name no longer leaks ruamel's warning to stderr.


## dc81dcc feat(config-aliases): record anchors, alias places and merge keys in the model and merge merge-key sources

The writer must tell a value written at an anchor from one reached through an
alias or a merge key, while readers keep working on one expanded tree. The
model therefore carries that provenance next to the nodes it describes, as
step 5 does for $ref layers.

The merge-key merge is a pure function, so the loader (task 2.3) and the
intended-configuration rebuild (task 3.2) share one definition of YAML merge
semantics: own keys first, then earlier sources.


## a821846 spec(config-aliases): record the product owner's approval of the implementation plan

The product owner confirmed the plan, the design clarifications that came with
it, and the temporary set refusal between tasks 2.1 and 4.1. Implementation can
start.


## 8514a80 spec(config-aliases): generate the implementation plan and record design clarifications

The plan has 5 groups and 18 sub-tasks covering all 51 requirement IDs. It
passed an independent task-graph review after one repair round.

- Safety window: anchors load from task 2.1, but the write guard only
  arrives in 4.1. A temporary set refusal, pinned by tests, keeps any commit
  in between from writing through an alias or a merge key, which is the
  reported bug.
- Test files: every test lives in this spec's own files, so the final
  traceability check is not confused by earlier specs' Req numbers.

Planning also showed that deep_merge drops anchor, alias and merge on the
merged mapping. The design now requires keeping them, otherwise the guard
would miss aliases behind $ref overrides. The refusal order and the
verification contract of the expansion loop are written down too. These
are clarifications and change no behaviour.


## 171b912 spec(config-aliases): record the product owner's approval of the design

The product owner confirmed the anchor-write, refusal, expansion and
merge-key behaviour as the contract's meaning. They accepted the design-level
choices (copies holding `<<`, removing a used anchor, flow and comment cases)
as ours. Recording which is which tells later steps which decisions can be
revisited.


## c9ec8ef spec(config-aliases): design an expanded tree with alias places, a write guard and in-memory expansion

ruamel composes an alias as the anchored node itself, so the alias's own
position is lost. A compose_node hook records each occurrence by parent and
slot instead.

Alias places are rebuilt per path with the anchor's origins and marked with
AliasRef, so every reader sees the expanded value. A write at the anchor is
replicated to every alias place by the existing written-location machinery
(step 5 choice 18).

One guard decides refuse, expand or proceed before the no-op check, which
keeps no-op sets through an alias refused (5.3). Expansion is done in
memory, then reloaded, then followed by the unchanged set pipeline. That
makes "set the value in the copy" literally a normal set, with one atomic
write and one read-back.


## e04c3f6 spec(config-aliases): record the product owner's approval of the requirements

The product owner confirmed the anchor, alias, --expand-alias and merge-key
rules as the contract's meaning. They accepted our choices where the
contract is silent: reading merge keys, several aliases on one path, the
flag with no alias, flow collections, and key lines that already have a
comment. Recording which choices are confirmed and which are our own tells
the design and later steps which ones can be revisited.


## 7e9eb73 spec(config-aliases): generate requirements for anchors, aliases, merge keys and --expand-alias

Pin down what issue #2 and the step 6 "Aliases" section mean in observable
terms: anchors, aliases and merge keys load, and every command sees the
expanded configuration. A set at an anchor changes every alias. A set
reached through an alias exits 3 and points to --expand-alias, which writes
a commented block copy and sets the value only there. Merge keys are never
written.

Merge keys now load instead of staying exit 4 as the brief proposed. The
contract names them, so files that use them are in contract, and loading
them cannot change a byte. Seventeen choices where the contract is silent
are listed with conservative defaults for product owner review.


## 79cbad6 spec(config-aliases): initialise the step 6 aliases spec from the discovery brief

The brief already states who has the problem (issue #2), the current state
(anchors refused, decision H) and the step 6 outcome, so requirements can
start from it directly.


## 2627541 discovery(config-aliases): plan step 6 aliases from tracker issue #2

Issue #2 asks that a set through an alias must not silently change every
other user of the anchor. On main, anchors are still refused (decision H),
so the reported corruption cannot happen today, but neither can any theatre
that uses anchors be read. The step 6 "Aliases" contract makes them
loadable, with writes at the anchor, exit 3 through an alias, and
--expand-alias. Record the approach (expanded tree with per-node alias
provenance, following the step 5 layers pattern) and the open choices with
conservative defaults so requirements can settle them.

