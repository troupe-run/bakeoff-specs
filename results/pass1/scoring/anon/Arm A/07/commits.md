# Commits (30, newest first)

Each commit's short SHA and subject, then its message body.

## e6c8a62 spec(config-remote-schema): align the safety-window note with the kept atomic backstop

Final validation found tasks.md saying task 3.3 removes both temporary refusals, while the design
(and the code) keep write_atomically's refusal of remote sources as a backstop.


## b38b9fb spec(config-remote-schema): mark step 7 done in the roadmap and check traceability

Every requirement of config-remote-schema is named by a test docstring and no test names a
requirement that does not exist, so the spec, code and tests agree; the roadmap records the spec
and its existing-spec updates as complete.


## efa4b66 test(config-remote-schema): validate writing include-like VALUEs and --include end to end

Pins the !literal tagging rules byte for byte, the schema uri exception, and --include writing
local and remote includes that are fetched once and recorded per leaf.


## 8c40bf4 test(config-remote-schema): validate schema checks of set end to end

Pins exit 3 for sets the schema rejects (with local $defs/$ref), byte-exact valid writes and exit
4 for an already-invalid configuration.


## 04cd9d9 test(config-remote-schema): validate the read-only rules for remote content end to end

Pins the contract's exit 3 with the include string exactly as written, byte-identical files on
refusal, and local overrides for new keys and overridden values below remote includes.


## f8a04de test(config-remote-schema): validate reading remote content, literals and the schema end to end

Pins, through the real CLI and a local server, that every reader sees remote content, that literals
are never fetched, and that fetch and schema failures exit 4 without touching history state.


## a1a9f8b spec(config-remote-schema): point earlier specs at step 7

Step 7 changes rules owned by earlier specs (explicit tags, include strings, decision D, the watch
set and --sources labels), so each gets a step-7 note pointing at config-remote-schema, keeping
the specs in agreement with the code.


## aa48ce0 feat(config-remote-schema): write include-like VALUEs as !literal unless --include is given

A set must not make troupe fetch or include something by accident, so set now marks VALUE before
planning: include-like strings are written !literal unless the schema makes their path a URI or
--include asks for an include. The decision-D tests that were about writing includes now pass
--include, and new rows pin the tagged form. The 8.1 example is corrected to the writer's real
block/flow style.


## 715d76a feat(config-remote-schema): refuse sets the schema rejects and reuse fetched content on read-back

A set must never leave the configuration in a shape its schema forbids, so a schema violation
found by the read-back is refused with exit 3 naming the schema file and the failing key path
instead of the generic read-back message. The read-back keeps reusing remote content by URL, so a
set fetches only the includes it newly writes.


## 7ab274b feat(config-remote-schema): refuse every write into remote content, naming the local include line

Remote content is shared and read-only from troupe's point of view, so any edit that would land in
it (a changed value, a removal, --in-include, a text rewrite, an alias or merge key written there)
exits 3 and quotes the include line the user should change instead. Overrides and new keys stay
local per step 5, so the temporary blanket refusal is removed. Writer messages name sources by
URL instead of a mangled stand-in path.


## aa8538d feat(config-remote-schema): write tagged strings and replace existing !literal scalars whole

A literal-marked string only stays a value if its tag is on disk, so the renderer writes
'!literal ' before it and never as a block scalar, a replaced !literal scalar loses its tag with
its text, and an alias expansion copies the tag so expanding never turns a literal into an
include.


## 9497224 feat(config-remote-schema): mark include strings in VALUE

A set must never make troupe fetch or include something the user did not ask for, so every
include-like string in VALUE is marked literal unless --include is given or the schema already
makes its path a URI. The intended configuration follows the marks, so a literal equal to a
loaded !literal value is a no-op.


## df063ef feat(config-remote-schema): show remote sources by URL and watch the schema file

A remote scalar's provenance is its URL, not a path relative to the theatre. watch must never
poll a URL (its stand-in path made every tick reload and fetch again), and since the schema
decides literals and validity, editing it must trigger a reload like any config file.


## 57a829a feat(config-remote-schema): load remote includes, with a temporary refusal of writes

https and http include strings now fetch shared configuration once per load and fail with exit 4
naming the including file and URL. Until the writer knows remote content is read-only, set
refuses any configuration with a remote source and the atomic writer refuses remote targets, so
no write can reach a URL in the meantime.


## e36520f refactor(config-remote-schema): key loading overrides and written texts by source identity

A remote source has a URL, not a path, so every override, text and layout map is keyed by
SourceFile.key before remote sources can appear. Behaviour is unchanged.


## 1101b69 feat(config-remote-schema): read and enforce the schema when the configuration loads

The schema decides which include-like strings are literals, so it must be read before anything is
included, and a configuration that does not match the declared shape must stop every command
with exit 4 before any history state is touched.


## 449677a feat(config-remote-schema): load !literal scalars and narrow the explicit-tag refusal

The step 7 contract makes !literal the way to keep an include-like string a value, so the loader
reads it as the scalar's text and never as an include. Every other tag, and !literal where a
string value cannot be meant (collections, keys, $ref), still exits 4 under decision I.


## f66077c feat(config-remote-schema): fetch remote sources, with a real local HTTP server for tests

Remote includes need one narrow fetcher whose failures all become a short reason the loader can
report with exit 4. urllib is enough for a single GET, so no HTTP dependency is added. The tests
serve real HTTP from 127.0.0.1 so they never depend on the internet.


## 8c8208d feat(config-remote-schema): read the schema, find format: uri and validate a configuration

The literal decision and the validity checks of loads and sets all need the same schema reading
and the same properties/items/additionalProperties walk, so they live in one module. The
validator gets an empty registry because jsonschema would otherwise fetch remote $refs, which
the spec forbids; research.md is corrected accordingly.


## 2930d50 feat(config-remote-schema): give the model remote identity, literal spans and a schema source

Remote sources have no local path, so sources are identified by key (URL or real path) and shown by
URL or path. Include strings are rebuilt in one place (IncludeRef.string) so a URL include is
reported exactly as written. Schema violations carry key path and detail separately so set can
reword them as a refusal later.


## 537bd05 feat(config-remote-schema): add the step 7 constants, jsonschema and include recognition

Remote includes and literals change what counts as an include string, so that decision gets one
home (config/includes.py) before the loader and writer start using it. jsonschema provides the
2020-12 validator the schema check needs.


## d2df27c spec(config-remote-schema): record fast-track approval of the implementation plan

The product owner is not available, so the plan is approved under -y and the
spec is marked ready for implementation. tasks.md states that the second
task-graph review's single finding was fixed as prescribed and not reviewed a
third time, so whoever starts implementation knows which part to check first.


## 35a7b39 spec(config-remote-schema): generate the implementation plan for step 7

Twenty sub-tasks in five groups. The foundation adds the dependencies,
recognition, model, schema and fetcher. The core work covers literals, the
schema, identity keys and remote loading in the loader. The file layer adds
marks, tagged rendering, the remote guard and the read-back schema refusal.
Four parallel end-to-end validations follow, then spec notes and
traceability. Tests that pin explicit-tag refusals and decision D change in
the tasks that change those rules. A temporary set refusal covers the window
between remote loading and the remote guard, so no commit in between can
write a remote source. Two independent task-graph reviews shaped the order.
The second review's one remaining finding was fixed as it prescribed.


## 344edf3 spec(config-remote-schema): record fast-track approval of the design

The product owner is not available, so the design is approved under -y.
The out-of-contract choices it relies on (SourceFile identity by key/shown,
the schema check done at read-back, the layout choke point) are recorded in
research.md as our decisions, so they can be revisited.


## 9d35017 spec(config-remote-schema): design include decisions while walking, URL-identified sources and a layout write guard

The loader already knows each node's configuration path, so the literal
decision (!literal, schema format: uri) is made before anything is fetched.
Remote content becomes ordinary SourceFiles with a URL identity, so every
reader works unchanged. Every planner edit passes one layout choke point,
which is where writes into remote content are refused. Schema validation
lives in the loader, so a set's read-back also checks the schema before any
write. research.md records the jsonschema, urllib and ruamel findings and
the 22 choices with what would make us revisit them.


## 3c85e15 spec(config-remote-schema): record fast-track approval of the requirements

The product owner is not available for step 7, so the requirements are
approved under -y with the brief's open-choice defaults as the decisions. The
approval note in requirements.md says which choice differs from the brief and
why, so a later review knows which decisions are ours to revisit.


## 99acdd5 spec(config-remote-schema): generate requirements for remote includes, literals, the schema and set --include

Ten requirement areas turn the step 7 contract into testable criteria: remote
includes and failed fetches, remote content in every reader, `!literal` and
`format: uri` literals, the schema on load and on set, read-only remote content
naming the local include line, include-like VALUE strings written `!literal`,
and `--include`. The brief's fourteen open choices are taken as written except
history's schema check: every command loads the configuration today, so history
fetches and validates too. Eight further choices found while writing are listed
with them for the design to record.


## d30ddad spec(config-remote-schema): initialise the step 7 remote includes and schema spec from the discovery brief

The brief already states who has the problem (teams sharing one configuration
by URL), the current state (only file: includes, every tag refused, no schema)
and the step 7 outcome, so requirements can start from it directly. The
contract section is copied verbatim as the authoritative input.


## cb78611 discovery(config-remote-schema): plan step 7 remote includes and a schema

Step 7 adds https includes and a JSON Schema whose format: uri and the !literal tag decide which
URL strings are values. Both change what the loader treats as an include, so they share one spec.
The brief records the chosen approach (urllib fetcher, jsonschema 2020-12 validator, literal
decision made while walking) and the conservative defaults for the open choices.


## 1be3c3a spec(config-aliases): point earlier specs at step 6 and mark the aliases work done

The step 6 behaviour is implemented and tested, so the earlier specs' 'anchors are refused'
statements now carry step-6 notes pointing to config-aliases, and the roadmap records the
aliases spec and its existing-spec updates as complete.

