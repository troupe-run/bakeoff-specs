# Commits (24, newest first)

Each commit's short SHA and subject, then its message body.

## 69eca9f feat(config-get-show): run the full quality gate and check traceability

Every config-get-show requirement from 1.1 to 6.8 is named by at least one test
that proves it, and no test cites an unknown requirement. The full suite, mypy
--strict and ruff pass. The roadmap now marks step 3, and its updates to
config-foundation and config-file-sync, as done.


## cf55b7d feat(config-get-show): validate --sources end to end

--sources is how users find the file to edit, so its comments are pinned byte for
byte through the real console script. One space then "# from <file>" on every
scalar line, including literal headers, and nowhere else. Text includes name the
included file, and an include outside the theatre is a ../ path. Labels stay
lexical through symlinks, and removing the comments gives the plain output.


## ef2c1fa feat(config-get-show): validate that the YAML output reads back exactly

Requirement 4.1 promises that show's YAML means exactly what the configuration
means. For every scalar kind, the quoting edge cases, awkward keys, nested and
empty collections, YAML includes and LF text includes, the real show output is
reloaded as a fresh theatre and compared leaf by leaf: paths, order, typed values,
keys and empty collections. Breaking the key typing, the indentation indicator or
quoting makes it fail.


## e72c038 feat(config-get-show): validate show output and command behaviour end to end

End-to-end tests through the real console script pin show's block YAML byte for
byte: sections mixing YAML and text includes, the whole configuration, and the
empty forms. They also prove show behaves like every other command: it
reconciles first, imports a new theatre, writes no file, keeps stdout empty on
errors, and leaves the store and lock free for the next command.


## cd686c1 feat(config-get-show): validate get end to end

Scripts rely on get printing exactly what step 1's show printed. These end-to-end
tests through the real console script pin every scalar kind byte for byte,
including text includes with CRLF. They also pin the exit-5 refusal with its
config show hint and every exit-2 usage error. Breaking the hint or any exit
code makes them fail.


## b24d1c8 feat(config-get-show): align docstrings and the earlier specs with step 3

Step 3 changed what show means, so the step 1 and 2 specs gain step-3 notes in
their existing style. config-foundation's Requirement 6 now describes get, and
its mapping/list refusal mentions config show. config-file-sync's
reconcile-first rule reads "get or show". Docstrings that still described a
scalar-only show now say get.


## 939598b feat(config-get-show): replace the step 1 show with the new show

show now prints any node: a scalar exactly like get, and a mapping, a list or the
whole configuration as block YAML, with --sources naming each value's file. The
tests that relied on step 1's scalar-only show were moved to get, which keeps
every exit-2 and exit-5 case, and now also check that show itself succeeds.


## 1fd562d feat(config-get-show): add the get command

troupe config get PATH takes over step 1's single-value read before show changes.
Scripts keep a scalar-only command, and a mapping or list now exits 5 with a hint
to use config show. It reconciles first, writes no file, and is registered first
so the subcommand order is already the design's final one.


## a59f759 feat(config-get-show): annotate scalar lines with their source file

--sources must say which file each value comes from. Every line holding a scalar
(including a literal block's header) now ends with " # from <file>": the root
file, the YAML include it is written in, or the included text file. Other lines
get nothing, so stripping the comments gives the plain output byte for byte. A
scalar printed alone becomes a one-line YAML document that carries its source.


## 18000ad feat(config-get-show): render text includes and multi-line strings as literal blocks

The contract shows text includes as literal blocks with no exception. Every text
include is now a | block with the chomping and indentation indicator its text
needs, its characters unchanged, so a CRLF file keeps its \r\n. Other multi-line
strings use a literal block when it reads back exactly, and double quotes
otherwise.


## 633f784 feat(config-get-show): render mappings, lists and one-line scalars as block YAML

show prints a section as plain block YAML: document order, two spaces per level,
compact collections in list items, {} and [] for empty ones, and scalars in the
minimal quoting that reads back as the same typed value. Each line records the
file of the scalar it holds, so --sources can annotate it later.


## 3dbb43d feat(config-get-show): provide the source label of a file

--sources names each value's file relative to the theatre directory, with /
separators. The label is computed lexically from the path as opened, so users
see the paths they wrote (symbolic links unresolved, as in error messages), and
a file outside the theatre gets a leading ../.


## 1114caf feat(config-get-show): turn the scalar read into get's use case and add the node lookup

get keeps step 1's single-value read. Its refusal of a mapping or list now points
the user to `troupe config show <PATH>`, which prints them. node_at gives show any
node, or the whole configuration when PATH is omitted, still read from the files
as on disk.


## d0c4bf4 feat(config-get-show): add the document-root quoting context

show PATH --sources prints a scalar alone as a YAML document. There, text such as
"--- a" or "..." would be read as a document marker, though it is a safe plain
value inside a mapping. The new context also probes the bare document, so such
strings are quoted and still read back exactly.


## a55f49b feat(config-get-show): move the write-neutral scalar presentation rules into a core module

show needs set's quoting, escaping, chomping and literal-character rules, but core
code may not import write-back, and write-back's renderers refuse what show must
print. The rules now live in troupe.config.yaml_style. Write-back re-exports the
same objects and keeps its refusals, so set's byte-exact tests pass unchanged.


## 8db034c spec(config-get-show): approve the implementation plan

The product owner approved the plan. The yaml_style move is checked against set's
unchanged bytes, get comes before show is replaced, every text include is a
literal block, and --sources labels are relative to the theatre directory.


## 9ac56c2 spec(config-get-show): generate the implementation plan

The yaml_style move comes first, on its own, so set's byte-exact tests prove it
is a pure move. get is added before show is replaced, and the tests that relied
on step 1's scalar-only show are retargeted in the same task, so the suite stays
green at every step. An independent task-graph review passed on its second run.


## c185fb4 spec(config-get-show): approve the design

The product owner approved the design: every text include is a literal block,
--sources comments go on scalar lines including literal headers, and the move to
yaml_style leaves set's bytes unchanged.


## 2f54cd2 spec(config-get-show): design get, YAML show and source annotations

show needs the quoting and literal-block rules that set already has, but core code
may not import write-back, and write-back's renderers refuse what show must print.
The design therefore moves the write-neutral scalar rules to a core yaml_style
module and adds a small line-based emitter in the CLI. Each line carries the file
of the scalar it holds, so --sources comments are exact by construction. The
literal-indent experiment and every decision are recorded in research.md.


## 9a59e64 spec(config-get-show): approve the requirements

The product owner approved the revised requirements: every text include is shown
as a literal block, and the choices made where the contract is silent are recorded
in the Boundary Context.


## 54634ed spec(config-get-show): show every text include as a literal block

The product owner rejected the double-quoted fallback for text includes: the
contract says text includes are shown as literal blocks, with no exception. A text
include a literal block cannot reproduce (CRLF, characters YAML rejects) now keeps
its exact text in the block and is the one exception to the read-back promise.
Other multi-line strings keep the double-quoted fallback, which the contract does
not address.


## 88ebdc5 spec(config-get-show): generate requirements for get, YAML show and sources

The contract fixes what get, show and --sources print but leaves the exact YAML
form open. The requirements pin it down so it can be tested: block layout, scalars
that read back exactly (with a double-quoted fallback where a literal block would
alter a text include), where comments may go, and how source paths are written.
Each choice the contract leaves open is listed with its conservative default.


## c2ef9e5 spec(config-get-show): initialise the step 3 get/show spec from the discovery brief

The project description quotes the step 3 contract section word for word, so
requirements are written against the contract rather than a paraphrase of it.


## 1db2f7e discovery(config-get-show): plan step 3 get and YAML show with sources

Step 3 splits reading in two: get keeps step 1's single-value behaviour, and show
prints any subtree as block YAML, optionally with each scalar's source file. The
loader's source-mapped tree already holds the provenance, so the roadmap records a
new spec built on our own emitter (reusing writeback's scalar rendering), the
rejected ruamel-based alternatives, and the amendments to config-foundation and
config-file-sync.

