# Commits (37, newest first)

Each commit's short SHA and subject, then its message body.

## a8eb266 feat(config-include-overrides): note the step 1 read-back example as superseded and check traceability

config-set-writeback 14.2 named a file included at more than one place as a
reason to refuse; under choice 18 that alone no longer refuses. Requirements
4.8 and 11.1-11.5 are each named by tests.


## c9627db feat(config-include-overrides): write agreeing keys once and refuse conflicting ones for one shared location

Choice 18: when one VALUE asks for the same written location of a shared file
at two places, agreeing values are written once and conflicting ones are
refused with exit 3, because no single write can give both. Placements and
slot changes are grouped by written location instead of loaded object.


## 6fb0c82 feat(config-include-overrides): replicate every written change at every place that reaches its location

Choice 18: no contract rule refuses a write because its file is included more
than once, so existing values, --in-include, list-item keys, appends, removals
and text-include replacements are written to the shared file and the intended
configuration carries the change to every place reaching that written
location, merged with each place's own overrides. The widening is computed
only from the pre-write files and refuses changes not reached from PATH.


## cd9a351 spec(config-include-overrides): record choice 18, writes to files included at more than one place

The product owner confirmed that no contract rule refuses a write because its
file is included more than once: existing values, --in-include, list-item keys
and removals are written to the shared file and appear wherever it is
included. A VALUE asking for conflicting values at one shared location is out
of contract; we refuse it with exit 3 (Requirement 11, Decision 12).


## c9df576 feat(config-include-overrides): write the override in an including file included at several places

Choice 17: per the contract the override goes into the file holding the
include reference even when that file is included more than once, so the new
key appears at every such place. The intended configuration used by the
read-back now gains the key at every place reaching the same written mapping
or include site; verification itself stays an exact ordered comparison.


## 28122c7 feat(config-include-overrides): refuse an include's own string over an include that has overrides

Choice 16: setting a mapping-form include with overrides to its bare include
string, or to a $ref mapping with other overrides, would drop or change them,
so it is refused with exit 3 like any change of a whole include. A VALUE now
equals a loaded include only with the same string and exactly the written
overrides; the same string over an include without overrides stays a no-op.


## 83cf8ef spec(config-include-overrides): plan the tasks for choices 16 and 17


## 1194072 spec(config-include-overrides): record the product owner's decisions on own include strings and shared including files

Choice 16: an include's own string (or a $ref VALUE with other overrides)
over an include with overrides is refused with exit 3, as rule 4 and choice 8
refuse any change of a whole include. Choice 17: per the contract, an override
is written in the file holding the include reference even when that file is
included at several places (new criterion 4.8).


## 55c5dd0 test(config-include-overrides): pin the refusal for a middle file shared by two includes

Feature validation asked for the exit-3 outcome of choice 5 on a shared middle
file to be pinned, whichever way the product owner later decides it.


## 253f4b7 fix(config-include-overrides): merge new keys per placement and place them by the layers holding their content

Feature validation found a set adding keys below two sibling mappings refused
(two insertions into one override or two conversions of one include), and new
keys under a chained include written into the outer file. New keys sharing a
placement are now merged first, and the placement walk follows the layers that
hold the ancestor's content to the innermost include, as choice 5 states,
whatever form the outer include takes.


## c351d18 feat(config-include-overrides): align the earlier specs, docstrings and roadmap with step 5 and check traceability

The step 1-4 specs gain step-5 notes where rule 2, includes, existing values,
the comment rule and the get/show provenance changed meaning; 7.5 now says
'differs' is judged as for a scalar-form include, pinned by a test. Every
requirement 1.1-10.7 is named by a test.


## c09b381 feat(config-include-overrides): accept --in-include on set and validate it end to end

CR-B: when a new setting belongs in the shared file, set --in-include writes it
there by the step 1 rule. The flag takes no value, may stand anywhere among the
arguments and combines with --reason; --in-include=TEXT is a usage error.


## 584be2b feat(config-include-overrides): validate lists, existing values, replacements and $ref end to end

List appends and list-item keys stay with the list, list-item includes are
converted in the list's file, existing values change where they are written,
replacements work across layers, and $ref in PATH or VALUE behaves as
required, all through the real CLI and byte for byte.


## 2faee16 feat(config-include-overrides): validate new keys below includes end to end

The contract example and the other new-key cases now run through the real CLI
byte for byte, with every other file unchanged and one set event per new leaf
and none for the conversion.


## 0dd15a8 feat(config-include-overrides): write new keys into the included file when in_include is chosen

CR-B: a set can ask for the step 1 rule, so new keys (also those of a mapping
VALUE) go into the included side of the deepest existing ancestor. The intended
tree lists them before the override-only keys, matching the merged order the
read-back sees.


## d7c9ebe feat(config-include-overrides): merge mappings across layers with removals, pruning and new keys

A mapping placed over a merged mapping now changes kept keys where they are
written, removes dropped keys from every layer, prunes overrides that would be
left empty and sends new keys through the placement walk. A written mapping
that loses every key becomes {} rather than null (research Decision 9).


## 16a81f3 feat(config-include-overrides): change existing values at their written place

An overridden value is changed in the override and any other value in the file
it comes from, found through the merged mapping's layers. A merged mapping
replaced by a mapping is refused until the layered merge lands.


## 2c9021a feat(config-include-overrides): convert a scalar-form include to mapping form for its first override

The include string moves to a $ref entry, kept byte for byte, and the new
override follows; the key line keeps its comment as in the contract example.
The step 1 tests that pinned a new key in the included file now expect the
override and say they supersede the old rule 2.


## bb0c7d9 feat(config-include-overrides): write a new key below an include as an override

A new key whose placement is a written override mapping or a bare $ref mapping
now goes into the including file, with the intermediate mappings it needs; the
shared included file is left untouched. Scalar-form includes follow in the
conversion task.


## bf9fd51 feat(config-include-overrides): decide where new keys are written and refuse $ref in a set PATH

The add-key target now carries the placement the step 5 rule chooses: the
override side of a merged mapping, a bare $ref mapping, or a scalar-form
include to convert in its directive's file; list items keep the step 1 rule.
The planner adopts it in the next task.


## 4355a76 feat(config-include-overrides): compare and verify configurations with mapping-form includes

A VALUE mapping with an include $ref is now a directive whose overrides the
read-back must contain, and verification compares the root's plain mapping so
a root $ref file can be checked. Include overrides absorbed by the merge into
an included mapping are accepted.


## 14ec53f fix(config-include-overrides): keep the include of a target whose root is a $ref mapping

Overrides on a file whose own root is a bare $ref mapping dropped that inner
include from the included side, hiding the middle file's $ref lines from the
layout and the writers. The merge now keeps it.


## 43a9a33 feat(config-include-overrides): teach the file layout about $ref mappings and merged mappings

The layout assumed a node and its entries live in one file. It now reads what
is written at a slot (the $ref mapping of a mapping-form include) and walks
the written sides of merged mappings, so comments, indentation and insertion
points stay right in files that hold overrides.


## dc273af feat(config-include-overrides): validate that every command reads the merged configuration

get, show, show --sources, history, reconcile and watch already work on the
merged tree; these end-to-end tests pin that, including that switching between
scalar and bare mapping form records nothing.


## 9d8bcfe feat(config-include-overrides): refuse mapping-form includes that cannot mean anything

A $ref that is not an include string, overrides on a non-YAML target and
overrides on included content that is not a mapping now fail with exit 4 and a
message naming the file, path and target, before any history state exists.


## 1649bd4 feat(config-include-overrides): load mapping-form includes wherever a value may be written

A $ref mapping is now an include: bare, it is exactly the scalar form; with
overrides, the included mapping deep-merged with them. Task 1.1's interim
fixtures now take the written override from include.form.


## 453c3c0 feat(config-include-overrides): record merged mappings and provide the deep merge and written-mapping lookups

Readers will see the merged value, so the model keeps each merged mapping's two
written layers and a mapping-form include's $ref mapping; the overrides module
gives the merge and the lookups writers need to reach the files behind a value.


## ce1b71a spec(config-include-overrides): record the product owner's approval of CR-B

Choices 12 and 13 are confirmed as the In-include contract's meaning; 14 and 15
are out of contract and accepted as our choice.


## a91f7a8 spec(config-include-overrides): add CR-B, set --in-include, to requirements, design and tasks

Requirement 10 states the option's effect: new keys follow the step 1 rule
(the included side of the deepest existing ancestor), everything else is
unchanged. The design keeps merged order in the intended tree so read-back
stays an ordered comparison. Tasks 3.8 and 4.3 implement and validate it; the
open choices 12-15 are recorded for the product owner.


## 6179568 discovery(config-include-overrides): fold CR-B (set --in-include) into the step 5 spec

The option only chooses between the step 1 and step 5 rules for new keys, which
config-include-overrides owns and has not implemented yet, so it extends that
spec rather than starting a new one.


## 963fb1c spec(config-include-overrides): record the product owner's approval of the open choices

The comment position, the including file for nested includes and removals
across layers are confirmed as the contract's meaning; the exit-4 and exit-3
refusals are out of contract and accepted as our choice.


## 0562ea6 spec(config-include-overrides): generate and approve the implementation plan

Sixteen tasks from the layered model through loading, the file layer
(layout, compare, placement, new keys, conversion, existing values, layered
merges) to end-to-end validation. An independent review of the task graph
split the planner work and moved the old rule-2 test rewrite into the task
that changes that behaviour.


## 97345ae spec(config-include-overrides): list every requirement ID in the design traceability table


## c90e053 spec(config-include-overrides): design merged view with layers and override placement

Readers keep working on the loaded tree, which becomes the merged view; each
merged mapping keeps its written layers so the writer can find the file and
mapping behind a value. Records the placement walk, pruning of emptied
overrides and the conversion's comment handling in research.md.


## 7309fa6 spec(config-include-overrides): generate requirements for mapping-form includes and override writes

Covers loading $ref includes with deep-merged overrides, the exit-4 refusals,
the merged view in every command, and the replaced rule 2 (new keys become
overrides in the including file). Records the choices the contract leaves open,
including following the contract's comment example for the scalar-form
conversion.


## 4690896 spec(config-include-overrides): initialise the step 5 overrides spec from the discovery brief


## 542d36e discovery(config-include-overrides): plan step 5 overrides for shared includes

Included files are shared between projects, so a new key under an included
section must stop changing the shared file. The brief fixes the approach
(merged view with layer provenance), the boundary and the open choices to
settle in requirements; the roadmap lists the spec and the existing-spec notes.

