# Commits (9, newest first)

Each commit's short SHA and subject, then its message body.

## b813885 Archive config-remote-includes-and-schema and sync its specs into spec/specs


## 266c9fe Mark config-remote-includes-and-schema tasks complete after full test, type and lint run


## e061d9a Write include-looking set VALUEs as !literal unless --include is given

Contract step 7: a string that would be read as an include, at a path the schema does not mark format: uri, is
written tagged !literal, so set never fetches or reads anything the user did not ask for. This covers strings
nested in collection VALUEs too. --include writes them as includes, and is refused at a URI path, where the string
cannot be one. This is a breaking change for scripts that relied on set X file:..., so three tests now pass
--include and the README has an upgrade note.


## 5128172 Read .troupe/troupe.schema.json: URI settings are literals, and the config must validate

Contract step 7: some settings are URLs that must never be fetched. Their schema marks them format: uri, found
only through properties, additionalProperties and items, as the contract says. The loader decides this as it
expands, before any fetch. The loaded configuration must be valid (exit 4 otherwise), and a set whose result is
not valid is refused (exit 3). set validates only its final result, since a multi-step change can pass through
invalid states. watch watches the schema file, because editing it changes what is an include. The old
test_schema.py (core-schema scalars) becomes test_core_schema.py to make room.


## 9b34dc0 Refuse writes to remote content and name the local include line instead

Contract step 7: values from a URL include are read-only. Every file an edit would touch is checked in one place
(apply._apply), so any operation that reaches remote content is refused with exit 3. The message quotes the
outermost include as written in a local file, with that file and line, since that is what the user can change.
New keys still become local overrides. Includes whose reference is itself remote are passed over, so the override
lands next to a line that can be written.


## 5a018c1 Load https:// and http:// includes, fetched once per command

Contract step 7: teams share configuration by URL. A URL include loads like a file include (YAML or text by its
path). A file: include inside remote content resolves against the URL, so shared content can never read local
files. Each URL is fetched once per command, so a set's reloads all see one snapshot, and a failed fetch exits 4
naming the URL. Remote sources are kept out of Config.files, so write-back and watch cannot touch them.


## 261692d Load !literal scalars as strings and keep the tag when set changes them

Step 7 needs a way to say "this string is not an include". !literal marks it. The tag sits outside the
scalar's span, like an anchor, so replacing the string keeps it. It is removed only when the new value is not a
string, which the tag would otherwise turn into one.


## 273bd08 Decide what is an include in one module, ready for URL includes

Remote includes and the schema both change which strings are includes. includes.py now holds that decision and
how an include string resolves, so later steps change it in one place. Also adds jsonschema for the schema step.
Behaviour is unchanged.


## e55580c Plan remote includes and a schema for contract step 7 (method change config-remote-includes-and-schema)

Values from https:// includes are read-only, and the error names the local include line to change instead. A
JSON Schema marks URL settings as literals, and the configuration must validate against it. set writes
include-looking strings as !literal unless --include is given.

