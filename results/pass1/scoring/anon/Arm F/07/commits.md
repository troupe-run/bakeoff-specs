# Commits (19, newest first)

Each commit's short SHA and subject, then its message body.

## a99c5f2 Make SC-606 and step 1's set rules agree with the updated tests

SC-606 promised step 1-6 tests pass unchanged without URL strings, but FR-640
also tags file: VALUEs, so five step 1 set tests pass --include. SC-606 now
states that exception, and step 1's FR-025 points to FR-640 so the next reader
finds why (Constitution VI).


## 0120c13 Append step 7 convergence task: SC-606 disagrees with the updated step 1 tests

SC-606 promises step 1-6 tests pass unchanged without URL strings, but FR-640
also tags file: VALUEs, so five step 1 set tests now pass --include. Spec and
tests must agree (Constitution VI).


## d15af4a Record step 7 decisions made while implementing and converging

Constitution VI: alias copies keep !literal tags, types-jsonschema for mypy,
how --include removes a tag (and the empty-value fix found with it), FetchError
and watch, and nested fetch failures naming the local include now have their
reasons in research.md (U-13).


## 704b5e4 Name the local include line when a nested remote include fails

A fetch failure (or invalid YAML) of a URL included from another remote
document named only that document; FR-602 asks for the local file holding the
include. The loader now remembers, per fetched URL, the include string in a
local file it is reached through, and the message adds 'included through
<string as written> at line N of <file>'. as_written moves to tree.py so the
loader and the remote refusal share it.


## 5002cef Let set --include remove a !literal tag on block and empty values

FR-644 says --include removes an existing tag; for block and empty scalars
set refused instead. The replaced span now starts at the tag in those cases
too. A literal block keeps its indicator, as step 1 FR-030 requires, with the
include string as its content.

The same code also mishandled an empty tagged value without --include: the
value was written before the tag and the re-check refused it (exit 3).
_after_properties now skips a !literal tag as it does an anchor, so the tag is
kept as FR-644 says.


## 7b678f4 Stop watch polling a URL that cannot be fetched

While a remote include failed, watch treated it as a broken file and re-synced
every 0.2 s, fetching the URL five times a second; D-65 says watch does not poll
URLs. Fetch failures are now a FetchError: watch reports them once and fetches
again only after a watched local file changes. Broken local files are still
retried on every poll (step 2 D-13).


## e9f161d Test refusals via $ref remote includes, folded literals, outside $dynamicRef

Convergence found three working behaviours with no test (Constitution II).
Each new test was seen to fail when its behaviour was broken. Doing so showed
remote.py's $ref branch was redundant - the loader already points included_by
at the $ref value - so it is removed.


## e50bc88 Append step 7 convergence tasks: watch polling, tag removal, untested paths

Convergence found the implementation short of its artifacts in five places:
watch re-fetches a failing URL every poll (D-65 says it does not poll URLs),
set --include refuses rather than removes a tag on block values (FR-644),
three behaviours lack tests (Constitution II), nested fetch failures omit the
local include line (FR-602), and implementation-time decisions are unrecorded.


## 8fa9208 Document remote includes, the schema and literals; update step 1's set tests

Step 7 changes what a URL or file: string means, so the README now explains
remote includes, the read-only rule, the schema file, !literal and set
--include, and warns that existing URL strings are now includes. Step 1's
FR-010 points to the extension.

Step 1's tests that set a value to an include string encoded the replaced
default: from step 7 such a value is written !literal unless --include is
given. They now pass --include, so they keep proving what an include written
by set does. The quickstart reads remote values before adding the URL setting
that has no schema, so its walk-through runs as written.


## e634a5d Write include-like set values as !literal unless --include is given

From step 7, set docs https://… would otherwise create an include and fetch it,
so get would not return what was set (US5). literals.mark tags each include-like
string in VALUE with !literal, judged by its own path, unless the schema marks
that path format: uri. set --include writes an include instead, and is refused
at a format: uri path. The renderer is the one place that spells the tag. An
existing tag is kept for the smallest diff, or removed by --include. Alias
expansion keeps tags so the copy reads back the same.

Also fixes two step 7 literal tests whose schemas forbade the mappings their
includes produce, which surfaced once validation landed.


## 679060c Validate the loaded configuration against the theatre's schema

A team's schema describes valid configuration (step 7 US4). load() validates
the merged configuration - includes, overrides and literals resolved - so any
command on an invalid configuration exits 4, naming the schema file and the
failing path. set's existing reload check turns a change that would
invalidate it into exit 3, with nothing written. format stays an annotation,
as 2020-12 defines it.


## fc62274 Keep URL settings literal: !literal tag and schema format: uri

From step 7 a URL string is an include, which would fetch existing URL
settings such as API endpoints (US3). A string tagged !literal, or whose
schema - found through properties, additionalProperties and items only - has
format: uri, is now a literal and is never fetched or read. The schema is read
from .troupe/troupe.schema.json; an unusable one is exit 4. watch also watches
the schema file, since it changes which strings are includes.


## 251c4d1 Refuse changes to remote content, naming the include line to change

troupe cannot write to a URL, so a set that would land in fetched content
exits 3 (step 7 US2). The message gives the include string as written, with
its local file and line, found by walking PATH so a URL included twice names
the include on the route taken. With nested remote includes it names the
outermost one. New keys still become local overrides (step 5).


## 5c755ce Load https:// and http:// includes, fetched once per command

Teams share configuration from a URL (step 7 US1). A URL string is now an
include: YAML when its path ends .yml/.yaml, else text. It is fetched with a
10-second limit for the whole response, and any failure is exit 4 naming the
URL and the including file. Remote content may not include local files (D-61).
A command fetches each URL once and reuses it for set's re-check (D-62), and
show --sources labels remote values with their URL.


## c1fd28c Prepare for URL includes: one include vocabulary, sources that may be URLs

Step 7 adds includes fetched from URLs, which troupe must never write. Include
prefixes now live in includes.py; a SourceFile's path may be a URL string, so
mypy forces every write through files.local_path, which refuses one. The loader
carries each node's subschema, ready for format: uri literals, and the tests
get a real HTTP/HTTPS server. Behaviour is unchanged (full suite green).


## dd208b2 Add jsonschema for step 7's 2020-12 schema validation

The reference implementation instead of a hand-written validator (research
U-12); types-jsonschema keeps mypy --strict meaningful where it is used.


## 8392274 Add step 7 task list: remote includes and schema, tests first by user story

Breaks the plan into 27 tasks: a behaviour-preserving foundation (include
vocabulary, URL-capable sources, subschema threading, a real HTTP/HTTPS test
server), then one phase per story with its e2e tests written first, so each
story is proven against real fetches before the next builds on it.


## c011391 Add step 7 plan: remote sources are unwritable by type, schema travels with the load

Remote includes must never be written, and URL settings must never be fetched.
The plan makes a source's location Path | str so mypy forces every write
through one local-only guard, threads the subschema through the loader so
literals are decided before anything is fetched, and validates inside load so
existing exit-4 and set re-check paths give the contract's exit codes. Adds
jsonschema as the 2020-12 validator; fetching uses the standard library.


## 3b4d346 Add step 7 spec: remote includes are read-only, a schema marks URI literals

Teams want to share configuration from a URL, but troupe cannot write to one,
and existing URL settings must not suddenly be fetched as includes. The spec
restates the Remote includes and schema contract: what a URL include loads
and when a fetch fails, refusing changes to remote values while naming the
local include line, `format: uri` and `!literal` literals, schema validation,
and `set --include`. It records the open points it decides (D-60 - D-70).

